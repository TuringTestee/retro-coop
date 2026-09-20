import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {once} from 'node:events';
import {WebSocket} from 'ws';
import {Rooms,limits,RoomError} from './rooms.ts';
import {createCoordinator,shutdown} from './server.ts';
import {parseRoomCommand,type Fingerprint,type RoomCommand,type RoomEvent} from '../../../packages/contracts/src/rooms.ts';
const fingerprint:Fingerprint = {romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:4,submapper:0,region:'NTSC',bytes:40976}};
type Command = RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'> : never : never;
function setup() {
 let now = 1000;const rooms = new Rooms(()=>now);
 const guest = () => {const events:RoomEvent[] = [];return {...rooms.attach(undefined,event=>events.push(event),()=>{}),events};};
 const act = (token:string,command:Command) => {assert.notEqual(command.type,'hello');return rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);};
 const host = (token:string,visibility:'public'|'unlisted' = 'public') => {const intent = randomUUID();const room = act(token,{type:'create',intent,visibility,fingerprint}).room!;act(token,{type:'confirmCreate',intent});return room;};
 return {rooms,guest,act,host,advance(ms:number){now+=ms;rooms.sweep();}};
}
test('creation acknowledgement and cancellation never expose stale invitations',()=>{
 const t = setup(), host = t.guest(), viewer = t.guest(), intent = randomUUID();
 const room = t.act(host.token,{type:'create',intent,visibility:'public',fingerprint}).room!;
 assert.match(room.code!,/^[A-HJ-NP-Z2-9]{8}$/);assert.equal(Buffer.from(room.invite,'base64url').length,32);
 assert.throws(()=>t.act(viewer.token,{type:'preview',invite:room.invite}),/room_unavailable/);
 t.act(host.token,{type:'cancelCreate',intent});
 assert.throws(()=>t.act(host.token,{type:'confirmCreate',intent}),/not_in_room/);
 assert.throws(()=>t.act(host.token,{type:'create',intent,visibility:'public',fingerprint}),/cancelled/);
 const provisional = t.act(host.token,{type:'create',intent:randomUUID(),visibility:'public',fingerprint}).room!;
 t.advance(5000);
 assert.throws(()=>t.act(viewer.token,{type:'join',intent:randomUUID(),invite:provisional.invite}),/room_unavailable/);
});
test('unlisted preview excludes hashes and codes, host alone controls room mutations',()=>{
 const t = setup(), host = t.guest(), guest = t.guest(), room = t.host(host.token,'unlisted');
 const preview = t.act(guest.token,{type:'preview',invite:room.invite}).preview!;
 assert.equal(preview.code,undefined);assert.equal(JSON.stringify(preview).includes(fingerprint.romSha256),false);
 t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite});
 for(const command of [{type:'close'},{type:'kick'},{type:'rename',label:'stolen'},{type:'visibility',visibility:'public'}] as Command[]) assert.throws(()=>t.act(guest.token,command),/host_only/);
 const publicRoom = t.act(host.token,{type:'visibility',visibility:'public'}).room!;assert.ok(publicRoom.code);
 assert.equal(t.act(host.token,{type:'visibility',visibility:'unlisted'}).room!.code,undefined);
 t.act(host.token,{type:'kick'});assert.throws(()=>t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite}),/room_unavailable/);
});
test('two concurrent contenders have one winner and cancellation frees the slot immediately',async()=>{
 const t = setup(), host = t.guest(), a = t.guest(), b = t.guest(), room = t.host(host.token);
 const results = await Promise.allSettled([a,b].map(guest=>Promise.resolve().then(()=>t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite}))));
 assert.equal(results.filter(result=>result.status === 'fulfilled').length,1);
 assert.equal(results.filter(result=>result.status === 'rejected').length,1);
 t.act(a.token,{type:'leave',intent:t.rooms.attach(a.token,()=>{},()=>{}).data.room!.reservationIntent!});assert.equal(t.act(b.token,{type:'join',intent:randomUUID(),invite:room.invite}).room!.slot,2);
});
test('mismatch, reconnect and retries do not extend the initial 120-second reservation',()=>{
 const t = setup(), host = t.guest(), guest = t.guest(), room = t.host(host.token);
 const reserved = t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite}).room!;
 t.advance(25_000);t.act(host.token,{type:'heartbeat'});
 const mismatch = t.act(guest.token,{type:'file',fingerprint:{...fingerprint,romSha256:'c'.repeat(64)}}).room!;assert.equal(mismatch.matches,false);assert.equal(mismatch.reservationUntil,reserved.reservationUntil);
 const restored = t.rooms.attach(guest.token,()=>{},()=>{}).data.room!;assert.equal(restored.reservationUntil,reserved.reservationUntil);
 assert.throws(()=>t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite}),/already_in_room/);
 for(let i=0;i<4;i++) {t.advance(24_000);t.act(host.token,{type:'heartbeat'});}
 assert.throws(()=>t.act(guest.token,{type:'file',fingerprint}),/not_in_room/);
 assert.equal(t.rooms.attach(guest.token,()=>{},()=>{}).data.room,undefined);
 const retry = t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite}).room!;assert.ok(retry.reservationUntil! > reserved.reservationUntil!);
});
test('only host membership receives heartbeat detection and 60-second recovery grace',()=>{
 const t = setup(), host = t.guest(), watcher = t.guest(), room = t.host(host.token);
 t.advance(30_000);assert.equal(t.act(watcher.token,{type:'preview',invite:room.invite}).preview!.status,'reconnecting');
 assert.throws(()=>t.act(watcher.token,{type:'join',intent:randomUUID(),invite:room.invite}),/host_reconnecting/);
 t.advance(59_000);const recovered = t.rooms.attach(host.token,()=>{},()=>{}).data.room!;assert.equal(recovered.status,'waiting');
 t.advance(90_000);assert.throws(()=>t.act(watcher.token,{type:'preview',invite:room.invite}),/room_unavailable/);
});
test('unused sessions expire, capacity is bounded, rate limits state their retry time',()=>{
 const t = setup(), guest = t.guest();t.advance(limits.sessionIdle);assert.throws(()=>t.rooms.attach(guest.token,()=>{},()=>{}),/session_expired/);
 const host = t.guest(), room = t.host(host.token), contender = t.guest();
 for(let i=0;i<5;i++) {const reservation=t.act(contender.token,{type:'join',intent:randomUUID(),invite:room.invite}).room!;t.act(contender.token,{type:'leave',intent:reservation.reservationIntent!});}
 assert.throws(()=>t.act(contender.token,{type:'join',intent:randomUUID(),invite:room.invite}),error=>error instanceof RoomError && error.code === 'rate_limited' && error.retryAfterMs! > 0);
 for(let i=1;i<limits.rooms;i++) t.host(t.guest().token);
 assert.throws(()=>t.host(t.guest().token),/capacity/);
});
test('strict metadata schema rejects uploads, arbitrary fields and malformed values',()=>{
 const requestId = randomUUID(), command = {type:'create',requestId,intent:randomUUID(),visibility:'public',fingerprint};
 assert.ok(parseRoomCommand(command));
 for(const invalid of [{...command,filename:'secret.nes'},{...command,rom:[1,2,3]},{...command,fingerprint:{...fingerprint,extra:'x'}},{...command,fingerprint:{...fingerprint,romSha256:'bad'}},{type:'rename',requestId,label:'\u0000hello'},{type:'file',requestId,fingerprint:{...fingerprint,cartridge:{...fingerprint.cartridge,mapper:-1}}}]) assert.equal(parseRoomCommand(invalid),undefined);
});

