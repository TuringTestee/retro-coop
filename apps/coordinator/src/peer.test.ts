import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID,createHmac} from 'node:crypto';
import {Rooms} from './rooms.ts';
import {relayConfig} from './peer.ts';
import {parseRoomCommand,type RoomCommand,type RoomEvent,type Fingerprint} from '../../../packages/contracts/src/rooms.ts';
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}};
type Command=RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'>:never:never;
function setup(relayRooms?:number) {
 let now=1000;const secret='test-secret'.repeat(4),rooms=new Rooms(()=>now,undefined,relayRooms===undefined?undefined:{urls:['turn:127.0.0.1:3478'],secret,rooms:relayRooms});
 const guest=()=>{const events:RoomEvent[]=[];const send=(event:RoomEvent)=>events.push(event);return {...rooms.attach(undefined,send,()=>{}),events,send};};
 const act=(token:string,command:Command)=>rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const pair=(policy:'standard'|'relay'='standard')=>{const host=guest(),peer=guest(),intent=randomUUID();const room=act(host.token,{type:'create',intent,visibility:'public',fingerprint,policy}).room!;act(host.token,{type:'confirmCreate',intent});const joined=act(peer.token,{type:'join',invite:room.invite,intent:randomUUID()}).room!;return {host,peer,room:joined};};
 return {rooms,secret,guest,act,pair,advance(ms:number){now+=ms;rooms.sweep();}};
}
test('both authenticated members acknowledge effective relay before any signal is forwarded',()=>{
 const t=setup(2),{host,peer,room}=t.pair('relay'),epoch=room.peer.epoch!;
 const prepared=host.events.find(event=>event.type==='peerPrepare');assert.ok(prepared?.type==='peerPrepare');assert.equal(prepared.policy,'relay');
 const ice=prepared.iceServers[0];assert.equal(ice.credential,createHmac('sha1',t.secret).update(ice.username!).digest('base64'));assert.ok(Number(ice.username!.split(':')[0])<=301);
 const offer={kind:'description',description:{type:'offer',sdp:'v=0\r\n'}} as const;
 assert.throws(()=>t.act(host.token,{type:'peerSignal',epoch,signal:offer}),/peer_not_prepared/);
 t.act(host.token,{type:'peerAck',epoch});assert.equal(host.events.some(event=>event.type==='peerStart'),false);
 t.act(peer.token,{type:'peerAck',epoch});assert.equal(host.events.some(event=>event.type==='peerStart'),true);
 assert.throws(()=>t.act(peer.token,{type:'peerSignal',epoch,signal:offer}),/invalid_peer_description/);
 assert.throws(()=>t.act(host.token,{type:'peerSignal',epoch,signal:{kind:'candidate',candidate:{candidate:'candidate:1 1 udp 1 127.0.0.1 99 typ host',sdpMid:'0',sdpMLineIndex:0}}}),/relay_required/);
 t.act(host.token,{type:'peerSignal',epoch,signal:offer});assert.equal(peer.events.filter(event=>event.type==='peerSignal').length,1);
 const stranger=t.guest();assert.throws(()=>t.act(stranger.token,{type:'peerAck',epoch}),/not_in_room/);
 const view=t.act(peer.token,{type:'file',fingerprint}).room!;assert.equal(view.role,'guest');assert.equal(view.peer.status,'connecting');assert.equal(view.reservationUntil,room.reservationUntil);
});
test('relay denial never emits preparation; released capacity supports explicit retry',()=>{
 const unavailable=setup(),a=unavailable.pair('relay');assert.equal(a.room.peer.status,'relay_unavailable');assert.equal(a.host.events.some(event=>event.type==='peerPrepare'),false);
 const t=setup(1),first=t.pair('relay'),second=t.pair('relay');assert.equal(second.room.peer.status,'relay_capacity');assert.equal(second.host.events.some(event=>event.type==='peerPrepare'),false);
 t.act(first.host.token,{type:'close'});const retried=t.act(second.peer.token,{type:'peerRetry',epoch:second.room.peer.epoch!}).room!;assert.equal(retried.peer.status,'preparing');assert.equal(retried.peer.policy,'relay');assert.equal(retried.reservationUntil,second.room.reservationUntil);
});
test('policy and socket changes invalidate epochs; cancellation and expiry remove signaling authority',()=>{
 const t=setup(1),{host,peer,room}=t.pair(),old=room.peer.epoch!;
 const changed=t.act(peer.token,{type:'peerPolicy',policy:'relay'}).room!;assert.notEqual(changed.peer.epoch,old);assert.equal(changed.peer.policy,'relay');assert.throws(()=>t.act(host.token,{type:'peerAck',epoch:old}),/stale_peer/);
 t.rooms.attach(host.token,()=>{},()=>{});assert.throws(()=>t.rooms.handle(host.token,{type:'heartbeat',requestId:randomUUID()},host.send),/session_replaced/);
 t.act(peer.token,{type:'leave',intent:room.reservationIntent!});assert.throws(()=>t.act(peer.token,{type:'peerAck',epoch:changed.peer.epoch!}),/not_in_room/);
 const exp=t.pair();t.advance(120_000);assert.throws(()=>t.act(exp.peer.token,{type:'peerAck',epoch:exp.room.peer.epoch!}),/not_in_room/);
});
test('negotiation timeouts and signaling schema are bounded independently of room lease',()=>{
 const t=setup(),{host,peer,room}=t.pair();t.advance(15_000);assert.ok(host.events.some(event=>event.type==='peerStop' && event.reason.includes('timed out')));
 assert.equal(t.act(peer.token,{type:'file',fingerprint}).room!.reservationUntil,room.reservationUntil);
 const base={type:'peerSignal',requestId:randomUUID(),epoch:randomUUID(),signal:{kind:'description',description:{type:'offer',sdp:'v=0\r\n'}}};assert.ok(parseRoomCommand(base));
 for(const bad of [{...base,target:'forged'},{...base,signal:{kind:'description',description:{type:'offer',sdp:'v=0'+'x'.repeat(12_000)}}},{...base,epoch:'short'},{type:'peerPolicy',requestId:randomUUID(),policy:'auto-fallback'}]) assert.equal(parseRoomCommand(bad),undefined);
 assert.throws(()=>relayConfig({TURN_URLS:'https://bad',TURN_SECRET:'x'.repeat(32),TURN_ROOM_LIMIT:'1'}));
});

