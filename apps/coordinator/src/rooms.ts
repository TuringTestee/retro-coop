import {catalogEntry,catalogId,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {SLOT_IDS,controllerRoles,controllerOwners,type RoomSlot,type SlotId,type SlotRole,type AcquisitionPhase} from '../../../packages/contracts/src/slots.ts';
import type {ControllerAssignment,RoleTransaction,GameCommand} from '../../../packages/contracts/src/gameplay.ts';
import {GameSession} from './gameplay.ts';
import {RoomChat} from './chat.ts';
import {CHAT_LIMITS} from '../../../packages/contracts/src/chat.ts';
import {PeerBroker,PeerError,type RelayConfig} from './peer.ts';
import type {ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
import {PUBLIC_CODE_ALPHABET,PUBLIC_CODE_LENGTH,publicCode} from '../../../packages/contracts/src/directory.ts';
import { randomBytes, randomInt } from 'node:crypto';
import type { EmptyRoomPreview,Fingerprint,HumanRoomPreview, RoomCommand, RoomData, RoomEvent, RoomView, Visibility } from '../../../packages/contracts/src/rooms.ts';
import { matchesFile } from '../../../packages/contracts/src/rooms.ts';

export const limits = { rooms:20, sessions:1000, connections:100, reservation:120_000, heartbeat:10_000, missedHeartbeat:30_000, reconnect:60_000, sessionIdle:24*60*60*1000 } as const;
type Session = { directory?:boolean; includeEmptyOffers?:boolean; previewInvite?:string; token:string; policy:ConnectionPolicy; nickname:string; touched:number; heartbeat:number; room?:string; send?:Sender; disconnect?:()=>void; cancelled:Map<string,number>; rates:Map<string,number[]> };
type Membership={id:string;session:Session;intent:string;file?:Fingerprint;acquisition:AcquisitionPhase;reservationStarted:number;reservationUntil?:number;reconnectUntil?:number;download?:{id:string;lastProgress:number}};
type Slot={id:SlotId;role:SlotRole;open:boolean;revision:number;member?:Membership};
type Room={game:GameSession;controllers:ControllerAssignment;revision:number;slots:Slot[];catalogId?:CatalogId;hostReady?:boolean;started?:'shared';established?:boolean;chat:RoomChat;id:string;invite:string;code?:string;label:string;visibility:Visibility;host:Session;fingerprint:Fingerprint;intent:string;confirmed:boolean;created:number;uploadAttempted?:boolean;upload?:{id:string;lastProgress:number};content?:string;reconnectUntil?:number;kicked:Set<string>};
type EmptyOffer = {id:string;code:string;catalogId:CatalogId};
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
 private offers = new Map<string,EmptyOffer>();
 private invites = new Map<string,string>();
 private codes = new Map<string,string>();
 private now:()=>number;
 private peers:PeerBroker;
 private codeCandidate:()=>string;
 private transfer?:{requireCustomUpload:boolean;discard:(roomId:string)=>void};
 constructor(now:()=>number = Date.now,codeCandidate:()=>string = ()=>Array.from({length:PUBLIC_CODE_LENGTH},()=>PUBLIC_CODE_ALPHABET[randomInt(PUBLIC_CODE_ALPHABET.length)]).join(''),relay?:RelayConfig,offerCatalogIds:readonly CatalogId[] = [],transfer?:{requireCustomUpload:boolean;discard:(roomId:string)=>void}) {this.now = now;this.codeCandidate=codeCandidate;this.peers=new PeerBroker(now,relay);this.transfer=transfer;for(const id of new Set(offerCatalogIds))this.makeOffer(id);}
 private session(token:string) { const session = this.sessions.get(token); if(!session) throw new RoomError('session_expired'); return session; }
 private rate(session:Session,kind:string,count:number,windowMs:number) {
  const now = this.now(), times = (session.rates.get(kind) ?? []).filter(time => time > now-windowMs);
  if(times.length >= count) throw new RoomError('rate_limited',times[0]+windowMs-now);
  times.push(now); session.rates.set(kind,times);
 }
 private cancelIntent(session:Session,intent:string) {if(session.cancelled.size>=32)session.cancelled.delete(session.cancelled.keys().next().value!);session.cancelled.set(intent,this.now()+limits.reservation);}
 private code(roomId:string) {
  for(let attempt=0;attempt<100;attempt++) {const code=this.codeCandidate();if(publicCode(code)!==code) throw new RoomError('capacity');if(!this.codes.has(code)) {this.codes.set(code,roomId);return code;}}
  throw new RoomError('capacity');
 }
 private makeOffer(catalogId:CatalogId):EmptyOffer {const id=secret(),offer={id,code:this.code(id),catalogId};this.offers.set(id,offer);return offer;}
 private offerPreview(offer:EmptyOffer):EmptyRoomPreview {return {id:offer.id,code:offer.code,catalogId:offer.catalogId,label:catalogEntry(offer.catalogId).title,host:'No host',visibility:'public',status:this.rooms.size>=limits.rooms?'unavailable':'waiting',occupancy:0,...(this.rooms.size>=limits.rooms?{unavailableReason:'room_capacity' as const}:{})};}
 private directory(session:Session) {return [...(session.includeEmptyOffers?[...this.offers.values()].map(offer=>this.offerPreview(offer)):[]),...[...this.rooms.values()].filter(room=>room.confirmed && room.visibility==='public').map(room=>this.preview(room))];}
 private publishDirectory() {for(const session of this.sessions.values()) if(session.directory) session.send?.({type:'directory',rooms:this.directory(session)});}
 private publicRoom(code:string) {const id=this.codes.get(code),room=id && this.rooms.get(id);return room && room.confirmed && room.visibility==='public' ? room:undefined;}
 private publicOffer(session:Session,code:string) {const id=session.includeEmptyOffers&&this.codes.get(code);return id?this.offers.get(id):undefined;}
 private claim(session:Session,offer:EmptyOffer|undefined,intent:string,fingerprint:Fingerprint,policy?:ConnectionPolicy,visibility:Visibility='public'):RoomData {
  this.rate(session,'join',5,60_000);
  if(session.cancelled.has(intent))throw new RoomError('cancelled');
  if(session.room) {const current=this.room(session);if(current.host===session&&current.intent===intent)return {room:this.view(current,session)};throw new RoomError('already_in_room');}
  if(!offer || catalogId(fingerprint)!==offer.catalogId) throw new RoomError('room_unavailable');
  if(this.rooms.size>=limits.rooms) throw new RoomError('capacity');
  // Reserve the replacement code before changing the claimed offer, so allocation failure is transactional.
  const replacementId=secret(),replacementCode=this.code(replacementId);
  session.policy=policy??session.policy;
  const room=this.makeRoom({catalogId:offer.catalogId,chat:new RoomChat(),id:offer.id,invite:secret(),...(visibility==='public'?{code:offer.code}:{}),label:catalogEntry(offer.catalogId).title,visibility,host:session,fingerprint,intent,confirmed:true,created:this.now(),kicked:new Set()});
  this.offers.delete(offer.id);this.offers.set(replacementId,{id:replacementId,code:replacementCode,catalogId:offer.catalogId});
  if(visibility==='unlisted')this.codes.delete(offer.code);
  this.rooms.set(room.id,room);this.invites.set(room.invite,room.id);session.room=room.id;session.heartbeat=this.now();this.publish(room);return {room:this.view(room,session)};
 }
 private members(room:Room){return room.slots.flatMap(slot=>slot.member?[slot.member]:[]);}
 private member(room:Room,session:Session){const member=this.members(room).find(member=>member.session===session);if(!member)throw new RoomError('membership_changed');return member;}
 private slotViews(room:Room):RoomSlot[]{return room.slots.map(slot=>({...slot,member:slot.member?{id:slot.member.id,nickname:slot.member.session.nickname,connected:!!slot.member.session.send&&!slot.member.reconnectUntil,matches:!!slot.member.file&&matchesFile(room.fingerprint,slot.member.file),acquisition:slot.member.acquisition,reconnectUntil:slot.member.reconnectUntil}:undefined}));}
 private assigned(room:Room){return {owners:controllerOwners(this.slotViews(room)),revision:room.controllers.revision+1};}
 private applyRoles(room:Room,pending:RoleTransaction){
  if(room.revision!==pending.revision)throw new RoomError('room_changed');
  for(const proposed of pending.roles){const slot=room.slots.find(slot=>slot.id===proposed.slotId)!;slot.role=proposed.role;slot.revision++;}
  room.revision++;room.controllers=this.assigned(room);return room.controllers;
 }
 private makeRoom(data:Omit<Room,'game'|'slots'|'revision'|'controllers'>):Room{
  const roles=controllerRoles(data.catalogId),slots:Slot[]=SLOT_IDS.map((id,index)=>({id,role:roles[index]??'observer',open:true,revision:0}));
  slots[0].member={id:data.intent,intent:data.intent,session:data.host,file:data.fingerprint,acquisition:'loading',reservationStarted:this.now()};
  const room:Room={...data,slots,revision:0,controllers:{owners:[data.intent,null],revision:0},game:undefined!};
  room.game=new GameSession(this.now,(member,event)=>this.members(room).find(value=>value.id===member)?.session.send?.(event),pending=>this.applyRoles(room,pending));return room;
 }
 private reserve(session:Session,room:Room|undefined,intent:string,policy?:ConnectionPolicy):RoomData {
  this.rate(session,'join',5,60_000);if(session.cancelled.has(intent))throw new RoomError('cancelled');
  if(!room||!room.confirmed||room.kicked.has(session.token))throw new RoomError('room_unavailable');
  if(room.reconnectUntil)throw new RoomError('host_reconnecting');
  if(session.room){if(session.room===room.id&&this.member(room,session).intent===intent)return {room:this.view(room,session)};throw new RoomError('already_in_room');}
  const slot=room.slots.find(slot=>slot.open&&!slot.member);if(!slot)throw new RoomError('room_full');
  session.policy=policy??session.policy;slot.member={id:secret(),session,intent,acquisition:'checking',reservationStarted:this.now(),reservationUntil:this.now()+limits.reservation};slot.revision++;room.revision++;session.room=room.id;session.heartbeat=this.now();
  if(!room.started)room.controllers=this.assigned(room);
  this.publish(room);return {room:this.view(room,session)};
 }
 private preview(room:Room):HumanRoomPreview{return {...(room.catalogId?{catalogId:room.catalogId}:{romBytes:room.fingerprint.cartridge.bytes}),id:room.id,label:room.label,host:room.host.nickname,visibility:room.visibility,...(room.code?{code:room.code}:{}),status:room.reconnectUntil||this.members(room).some(member=>member.reconnectUntil)?'reconnecting':room.started?room.game.view().status==='playing'?'playing':'paused':this.members(room).length>1?'reserved':'waiting',occupancy:this.members(room).length,openSlots:room.slots.filter(slot=>slot.open&&!slot.member).length};}
 private view(room:Room,session:Session):RoomView{const member=this.member(room,session),slot=room.slots.find(slot=>slot.member===member)!;return {...this.preview(room),game:room.game.view(),hostReady:!!room.hostReady,started:room.started,established:!!room.established,chatMembership:member.id,hostMembership:room.intent,invite:room.invite,role:room.host===session?'host':'member',slot:slot.id,slots:this.slotViews(room),revision:room.revision,controllerRoles:controllerRoles(room.catalogId),fingerprint:room.fingerprint,connectionPolicy:session.policy,peers:this.peers.views(room.id,member.id),reservationUntil:member.reservationUntil,reservationIntent:member.intent,matches:!!member.file&&matchesFile(room.fingerprint,member.file),hostReconnectUntil:room.reconnectUntil};}
 private publish(room:Room,directory=true){
  const members=this.members(room);
  this.peers.syncRoom(room.id,room.confirmed?members.map(member=>({id:member.id,token:member.session.token,policy:member.session.policy,send:member.reconnectUntil?undefined:member.session.send})):[],room.intent);
  room.game.configure(room.intent,members.map(member=>({id:member.id,connected:!!member.session.send&&!member.reconnectUntil,loaded:!!member.file&&matchesFile(room.fingerprint,member.file)&&member.acquisition==='loaded',transport:this.peers.views(room.id,member.id).some(peer=>peer.member===room.intent&&peer.status==='connected')})),room.controllers);
  for(const member of members)member.session.send?.({type:'room',room:this.view(room,member.session)});
  for(const session of this.sessions.values())if(session.previewInvite===room.invite)session.send?.({type:'preview',preview:this.preview(room)});if(directory)this.publishDirectory();
 }
 private releaseMember(room:Room,member:Membership,reason:string){
  const slot=room.slots.find(slot=>slot.member===member);if(!slot)return;room.chat.leave(member.id);member.session.room=undefined;slot.member=undefined;slot.revision++;room.revision++;if(!room.started)room.controllers=this.assigned(room);
  member.session.send?.({type:'ended',reason});this.publish(room);
 }
 private close(room:Room,reason:string){this.transfer?.discard(room.id);room.game.stop('The room closed. Your local game is preserved.');this.peers.clearRoom(room.id);this.rooms.delete(room.id);this.invites.delete(room.invite);if(room.code)this.codes.delete(room.code);for(const member of this.members(room)){member.session.room=undefined;member.session.send?.({type:'ended',reason});}this.publishDirectory();}
 private room(session:Session) { const room = session.room && this.rooms.get(session.room); if(!room) throw new RoomError('not_in_room'); return room; }
 private hosted(session:Session,expectedRoom?:string) { const room = this.room(session); if(room.host !== session) throw new RoomError('host_only'); if(expectedRoom!==undefined && room.id!==expectedRoom) throw new RoomError('room_changed'); return room; }
 beginUpload(token:string,roomId:string,intent:string,bytes:number) {
  this.sweep();const session=this.session(token),room=this.hosted(session,roomId),now=this.now();
  if(room.confirmed || room.intent!==intent || room.content || room.upload || now-room.created>=300_000)throw new RoomError('upload_unavailable');
  if(room.host.send===undefined)throw new RoomError('host_disconnected');
  if(bytes!==room.fingerprint.cartridge.bytes)throw new RoomError('length_mismatch');
  this.rate(session,'upload',5,60_000);
  const id=secret();room.upload={id,lastProgress:now};room.uploadAttempted=true;return {id,fingerprint:room.fingerprint};
 }
 uploadProgress(roomId:string,id:string) {const room=this.rooms.get(roomId),now=this.now();if(!room?.upload || room.upload.id!==id || room.confirmed || now-room.created>=300_000 || now-room.upload.lastProgress>=30_000)throw new RoomError('upload_expired');room.upload.lastProgress=now;room.host.heartbeat=now;room.host.touched=now;}
 commitUpload(roomId:string,id:string,content:string) {this.uploadProgress(roomId,id);const room=this.rooms.get(roomId)!;room.content=content;room.upload=undefined;}
 failUpload(roomId:string,id:string) {const room=this.rooms.get(roomId);if(room?.upload?.id===id)room.upload=undefined;}
 beginDownload(token:string,roomId:string,membership:string){
  this.sweep();const session=this.session(token),room=this.rooms.get(roomId),now=this.now();if(!room||!room.confirmed||session.room!==roomId||!room.content)throw new RoomError('room_changed');const member=this.member(room,session);
  if(member.id!==membership||session===room.host||member.reservationUntil!==undefined&&member.reservationUntil<=now)throw new RoomError('room_changed');
  if(member.download&&now-member.download.lastProgress<30_000)throw new RoomError('download_busy');this.rate(session,'download',5,60_000);const id=secret();member.download={id,lastProgress:now};return {id,path:room.content,bytes:room.fingerprint.cartridge.bytes,sha256:room.fingerprint.romSha256};
 }
 downloadProgress(roomId:string,id:string){const room=this.rooms.get(roomId),now=this.now(),member=room&&this.members(room).find(member=>member.download?.id===id);if(!member||now-member.download!.lastProgress>=30_000||member.reservationUntil!==undefined&&(member.reservationUntil<=now||now-member.reservationStarted>=300_000))throw new RoomError('download_expired');member.download!.lastProgress=now;if(member.reservationUntil!==undefined)member.reservationUntil=Math.min(member.reservationStarted+300_000,now+limits.reservation);}
 endDownload(roomId:string,id:string){const room=this.rooms.get(roomId),member=room&&this.members(room).find(member=>member.download?.id===id);if(member)member.download=undefined;}
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
  session.disconnect?.(); session.send = send; session.disconnect = disconnect; session.includeEmptyOffers=false;session.touched = session.heartbeat = this.now();
  let room = session.room && this.rooms.get(session.room);
  if(room && !room.confirmed) {this.close(room,'creation_cancelled');room = undefined;}
  if(room){if(room.host===session)room.reconnectUntil=undefined;this.member(room,session).reconnectUntil=undefined;this.publish(room);}
  return {token:session.token,data:{session:{token:session.token,nickname:session.nickname,expiresInMs:limits.sessionIdle},...(room ? {room:this.view(room,session)}:{})}};
 }
 detach(token:string,send:Sender) { const session = this.sessions.get(token); if(session?.send === send) {session.send = undefined;session.disconnect = undefined;const room=session.room && this.rooms.get(session.room);if(room && !room.confirmed && room.host===session)this.close(room,'creation_cancelled');else if(room)this.publish(room);} }
 handle(token:string,command:Exclude<RoomCommand,{type:'hello'}>,sender?:Sender): RoomData {
  this.sweep(); const session = this.session(token); if(sender && session.send!==sender) throw new RoomError('session_replaced');this.rate(session,'messages',60,10_000); session.touched = this.now();
  if(command.type==='peerPolicy') {this.rate(session,'peerPolicy',10,60_000);session.policy=command.policy;const room=session.room && this.rooms.get(session.room);if(room) this.publish(room,false);return room?{room:this.view(room,session)}:{};}
  if(command.type.startsWith('peer')) {
   const room=this.room(session);
   if(command.type==='peerRetry') this.rate(session,'peerRetry',5,60_000);
   try {this.peers.handle(room.id,token,command as Exclude<import('../../../packages/contracts/src/peer.ts').PeerCommand,{type:'peerPolicy'}>);}catch(error) {if(error instanceof PeerError) throw new RoomError(error.message);throw error;}
   if(command.type==='peerSignal'||command.type==='peerRoute') return {};
   this.publish(room,false);return {room:this.view(room,session)};
  }
  if(command.type.startsWith('game')){
   const room=this.room(session),member=this.member(room,session);this.rate(session,'game',40,10_000);
   try{room.game.handle(member.id,command as GameCommand);}catch(error){throw new RoomError(error instanceof Error?error.message:'game_failed');}
   if(room.game.view().status==='playing'){room.established=true;for(const member of this.members(room))if(member.acquisition==='loaded')member.reservationUntil=undefined;}
   this.publish(room);return {room:this.view(room,session)};
  }
  switch(command.type) {
   case 'chat':{const room=this.room(session),member=this.member(room,session);if(room.id!==command.roomId||!room.confirmed||member.id!==command.membership)throw new RoomError('membership_changed');this.rate(session,'chat',CHAT_LIMITS.rateCount,CHAT_LIMITS.rateWindowMs);let result;try{result=room.chat.send(member.id,command.clientId,command.text,session===room.host?'host':'member',session.nickname,this.now());}catch{throw new RoomError('chat_retry_changed');}if(result.message)for(const recipient of this.members(room))recipient.session.send?.({type:'chat',roomId:room.id,membership:recipient.id,message:result.message});return {chatAck:result.ack};}
   case 'heartbeat': {session.heartbeat = this.now();const room = session.room && this.rooms.get(session.room);if(room && room.host === session && room.reconnectUntil) {room.reconnectUntil = undefined;this.publish(room);}return {};}
   case 'directory': {this.rate(session,'directory',20,60_000);session.directory=true;session.includeEmptyOffers=command.includeEmptyOffers===true;return {directory:this.directory(session)};}
   case 'lookupCode': {this.rate(session,'preview',20,60_000);const room=this.publicRoom(command.code),offer=this.publicOffer(session,command.code);if(!room&&!offer) throw new RoomError('room_unavailable');return {preview:room?this.preview(room):this.offerPreview(offer!)};}
   case 'joinCode': return this.reserve(session,this.publicRoom(command.code),command.intent,command.policy);
   case 'claimCode': return this.claim(session,this.publicOffer(session,command.code),command.intent,command.fingerprint,command.policy,command.visibility);
   case 'preview': { this.rate(session,'preview',20,60_000); const id = this.invites.get(command.invite), room = id && this.rooms.get(id); if(!room || !room.confirmed) throw new RoomError('room_unavailable'); session.previewInvite=command.invite;return {preview:this.preview(room)}; }
   case 'create': {
    this.rate(session,'create',5,60_000);session.policy=command.policy??session.policy;
    if(session.cancelled.has(command.intent)) throw new RoomError('cancelled');
    if(session.room) {const room = this.room(session); if(room.host === session && room.intent === command.intent) return {room:this.view(room,session)}; throw new RoomError('already_in_room');}
    if(this.rooms.size >= limits.rooms) throw new RoomError('capacity');
    const id=secret(), code = command.visibility === 'public' ? this.code(id):undefined;
    const room=this.makeRoom({catalogId:catalogId(command.fingerprint),chat:new RoomChat(),id,invite:secret(),code,label:`${pick(colors)} ${pick(places)}`,visibility:command.visibility,host:session,fingerprint:command.fingerprint,intent:command.intent,confirmed:false,created:this.now(),kicked:new Set()});
    this.rooms.set(room.id,room);this.invites.set(room.invite,room.id);session.room = room.id;session.heartbeat = this.now();this.publishDirectory();
    return {room:this.view(room,session)};
   }
   case 'confirmCreate': {const room = this.hosted(session);if(room.intent !== command.intent || session.cancelled.has(command.intent)) throw new RoomError('cancelled');if((this.transfer?.requireCustomUpload || room.uploadAttempted) && !room.content)throw new RoomError('upload_required');room.confirmed = true;this.publishDirectory();return {room:this.view(room,session)};}
   case 'cancelCreate': {
    // A bounded tombstone also rejects a delayed create arriving after cancellation.
    this.cancelIntent(session,command.intent);
    const room = session.room && this.rooms.get(session.room);
    if(room && room.host === session && room.intent === command.intent) this.close(room,'creation_cancelled'); return {};
   }
   case 'join': {const id=this.invites.get(command.invite);return this.reserve(session,id ? this.rooms.get(id):undefined,command.intent,command.policy);}
   case 'leave': {
    // Cancellation belongs to one attempt, never whichever reservation this session has now.
    this.cancelIntent(session,command.intent);
    const room = session.room && this.rooms.get(session.room);
    if(room){const member=this.member(room,session);if(member.intent===command.intent){if(room.host===session)this.close(room,'left');else this.releaseMember(room,member,'left');}}
    return {};
   }
   case 'prepareHost':case 'startRoom':{const room=this.hosted(session,command.roomId);if(!room.confirmed||room.intent!==command.membership)throw new RoomError('membership_changed');if(!matchesFile(room.fingerprint,command.fingerprint))throw new RoomError('game_mismatch');room.hostReady=true;this.member(room,session).acquisition='loaded';this.publish(room,false);if(command.type==='startRoom'&&!room.started){try{room.game.requestStart();room.started='shared';}catch(error){throw new RoomError(error instanceof Error?error.message:'game_prerequisites');}}this.publish(room);return {room:this.view(room,session)};}
   case 'close':this.close(this.hosted(session,command.roomId),'host_closed');return {};
   case 'memberRemove':{const room=this.hosted(session,command.roomId);if(command.expectedRevision!==room.revision)throw new RoomError('room_changed');const member=this.members(room).find(member=>member.id===command.membership);if(!member||member.session===room.host)throw new RoomError('membership_changed');room.kicked.add(member.session.token);this.releaseMember(room,member,'removed');return {room:this.view(room,session)};}
   case 'slotAvailability':{const room=this.hosted(session,command.roomId),slot=room.slots.find(slot=>slot.id===command.slotId);if(!slot||command.expectedRevision!==room.revision)throw new RoomError('room_changed');if(slot.member)throw new RoomError('slot_occupied');if(slot.open!==command.open){slot.open=command.open;slot.revision++;room.revision++;}this.publish(room);return {room:this.view(room,session)};}
   case 'slotRole':{const room=this.hosted(session,command.roomId),slot=room.slots.find(slot=>slot.id===command.slotId);if(!slot||command.expectedRevision!==room.revision)throw new RoomError('room_changed');if(command.role!=='observer'&&!controllerRoles(room.catalogId).includes(command.role))throw new RoomError('unsupported_role');if(slot.role===command.role)return {room:this.view(room,session)};const other=command.role==='observer'?undefined:room.slots.find(value=>value!==slot&&value.role===command.role);if(!slot.member&&other?.member)throw new RoomError('controller_occupied');const roles=[{slotId:slot.id,role:command.role},...(other?[{slotId:other.id,role:slot.role}]:[])];const pending:RoleTransaction={id:secret(),revision:room.revision,roles,status:'freezing'};if(room.started){const proposed=this.slotViews(room).map(value=>({...value,role:roles.find(role=>role.slotId===value.id)?.role??value.role}));room.game.requestRoles(pending,{owners:controllerOwners(proposed),revision:room.controllers.revision+1});}else this.applyRoles(room,pending);this.publish(room);return {room:this.view(room,session)};}
   case 'visibility': { const room = this.hosted(session,command.roomId);if(room.visibility !== command.visibility) {if(command.visibility === 'public') room.code = this.code(room.id);else if(room.code) {this.codes.delete(room.code);room.code = undefined;}room.visibility = command.visibility;this.publish(room);}return {room:this.view(room,session)}; }
   case 'rename': {const room = this.hosted(session,command.roomId);room.label = command.label.trim();this.publish(room);return {room:this.view(room,session)};}
   case 'nickname': {session.nickname = command.nickname.trim();const room = session.room && this.rooms.get(session.room);if(room) this.publish(room);return {session:{token:session.token,nickname:session.nickname,expiresInMs:limits.sessionIdle}};}
   case 'file':{const room=this.room(session),member=this.member(room,session);if(session===room.host)throw new RoomError('close_before_changing_game');if(member.file&&!matchesFile(member.file,command.fingerprint)&&room.controllers.owners.includes(member.id))room.game.stop('A controller game changed. Play is paused.');member.file=command.fingerprint;this.publish(room);return {room:this.view(room,session)};}
   case 'memberAcquisition':{const room=this.room(session),member=this.member(room,session);if(room.id!==command.roomId||member.id!==command.membership)throw new RoomError('membership_changed');member.acquisition=command.phase;if(command.phase==='loaded')member.reservationUntil=undefined;this.publish(room,false);return {room:this.view(room,session)};}

  }
  return {};
 }
 sweep() {
  const now = this.now();
  // Rooms is the sole publisher of membership plus peer state, including timer transitions.
  for(const id of this.peers.sweep()) {const room=this.rooms.get(id);if(room) this.publish(room,false);}
  for(const room of this.rooms.values()) {
   if(!room.confirmed && room.upload && (now-room.created>=300_000 || now-room.upload.lastProgress>=30_000)) {this.close(room,'upload_expired');continue;}
   if(!room.confirmed && now-room.created >= (room.uploadAttempted ? 300_000:5000)) {this.close(room,'creation_expired');continue;}
   for(const token of room.kicked) if(!this.sessions.has(token)) room.kicked.delete(token);
   if(room.game.sweep()) this.publish(room,false);
   for(const member of [...this.members(room)]){if(member.session===room.host)continue;if(!member.reconnectUntil&&now-member.session.heartbeat>=limits.missedHeartbeat){member.reconnectUntil=member.session.heartbeat+limits.missedHeartbeat+limits.reconnect;this.publish(room);}if(member.reconnectUntil&&now>=member.reconnectUntil){this.releaseMember(room,member,'member_expired');continue;}if(member.download&&now-member.download.lastProgress>=30_000)member.download=undefined;if(member.reservationUntil!==undefined&&member.reservationUntil<=now)this.releaseMember(room,member,'reservation_expired');}
   if(!room.reconnectUntil && now-room.host.heartbeat >= limits.missedHeartbeat) {room.reconnectUntil = room.host.heartbeat+limits.missedHeartbeat+limits.reconnect;this.publish(room);}
   if(room.reconnectUntil && now >= room.reconnectUntil) this.close(room,'host_expired');
  }
  for(const session of this.sessions.values()) {
   for(const [intent,expiry] of session.cancelled) if(expiry <= now) session.cancelled.delete(intent);
   if(now-session.touched >= limits.sessionIdle) {session.disconnect?.();this.sessions.delete(session.token);}
  }
 }
 stop() {for(const room of this.rooms.values()) this.close(room,'service_restarted');for(const offer of this.offers.values())this.codes.delete(offer.code);this.offers.clear();for(const session of this.sessions.values()) session.disconnect?.();this.sessions.clear();}
 /** Restricted operator interface: never expose session tokens, invites, chat or fingerprints. */
 operatorRooms() {this.sweep();return [...this.rooms.values()].filter(room=>room.confirmed).map(room=>({id:room.id,label:room.label,visibility:room.visibility,occupancy:this.members(room).length}));}
 removeRoom(id:string) {this.sweep();const room=this.rooms.get(id);if(!room?.confirmed)throw new RoomError('room_unavailable');this.close(room,'operator_removed');}
 revoke(token:string,sender:Sender) {
  const session=this.sessions.get(token);if(!session || session.send!==sender)return;
  const room=session.room && this.rooms.get(session.room);
  if(room) {if(room.host===session)this.close(room,'operator_removed');else this.releaseMember(room,this.member(room,session),'admission_blocked');}
  session.send?.({type:'ended',reason:'admission_blocked'});
  this.sessions.delete(token);
 }
}
