import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID,createHmac} from 'node:crypto';
import {Rooms} from './rooms.ts';
import {PeerBroker,relayConfig} from './peer.ts';
import {parseRoomCommand,type RoomCommand,type RoomEvent,type Fingerprint} from '../../../packages/contracts/src/rooms.ts';
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}};
type Command=RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'>:never:never;
function setup(relayRooms?:number) {
 let now=1000;const secret='test-secret'.repeat(4),rooms=new Rooms(()=>now,undefined,relayRooms===undefined?undefined:{urls:['turn:127.0.0.1:3478'],secret,pairs:relayRooms});
 const guest=()=>{const events:RoomEvent[]=[];const send=(event:RoomEvent)=>events.push(event);return {...rooms.attach(undefined,send,()=>{}),events,send};};
 const pairs=new Map<string,string>();
 const act=(token:string,command:Record<string,unknown>)=>rooms.handle(token,{...(String(command.type).startsWith('peer')?{pairId:pairs.get(token)}:{}),...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const pair=()=>{const host=guest(),peer=guest(),intent=randomUUID();const room=act(host.token,{type:'create',intent,visibility:'public',fingerprint}).room!;act(host.token,{type:'confirmCreate',intent});const joined=act(peer.token,{type:'join',invite:room.invite,intent:randomUUID()}).room!;pairs.set(host.token,joined.peers[0].pairId);pairs.set(peer.token,joined.peers[0].pairId);return {host,peer,room:joined};};
 return {rooms,secret,guest,act,pair,advance(ms:number){now+=ms;rooms.sweep();}};
}
test('automatic peers receive direct and relay options and acknowledge before signaling',()=>{
 const t=setup(2),{host,peer,room}=t.pair(),epoch=room.peers[0].epoch!;
 const prepared=host.events.find(event=>event.type==='peerPrepare');assert.ok(prepared?.type==='peerPrepare');assert.equal(prepared.policy,'standard');
 const ice=prepared.iceServers[0];assert.equal(ice.credential,createHmac('sha1',t.secret).update(ice.username!).digest('base64'));assert.ok(Number(ice.username!.split(':')[0])<=301);
 const offer={kind:'description' as const,description:{type:prepared.offerer?'offer' as const:'answer' as const,sdp:'v=0\r\n'}};
 assert.throws(()=>t.act(host.token,{type:'peerSignal',epoch,signal:offer}),/peer_not_prepared/);
 t.act(host.token,{type:'peerAck',epoch});assert.equal(host.events.some(event=>event.type==='peerStart'),false);
 t.act(peer.token,{type:'peerAck',epoch});assert.equal(host.events.some(event=>event.type==='peerStart'),true);
 assert.throws(()=>t.act(peer.token,{type:'peerSignal',epoch,signal:offer}),/invalid_peer_description/);
 t.act(host.token,{type:'peerSignal',epoch,signal:{kind:'candidate',candidate:{candidate:'candidate:1 1 udp 1 127.0.0.1 99 typ host',sdpMid:'0',sdpMLineIndex:0}}});
 t.act(host.token,{type:'peerSignal',epoch,signal:offer});assert.equal(peer.events.filter(event=>event.type==='peerSignal').length,2);
 const stranger=t.guest();assert.throws(()=>t.act(stranger.token,{type:'peerAck',pairId:room.peers[0].pairId,epoch}),/not_in_room/);
 const view=t.act(peer.token,{type:'file',fingerprint}).room!;assert.equal(view.role,'member');assert.equal(view.peers[0].status,'connecting');assert.equal(view.reservationUntil,room.reservationUntil);
});
test('relay capacity exhaustion still permits direct negotiation and retry',()=>{
 const unavailable=setup(),a=unavailable.pair();assert.equal(a.room.peers[0].status,'preparing');assert.deepEqual((a.host.events.find(event=>event.type==='peerPrepare') as Extract<RoomEvent,{type:'peerPrepare'}>).iceServers,[]);
 const t=setup(1),first=t.pair(),second=t.pair();assert.equal(second.room.peers[0].status,'preparing');assert.deepEqual((second.host.events.find(event=>event.type==='peerPrepare') as Extract<RoomEvent,{type:'peerPrepare'}>).iceServers,[]);
 t.act(first.host.token,{type:'close',roomId:first.room.id});const retried=t.act(second.peer.token,{type:'peerRetry',epoch:second.room.peers[0].epoch!}).room!;assert.equal(retried.peers[0].status,'preparing');assert.equal(retried.peers[0].policy,'standard');assert.equal(retried.reservationUntil,second.room.reservationUntil);
});
test('socket changes invalidate epochs; cancellation and expiry remove signaling authority',()=>{
 const t=setup(1),{host,peer,room}=t.pair(),old=room.peers[0].epoch!;
 t.rooms.attach(host.token,()=>{},()=>{});assert.throws(()=>t.rooms.handle(host.token,{type:'heartbeat',requestId:randomUUID()},host.send),/session_replaced/);assert.throws(()=>t.act(peer.token,{type:'peerAck',epoch:old}),/stale_peer/);
 t.act(peer.token,{type:'leave',intent:room.reservationIntent!});assert.throws(()=>t.act(peer.token,{type:'peerAck',epoch:old}),/not_in_room/);
 const exp=t.pair();t.advance(120_000);assert.throws(()=>t.act(exp.peer.token,{type:'peerAck',epoch:exp.room.peers[0].epoch!}),/not_in_room/);
});
test('negotiation timeouts and signaling schema are bounded independently of room lease',()=>{
 const t=setup(),{host,peer,room}=t.pair();t.advance(15_000);assert.ok(host.events.some(event=>event.type==='peerStop' && event.reason.includes('timed out')));
 assert.equal(t.act(peer.token,{type:'file',fingerprint}).room!.reservationUntil,room.reservationUntil);
 const base={type:'peerSignal',requestId:randomUUID(),pairId:randomUUID(),epoch:randomUUID(),signal:{kind:'description',description:{type:'offer',sdp:'v=0\r\n'}}};assert.ok(parseRoomCommand(base));
 for(const bad of [{...base,target:'forged'},{...base,signal:{kind:'description',description:{type:'offer',sdp:'v=0'+'x'.repeat(12_000)}}},{...base,epoch:'short'},{type:'peerPolicy',requestId:randomUUID(),policy:'relay'},{type:'hello',gameplayProtocol:2,requestId:randomUUID(),policy:'relay'}]) assert.equal(parseRoomCommand(bad),undefined);
 assert.throws(()=>relayConfig({TURN_URLS:'https://bad',TURN_SECRET:'x'.repeat(32),TURN_ROOM_LIMIT:'1'}));
});

test('reconnecting a member retains the automatic policy and renews its epoch',()=>{
 const t=setup(1),{host,peer,room}=t.pair(),events:RoomEvent[]=[];
 const restored=t.rooms.attach(peer.token,event=>events.push(event),()=>{}).data.room!;
 assert.equal(restored.peers[0].policy,'standard');assert.equal(restored.reservationUntil,room.reservationUntil);
 assert.ok(events.some(event=>event.type==='peerPrepare' && event.policy==='standard'));
 assert.throws(()=>t.act(host.token,{type:'peerAck',epoch:room.peers[0].epoch!}),/stale_peer/);
});

test('public-code admission uses automatic policy without a visitor override',()=>{
 const t=setup(),host=t.guest(),peer=t.guest(),intent=randomUUID();
 const room=t.act(host.token,{type:'create',intent,visibility:'public',fingerprint}).room!;t.act(host.token,{type:'confirmCreate',intent});
 const command={type:'joinCode',code:room.code!,intent:randomUUID()} as const;
 assert.ok(parseRoomCommand({...command,requestId:randomUUID()}));
 const joined=t.act(peer.token,command).room!;
 assert.equal(joined.connectionPolicy,'standard');assert.equal(joined.peers[0].status,'preparing');
 assert.ok(host.events.some(event=>event.type==='peerPrepare'));
 assert.equal(parseRoomCommand({...command,requestId:randomUUID(),policy:'relay'}),undefined);
});
test('an existing strict relay pair stays strict through retry',()=>{
 const hostEvents:RoomEvent[]=[],memberEvents:RoomEvent[]=[],broker=new PeerBroker(()=>1000,{urls:['turn:127.0.0.1:3478'],secret:'test-secret'.repeat(4),pairs:1});
 const pair={id:'pair',roomId:'room',offerer:{id:'host',token:'host-token',policy:'relay' as const,send:(event:RoomEvent)=>hostEvents.push(event)},answerer:{id:'member',token:'member-token',policy:'standard' as const,send:(event:RoomEvent)=>memberEvents.push(event)},gameplay:true,reservation:'reservation'};
 broker.sync(pair,pair.id);const prepared=hostEvents.find(event=>event.type==='peerPrepare');assert.ok(prepared?.type==='peerPrepare');assert.equal(prepared.policy,'relay');
 broker.handle(pair.roomId,pair.offerer.token,{type:'peerRetry',pairId:pair.id,epoch:prepared.epoch,requestId:randomUUID()});broker.sync(pair,pair.id);
 const next=hostEvents.filter(event=>event.type==='peerPrepare').at(-1)!;assert.equal(next.policy,'relay');assert.notEqual(next.epoch,prepared.epoch);
 broker.handle(pair.roomId,pair.offerer.token,{type:'peerAck',pairId:pair.id,epoch:next.epoch,requestId:randomUUID()});broker.handle(pair.roomId,pair.answerer.token,{type:'peerAck',pairId:pair.id,epoch:next.epoch,requestId:randomUUID()});
 assert.throws(()=>broker.handle(pair.roomId,pair.offerer.token,{type:'peerSignal',pairId:pair.id,epoch:next.epoch,requestId:randomUUID(),signal:{kind:'candidate',candidate:{candidate:'candidate:1 1 udp 1 127.0.0.1 99 typ host',sdpMid:'0',sdpMLineIndex:0}}}),/relay_required/);
});

for(const phase of ['preparing','connecting'] as const) test(`${phase} deadline publishes failed state to both members without another command`,()=>{
 const t=setup(1),{host,peer,room}=t.pair(),epoch=room.peers[0].epoch!;
 if(phase==='connecting') {t.act(host.token,{type:'peerAck',epoch});t.act(peer.token,{type:'peerAck',epoch});}
 host.events.length=0;peer.events.length=0;
 const deadline=phase==='preparing'?15_000:20_000;
 t.advance(deadline-1);assert.equal(host.events.length,0);assert.equal(peer.events.length,0);
 t.advance(1);
 for(const member of [host,peer]) {
  assert.equal(member.events[0]?.type,'peerStop');
  const views=member.events.filter(event=>event.type==='room');assert.equal(views.length,1);
  assert.equal(views[0].room.peers[0].status,'failed');assert.equal(views[0].room.peers[0].epoch,epoch);
  assert.equal(views[0].room.id,room.id);assert.equal(views[0].room.reservationUntil,member===peer?room.reservationUntil:undefined);assert.equal(views[0].room.status,'reserved');
 }
 t.advance(1);assert.equal(host.events.filter(event=>event.type==='room').length,1);
 const retried=t.act(peer.token,{type:'peerRetry',epoch}).room!;
 assert.notEqual(retried.peers[0].epoch,epoch);assert.equal(retried.peers[0].status,'preparing');assert.equal(retried.reservationUntil,room.reservationUntil);
});

test('ICE completion markers remain authenticated under automatic policy',()=>{
 const t=setup(1),{host,peer,room}=t.pair();const epoch=room.peers[0].epoch!;
 t.act(host.token,{type:'peerAck',epoch});t.act(peer.token,{type:'peerAck',epoch});
 const command={type:'peerSignal',requestId:randomUUID(),pairId:room.peers[0].pairId,epoch,signal:{kind:'candidate',candidate:{candidate:'',sdpMid:'0',sdpMLineIndex:0,usernameFragment:'generation'}}} as const;
 assert.ok(parseRoomCommand(command));
 t.act(host.token,command);assert.ok(peer.events.some(event=>event.type==='peerSignal' && event.signal.kind==='candidate' && event.signal.candidate.candidate===''));
 assert.equal(parseRoomCommand({...command,signal:{...command.signal,candidate:{...command.signal.candidate,candidate:' '}}}),undefined);
 assert.throws(()=>t.act(host.token,{...command,epoch:randomUUID()}),/stale_peer/);
});

test('selected routes log once per member and epoch without connection secrets',t=>{
 const lines:string[]=[];t.mock.method(console,'info',(line:string)=>lines.push(line));
 const setupRoom=setup(1),{host,peer,room}=setupRoom.pair(),epoch=room.peers[0].epoch!;
 const route=(token:string,selected:'direct'|'relay')=>setupRoom.act(token,{type:'peerRoute',epoch,route:selected});
 assert.equal(parseRoomCommand({type:'peerRoute',requestId:randomUUID(),epoch,route:'host'}),undefined);
 assert.throws(()=>route(host.token,'direct'),/peer_not_connected/);
 setupRoom.act(host.token,{type:'peerAck',epoch});setupRoom.act(peer.token,{type:'peerAck',epoch});
 setupRoom.act(host.token,{type:'peerConnected',epoch});route(host.token,'direct');route(host.token,'direct');
 setupRoom.act(peer.token,{type:'peerConnected',epoch});route(peer.token,'relay');
 assert.equal(lines.length,2);
 const logged=lines.map(line=>JSON.parse(line));
 assert.deepEqual(logged.map(line=>[line.event,line.member,line.route]),[['peer_route',room.hostMembership,'direct'],['peer_route',room.chatMembership,'relay']]);
 for(const line of lines)assert.doesNotMatch(line,/candidate|credential|sdp|token|127\.0\.0\.1/);
 assert.throws(()=>setupRoom.act(host.token,{type:'peerRoute',epoch:randomUUID(),route:'relay'}),/stale_peer/);
 setupRoom.act(host.token,{type:'peerFailed',epoch});
 assert.throws(()=>route(peer.token,'direct'),/peer_not_connected/);
 assert.equal(lines.length,2);
});

// A third legitimate room member still has no authority over someone else's pair.
test('pair IDs confine signaling and retries to exactly two authenticated members',()=>{
 const t=setup(10),{host,peer,room}=t.pair(),third=t.guest();
 const joined=t.act(third.token,{type:'join',invite:room.invite,intent:randomUUID()}).room!;
 assert.equal(joined.peers.length,2);assert.equal(new Set(joined.peers.map(pair=>pair.pairId)).size,2);
 const target=room.peers[0];
 for(const type of ['peerAck','peerRetry','peerConnected','peerFailed'])assert.throws(()=>t.act(third.token,{type,pairId:target.pairId,epoch:target.epoch}),/stale_peer/);
 assert.throws(()=>t.act(third.token,{type:'peerSignal',pairId:target.pairId,epoch:target.epoch,signal:{kind:'candidate',candidate:{candidate:'',sdpMid:'0',sdpMLineIndex:0}}}),/stale_peer/);
 t.act(host.token,{type:'peerAck',pairId:target.pairId,epoch:target.epoch});t.act(peer.token,{type:'peerAck',pairId:target.pairId,epoch:target.epoch});
 assert.equal(third.events.some(event=>event.type==='peerStart'&&event.pairId===target.pairId),false);
 assert.equal(host.events.filter(event=>event.type==='peerStart'&&event.pairId===target.pairId).length,1);
});
