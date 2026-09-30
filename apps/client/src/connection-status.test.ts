import test from 'node:test';
import assert from 'node:assert/strict';
import {connectionStatus} from './connection-status.ts';
import type {RoomState} from './room-client.ts';
import type {PeerView} from '../../../packages/contracts/src/peer.ts';
const state=(peers:PeerView[],route?:'direct'|'relay',connected=true)=>({connected,room:{occupancy:peers.length+1,peers,slots:peers.map((peer,index)=>({member:{id:peer.member,nickname:`Friend ${index+1}`}}))},connection:{status:'Last link changed.',route}} as unknown as RoomState);
const peer=(index:number,status:PeerView['status']='connected',policy:PeerView['policy']='standard'):PeerView=>({pairId:`pair${index}`,member:`member${index}`,gameplay:true,status,policy});
test('reports partial five-member connectivity without claiming whole-room failure',()=>{
 const text=connectionStatus(state([peer(1),peer(2),peer(3,'connecting'),peer(4,'relay_capacity','relay')],'relay'));
 assert.match(text,/2\/4 member connections ready/);assert.match(text,/1 connecting/);assert.match(text,/Could not connect to Friend 4/);assert.match(text,/Retry this connection or leave the room/);
 assert.doesNotMatch(text,/room.*failed|All.*disconnected/);
});
test('keeps route details out of ordinary connection feedback',()=>{
 assert.equal(connectionStatus(state([peer(1)],'relay')),'1/1 member connections ready.');
 assert.equal(connectionStatus(state([peer(1)],'direct')),'1/1 member connections ready.');
 assert.doesNotMatch(connectionStatus(state([peer(1,'relay_unavailable','relay')])),/relay|direct/i);
});
test('separates service loss from remaining links and handles an empty lobby',()=>{
 const text=connectionStatus(state([peer(1),peer(2,'failed')],'direct',false));
 assert.match(text,/Room service disconnected/);assert.match(text,/1\/2 member connections ready/);assert.match(text,/Could not connect to Friend 2/);
 assert.equal(connectionStatus(state([])),'No other members are connected.');
 assert.equal(connectionStatus({...state([]),room:undefined}),'Last link changed.');
});
