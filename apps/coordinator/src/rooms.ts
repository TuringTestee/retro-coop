import {catalogEntry,catalogId,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
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
type Session = { directory?:boolean; includeEmptyOffers?:boolean; token:string; policy:ConnectionPolicy; nickname:string; touched:number; heartbeat:number; room?:string; send?:Sender; disconnect?:()=>void; cancelled:Map<string,number>; rates:Map<string,number[]> };
type Room = { game:GameSession; hostReady?:boolean; started?:'solo'|'shared'; established?:boolean; guestReconnectUntil?:number; chat:RoomChat; id:string; invite:string; code?:string; label:string; visibility:Visibility; host:Session; guest?:Session; reservationUntil?:number; reservationStarted?:number; guestIntent?:string; guestMembership?:string; guestFile?:Fingerprint; fingerprint:Fingerprint; intent:string; confirmed:boolean; created:number; uploadAttempted?:boolean; upload?:{id:string;lastProgress:number}; download?:{id:string;lastProgress:number}; content?:string; reconnectUntil?:number; kicked:Set<string> };
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
 private claim(session:Session,offer:EmptyOffer|undefined,intent:string,fingerprint:Fingerprint,policy?:ConnectionPolicy):RoomData {
  this.rate(session,'join',5,60_000);
  if(session.cancelled.has(intent))throw new RoomError('cancelled');
  if(session.room) {const current=this.room(session);if(current.host===session&&current.intent===intent)return {room:this.view(current,session)};throw new RoomError('already_in_room');}
  if(!offer || catalogId(fingerprint)!==offer.catalogId) throw new RoomError('room_unavailable');
  if(this.rooms.size>=limits.rooms) throw new RoomError('capacity');
  // Reserve the replacement code before changing the claimed offer, so allocation failure is transactional.
  const replacementId=secret(),replacementCode=this.code(replacementId);
  session.policy=policy??session.policy;
  const room:Room={game:new GameSession(this.now,(role,event)=>{const current=this.rooms.get(offer.id);(role==='host'?current?.host:current?.guest)?.send?.(event);},offer.catalogId==='from-below-1.0'),chat:new RoomChat(),id:offer.id,invite:secret(),code:offer.code,label:catalogEntry(offer.catalogId).title,visibility:'public',host:session,fingerprint,intent,confirmed:true,created:this.now(),kicked:new Set()};
  this.offers.delete(offer.id);this.offers.set(replacementId,{id:replacementId,code:replacementCode,catalogId:offer.catalogId});
  this.rooms.set(room.id,room);this.invites.set(room.invite,room.id);session.room=room.id;session.heartbeat=this.now();this.publish(room);return {room:this.view(room,session)};
 }
 private reserve(session:Session,room:Room|undefined,intent:string,policy?:ConnectionPolicy):RoomData {
  this.rate(session,'join',5,60_000);
  if(!room || !room.confirmed || room.kicked.has(session.token)) throw new RoomError('room_unavailable');
  if(room.started)throw new RoomError('room_started');
  if(room.reconnectUntil) throw new RoomError('host_reconnecting');
  if(session.room) throw new RoomError('already_in_room');
  if(room.guest) throw new RoomError('place_taken');
  session.policy=policy??session.policy;room.guest=session;room.guestIntent=intent;room.guestMembership=secret();room.reservationStarted=this.now();room.reservationUntil=this.now()+limits.reservation;session.room=room.id;
  this.publish(room);return {room:this.view(room,session)};
 }
 private preview(room:Room): HumanRoomPreview { return {...(catalogId(room.fingerprint) ? {catalogId:catalogId(room.fingerprint)}:{}),id:room.id,label:room.label,host:room.host.nickname,visibility:room.visibility,...(room.code ? {code:room.code}:{}),status:room.reconnectUntil||room.guestReconnectUntil ? 'reconnecting' : room.started==='solo' ? 'playing' : room.started==='shared'&&!room.guest ? 'paused' : room.established ? room.game.view().status==='playing'?'playing':'paused' : room.guest ? 'reserved':'waiting',occupancy:room.guest ? 2:1}; }
 private view(room:Room,session:Session): RoomView { return {...this.preview(room),game:room.game.view(),hostReady:!!room.hostReady,started:room.started,established:!!room.established,...(room.guestReconnectUntil?{guestReconnectUntil:room.guestReconnectUntil}:{}),chatMembership:room.host===session ? room.intent:room.guestMembership!,invite:room.invite,role:room.host === session ? 'host':'guest',slot:room.host === session ? 1:2,fingerprint:room.fingerprint,connectionPolicy:session.policy,peer:this.peers.view(room.id,session.policy),...(room.guest ? {guest:room.guest.nickname,guestMembership:room.guestMembership,reservationUntil:room.reservationUntil,reservationIntent:room.guestIntent,matches:!!room.guestFile && matchesFile(room.fingerprint,room.guestFile)}:{}),...(room.reconnectUntil ? {hostReconnectUntil:room.reconnectUntil}:{})}; }
 private publish(room:Room,directory=true) {this.peers.sync(room.confirmed && room.guest && !room.reconnectUntil ? {id:room.id,host:room.host,guest:room.guest,reservation:room.guestIntent!}:undefined,room.id); const peer=this.peers.view(room.id,room.host.policy);room.game.bind(peer.status==='connected'?peer.epoch:undefined);for(const session of [room.host,room.guest]) if(session) session.send?.({type:'room',room:this.view(room,session)});if(directory) this.publishDirectory(); }
 private releaseGuest(room:Room,reason:string) { const guest = room.guest; if(!guest) return; room.game.stop('Guest left. Your local game is preserved.');room.game.resetControllers();room.established=false;room.guestReconnectUntil=undefined;room.chat.leave(room.guestMembership!);guest.room = undefined; room.guest = undefined; room.guestFile = undefined; room.reservationUntil = undefined; room.reservationStarted=undefined; room.download=undefined; room.guestIntent = undefined; room.guestMembership = undefined; guest.send?.({type:'ended',reason}); this.publish(room); }
 private close(room:Room,reason:string) {
  this.transfer?.discard(room.id);
  room.game.stop('The room closed. Your local game is preserved.');this.peers.clear(room.id);
  this.rooms.delete(room.id); this.invites.delete(room.invite); if(room.code) this.codes.delete(room.code);
  for(const session of [room.host,room.guest]) if(session) {session.room = undefined;session.send?.({type:'ended',reason});}
  this.publishDirectory();
 }
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
 beginDownload(token:string,roomId:string,membership:string) {
  this.sweep();const session=this.session(token),room=this.rooms.get(roomId),now=this.now();
  if(!room || !room.confirmed || room.guest!==session || room.guestMembership!==membership || session.room!==roomId || !room.content || room.started || room.established || !room.reservationUntil || room.reservationUntil<=now || !room.reservationStarted)throw new RoomError('room_changed');
  if(room.download && now-room.download.lastProgress<30_000)throw new RoomError('download_busy');
  this.rate(session,'download',5,60_000);
  const id=secret();room.download={id,lastProgress:now};
  return {id,path:room.content,bytes:room.fingerprint.cartridge.bytes,sha256:room.fingerprint.romSha256};
 }
 downloadProgress(roomId:string,id:string) {
  const room=this.rooms.get(roomId),now=this.now();
  if(!room?.download || room.download.id!==id || !room.guest || !room.reservationStarted || !room.reservationUntil || room.reservationUntil<=now || now-room.download.lastProgress>=30_000 || now-room.reservationStarted>=300_000)throw new RoomError('download_expired');
  room.download.lastProgress=now;room.reservationUntil=Math.min(room.reservationStarted+300_000,now+limits.reservation);
 }
 endDownload(roomId:string,id:string) {const room=this.rooms.get(roomId);if(room?.download?.id===id)room.download=undefined;}
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
  if(room) {if(room.host===session){room.reconnectUntil=undefined;room.hostReady=false;}else room.guestReconnectUntil=undefined;this.publish(room);}
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
   if(command.type==='peerSignal') return {};
   this.publish(room,false);return {room:this.view(room,session)};
  }
  if(command.type==='gameControllerPropose'||command.type==='gameControllerRespond'||command.type==='gameControllerCancel'||command.type==='gameReady'||command.type==='gameUnready'||command.type==='gameAck'||command.type==='gamePause'||command.type==='gamePaused'||command.type==='gameResume'||command.type==='gameAbort') {
   const room=this.room(session),role=room.host===session?'host':'guest';
   try {
    if(command.type==='gameControllerPropose'||command.type==='gameControllerRespond'||command.type==='gameControllerCancel') {
     if(!room.guest||!room.host.send||!room.guest.send||room.reconnectUntil||room.guestReconnectUntil)throw new RoomError('game_prerequisites');
     this.rate(session,'controllers',20,60_000);
     if(command.type==='gameControllerPropose')room.game.proposeControllers(role,command);else room.game.respondControllers(role,command);
    } else if(command.type==='gameReady') {
     this.rate(session,'gameReady',10,60_000);
     if(!room.guest || !room.guestFile || !matchesFile(room.fingerprint,room.guestFile) || this.peers.view(room.id,session.policy).status!=='connected') throw new RoomError('game_prerequisites');
     room.game.ready(role,command,room.established);
     if(!room.started&&room.game.view().status==='starting')room.started='shared';
    } else if(command.type==='gameUnready') {this.rate(session,'gameReady',10,60_000);room.game.unready(role,command.peerEpoch);}
    else if(command.type==='gameAck') {if(room.game.ack(role,command.epoch,command.hash)) {room.established=true;room.reservationUntil=undefined;}}
    else if(command.type==='gamePause')room.game.pause(command.epoch,command.frame,command.reason,role);
    else if(command.type==='gamePaused')room.game.pausedAt(role,command.epoch,command.frame,command.hash);
    else if(command.type==='gameResume')room.game.resume(role,command.epoch);
    else {if(command.epoch!==room.game.view().epoch)throw new RoomError('stale_game');room.game.stop(`Shared play stopped (${command.reason}). Your game is preserved.`,'failed');}
   }catch(error) {if(error instanceof RoomError) throw error;throw new RoomError(error instanceof Error?error.message:'game_failed');}
   this.publish(room);return {room:this.view(room,session)};
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
   case 'directory': {this.rate(session,'directory',20,60_000);session.directory=true;session.includeEmptyOffers=command.includeEmptyOffers===true;return {directory:this.directory(session)};}
   case 'lookupCode': {this.rate(session,'preview',20,60_000);const room=this.publicRoom(command.code),offer=this.publicOffer(session,command.code);if(!room&&!offer) throw new RoomError('room_unavailable');return {preview:room?this.preview(room):this.offerPreview(offer!)};}
   case 'joinCode': return this.reserve(session,this.publicRoom(command.code),command.intent,command.policy);
   case 'claimCode': return this.claim(session,this.publicOffer(session,command.code),command.intent,command.fingerprint,command.policy);
   case 'preview': { this.rate(session,'preview',20,60_000); const id = this.invites.get(command.invite), room = id && this.rooms.get(id); if(!room || !room.confirmed) throw new RoomError('room_unavailable'); return {preview:this.preview(room)}; }
   case 'create': {
    this.rate(session,'create',5,60_000);session.policy=command.policy??session.policy;
    if(session.cancelled.has(command.intent)) throw new RoomError('cancelled');
    if(session.room) {const room = this.room(session); if(room.host === session && room.intent === command.intent) return {room:this.view(room,session)}; throw new RoomError('already_in_room');}
    if(this.rooms.size >= limits.rooms) throw new RoomError('capacity');
    const id=secret(), code = command.visibility === 'public' ? this.code(id):undefined;
    const room:Room = {game:new GameSession(this.now,(role,event)=>{const current=this.rooms.get(id);(role==='host'?current?.host:current?.guest)?.send?.(event);},catalogId(command.fingerprint)==='from-below-1.0'),chat:new RoomChat(),id,invite:secret(),code,label:`${pick(colors)} ${pick(places)}`,visibility:command.visibility,host:session,fingerprint:command.fingerprint,intent:command.intent,confirmed:false,created:this.now(),kicked:new Set()};
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
    if(room && room.guest === session && room.guestIntent === command.intent) this.releaseGuest(room,'left');
    else if(room && room.host===session && room.intent===command.intent) this.close(room,'claim_cancelled');
    return {};
   }
   case 'prepareHost': case 'startRoom': {
    const room=this.hosted(session,command.roomId);
    if(!room.confirmed||room.intent!==command.membership)throw new RoomError('membership_changed');
    if(!matchesFile(room.fingerprint,command.fingerprint))throw new RoomError('game_mismatch');
    if(command.type==='prepareHost') {if(room.started)throw new RoomError('room_started');room.hostReady=true;this.publish(room,false);return {room:this.view(room,session)};}
    if(room.started)return {room:this.view(room,session)};
    if(!room.hostReady)throw new RoomError('host_not_ready');
    if(room.reconnectUntil)throw new RoomError('host_reconnecting');
    if(room.game.view().startRequested)return {room:this.view(room,session)};
    const readyGuest=!!room.guest?.send&&!!room.guestFile&&matchesFile(room.fingerprint,room.guestFile)&&this.peers.view(room.id,session.policy).status==='connected'&&room.game.view().ready?.includes('guest');
    if(readyGuest){try {room.game.requestStart();}catch(error){throw new RoomError(error instanceof Error?error.message:'game_prerequisites');}if(room.game.view().status==='starting')room.started='shared';this.publish(room);if(room.game.view().status==='late_join'||room.game.view().status==='failed')throw new RoomError(room.game.view().status==='late_join'?'late_join':'game_prerequisites');}
    else {room.started='solo';if(room.guest)this.releaseGuest(room,'host_started_solo');else this.publish(room);}
    return {room:this.view(room,session)};
   }
   case 'close': this.close(this.hosted(session,command.roomId),'host_closed');return {};
   case 'kick': { const room = this.hosted(session,command.roomId);if(!room.guest || room.guestMembership!==command.guestMembership) throw new RoomError('membership_changed');room.kicked.add(room.guest.token); this.releaseGuest(room,'removed');return {room:this.view(room,session)}; }
   case 'visibility': { const room = this.hosted(session,command.roomId);if(room.visibility !== command.visibility) {if(command.visibility === 'public') room.code = this.code(room.id);else if(room.code) {this.codes.delete(room.code);room.code = undefined;}room.visibility = command.visibility;this.publish(room);}return {room:this.view(room,session)}; }
   case 'rename': {const room = this.hosted(session,command.roomId);room.label = command.label.trim();this.publish(room);return {room:this.view(room,session)};}
   case 'nickname': {session.nickname = command.nickname.trim();const room = session.room && this.rooms.get(session.room);if(room) this.publish(room);return {session:{token:session.token,nickname:session.nickname,expiresInMs:limits.sessionIdle}};}
   case 'file': { const room = this.room(session);if(room.host === session) throw new RoomError('close_before_changing_game');if(room.guestFile&&!matchesFile(room.guestFile,command.fingerprint))room.game.stop('Guest game changed. Shared play is paused.');room.guestFile = command.fingerprint;this.publish(room);return {room:this.view(room,session)}; }
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
   if(room.established && room.guest && !room.guestReconnectUntil && now-room.guest.heartbeat>=limits.missedHeartbeat) {room.guestReconnectUntil=room.guest.heartbeat+limits.missedHeartbeat+limits.reconnect;room.game.stop('Guest is reconnecting. Shared play is paused.');this.publish(room);}
   if(room.guestReconnectUntil && now>=room.guestReconnectUntil) this.releaseGuest(room,'guest_expired');
   if(room.download && now-room.download.lastProgress>=30_000)room.download=undefined;
   if(room.guest && !room.established && room.reservationUntil! <= now) this.releaseGuest(room,'reservation_expired');
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
