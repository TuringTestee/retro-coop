import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {Rooms} from './rooms.ts';
import {parseRoomCommand,type Fingerprint,type RoomCommand,type RoomEvent} from '../../../packages/contracts/src/rooms.ts';
type Command = RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'> : never : never;
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}};
function setup(){
 const rooms=new Rooms(()=>1000);
 const session=()=>{const events:RoomEvent[]=[];return {...rooms.attach(undefined,event=>events.push(event),()=>{}),events};};
 const act=(token:string,command:Command)=>rooms.handle(token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const host=session(),first=session(),replacement=session();
 const create=()=>{const intent=randomUUID();const room=act(host.token,{type:'create',intent,visibility:'public',fingerprint}).room!;act(host.token,{type:'confirmCreate',intent});return room;};
 return {rooms,session,act,host,first,replacement,create};
}
test('confirmed removal cannot remove a replacement member; current removal revokes only its target',()=>{
 const t=setup(),room=t.create(),intent=randomUUID();
 const old=t.act(t.first.token,{type:'join',invite:room.invite,intent}).room!;
 const kick={type:'memberRemove' as const,roomId:room.id,membership:old.chatMembership,expectedRevision:old.revision};
 t.act(t.first.token,{type:'leave',intent});
 const current=t.act(t.replacement.token,{type:'join',invite:room.invite,intent:randomUUID()}).room!;
 assert.throws(()=>t.act(t.host.token,{...kick,expectedRevision:current.revision}),/membership_changed/);
 assert.equal(t.replacement.events.some(event=>event.type==='ended'),false);
 assert.throws(()=>t.act(t.replacement.token,{...kick,membership:current.chatMembership,expectedRevision:current.revision}),/host_only/);
 const result=t.act(t.host.token,{...kick,membership:current.chatMembership,expectedRevision:current.revision});
 assert.equal(result.room!.slots.find(slot=>slot.member?.id===current.chatMembership),undefined);
 assert.ok(t.replacement.events.some(event=>event.type==='ended'&&event.reason==='removed'));
 assert.throws(()=>t.act(t.replacement.token,{type:'join',invite:room.invite,intent:randomUUID()}),/room_unavailable/);
 // The former, voluntarily departing guest was never the target of the successful kick.
 assert.ok(t.act(t.first.token,{type:'join',invite:room.invite,intent:randomUUID()}).room);
});
test('reusing a client intent never restores a prior membership or delayed chat authority',()=>{
 const t=setup(),room=t.create(),intent=randomUUID();
 const old=t.act(t.first.token,{type:'join',invite:room.invite,intent}).room!;
 t.act(t.first.token,{type:'leave',intent});
 assert.throws(()=>t.act(t.first.token,{type:'join',invite:room.invite,intent}),/cancelled/);
 const current=t.act(t.first.token,{type:'join',invite:room.invite,intent:randomUUID()}).room!;
 assert.notEqual(current.chatMembership,old.chatMembership);
 assert.throws(()=>t.act(t.host.token,{type:'memberRemove',roomId:room.id,membership:old.chatMembership,expectedRevision:current.revision}),/membership_changed/);
 assert.throws(()=>t.act(t.first.token,{type:'chat',roomId:room.id,membership:old.chatMembership,clientId:randomUUID(),text:'late message'}),/membership_changed/);
 assert.ok(t.act(t.first.token,{type:'chat',roomId:room.id,membership:current.chatMembership,clientId:randomUUID(),text:'current message'}).chatAck);
});
test('host actions target the confirmed room, not a newer room belonging to the same host',()=>{
 const t=setup(),old=t.create();t.act(t.host.token,{type:'close',roomId:old.id});
 const current=t.create();
 for(const command of [{type:'close'},{type:'rename',label:'stale label'},{type:'visibility',visibility:'public',expectedAccessRevision:0},{type:'memberRemove',membership:randomUUID(),expectedRevision:0}] as const){
  assert.throws(()=>t.act(t.host.token,{...command,roomId:old.id}),/room_changed/);
 }
 assert.equal(t.act(t.first.token,{type:'preview',invite:current.invite}).preview!.label,current.label);
 assert.equal(t.act(t.first.token,{type:'preview',invite:current.invite}).preview!.visibility,'public');
});
test('host mutation wire schema requires exact targets and rejects public authority extensions',()=>{
 const requestId=randomUUID(),roomId=randomUUID(),membership=randomUUID();
 for(const command of [{type:'close'},{type:'memberRemove',membership,expectedRevision:0},{type:'rename',label:'Current name'},{type:'visibility',visibility:'protected',expectedAccessRevision:0,password:'password 123'}]) {
  assert.equal(parseRoomCommand({...command,requestId}),undefined);
  assert.ok(parseRoomCommand({...command,requestId,roomId}));
 }
 assert.equal(parseRoomCommand({type:'memberRemove',requestId,roomId}),undefined);
 assert.equal(parseRoomCommand({type:'memberRemove',requestId,roomId,membership,expectedRevision:0,operator:true}),undefined);
 assert.equal(parseRoomCommand({type:'close',requestId,roomId,membership}),undefined);
});
