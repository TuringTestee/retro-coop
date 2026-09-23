import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {once} from 'node:events';
import {WebSocket} from 'ws';
import {Rooms,limits,RoomError} from './rooms.ts';
import {createCoordinator,shutdown} from './server.ts';
import {parseRoomCommand,type Fingerprint,type RoomCommand,type RoomEvent} from '../../../packages/contracts/src/rooms.ts';
import {catalogEntry} from '../../../packages/contracts/src/catalog.ts';
import {LOCAL_SCHEMA,LOCAL_SETTINGS} from '../../../packages/contracts/src/fingerprint.ts';
const fingerprint:Fingerprint = {romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:4,submapper:0,region:'NTSC',bytes:40976}};
const includedFingerprint=(id:'super-tilt-bro-pal'|'from-below-1.0'):Fingerprint=>{const entry=catalogEntry(id);return {romSha256:entry.sha256,coreSha256:'b'.repeat(64),localSchema:LOCAL_SCHEMA,settings:LOCAL_SETTINGS,cartridge:{format:entry.format,mapper:entry.mapper,submapper:entry.submapper,region:entry.region,bytes:entry.bytes}};};
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
 const joined=t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite}).room!;
 for(const command of [{type:'close',roomId:room.id},{type:'kick',roomId:room.id,guestMembership:joined.chatMembership},{type:'rename',roomId:room.id,label:'stolen'},{type:'visibility',roomId:room.id,visibility:'public'}] as Command[]) assert.throws(()=>t.act(guest.token,command),/host_only/);
 const publicRoom = t.act(host.token,{type:'visibility',roomId:room.id,visibility:'public'}).room!;assert.ok(publicRoom.code);
 assert.equal(t.act(host.token,{type:'visibility',roomId:room.id,visibility:'unlisted'}).room!.code,undefined);
 t.act(host.token,{type:'kick',roomId:room.id,guestMembership:joined.chatMembership});assert.throws(()=>t.act(guest.token,{type:'join',intent:randomUUID(),invite:room.invite}),/room_unavailable/);
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
 const claim={type:'claimCode',requestId,code:'ABCDEFGH',intent:randomUUID(),fingerprint:includedFingerprint('from-below-1.0')};
 assert.ok(parseRoomCommand(claim));
 const start={type:'startRoom',requestId,roomId:randomUUID(),membership:randomUUID(),fingerprint};assert.ok(parseRoomCommand(start));assert.ok(parseRoomCommand({...start,type:'prepareHost'}));
 for(const invalid of [{...command,filename:'secret.nes'},{...command,rom:[1,2,3]},{...command,fingerprint:{...fingerprint,extra:'x'}},{...command,fingerprint:{...fingerprint,romSha256:'bad'}},{...claim,filename:'secret.nes'},{...claim,fingerprint:{...claim.fingerprint,romSha256:'bad'}},{...start,filename:'private.nes'},{...start,fingerprint:{...fingerprint,romSha256:'bad'}},{type:'rename',roomId:randomUUID(),requestId,label:'\u0000hello'},{type:'file',requestId,fingerprint:{...fingerprint,cartridge:{...fingerprint.cartridge,mapper:-1}}}]) assert.equal(parseRoomCommand(invalid),undefined);
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
  assert.equal((await request(a,{type:'close',roomId:randomUUID()})).ok,false);
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
 t.act(host.token,{type:'rename',roomId:provisional.id,label:'Same name'});assert.equal(latest()[0].label,'Same name');
 t.act(host.token,{type:'nickname',nickname:'Local host'});assert.equal(latest()[0].host,'Local host');
 t.advance(30_000);assert.equal(latest()[0].status,'reconnecting');
 t.rooms.attach(host.token,()=>{},()=>{});assert.equal(latest()[0].status,'waiting');
 t.act(host.token,{type:'visibility',roomId:provisional.id,visibility:'unlisted'});assert.deepEqual(latest(),[]);
 assert.throws(()=>t.act(joiner.token,{type:'lookupCode',code}),/room_unavailable/);
 assert.throws(()=>t.act(joiner.token,{type:'joinCode',code,intent:randomUUID()}),/room_unavailable/);
 t.act(host.token,{type:'visibility',roomId:provisional.id,visibility:'public'});assert.equal(latest().length,1);
 t.act(host.token,{type:'close',roomId:provisional.id});assert.deepEqual(latest(),[]);
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

