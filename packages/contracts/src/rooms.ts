import {parseGameCommand,type GameCommand,type GameEvent,type GameView} from './gameplay.ts';
import {validChatText,type ChatCommand,type ChatEvent,type ChatAck} from './chat.ts';
import {SLOT_IDS,validSlotId,validSlotRole,type SlotId,type SlotRole,type RoomSlot,type PlayerRole} from './slots.ts';
import {object,keys,text,token} from './protocol-validation.ts';
import {parsePeerCommand,type PeerCommand,type PeerEvent,type PeerView,type ConnectionPolicy} from './peer.ts';
import {publicCode,type DirectoryCommand} from './directory.ts';
/** Room protocol: bounded control and text chat messages. No binary or arbitrary extension fields. */
export const ROOM_PROTOCOL = 2;
export const ROOM_METADATA_BYTES = 16384;
// Each member negotiates at most four pairs; retain finite per-link command headroom.
export const ROOM_COMMAND_BURST = 60 * (SLOT_IDS.length - 1);
export const ROOM_GAME_BURST = 40 * (SLOT_IDS.length - 1);
export const ROOM_WIRE_BURST = 2 * ROOM_COMMAND_BURST;
export type RoomRole = 'host'|'member';
export type Visibility = 'public' | 'protected' | 'unlisted';
export type NewVisibility = Exclude<Visibility,'unlisted'>;
export function validRoomPassword(value:unknown):value is string {return typeof value==='string'&&Array.from(value).length>=8&&Array.from(value).length<=128&&!/[\uD800-\uDFFF]/u.test(value);}
import {validFingerprint,type Fingerprint} from './fingerprint.ts';
import type {CatalogId} from './catalog.ts';
export {validFingerprint,matchesFile} from './fingerprint.ts';
export type {Fingerprint} from './fingerprint.ts';
type PreviewBase = { id:string; label:string; visibility:Visibility; code?:string };
export type HumanRoomPreview = PreviewBase & {host:string; catalogId?:CatalogId; romBytes?:number; status:'waiting'|'reserved'|'reconnecting'|'playing'|'paused'; occupancy:number; openSlots:number};
export type EmptyRoomPreview = PreviewBase & {host:'No host'; visibility:'public'; code:string; catalogId:CatalogId; status:'waiting'|'unavailable'; occupancy:0; unavailableReason?:'room_capacity'};
export type RoomPreview = HumanRoomPreview | EmptyRoomPreview;
export type RoomView = HumanRoomPreview & {game:GameView;hostReady:boolean;started?:'shared';established:boolean;chatMembership:string;hostMembership:string;invite:string;role:RoomRole;slot:SlotId;slots:RoomSlot[];revision:number;accessRevision:number;controllerRoles:PlayerRole[];connectionPolicy:ConnectionPolicy;peers:PeerView[];reservationUntil?:number;reservationIntent:string;fingerprint:Fingerprint;matches:boolean;hostReconnectUntil?:number};
export type SessionInfo = { token:string; nickname:string; expiresInMs:number };
export type ReservationRequest = {requestId:string;intent:string};
export type RoomCommand = GameCommand | ChatCommand | PeerCommand | DirectoryCommand
 | { type:'hello'; requestId:string; token?:string }
 | { type:'heartbeat'; requestId:string }
 | { type:'preview'; requestId:string; invite:string }
 | { type:'create'; requestId:string; intent:string; visibility:NewVisibility; fingerprint:Fingerprint; password?:string }
 | { type:'confirmCreate'; requestId:string; intent:string }
 | { type:'cancelCreate'; requestId:string; intent:string }
 | { type:'prepareHost'; requestId:string; roomId:string; membership:string; fingerprint:Fingerprint }
 | { type:'startRoom'; requestId:string; roomId:string; membership:string; fingerprint:Fingerprint }
 | (ReservationRequest & { type:'join'; invite:string; password?:string })
 | { type:'leave'; requestId:string; intent:string }
 | { type:'close'; requestId:string; roomId:string }
 | { type:'memberRemove'; requestId:string; roomId:string; membership:string; expectedRevision:number }
 | { type:'slotAvailability'; requestId:string; roomId:string; slotId:SlotId; open:boolean; expectedRevision:number }
 | { type:'slotRole'; requestId:string; roomId:string; slotId:SlotId; role:SlotRole; expectedRevision:number }
 | { type:'rename'; requestId:string; roomId:string; label:string }
 | { type:'nickname'; requestId:string; nickname:string }
 | { type:'visibility'; requestId:string; roomId:string; visibility:NewVisibility; expectedAccessRevision:number; password?:string }
 | { type:'file'; requestId:string; fingerprint:Fingerprint }
 | { type:'memberAcquisition'; requestId:string; roomId:string; membership:string; phase:'checking'|'downloading'|'loading'|'loaded'|'failed' };