test('real WebSockets enforce origin/auth/schema and atomic reservations across clients',async()=>{
 const origin = 'http://127.0.0.1:5173', server = createCoordinator({origins:[origin]});server.listen(0,'127.0.0.1');await once(server,'listening');
 const url = `ws://127.0.0.1:${(server.address() as {port:number}).port}/ws`, clients:WebSocket[] = [];
 const connect = async() => {const socket = new WebSocket(url,{origin});clients.push(socket);await once(socket,'open');return socket;};
 const request = async(socket:WebSocket,command:Command) => {
  const requestId = randomUUID();
  const result = new Promise<Extract<RoomEvent,{type:'result'}>>(resolve=>{const listen = (raw:Buffer)=>{const event = JSON.parse(raw.toString());if(event.type === 'result' && event.requestId === requestId) {socket.off('message',listen);resolve(event);}};socket.on('message',listen);});
  socket.send(JSON.stringify({...command,requestId}));return result;
 };
 try {
  const rejected = new WebSocket(url,{origin:'https://evil.example'});rejected.on('error',()=>{});const rejection = await once(rejected,'unexpected-response');assert.equal(rejection[1].statusCode,403);rejection[1].destroy();rejected.terminate();
  const host = await connect(), a = await connect(), b = await connect();
  assert.equal((await request(a,{type:'close'})).ok,false);
  for(const client of [host,a,b]) assert.equal((await request(client,{type:'hello'})).ok,true);
  const intent = randomUUID();const created = await request(host,{type:'create',intent,visibility:'public',fingerprint});assert.ok(created.ok);
  await request(host,{type:'confirmCreate',intent});const invite = created.data.room!.invite;
  const race = await Promise.all([a,b].map(socket=>request(socket,{type:'join',intent:randomUUID(),invite})));assert.equal(race.filter(result=>result.ok).length,1);
  const attacker = await connect(), closed = once(attacker,'close');attacker.send(Buffer.from('binary ROM'));assert.equal((await closed)[0],1008);
  const forged = await connect(), invalid = once(forged,'close');forged.send(JSON.stringify({type:'hello',requestId:randomUUID(),filename:'private.nes'}));assert.equal((await invalid)[0],1008);
  const flood = await connect(), flooded = once(flood,'close');for(let i=0;i<121;i++) flood.send(JSON.stringify({type:'hello',requestId:randomUUID()}));assert.equal((await flooded)[0],1008);
  const large = await connect(), over = once(large,'close');large.send('x'.repeat(5000));assert.equal((await over)[0],1009);
  const padded=await connect(),paddingClosed=once(padded,'close');padded.send(JSON.stringify({type:'nickname',requestId:randomUUID(),nickname:'peerSignal'})+' '.repeat(4500));assert.equal((await paddingClosed)[0],1009);
 } finally {for(const client of clients) client.terminate();await shutdown(server);}
});

