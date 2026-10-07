import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {once} from 'node:events';
import {WebSocket} from 'ws';
import {Rooms,RoomError} from './rooms.ts';
import {createCoordinator,shutdown} from './server.ts';
import {parseRoomCommand,type RoomData,type RoomEvent,type Fingerprint} from '../../../packages/contracts/src/rooms.ts';

const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:1,submapper:0,region:'NTSC',bytes:32784}};
const password='correct horse battery';
function setup(){
 let now=1000;const rooms=new Rooms(()=>now);
 const guest=()=>{const events:RoomEvent[]=[];const send=(event:RoomEvent)=>events.push(event);const token=rooms.attach(undefined,send,()=>{}).token;return {token,events,send};};
 const command=(input:Record<string,unknown>)=>{const value=parseRoomCommand({...input,requestId:randomUUID()});assert.ok(value&&value.type!=='hello');return value;};
 const act=(token:string,input:Record<string,unknown>):RoomData=>rooms.handle(token,command(input));
 const authorize=(token:string,input:Record<string,unknown>,address='203.0.113.10')=>rooms.authorize(token,command(input),address);
 return {rooms,guest,act,authorize,advance(ms:number){now+=ms;rooms.sweep();}};
}

test('protected directory, code and invite use one password gate before allocating a place',async()=>{
 const t=setup(),host=t.guest(),member=t.guest(),watcher=t.guest(),intent=randomUUID();
 const created=(await t.authorize(host.token,{type:'create',intent,visibility:'protected',password,fingerprint})).room!;
 assert.equal(created.visibility,'protected');assert.equal(created.accessRevision,0);assert.ok(created.code);t.act(host.token,{type:'confirmCreate',intent});
 const row=t.act(watcher.token,{type:'directory'}).directory!.find(item=>item.id===created.id)!;
 const preview=t.act(watcher.token,{type:'preview',invite:created.invite}).preview!;
 for(const value of [row,preview,created])assert.equal(JSON.stringify(value).includes(password),false);
 assert.equal(row.visibility,'protected');assert.equal(preview.visibility,'protected');
 const first=randomUUID();
 await assert.rejects(t.authorize(member.token,{type:'join',intent:first,invite:created.invite}),/password_required/);
 await assert.rejects(t.authorize(member.token,{type:'joinCode',intent:first,code:created.code,password:'wrong passphrase'}),/bad_password/);
 assert.equal(t.act(watcher.token,{type:'directory'}).directory!.find(item=>item.id===created.id)!.occupancy,1);
 const joined=(await t.authorize(member.token,{type:'join',intent:first,invite:created.invite,password})).room!;
 assert.equal(joined.occupancy,2);assert.equal(joined.slot,'slot-2');assert.equal(JSON.stringify(member.events).includes(password),false);
 assert.equal(t.rooms.attach(member.token,member.send,()=>{}).data.room?.id,created.id,'reconnect uses admitted membership without password');
});

test('access revision changes atomically; old password and stale host change cannot admit or mutate',async()=>{
 const t=setup(),host=t.guest(),member=t.guest(),intent=randomUUID();
 const room=(await t.authorize(host.token,{type:'create',intent,visibility:'protected',password,fingerprint})).room!;t.act(host.token,{type:'confirmCreate',intent});
 const changed=(await t.authorize(host.token,{type:'visibility',roomId:room.id,visibility:'protected',expectedAccessRevision:0,password:'new password 123'})).room!;
 assert.equal(changed.accessRevision,1);assert.equal(changed.code,room.code);
 await assert.rejects(t.authorize(member.token,{type:'joinCode',code:room.code,intent:randomUUID(),password}),/bad_password/);
 await assert.rejects(t.authorize(host.token,{type:'visibility',roomId:room.id,visibility:'public',expectedAccessRevision:0}),/room_changed/);
 const joined=(await t.authorize(member.token,{type:'joinCode',code:room.code,intent:randomUUID(),password:'new password 123'})).room!;
 assert.equal(joined.occupancy,2);
 const opened=(await t.authorize(host.token,{type:'visibility',roomId:room.id,visibility:'public',expectedAccessRevision:1})).room!;
 assert.equal(opened.visibility,'public');assert.equal(opened.accessRevision,2);assert.equal(opened.occupancy,2);
 const visitor=t.guest();assert.equal((await t.authorize(visitor.token,{type:'joinCode',code:room.code,intent:randomUUID()})).room?.occupancy,3);
});

test('short passwords and failed guesses across fresh sessions do not publish or reserve',async()=>{
 const t=setup(),host=t.guest(),intent=randomUUID();
 await assert.rejects(t.authorize(host.token,{type:'create',intent,visibility:'protected',password:'short',fingerprint}),/invalid_password/);
 assert.equal(t.act(host.token,{type:'directory'}).directory?.some(item=>item.host==='No host'),false);
 const room=(await t.authorize(host.token,{type:'create',intent,visibility:'protected',password,fingerprint})).room!;t.act(host.token,{type:'confirmCreate',intent});
 for(let i=0;i<5;i++){const guest=t.guest();await assert.rejects(t.authorize(guest.token,{type:'joinCode',code:room.code,intent:randomUUID(),password:'incorrect pass'},'198.51.100.8'),/bad_password/);}
 const blocked=t.guest();await assert.rejects(t.authorize(blocked.token,{type:'joinCode',code:room.code,intent:randomUUID(),password},'198.51.100.8'),error=>error instanceof RoomError&&error.code==='rate_limited'&&!!error.retryAfterMs);
 assert.equal(t.act(host.token,{type:'directory'}).directory!.find(item=>item.id===room.id)?.occupancy,1);
 const unaffected=t.guest();assert.equal((await t.authorize(unaffected.token,{type:'joinCode',code:room.code,intent:randomUUID(),password},'198.51.100.9')).room?.occupancy,2);
});