export type RoomData = { chatAck?:ChatAck; session?:SessionInfo; room?:RoomView; preview?:RoomPreview; directory?:RoomPreview[] };
export type RoomEvent = GameEvent | ChatEvent | PeerEvent
 | { type:'result'; requestId:string; ok:true; data:RoomData }
 | { type:'result'; requestId:string; ok:false; error:string; retryAfterMs?:number }
 | { type:'directory'; rooms:RoomPreview[] }
 | { type:'preview'; preview:RoomPreview }
 | { type:'room'; room:RoomView }
 | { type:'ended'; reason:string };

export function parseRoomCommand(value:unknown): RoomCommand | undefined {
 if(!object(value) || typeof value.type !== 'string' || !token(value.requestId)) return;
 const game=parseGameCommand(value);if(game) return game;
 const peer=parsePeerCommand(value);if(peer) return peer;
 const base = ['type','requestId'];
 let valid = false;
 switch(value.type) {
  case 'chat': valid=keys(value,[...base,'roomId','membership','clientId','text']) && token(value.roomId) && token(value.membership) && token(value.clientId) && validChatText(value.text);break;
  case 'hello': valid = keys(value,base,['token']) && (value.token === undefined || token(value.token)); break;
  case 'directory': valid = keys(value,base,['includeEmptyOffers']) && (value.includeEmptyOffers===undefined || typeof value.includeEmptyOffers==='boolean'); break;
  case 'heartbeat': valid = keys(value,base); break;
  case 'close': valid=keys(value,[...base,'roomId']) && token(value.roomId);break;
  case 'memberRemove': valid=keys(value,[...base,'roomId','membership','expectedRevision']) && token(value.roomId) && token(value.membership) && Number.isSafeInteger(value.expectedRevision) && (value.expectedRevision as number)>=0;break;
  case 'slotAvailability': valid=keys(value,[...base,'roomId','slotId','open','expectedRevision']) && token(value.roomId) && validSlotId(value.slotId) && typeof value.open==='boolean' && Number.isSafeInteger(value.expectedRevision) && (value.expectedRevision as number)>=0;break;
  case 'slotRole': valid=keys(value,[...base,'roomId','slotId','role','expectedRevision']) && token(value.roomId) && validSlotId(value.slotId) && validSlotRole(value.role) && Number.isSafeInteger(value.expectedRevision) && (value.expectedRevision as number)>=0;break;
  case 'lookupCode': valid = keys(value,[...base,'code']) && typeof value.code === 'string' && !!publicCode(value.code); break;
  case 'joinCode': valid = keys(value,[...base,'code','intent'],['password']) && (value.password===undefined || typeof value.password==='string'&&Array.from(value.password).length<=128) && typeof value.code === 'string' && !!publicCode(value.code) && token(value.intent); break;
  case 'claimCode': valid = keys(value,[...base,'code','intent','fingerprint'],['visibility','password']) && (value.visibility===undefined || value.visibility==='public' || value.visibility==='protected') && (value.password===undefined || typeof value.password==='string'&&Array.from(value.password).length<=128) && typeof value.code === 'string' && !!publicCode(value.code) && token(value.intent) && validFingerprint(value.fingerprint); break;
  case 'preview': valid = keys(value,[...base,'invite']) && token(value.invite); break;
  case 'join': valid = keys(value,[...base,'invite','intent'],['password']) && (value.password===undefined || typeof value.password==='string'&&Array.from(value.password).length<=128) && token(value.invite) && token(value.intent); break;
  case 'leave': valid = keys(value,[...base,'intent']) && token(value.intent); break;
  case 'create': valid = keys(value,[...base,'intent','visibility','fingerprint'],['password']) && token(value.intent) && ['public','protected'].includes(value.visibility as string) && (value.password===undefined || typeof value.password==='string'&&Array.from(value.password).length<=128) && validFingerprint(value.fingerprint); break;
  case 'prepareHost': case 'startRoom': valid = keys(value,[...base,'roomId','membership','fingerprint']) && token(value.roomId) && token(value.membership) && validFingerprint(value.fingerprint); break;
  case 'confirmCreate': case 'cancelCreate': valid = keys(value,[...base,'intent']) && token(value.intent); break;
  case 'rename': valid = keys(value,[...base,'roomId','label']) && token(value.roomId) && text(value.label,80); break;
  case 'nickname': valid = keys(value,[...base,'nickname']) && text(value.nickname,32); break;
  case 'visibility': valid = keys(value,[...base,'roomId','visibility','expectedAccessRevision'],['password']) && token(value.roomId) && ['public','protected'].includes(value.visibility as string) && Number.isSafeInteger(value.expectedAccessRevision) && (value.expectedAccessRevision as number)>=0 && (value.password===undefined || typeof value.password==='string'&&Array.from(value.password).length<=128); break;
  case 'file': valid = keys(value,[...base,'fingerprint']) && validFingerprint(value.fingerprint); break;
  case 'memberAcquisition': valid=keys(value,[...base,'roomId','membership','phase']) && token(value.roomId) && token(value.membership) && ['checking','downloading','loading','loaded','failed'].includes(value.phase as string);break;
 }
 if(!valid) return;
 return (value.type === 'lookupCode' || value.type === 'joinCode' || value.type === 'claimCode' ? {...value,code:publicCode(value.code as string)!} : value) as RoomCommand;
}
