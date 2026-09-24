import {parseGameCommand,type GameCommand,type GameEvent,type GameView} from './gameplay.ts';
import {validChatText,type ChatCommand,type ChatEvent,type ChatAck} from './chat.ts';
import {object,keys,text,token} from './protocol-validation.ts';
import {parsePeerCommand,validPolicy,type PeerCommand,type PeerEvent,type PeerView,type ConnectionPolicy} from './peer.ts';
import {publicCode,type DirectoryCommand} from './directory.ts';
/** Room protocol: bounded control and text chat messages. No binary or arbitrary extension fields. */
export const ROOM_PROTOCOL = 1;
export const ROOM_METADATA_BYTES = 4096;
export type RoomRole = 'host'|'guest';
export type Visibility = 'public' | 'unlisted';
import {validFingerprint,type Fingerprint} from './fingerprint.ts';
import type {CatalogId} from './catalog.ts';
export {validFingerprint,matchesFile} from './fingerprint.ts';
export type {Fingerprint} from './fingerprint.ts';
type PreviewBase = { id:string; label:string; visibility:Visibility; code?:string };
export type HumanRoomPreview = PreviewBase & {host:string; catalogId?:CatalogId; romBytes?:number; status:'waiting'|'reserved'|'reconnecting'|'playing'|'paused'; occupancy:1|2; guestPlace:'open'|'closed'; guestPlaceVersion:number};
export type EmptyRoomPreview = PreviewBase & {host:'No host'; visibility:'public'; code:string; catalogId:CatalogId; status:'waiting'|'unavailable'; occupancy:0; unavailableReason?:'room_capacity'};
export type RoomPreview = HumanRoomPreview | EmptyRoomPreview;
export type RoomView = HumanRoomPreview & { game?:GameView; hostReady?:boolean; guestConnected?:boolean; guestAcquisition?:'checking'|'downloading'|'loading'|'loaded'|'failed'; started?:'solo'|'shared'; established?:boolean; guestReconnectUntil?:number; chatMembership:string; invite:string; role:RoomRole; slot:1|2; connectionPolicy:ConnectionPolicy; peer:PeerView; guest?:string; guestMembership?:string; reservationUntil?:number; reservationIntent?:string; fingerprint:Fingerprint; matches?:boolean; hostReconnectUntil?:number };
export type SessionInfo = { token:string; nickname:string; expiresInMs:number };
export type ReservationRequest = {requestId:string;intent:string;policy?:ConnectionPolicy};
export type RoomCommand = GameCommand | ChatCommand | PeerCommand | DirectoryCommand
 | { type:'hello'; requestId:string; token?:string; policy?:ConnectionPolicy }
 | { type:'heartbeat'; requestId:string }
 | { type:'preview'; requestId:string; invite:string }
 | { type:'create'; requestId:string; intent:string; visibility:Visibility; fingerprint:Fingerprint; policy?:ConnectionPolicy }
 | { type:'confirmCreate'; requestId:string; intent:string }
 | { type:'cancelCreate'; requestId:string; intent:string }
 | { type:'prepareHost'; requestId:string; roomId:string; membership:string; fingerprint:Fingerprint }
 | { type:'startRoom'; requestId:string; roomId:string; membership:string; fingerprint:Fingerprint }
 | (ReservationRequest & { type:'join'; invite:string })
 | { type:'leave'; requestId:string; intent:string }
 | { type:'close'; requestId:string; roomId:string }
 | { type:'kick'; requestId:string; roomId:string; guestMembership:string }
 | { type:'guestPlace'; requestId:string; roomId:string; place:'open'|'closed'; expectedVersion:number }
 | { type:'rename'; requestId:string; roomId:string; label:string }
 | { type:'nickname'; requestId:string; nickname:string }
 | { type:'visibility'; requestId:string; roomId:string; visibility:Visibility }
 | { type:'file'; requestId:string; fingerprint:Fingerprint }
 | { type:'guestAcquisition'; requestId:string; roomId:string; membership:string; phase:'checking'|'downloading'|'loading'|'loaded'|'failed' };
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
  case 'hello': valid = keys(value,base,['token','policy']) && (value.policy===undefined || validPolicy(value.policy)) && (value.token === undefined || token(value.token)); break;
  case 'directory': valid = keys(value,base,['includeEmptyOffers']) && (value.includeEmptyOffers===undefined || typeof value.includeEmptyOffers==='boolean'); break;
  case 'heartbeat': valid = keys(value,base); break;
  case 'close': valid=keys(value,[...base,'roomId']) && token(value.roomId);break;
  case 'kick': valid=keys(value,[...base,'roomId','guestMembership']) && token(value.roomId) && token(value.guestMembership);break;
  case 'guestPlace': valid=keys(value,[...base,'roomId','place','expectedVersion']) && token(value.roomId) && (value.place==='open'||value.place==='closed') && Number.isSafeInteger(value.expectedVersion) && (value.expectedVersion as number)>=0;break;
  case 'lookupCode': valid = keys(value,[...base,'code']) && typeof value.code === 'string' && !!publicCode(value.code); break;
  case 'joinCode': valid = keys(value,[...base,'code','intent'],['policy']) && (value.policy===undefined || validPolicy(value.policy)) && typeof value.code === 'string' && !!publicCode(value.code) && token(value.intent); break;
  case 'claimCode': valid = keys(value,[...base,'code','intent','fingerprint'],['policy','visibility']) && (value.policy===undefined || validPolicy(value.policy)) && (value.visibility===undefined || value.visibility==='public' || value.visibility==='unlisted') && typeof value.code === 'string' && !!publicCode(value.code) && token(value.intent) && validFingerprint(value.fingerprint); break;
  case 'preview': valid = keys(value,[...base,'invite']) && token(value.invite); break;
  case 'join': valid = keys(value,[...base,'invite','intent'],['policy']) && (value.policy===undefined || validPolicy(value.policy)) && token(value.invite) && token(value.intent); break;
  case 'leave': valid = keys(value,[...base,'intent']) && token(value.intent); break;
  case 'create': valid = keys(value,[...base,'intent','visibility','fingerprint'],['policy']) && (value.policy===undefined || validPolicy(value.policy)) && token(value.intent) && ['public','unlisted'].includes(value.visibility as string) && validFingerprint(value.fingerprint); break;
  case 'prepareHost': case 'startRoom': valid = keys(value,[...base,'roomId','membership','fingerprint']) && token(value.roomId) && token(value.membership) && validFingerprint(value.fingerprint); break;
  case 'confirmCreate': case 'cancelCreate': valid = keys(value,[...base,'intent']) && token(value.intent); break;
  case 'rename': valid = keys(value,[...base,'roomId','label']) && token(value.roomId) && text(value.label,80); break;
  case 'nickname': valid = keys(value,[...base,'nickname']) && text(value.nickname,32); break;
  case 'visibility': valid = keys(value,[...base,'roomId','visibility']) && token(value.roomId) && ['public','unlisted'].includes(value.visibility as string); break;
  case 'file': valid = keys(value,[...base,'fingerprint']) && validFingerprint(value.fingerprint); break;
  case 'guestAcquisition': valid=keys(value,[...base,'roomId','membership','phase']) && token(value.roomId) && token(value.membership) && ['checking','downloading','loading','loaded','failed'].includes(value.phase as string);break;
 }
 if(!valid) return;
 return (value.type === 'lookupCode' || value.type === 'joinCode' || value.type === 'claimCode' ? {...value,code:publicCode(value.code as string)!} : value) as RoomCommand;
}
