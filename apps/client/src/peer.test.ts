import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {PeerConnection} from './peer.ts';

test('transient disconnected preserves the established channel and recovers without another ready callback',async()=>{
 const original=globalThis.RTCPeerConnection;
 const sent:any[]=[],wire:any[]=[],updates:any[]=[];let ready=0,closed=0,pc:any;
 class FakePeer {
  connectionState='new';closed=0;onconnectionstatechange?:()=>void;ondatachannel?:unknown;onicecandidate?:unknown;
  localDescription={sdp:'test'};
  channel:any={label:'retro-coop-control',readyState:'open',send:(raw:string)=>wire.push(JSON.parse(raw)),close(){this.readyState='closed';}};
  constructor(){pc=this;}
  createDataChannel(){return this.channel;}
  async createOffer(){return {type:'offer',sdp:'test'};}
  async setLocalDescription(){}
  async getStats(){return new Map();}
  close(){this.closed++;this.connectionState='closed';}
 }
 globalThis.RTCPeerConnection=FakePeer as unknown as typeof RTCPeerConnection;
 const peer=new PeerConnection(async command=>{sent.push(command);},state=>updates.push(state),{ready:()=>ready++,closed:()=>closed++});
 try {
  peer.handle({type:'peerPrepare',epoch:'epoch',role:'host',policy:'standard',iceServers:[]});
  peer.handle({type:'peerStart',epoch:'epoch'});await setImmediate();
  pc.connectionState='connected';pc.channel.onopen();
  const nonce=wire[0].nonce;
  pc.channel.onmessage({data:JSON.stringify({type:'transportProbe',nonce:'r'.repeat(36)})});
  pc.channel.onmessage({data:JSON.stringify({type:'transportReply',nonce})});await setImmediate();
  assert.equal(ready,1);const before=wire.length;
  pc.connectionState='disconnected';pc.onconnectionstatechange();
  assert.equal(pc.closed,0,'a transient connectivity indication destroyed the live transport');
  assert.equal(closed,0);assert.equal(sent.filter(x=>x.type==='peerFailed').length,0);
  pc.connectionState='connected';pc.onconnectionstatechange();await setImmediate();
  assert.equal(ready,1);assert.equal(wire.length,before,'recovery sent another transport challenge');
  assert.equal(updates.at(-1).status,'Peer transport connected.');
  pc.connectionState='failed';pc.onconnectionstatechange();
  assert.equal(pc.closed,1);assert.equal(closed,1);assert.equal(sent.filter(x=>x.type==='peerFailed').length,1);
 } finally {peer.close();globalThis.RTCPeerConnection=original;}
});