test('delayed cancellation cannot release a newer reservation from the same guest',()=>{
 const t=setup(),host=t.guest(),guest=t.guest(),room=t.host(host.token),a=randomUUID(),b=randomUUID();
 t.act(guest.token,{type:'join',invite:room.invite,intent:a});
 t.act(guest.token,{type:'leave',intent:a});
 const second=t.act(guest.token,{type:'join',invite:room.invite,intent:b}).room!;
 t.act(guest.token,{type:'leave',intent:a});
 t.act(host.token,{type:'leave',intent:b}); // Knowing an intent does not confer guest authority.
 const restored=t.rooms.attach(guest.token,()=>{},()=>{}).data.room!;
 assert.equal(restored.reservationIntent,b);assert.equal(restored.reservationUntil,second.reservationUntil);
 t.act(guest.token,{type:'leave',intent:b});
 assert.equal(t.rooms.attach(guest.token,()=>{},()=>{}).data.room,undefined);
});

test('directory publishes admitted public metadata through reservation, visibility and recovery',()=>{
 const t=setup(),watcher=t.guest(),host=t.guest(),hidden=t.guest(),joiner=t.guest();
 assert.deepEqual(t.act(watcher.token,{type:'directory'}).directory,[]);
 const intent=randomUUID(),provisional=t.act(host.token,{type:'create',intent,visibility:'public',fingerprint}).room!;
 t.host(hidden.token,'unlisted');assert.deepEqual(t.act(watcher.token,{type:'directory'}).directory,[]);
 t.act(host.token,{type:'confirmCreate',intent});
 const latest=()=>watcher.events.filter(event=>event.type==='directory').at(-1)!.rooms;
 assert.equal(latest().length,1);assert.equal(latest()[0].id,provisional.id);
 assert.deepEqual(Object.keys(latest()[0]).sort(),['code','host','id','label','occupancy','status','visibility']);
 const code=provisional.code!;
 assert.equal(t.act(joiner.token,{type:'lookupCode',code}).preview!.id,provisional.id);
 const joined=t.act(joiner.token,{type:'joinCode',code,intent:randomUUID()}).room!;
 assert.equal(latest()[0].occupancy,2);assert.equal(latest()[0].status,'reserved');
 t.act(joiner.token,{type:'leave',intent:joined.reservationIntent!});assert.equal(latest()[0].status,'waiting');
 t.act(host.token,{type:'rename',label:'Same name'});assert.equal(latest()[0].label,'Same name');
 t.act(host.token,{type:'nickname',nickname:'Local host'});assert.equal(latest()[0].host,'Local host');
 t.advance(30_000);assert.equal(latest()[0].status,'reconnecting');
 t.rooms.attach(host.token,()=>{},()=>{});assert.equal(latest()[0].status,'waiting');
 t.act(host.token,{type:'visibility',visibility:'unlisted'});assert.deepEqual(latest(),[]);
 assert.throws(()=>t.act(joiner.token,{type:'lookupCode',code}),/room_unavailable/);
 assert.throws(()=>t.act(joiner.token,{type:'joinCode',code,intent:randomUUID()}),/room_unavailable/);
 t.act(host.token,{type:'visibility',visibility:'public'});assert.equal(latest().length,1);
 t.act(host.token,{type:'close'});assert.deepEqual(latest(),[]);
});

