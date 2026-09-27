import test from 'node:test';
import assert from 'node:assert/strict';
import {connectionStatus} from './connection-status.ts';
import type {RoomState} from './room-client.ts';
import type {PeerView} from '../../../packages/contracts/src/peer.ts';
const state=(peers:PeerView[],route?:'direct'|'relay',connected=true)=>({connected,room:{occupancy:peers.length+1,peers,slots:peers.map((peer,index)=>({member:{id:peer.member,nickname:`Friend ${index+1}`}}))},connection:{status:'Last link changed.',route}} as unknown as RoomState);
const peer=(index:number,status:PeerView['status']='connected',policy:PeerView['policy']='standard'):PeerView=>({pairId:`pair${index}`,member:`member${index}`,gameplay:true,status,policy});
test('reports partial five-member connectivity without claiming whole-room failure',()=>{
 const text=connectionStatus(state([peer(1),peer(2),peer(3,'connecting'),peer(4,'relay_capacity','relay')],'relay'));
 assert.match(text,/2\/4 member connections ready/);assert.match(text,/1 connecting/);assert.match(text,/Friend 4: relay capacity full/);assert.match(text,/At least one member connection uses the relay/);assert.match(text,/Relay only will not switch to direct/);
 assert.doesNotMatch(text,/room.*failed|All.*disconnected/);
});
test('reports a single relay policy, direct links, and unavailable relay truthfully',()=>{
 assert.match(connectionStatus(state([peer(1)],'relay')),/Direct connection unavailable\. Relay keeps you playing together/);
 assert.match(connectionStatus(state([peer(1,'connected','relay')],'relay')),/Relay only is on/);
 assert.match(connectionStatus(state([peer(1)],'direct')),/Connected member links use the direct route/);
 assert.match(connectionStatus(state([peer(1,'relay_unavailable','relay')])),/Friend 1: relay service unavailable/);
});
test('separates service loss from remaining links and handles an empty lobby',()=>{
 const text=connectionStatus(state([peer(1),peer(2,'failed')],'direct',false));
 assert.match(text,/Room service disconnected/);assert.match(text,/1\/2 member connections ready/);assert.match(text,/Friend 2: connection failed/);
 assert.equal(connectionStatus(state([])),'No other members are connected.');
 assert.equal(connectionStatus({...state([]),room:undefined}),'Last link changed.');
});