test('successful admissions and host password changes do not consume the failed-guess quota',async()=>{
 const t=setup(),host=t.guest(),intent=randomUUID(),address='198.51.100.33';
 const room=(await t.authorize(host.token,{type:'create',intent,visibility:'protected',password,fingerprint},address)).room!;t.act(host.token,{type:'confirmCreate',intent});
 let revision=0;for(let i=0;i<2;i++){const changed=(await t.authorize(host.token,{type:'visibility',roomId:room.id,visibility:'protected',expectedAccessRevision:revision,password},address)).room!;revision=changed.accessRevision;}
 const admitted=[];for(let i=0;i<4;i++){const guest=t.guest();const joined=(await t.authorize(guest.token,{type:'joinCode',code:room.code,intent:randomUUID(),password},address)).room!;admitted.push({guest,joined});}
 t.act(admitted[0].guest.token,{type:'leave',intent:admitted[0].joined.reservationIntent});
 const wrong=t.guest();await assert.rejects(t.authorize(wrong.token,{type:'joinCode',code:room.code,intent:randomUUID(),password:'incorrect pass'},address),/bad_password/);
 const newcomer=t.guest();const joined=(await t.authorize(newcomer.token,{type:'joinCode',code:room.code,intent:randomUUID(),password},address)).room!;
 assert.equal(joined.occupancy,5);
});

test('a password verified against the old access revision cannot reserve after a password change',async()=>{
 const t=setup(),host=t.guest(),member=t.guest(),intent=randomUUID();
 const room=(await t.authorize(host.token,{type:'create',intent,visibility:'protected',password,fingerprint})).room!;t.act(host.token,{type:'confirmCreate',intent});
 const work=t.rooms as unknown as {passwordWork:{verify:(candidate:string,verifier:unknown)=>Promise<boolean>}};
 const verify=work.passwordWork.verify.bind(work.passwordWork);
 let entered!:()=>void,release!:()=>void;
 const started=new Promise<void>(resolve=>entered=resolve),held=new Promise<void>(resolve=>release=resolve);
 work.passwordWork.verify=async(candidate,verifier)=>{entered();await held;return verify(candidate,verifier);};
 const pending=t.authorize(member.token,{type:'join',invite:room.invite,intent:randomUUID(),password});await started;
 const changed=(await t.authorize(host.token,{type:'visibility',roomId:room.id,visibility:'protected',expectedAccessRevision:0,password:'new password 123'})).room!;
 assert.equal(changed.accessRevision,1);release();await assert.rejects(pending,/room_changed/);
 assert.equal(t.act(host.token,{type:'directory'}).directory!.find(row=>row.id===room.id)?.occupancy,1);
});

test('WebSocket admission rejects wrong password before room, ROM or peer authority is issued',async()=>{
 const origin='http://127.0.0.1:5173',server=createCoordinator({origins:[origin]});server.listen(0,'127.0.0.1');await once(server,'listening');
 const url=`ws://127.0.0.1:${(server.address() as {port:number}).port}/ws`,sockets:WebSocket[]=[];
 const connect=async()=>{const socket=new WebSocket(url,{origin});sockets.push(socket);await once(socket,'open');return socket;};
 const request=async(socket:WebSocket,input:Record<string,unknown>)=>{const requestId=randomUUID();const result=new Promise<Extract<RoomEvent,{type:'result'}>>(resolve=>{const onMessage=(raw:Buffer)=>{const event=JSON.parse(raw.toString()) as RoomEvent;if(event.type==='result'&&event.requestId===requestId){socket.off('message',onMessage);resolve(event);}};socket.on('message',onMessage);});socket.send(JSON.stringify({...input,requestId}));return result;};
 try{
  const host=await connect(),guest=await connect();for(const socket of [host,guest])assert.equal((await request(socket,{type:'hello',gameplayProtocol:2})).ok,true);
  const intent=randomUUID(),created=await request(host,{type:'create',intent,visibility:'protected',password,fingerprint});assert.equal(created.ok,true);if(!created.ok)return;
  const room=created.data.room!;assert.equal((await request(host,{type:'confirmCreate',intent})).ok,true);
  const received:RoomEvent[]=[];guest.on('message',raw=>received.push(JSON.parse(raw.toString())));
  const denied=await request(guest,{type:'joinCode',code:room.code,intent:randomUUID(),password:'wrong password 123'});assert.equal(denied.ok,false);if(!denied.ok)assert.equal(denied.error,'bad_password');
  assert.equal(received.some(event=>['room','peerPrepare','chat'].includes(event.type)),false);
  const allowed=await request(guest,{type:'joinCode',code:room.code,intent:randomUUID(),password});assert.equal(allowed.ok,true);if(allowed.ok)assert.equal(allowed.data.room?.occupancy,2);
 }finally{for(const socket of sockets)socket.terminate();await shutdown(server);}
});
