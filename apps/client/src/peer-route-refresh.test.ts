import test from 'node:test';
import assert from 'node:assert/strict';
import {PeerConnection,type ConnectionState} from './peer.ts';

test('late route stats cannot replace an interruption, and recovery can publish the route',async()=>{
 const updates:ConnectionState[]=[];
 let completeStats:(stats:RTCStatsReport)=>void=()=>{};
 const stats=new Map([
  ['transport',{type:'transport',selectedCandidatePairId:'pair'}],
  ['pair',{type:'candidate-pair',localCandidateId:'local',remoteCandidateId:'remote'}],
  ['local',{type:'local-candidate',candidateType:'relay'}],
  ['remote',{type:'remote-candidate',candidateType:'relay'}],
 ]) as unknown as RTCStatsReport;
 const pc={connectionState:'connected',close:()=>{},getStats:()=>new Promise<RTCStatsReport>(resolve=>{completeStats=resolve;})};
 const peer=new PeerConnection(async()=>{},state=>updates.push(state)) as unknown as {
  pc:typeof pc;epoch:string;connectedState:ConnectionState;
  refreshRoute:(epoch:string,remaining:number)=>void;
  close:()=>void;
 };
 peer.pc=pc;peer.epoch='epoch';peer.connectedState={status:'Peer transport connected.',epoch:'epoch'};
 peer.refreshRoute('epoch',1);
 await new Promise(resolve=>setTimeout(resolve,120));
 pc.connectionState='disconnected';
 updates.push({status:'Connection interrupted. Waiting for transport recovery.',epoch:'epoch'});
 completeStats(stats);
 await new Promise(resolve=>setTimeout(resolve,20));
 assert.equal(updates.at(-1)?.status,'Connection interrupted. Waiting for transport recovery.');
 assert.equal(peer.connectedState.route,undefined);
 pc.connectionState='connected';
 peer.refreshRoute('epoch',1);
 await new Promise(resolve=>setTimeout(resolve,120));
 completeStats(stats);
 await new Promise(resolve=>setTimeout(resolve,20));
 assert.equal(updates.at(-1)?.route,'relay');
 peer.close();
});