test('empty offers are opt-in, first claim is atomic, and the same room becomes host-owned',async()=>{
 let now=1000;const rooms=new Rooms(()=>now,undefined,undefined,['super-tilt-bro-pal','from-below-1.0']);
 const attach=()=>{const events:RoomEvent[]=[];return {...rooms.attach(undefined,event=>events.push(event),()=>{}),events};};
 const act=(token:string,command:Command)=>rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const old=attach(),watcher=attach(),a=attach(),b=attach();
 assert.deepEqual(act(old.token,{type:'directory'}).directory,[]);
 const offers=act(watcher.token,{type:'directory',includeEmptyOffers:true}).directory!;
 assert.equal(offers.length,2);assert.ok(offers.every(offer=>offer.occupancy===0&&offer.host==='No host'&&offer.status==='waiting'));
 assert.ok(offers.every(offer=>!JSON.stringify(offer).includes('romSha256')));
 const first=offers.find(offer=>offer.catalogId==='super-tilt-bro-pal')!;
 assert.throws(()=>act(old.token,{type:'lookupCode',code:first.code!}),/room_unavailable/);
 assert.equal(act(watcher.token,{type:'lookupCode',code:first.code!}).preview!.id,first.id);
 for(const contender of [a,b])act(contender.token,{type:'directory',includeEmptyOffers:true});
 const command:Command={type:'claimCode',code:first.code!,intent:randomUUID(),fingerprint:includedFingerprint('super-tilt-bro-pal')};
 const race=await Promise.allSettled([a,b].map(contender=>Promise.resolve().then(()=>act(contender.token,command))));
 assert.equal(race.filter(result=>result.status==='fulfilled').length,1);
 const winnerIndex=race.findIndex(result=>result.status==='fulfilled'),winner=[a,b][winnerIndex],loser=[a,b][1-winnerIndex];
 const claimed=(race[winnerIndex] as PromiseFulfilledResult<ReturnType<typeof act>>).value.room!;
 assert.equal(claimed.id,first.id);assert.equal(claimed.code,first.code);assert.equal(claimed.role,'host');assert.equal(claimed.slot,1);assert.equal(claimed.occupancy,1);
 assert.equal(act(winner.token,command).room!.id,claimed.id);
 const rows=act(watcher.token,{type:'directory',includeEmptyOffers:true}).directory!;
 assert.equal(rows.filter(row=>row.occupancy===0&&row.catalogId==='super-tilt-bro-pal').length,1);
 assert.equal(rows.find(row=>row.id===first.id)?.host,winner.data.session!.nickname);
 assert.equal(act(old.token,{type:'directory'}).directory!.length,1);
 assert.equal(rooms.operatorRooms().length,1);
 const joined=act(loser.token,{type:'joinCode',code:first.code!,intent:randomUUID()}).room!;
 assert.equal(joined.role,'guest');assert.equal(joined.id,first.id);
 act(winner.token,{type:'close',roomId:first.id});
 assert.equal(act(watcher.token,{type:'directory',includeEmptyOffers:true}).directory!.length,2);
 assert.equal(rooms.operatorRooms().length,0);
 assert.deepEqual(rooms.attach(watcher.token,()=>{},()=>{}).data.room,undefined);
 assert.deepEqual(act(watcher.token,{type:'directory'}).directory,[]);
 now+=1;rooms.stop();
});

test('offer claim rejects wrong file and full capacity without mutating the empty room',()=>{
 const rooms=new Rooms(()=>1000,undefined,undefined,['from-below-1.0']);
 const attach=()=>rooms.attach(undefined,()=>{},()=>{}).token;
 const act=(token:string,command:Command)=>rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const observer=attach(),claimant=attach();
 const offer=act(observer,{type:'directory',includeEmptyOffers:true}).directory![0];
 act(claimant,{type:'directory',includeEmptyOffers:true});
 assert.throws(()=>act(claimant,{type:'claimCode',code:offer.code!,intent:randomUUID(),fingerprint}),/room_unavailable/);
 assert.equal(act(observer,{type:'directory',includeEmptyOffers:true}).directory![0].id,offer.id);
 const hosts:string[]=[];
 for(let i=0;i<limits.rooms;i++){const host=attach(),intent=randomUUID();act(host,{type:'create',intent,visibility:'public',fingerprint});act(host,{type:'confirmCreate',intent});hosts.push(host);}
 const full=act(observer,{type:'directory',includeEmptyOffers:true}).directory!.find(row=>row.id===offer.id)!;
 assert.equal(full.status,'unavailable');assert.equal(full.unavailableReason,'room_capacity');
 assert.throws(()=>act(claimant,{type:'claimCode',code:offer.code!,intent:randomUUID(),fingerprint:includedFingerprint('from-below-1.0')}),/capacity/);
 assert.equal(rooms.operatorRooms().length,limits.rooms);
 act(hosts[0],{type:'close',roomId:rooms.operatorRooms()[0].id});
 assert.equal(act(observer,{type:'directory',includeEmptyOffers:true}).directory!.find(row=>row.id===offer.id)?.status,'waiting');
 assert.equal(act(claimant,{type:'claimCode',code:offer.code!,intent:randomUUID(),fingerprint:includedFingerprint('from-below-1.0')}).room?.id,offer.id);
});

