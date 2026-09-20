import {RoomChat} from './chat.ts';
import {CHAT_LIMITS} from '../../../packages/contracts/src/chat.ts';
import {PeerBroker,PeerError,type RelayConfig} from './peer.ts';
import type {ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
import {PUBLIC_CODE_ALPHABET,PUBLIC_CODE_LENGTH,publicCode} from '../../../packages/contracts/src/directory.ts';
import { randomBytes, randomInt } from 'node:crypto';
import type { Fingerprint, RoomCommand, RoomData, RoomEvent, RoomPreview, RoomView, Visibility } from '../../../packages/contracts/src/rooms.ts';
import { matchesFile } from '../../../packages/contracts/src/rooms.ts';

export const limits = { rooms:20, sessions:1000, connections:100, reservation:120_000, heartbeat:10_000, missedHeartbeat:30_000, reconnect:60_000, sessionIdle:24*60*60*1000 } as const;
type Session = { directory?:boolean; token:string; policy:ConnectionPolicy; nickname:string; touched:number; heartbeat:number; room?:string; send?:Sender; disconnect?:()=>void; cancelled:Map<string,number>; rates:Map<string,number[]> };
type Room = { chat:RoomChat; id:string; invite:string; code?:string; label:string; visibility:Visibility; host:Session; guest?:Session; reservationUntil?:number; guestIntent?:string; guestMembership?:string; guestFile?:Fingerprint; fingerprint:Fingerprint; intent:string; confirmed:boolean; created:number; reconnectUntil?:number; kicked:Set<string> };
export type Sender = (event:RoomEvent)=>void;
export class RoomError extends Error { code:string;retryAfterMs?:number;constructor(code:string,retryAfterMs?:number) { super(code);this.code = code;this.retryAfterMs = retryAfterMs; } }
const secret = () => randomBytes(32).toString('base64url');
const colors = ['Amber','Azure','Coral','Indigo','Jade','Lilac','Silver','Teal'];
const places = ['Arcade','Garden','Harbor','Lounge','Meadow','Orbit','Studio','Terrace'];
const pick = (items:string[]) => items[randomInt(items.length)];

/** Single-process mutations are synchronous: slot checks and claims cannot interleave. */
export class Rooms {
 private sessions = new Map<string,Session>();
 private rooms = new Map<string,Room>();
 private invites = new Map<string,string>();
 private codes = new Map<string,string>();
 private now:()=>number;
 private peers:PeerBroker;
 private codeCandidate:()=>string;
 constructor(now:()=>number = Date.now,codeCandidate:()=>string = ()=>Array.from({length:PUBLIC_CODE_LENGTH},()=>PUBLIC_CODE_ALPHABET[randomInt(PUBLIC_CODE_ALPHABET.length)]).join(''),relay?:RelayConfig) {this.now = now;this.codeCandidate=codeCandidate;this.peers=new PeerBroker(now,relay);}
 private session(token:string) { const session = this.sessions.get(token); if(!session) throw new RoomError('session_expired'); return session; }
 private rate(session:Session,kind:string,count:number,windowMs:number) {
  const now = this.now(), times = (session.rates.get(kind) ?? []).filter(time => time > now-windowMs);
  if(times.length >= count) throw new RoomError('rate_limited',times[0]+windowMs-now);
  times.push(now); session.rates.set(kind,times);
 }
 private code(roomId:string) {
  for(let attempt=0;attempt<100;attempt++) {const code=this.codeCandidate();if(publicCode(code)!==code) throw new RoomError('capacity');if(!this.codes.has(code)) {this.codes.set(code,roomId);return code;}}
  throw new RoomError('capacity');
 }
 private directory() {return [...this.rooms.values()].filter(room=>room.confirmed && room.visibility==='public').map(room=>this.preview(room));}
 private publishDirectory() {const rooms=this.directory();for(const session of this.sessions.values()) if(session.directory) session.send?.({type:'directory',rooms});}
 private publicRoom(code:string) {const id=this.codes.get(code),room=id && this.rooms.get(id);return room && room.confirmed && room.visibility==='public' ? room:undefined;}
 private reserve(session:Session,room:Room|undefined,intent:string,policy?:ConnectionPolicy):RoomData {
  this.rate(session,'join',5,60_000);
  if(!room || !room.confirmed || room.kicked.has(session.token)) throw new RoomError('room_unavailable');
  if(room.reconnectUntil) throw new RoomError('host_reconnecting');
  if(session.room) throw new RoomError('already_in_room');
  if(room.guest) throw new RoomError('place_taken');
  session.policy=policy??session.policy;room.guest=session;room.guestIntent=intent;room.guestMembership=secret();room.reservationUntil=this.now()+limits.reservation;session.room=room.id;
  this.publish(room);return {room:this.view(room,session)};
 }
 private preview(room:Room): RoomPreview { return {id:room.id,label:room.label,host:room.host.nickname,visibility:room.visibility,...(room.code ? {code:room.code}:{}),status:room.reconnectUntil ? 'reconnecting' : room.guest ? 'reserved':'waiting',occupancy:room.guest ? 2:1}; }
 private view(room:Room,session:Session): RoomView { return {...this.preview(room),chatMembership:room.host===session ? room.intent:room.guestMembership!,invite:room.invite,role:room.host === session ? 'host':'guest',slot:room.host === session ? 1:2,fingerprint:room.fingerprint,connectionPolicy:session.policy,peer:this.peers.view(room.id,session.policy),...(room.guest ? {guest:room.guest.nickname,guestMembership:room.guestMembership,reservationUntil:room.reservationUntil,reservationIntent:room.guestIntent,matches:!!room.guestFile && matchesFile(room.fingerprint,room.guestFile)}:{}),...(room.reconnectUntil ? {hostReconnectUntil:room.reconnectUntil}:{})}; }
 private publish(room:Room,directory=true) {this.peers.sync(room.confirmed && room.guest && !room.reconnectUntil ? {id:room.id,host:room.host,guest:room.guest,reservation:room.guestIntent!}:undefined,room.id); for(const session of [room.host,room.guest]) if(session) session.send?.({type:'room',room:this.view(room,session)});if(directory) this.publishDirectory(); }
 private releaseGuest(room:Room,reason:string) { const guest = room.guest; if(!guest) return; room.chat.leave(room.guestMembership!);guest.room = undefined; room.guest = undefined; room.guestFile = undefined; room.reservationUntil = undefined; room.guestIntent = undefined; room.guestMembership = undefined; guest.send?.({type:'ended',reason}); this.publish(room); }
 private close(room:Room,reason:string) {
  this.peers.clear(room.id);
  this.rooms.delete(room.id); this.invites.delete(room.invite); if(room.code) this.codes.delete(room.code);
  for(const session of [room.host,room.guest]) if(session) {session.room = undefined;session.send?.({type:'ended',reason});}
  this.publishDirectory();
 }
 private room(session:Session) { const room = session.room && this.rooms.get(session.room); if(!room) throw new RoomError('not_in_room'); return room; }
 private hosted(session:Session,expectedRoom?:string) { const room = this.room(session); if(room.host !== session) throw new RoomError('host_only'); if(expectedRoom!==undefined && room.id!==expectedRoom) throw new RoomError('room_changed'); return room; }
 attach(token:string|undefined,send:Sender,disconnect:()=>void,policy?:ConnectionPolicy): {token:string;data:RoomData} {
  this.sweep();
  let session:Session;
  if(token) session = this.session(token);
  else {
   if(this.sessions.size >= limits.sessions) throw new RoomError('capacity');
   const now = this.now(); session = {token:secret(),policy:'standard',nickname:`Guest ${pick(colors)} ${randomInt(10000)}`,touched:now,heartbeat:now,cancelled:new Map(),rates:new Map()};
   this.sessions.set(session.token,session);
  }
  if(policy) session.policy=policy;
  session.disconnect?.(); session.send = send; session.disconnect = disconnect; session.touched = session.heartbeat = this.now();
  let room = session.room && this.rooms.get(session.room);
  if(room && !room.confirmed) {this.close(room,'creation_cancelled');room = undefined;}
  if(room) {if(room.host===session) room.reconnectUntil=undefined;this.publish(room);}
  return {token:session.token,data:{session:{token:session.token,nickname:session.nickname,expiresInMs:limits.sessionIdle},...(room ? {room:this.view(room,session)}:{})}};
 }
 detach(token:string,send:Sender) { const session = this.sessions.get(token); if(session?.send === send) {session.send = undefined;session.disconnect = undefined;const room=session.room && this.rooms.get(session.room);if(room) this.publish(room);} }
 handle(token:string,command:Exclude<RoomCommand,{type:'hello'}>,sender?:Sender): RoomData {
  this.sweep(); const session = this.session(token); if(sender && session.send!==sender) throw new RoomError('session_replaced');this.rate(session,'messages',60,10_000); session.touched = this.now();
  if(command.type==='peerPolicy') {this.rate(session,'peerPolicy',10,60_000);session.policy=command.policy;const room=session.room && this.rooms.get(session.room);if(room) this.publish(room,false);return room?{room:this.view(room,session)}:{};}
  if(command.type.startsWith('peer')) {
   const room=this.room(session);
   if(command.type==='peerRetry') this.rate(session,'peerRetry',5,60_000);
   try {this.peers.handle(room.id,token,command as Exclude<import('../../../packages/contracts/src/peer.ts').PeerCommand,{type:'peerPolicy'}>);}catch(error) {if(error instanceof PeerError) throw new RoomError(error.message);throw error;}
   if(command.type==='peerSignal') return {};
   this.publish(room,false);return {room:this.view(room,session)};
  }
  switch(command.type) {
   case 'chat': {
    const room=this.room(session),membership=room.host===session ? room.intent:room.guestMembership;
    if(room.id!==command.roomId || !room.confirmed) throw new RoomError('not_in_room');
    if(membership!==command.membership) throw new RoomError('membership_changed');
    this.rate(session,'chat',CHAT_LIMITS.rateCount,CHAT_LIMITS.rateWindowMs);
    let result;try {result=room.chat.send(membership!,command.clientId,command.text,room.host===session ? 'host':'guest',session.nickname,this.now());}catch {throw new RoomError('chat_retry_changed');}
    if(result.message) for(const recipient of [room.host,room.guest]) recipient?.send?.({type:'chat',roomId:room.id,membership:recipient===room.host ? room.intent:room.guestMembership!,message:result.message});
    return {chatAck:result.ack};
   }
   case 'heartbeat': {session.heartbeat = this.now();const room = session.room && this.rooms.get(session.room);if(room && room.host === session && room.reconnectUntil) {room.reconnectUntil = undefined;this.publish(room);}return {};}
   case 'directory': {this.rate(session,'directory',20,60_000);session.directory=true;return {directory:this.directory()};}
   case 'lookupCode': {this.rate(session,'preview',20,60_000);const room=this.publicRoom(command.code);if(!room) throw new RoomError('room_unavailable');return {preview:this.preview(room)};}
   case 'joinCode': return this.reserve(session,this.publicRoom(command.code),command.intent,command.policy);
   case 'preview': { this.rate(session,'preview',20,60_000); const id = this.invites.get(command.invite), room = id && this.rooms.get(id); if(!room || !room.confirmed) throw new RoomError('room_unavailable'); return {preview:this.preview(room)}; }
   case 'create': {
    this.rate(session,'create',5,60_000);session.policy=command.policy??session.policy;
    if(session.cancelled.has(command.intent)) throw new RoomError('cancelled');
    if(session.room) {const room = this.room(session); if(room.host === session && room.intent === command.intent) return {room:this.view(room,session)}; throw new RoomError('already_in_room');}
    if(this.rooms.size >= limits.rooms) throw new RoomError('capacity');
    const id=secret(), code = command.visibility === 'public' ? this.code(id):undefined;
    const room:Room = {chat:new RoomChat(),id,invite:secret(),code,label:`${pick(colors)} ${pick(places)}`,visibility:command.visibility,host:session,fingerprint:command.fingerprint,intent:command.intent,confirmed:false,created:this.now(),kicked:new Set()};
    this.rooms.set(room.id,room);this.invites.set(room.invite,room.id);session.room = room.id;session.heartbeat = this.now();
    return {room:this.view(room,session)};
   }
   case 'confirmCreate': {const room = this.hosted(session);if(room.intent !== command.intent || session.cancelled.has(command.intent)) throw new RoomError('cancelled');room.confirmed = true;this.publishDirectory();return {room:this.view(room,session)};}
   case 'cancelCreate': {
    // A bounded tombstone also rejects a delayed create arriving after cancellation.
    if(session.cancelled.size >= 32) session.cancelled.delete(session.cancelled.keys().next().value!);
    session.cancelled.set(command.intent,this.now()+limits.reservation);
    const room = session.room && this.rooms.get(session.room);
    if(room && room.host === session && room.intent === command.intent) this.close(room,'creation_cancelled'); return {};
   }
   case 'join': {const id=this.invites.get(command.invite);return this.reserve(session,id ? this.rooms.get(id):undefined,command.intent,command.policy);}
   case 'leave': {
    // Cancellation belongs to one attempt, never whichever reservation this session has now.
    const room = session.room && this.rooms.get(session.room);
    if(room && room.guest === session && room.guestIntent === command.intent) this.releaseGuest(room,'left');
    return {};
   }
   case 'close': this.close(this.hosted(session,command.roomId),'host_closed');return {};
   case 'kick': { const room = this.hosted(session,command.roomId);if(!room.guest || room.guestMembership!==command.guestMembership) throw new RoomError('membership_changed');room.kicked.add(room.guest.token); this.releaseGuest(room,'removed');return {room:this.view(room,session)}; }
   case 'visibility': { const room = this.hosted(session,command.roomId);if(room.visibility !== command.visibility) {if(command.visibility === 'public') room.code = this.code(room.id);else if(room.code) {this.codes.delete(room.code);room.code = undefined;}room.visibility = command.visibility;this.publish(room);}return {room:this.view(room,session)}; }
   case 'rename': {const room = this.hosted(session,command.roomId);room.label = command.label.trim();this.publish(room);return {room:this.view(room,session)};}
   case 'nickname': {session.nickname = command.nickname.trim();const room = session.room && this.rooms.get(session.room);if(room) this.publish(room);return {session:{token:session.token,nickname:session.nickname,expiresInMs:limits.sessionIdle}};}
   case 'file': { const room = this.room(session);if(room.host === session) throw new RoomError('close_before_changing_game');room.guestFile = command.fingerprint;this.publish(room);return {room:this.view(room,session)}; }
  }
  return {};
 }
 sweep() {
  const now = this.now();
  // Rooms is the sole publisher of membership plus peer state, including timer transitions.
  for(const id of this.peers.sweep()) {const room=this.rooms.get(id);if(room) this.publish(room,false);}
  for(const room of this.rooms.values()) {
   if(!room.confirmed && now-room.created >= 5000) {this.close(room,'creation_expired');continue;}
   for(const token of room.kicked) if(!this.sessions.has(token)) room.kicked.delete(token);
   if(room.guest && room.reservationUntil! <= now) this.releaseGuest(room,'reservation_expired');
   if(!room.reconnectUntil && now-room.host.heartbeat >= limits.missedHeartbeat) {room.reconnectUntil = room.host.heartbeat+limits.missedHeartbeat+limits.reconnect;this.publish(room);}
   if(room.reconnectUntil && now >= room.reconnectUntil) this.close(room,'host_expired');
  }
  for(const session of this.sessions.values()) {
   for(const [intent,expiry] of session.cancelled) if(expiry <= now) session.cancelled.delete(intent);
   if(now-session.touched >= limits.sessionIdle) {session.disconnect?.();this.sessions.delete(session.token);}
  }
 }
 stop() {for(const room of this.rooms.values()) this.close(room,'service_restarted');for(const session of this.sessions.values()) session.disconnect?.();this.sessions.clear();}
 /** Restricted operator interface: never expose session tokens, invites, chat or fingerprints. */
 operatorRooms() {this.sweep();return [...this.rooms.values()].filter(room=>room.confirmed).map(room=>({id:room.id,label:room.label,visibility:room.visibility,occupancy:room.guest?2:1}));}
 removeRoom(id:string) {this.sweep();const room=this.rooms.get(id);if(!room?.confirmed)throw new RoomError('room_unavailable');this.close(room,'operator_removed');}
 revoke(token:string,sender:Sender) {
  const session=this.sessions.get(token);if(!session || session.send!==sender)return;
  const room=session.room && this.rooms.get(session.room);
  if(room) {if(room.host===session)this.close(room,'operator_removed');else this.releaseGuest(room,'admission_blocked');}
  session.send?.({type:'ended',reason:'admission_blocked'});
  this.sessions.delete(token);
 }
}