test('hello applies stricter policy before recovering an existing room transport',()=>{
 const t=setup(1),{host,peer,room}=t.pair();const events:RoomEvent[]=[];
 const restored=t.rooms.attach(peer.token,event=>events.push(event),()=>{},'relay').data.room!;
 assert.equal(restored.peer.policy,'relay');assert.equal(restored.reservationUntil,room.reservationUntil);
 assert.ok(events.some(event=>event.type==='peerPrepare' && event.policy==='relay'));
 assert.equal(events.some(event=>event.type==='peerPrepare' && event.policy==='standard'),false);
 assert.throws(()=>t.act(host.token,{type:'peerAck',epoch:room.peer.epoch!}),/stale_peer/);
});

test('public-code admission captures the same strict policy before preparing peers',()=>{
 const t=setup(),host=t.guest(),peer=t.guest(),intent=randomUUID();
 const room=t.act(host.token,{type:'create',intent,visibility:'public',fingerprint}).room!;t.act(host.token,{type:'confirmCreate',intent});
 const command={type:'joinCode',code:room.code!,intent:randomUUID(),policy:'relay'} as const;
 assert.ok(parseRoomCommand({...command,requestId:randomUUID()}));
 const joined=t.act(peer.token,command).room!;
 assert.equal(joined.connectionPolicy,'relay');assert.equal(joined.peer.status,'relay_unavailable');
 assert.equal(host.events.some(event=>event.type==='peerPrepare'),false);
});

test('either local policy change renews the epoch even when the other peer keeps relay required',()=>{
 const t=setup(1),{host,peer}=t.pair('relay');
 const both=t.act(peer.token,{type:'peerPolicy',policy:'relay'}).room!;
 const relaxed=t.act(host.token,{type:'peerPolicy',policy:'standard'}).room!;
 assert.equal(relaxed.peer.policy,'relay');assert.notEqual(relaxed.peer.epoch,both.peer.epoch);
 assert.throws(()=>t.act(peer.token,{type:'peerAck',epoch:both.peer.epoch!}),/stale_peer/);
});

for(const phase of ['preparing','connecting'] as const) test(`${phase} deadline publishes failed state to both members without another command`,()=>{
 const t=setup(1),{host,peer,room}=t.pair('relay'),epoch=room.peer.epoch!;
 if(phase==='connecting') {t.act(host.token,{type:'peerAck',epoch});t.act(peer.token,{type:'peerAck',epoch});}
 host.events.length=0;peer.events.length=0;
 const deadline=phase==='preparing'?15_000:20_000;
 t.advance(deadline-1);assert.equal(host.events.length,0);assert.equal(peer.events.length,0);
 t.advance(1);
 for(const member of [host,peer]) {
  assert.equal(member.events[0]?.type,'peerStop');
  const views=member.events.filter(event=>event.type==='room');assert.equal(views.length,1);
  assert.equal(views[0].room.peer.status,'failed');assert.equal(views[0].room.peer.epoch,epoch);
  assert.equal(views[0].room.id,room.id);assert.equal(views[0].room.reservationUntil,room.reservationUntil);assert.equal(views[0].room.status,'reserved');
 }
 t.advance(1);assert.equal(host.events.filter(event=>event.type==='room').length,1);
 const retried=t.act(peer.token,{type:'peerRetry',epoch}).room!;
 assert.notEqual(retried.peer.epoch,epoch);assert.equal(retried.peer.status,'preparing');assert.equal(retried.reservationUntil,room.reservationUntil);
});