test('pending human creation publishes an unavailable offer and cancellation or expiry restores it',()=>{
 let now=1000;const rooms=new Rooms(()=>now,undefined,undefined,['from-below-1.0']);
 const attach=()=>{const events:RoomEvent[]=[];return {...rooms.attach(undefined,event=>events.push(event),()=>{}),events};};
 const act=(token:string,command:Command)=>rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const watcher=attach();const offer=act(watcher.token,{type:'directory',includeEmptyOffers:true}).directory![0];
 for(let i=0;i<limits.rooms-1;i++){const host=attach(),intent=randomUUID();act(host.token,{type:'create',intent,visibility:'public',fingerprint});act(host.token,{type:'confirmCreate',intent});}
 const latest=()=>watcher.events.filter(event=>event.type==='directory').at(-1)!.rooms.find(row=>row.id===offer.id)!;
 assert.equal(latest().status,'waiting');
 const last=attach(),intent=randomUUID();act(last.token,{type:'create',intent,visibility:'unlisted',fingerprint});
 const fullOffer=latest();assert.equal(fullOffer.status,'unavailable');assert.equal(fullOffer.occupancy,0);
 if(fullOffer.occupancy===0) assert.equal(fullOffer.unavailableReason,'room_capacity');
 assert.equal(watcher.events.filter(event=>event.type==='directory').at(-1)!.rooms.filter(row=>row.occupancy>0).length,limits.rooms-1);
 act(last.token,{type:'cancelCreate',intent});assert.equal(latest().status,'waiting');
 const expired=attach();act(expired.token,{type:'create',intent:randomUUID(),visibility:'unlisted',fingerprint});
 assert.equal(latest().status,'unavailable');now+=5000;rooms.sweep();assert.equal(latest().status,'waiting');
});

test('cancel before or after an empty-room claim leaves no ghost host',()=>{
 const rooms=new Rooms(()=>1000,undefined,undefined,['from-below-1.0']);
 const token=rooms.attach(undefined,()=>{},()=>{}).token;
 const act=(command:Command)=>rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const first=act({type:'directory',includeEmptyOffers:true}).directory![0],intent=randomUUID(),fingerprint=includedFingerprint('from-below-1.0');
 act({type:'leave',intent});
 assert.throws(()=>act({type:'claimCode',code:first.code!,intent,fingerprint}),/cancelled/);
 assert.equal(act({type:'directory',includeEmptyOffers:true}).directory![0].id,first.id);
 const nextIntent=randomUUID(),claimed=act({type:'claimCode',code:first.code!,intent:nextIntent,fingerprint}).room!;
 act({type:'leave',intent:nextIntent});
 assert.equal(rooms.operatorRooms().length,0);
 assert.equal(act({type:'directory',includeEmptyOffers:true}).directory!.length,1);
 assert.throws(()=>act({type:'claimCode',code:first.code!,intent:nextIntent,fingerprint}),/cancelled/);
 assert.equal(claimed.id,first.id);
});

test('replacement-code exhaustion leaves the original offer and host session untouched',()=>{
 const rooms=new Rooms(()=>1000,()=>'AAAAAAAA',undefined,['from-below-1.0']);
 const token=rooms.attach(undefined,()=>{},()=>{}).token;
 const act=(command:Command)=>rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const offer=act({type:'directory',includeEmptyOffers:true}).directory![0];
 assert.throws(()=>act({type:'claimCode',code:offer.code!,intent:randomUUID(),fingerprint:includedFingerprint('from-below-1.0')}),/capacity/);
 assert.equal(rooms.attach(token,()=>{},()=>{}).data.room,undefined);
 assert.equal(act({type:'directory',includeEmptyOffers:true}).directory![0].id,offer.id);
 assert.equal(rooms.operatorRooms().length,0);
});