test('public-code admission shares invitation slot ownership, deadline and invalid-attempt limits',async()=>{
 const t=setup(),host=t.guest(),a=t.guest(),b=t.guest(),room=t.host(host.token);
 const results=await Promise.allSettled([
  Promise.resolve().then(()=>t.act(a.token,{type:'joinCode',code:room.code!,intent:randomUUID()})),
  Promise.resolve().then(()=>t.act(b.token,{type:'join',invite:room.invite,intent:randomUUID()})),
 ]);
 assert.equal(results.filter(result=>result.status==='fulfilled').length,1);
 const winner=results.find(result=>result.status==='fulfilled')!;assert.equal(winner.value.room!.reservationUntil,121000);
 const attacker=t.guest();for(let i=0;i<5;i++) assert.throws(()=>t.act(attacker.token,{type:'joinCode',code:'ZZZZZZZZ',intent:randomUUID()}),/room_unavailable/);
 assert.throws(()=>t.act(attacker.token,{type:'join',invite:room.invite,intent:randomUUID()}),/rate_limited/);
});

test('public-code allocation retries collisions atomically and fails without creating a room',()=>{
 const candidates=['AAAAAAAA','AAAAAAAA','BBBBBBBB'];
 const rooms=new Rooms(()=>1000,()=>candidates.shift() ?? 'AAAAAAAA');
 const host=()=>rooms.attach(undefined,()=>{},()=>{}).token;
 const create=(token:string)=>rooms.handle(token,{type:'create',requestId:randomUUID(),intent:randomUUID(),visibility:'public',fingerprint});
 assert.equal(create(host()).room!.code,'AAAAAAAA');assert.equal(create(host()).room!.code,'BBBBBBBB');
 const token=host();assert.throws(()=>create(token),/capacity/);assert.equal(rooms.attach(token,()=>{},()=>{}).data.room,undefined);
});
