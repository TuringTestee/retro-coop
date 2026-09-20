import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {PeerConnection} from './peer.ts';

for(const terminal of ['failed','channel-close','channel-error'])test(`transient disconnect recovers once; ${terminal} still terminates transport`,async(t)=>{
 const original=globalThis.RTCPeerConnection;
 const sent:any[]=[],wire:any[]=[],updates:any[]=[];let ready=0,closed=0,pc:any,now=100,observedRtt=0;
 t.mock.method(performance,'now',()=>now);
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
 const peer=new PeerConnection(async command=>{sent.push(command);},state=>updates.push(state),{ready:(_channel,_epoch,rtt)=>{ready++;observedRtt=rtt;},closed:()=>closed++});
 try {
  peer.handle({type:'peerPrepare',epoch:'epoch',role:'host',policy:'standard',iceServers:[]});
  peer.handle({type:'peerStart',epoch:'epoch'});await setImmediate();
  pc.connectionState='connected';pc.channel.onopen();
  const nonce=wire[0].nonce;
  pc.channel.onmessage({data:JSON.stringify({type:'transportProbe',nonce:'r'.repeat(36)})});
  now=217;pc.channel.onmessage({data:JSON.stringify({type:'transportReply',nonce})});await setImmediate();
  assert.equal(ready,1);assert.equal(observedRtt,117);const before=wire.length;
  pc.connectionState='disconnected';pc.onconnectionstatechange();
  assert.equal(pc.closed,0,'a transient connectivity indication destroyed the live transport');
  assert.equal(closed,0);assert.equal(sent.filter(x=>x.type==='peerFailed').length,0);
  pc.connectionState='connected';pc.onconnectionstatechange();await setImmediate();
  assert.equal(ready,1);assert.equal(wire.length,before,'recovery sent another transport challenge');
  assert.equal(updates.at(-1).status,'Peer transport connected.');
  if(terminal==='failed'){pc.connectionState='failed';pc.onconnectionstatechange();}
  else if(terminal==='channel-close')pc.channel.onclose();
  else pc.channel.onerror();
  assert.equal(pc.closed,1);assert.equal(closed,1);assert.equal(sent.filter(x=>x.type==='peerFailed').length,1);
 } finally {peer.close();globalThis.RTCPeerConnection=original;}
});

test('a replaced connection cannot deliver its delayed readiness or RTT',async()=>{
 const original=globalThis.RTCPeerConnection;let pc:any,release!:()=>void;const ready:number[]=[];
 class FakePeer {
  localDescription={sdp:'test'};channel:any={label:'retro-coop-control',send(raw:string){this.last=JSON.parse(raw);},close(){}};
  constructor(){pc=this;}createDataChannel(){return this.channel;}async createOffer(){return {type:'offer',sdp:'test'};}async setLocalDescription(){}async getStats(){return new Map();}close(){}
 }
 globalThis.RTCPeerConnection=FakePeer as unknown as typeof RTCPeerConnection;
 const peer=new PeerConnection(command=>command.type==='peerConnected'?new Promise<void>(resolve=>{release=resolve;}):Promise.resolve(),()=>{},{ready:(_channel,_epoch,rtt)=>ready.push(rtt)});
 try {
  peer.handle({type:'peerPrepare',epoch:'old',role:'host',policy:'standard',iceServers:[]});peer.handle({type:'peerStart',epoch:'old'});await setImmediate();
  const channel=pc.channel;channel.onopen();const nonce=channel.last.nonce;
  channel.onmessage({data:JSON.stringify({type:'transportProbe',nonce:'r'.repeat(36)})});channel.onmessage({data:JSON.stringify({type:'transportReply',nonce})});await setImmediate();
  assert.equal(typeof release,'function');peer.handle({type:'peerPrepare',epoch:'new',role:'host',policy:'standard',iceServers:[]});release();await setImmediate();assert.deepEqual(ready,[]);
 } finally {peer.close();globalThis.RTCPeerConnection=original;}
});