test('real WebSocket clients opt into offers and race for one first-host claim',async()=>{
 const origin='http://127.0.0.1:5173',server=createCoordinator({origins:[origin],offerCatalogIds:['from-below-1.0']});server.listen(0,'127.0.0.1');await once(server,'listening');
 const url=`ws://127.0.0.1:${(server.address() as {port:number}).port}/ws`,sockets:WebSocket[]=[];
 const connect=async()=>{const socket=new WebSocket(url,{origin});sockets.push(socket);await once(socket,'open');return socket;};
 const request=async(socket:WebSocket,command:Command)=>{const requestId=randomUUID();const response=new Promise<Extract<RoomEvent,{type:'result'}>>(resolve=>{const onMessage=(raw:Buffer)=>{const event=JSON.parse(raw.toString());if(event.type==='result'&&event.requestId===requestId){socket.off('message',onMessage);resolve(event);}};socket.on('message',onMessage);});socket.send(JSON.stringify({...command,requestId}));return response;};
 const data=(result:Extract<RoomEvent,{type:'result'}>)=>{if(!result.ok)throw Error(result.error);return result.data;};
 try {
  const old=await connect(),a=await connect(),b=await connect();
  for(const socket of [old,a,b])assert.equal((await request(socket,{type:'hello'})).ok,true);
  assert.deepEqual(data(await request(old,{type:'directory'})).directory,[]);
  const initial=data(await request(a,{type:'directory',includeEmptyOffers:true})).directory!;
  assert.equal(initial.length,1);assert.equal(initial[0].occupancy,0);
  await request(b,{type:'directory',includeEmptyOffers:true});
  const race=await Promise.all([a,b].map(socket=>request(socket,{type:'claimCode',code:initial[0].code!,intent:randomUUID(),fingerprint:includedFingerprint('from-below-1.0')})));
  assert.equal(race.filter(result=>result.ok).length,1);
  const claimed=data(race.find(result=>result.ok)!);
  assert.equal(claimed.room!.id,initial[0].id);
  const after=data(await request(b,{type:'directory',includeEmptyOffers:true})).directory!;
  assert.equal(after.filter(row=>row.occupancy===0).length,1);
  assert.equal(after.find(row=>row.id===initial[0].id)?.occupancy,1);
  assert.equal(data(await request(old,{type:'directory'})).directory!.length,1);
 }finally{for(const socket of sockets)socket.terminate();await shutdown(server);}
});

test('separate WebSocket browsers see host Start close an unready guest place',async()=>{
 const origin='http://127.0.0.1:5173',server=createCoordinator({origins:[origin]});server.listen(0,'127.0.0.1');await once(server,'listening');
 const url=`ws://127.0.0.1:${(server.address() as {port:number}).port}/ws`,sockets:WebSocket[]=[];
 const connect=async()=>{const socket=new WebSocket(url,{origin});sockets.push(socket);await once(socket,'open');return socket;};
 const request=async(socket:WebSocket,command:Command)=>{const requestId=randomUUID();const response=new Promise<Extract<RoomEvent,{type:'result'}>>(resolve=>{const onMessage=(raw:Buffer)=>{const event=JSON.parse(raw.toString());if(event.type==='result'&&event.requestId===requestId){socket.off('message',onMessage);resolve(event);}};socket.on('message',onMessage);});socket.send(JSON.stringify({...command,requestId}));return response;};
 const data=(result:Extract<RoomEvent,{type:'result'}>)=>{if(!result.ok)throw Error(result.error);return result.data;};
 try {
  const host=await connect(),guest=await connect(),watcher=await connect();
  for(const socket of [host,guest,watcher])data(await request(socket,{type:'hello'}));
  const intent=randomUUID();data(await request(host,{type:'create',intent,visibility:'public',fingerprint}));
  const room=data(await request(host,{type:'confirmCreate',intent})).room!;
  const joined=data(await request(guest,{type:'joinCode',code:room.code!,intent:randomUUID()})).room!;
  assert.equal(joined.occupancy,2);
  const beforeReady=await request(host,{type:'startRoom',roomId:room.id,membership:room.chatMembership,fingerprint});assert.equal(beforeReady.ok,false);if(!beforeReady.ok)assert.equal(beforeReady.error,'host_not_ready');
  data(await request(host,{type:'prepareHost',roomId:room.id,membership:room.chatMembership,fingerprint}));
  const started=data(await request(host,{type:'startRoom',roomId:room.id,membership:room.chatMembership,fingerprint})).room!;
  assert.equal(started.started,'solo');assert.equal(started.status,'playing');assert.equal(started.occupancy,1);
  const preview=data(await request(watcher,{type:'directory'})).directory!.find(row=>row.id===room.id)!;
  assert.equal(preview.status,'playing');assert.equal(preview.occupancy,1);
  const denied=await request(watcher,{type:'joinCode',code:room.code!,intent:randomUUID()});
  assert.equal(denied.ok,false);if(!denied.ok)assert.equal(denied.error,'room_started');
  assert.equal(data(await request(host,{type:'startRoom',roomId:room.id,membership:room.chatMembership,fingerprint})).room!.id,room.id);
 }finally{for(const socket of sockets)socket.terminate();await shutdown(server);}
});
