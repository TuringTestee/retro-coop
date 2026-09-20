import {validChatText,type ChatCommand,type ChatEvent,type ChatAck} from './chat.ts';
import {publicCode,type DirectoryCommand} from './directory.ts';
/** Room protocol: bounded control and text chat messages. No binary or arbitrary extension fields. */
export const ROOM_PROTOCOL = 1;
export type Visibility = 'public' | 'unlisted';
import {validFingerprint,type Fingerprint} from './fingerprint.ts';
export {validFingerprint,matchesFile} from './fingerprint.ts';
export type {Fingerprint} from './fingerprint.ts';
export type RoomPreview = { id:string; label:string; host:string; visibility:Visibility; code?:string; status:'waiting'|'reserved'|'reconnecting'; occupancy:1|2 };
export type RoomView = RoomPreview & { chatMembership:string; invite:string; role:'host'|'guest'; slot:1|2; guest?:string; reservationUntil?:number; reservationIntent?:string; fingerprint:Fingerprint; matches?:boolean; hostReconnectUntil?:number };
export type SessionInfo = { token:string; nickname:string; expiresInMs:number };
export type ReservationRequest = {requestId:string;intent:string};
export type RoomCommand =
 | ChatCommand
 | DirectoryCommand
 | { type:'hello'; requestId:string; token?:string }
 | { type:'heartbeat'; requestId:string }
 | { type:'preview'; requestId:string; invite:string }
 | { type:'create'; requestId:string; intent:string; visibility:Visibility; fingerprint:Fingerprint }
 | { type:'confirmCreate'; requestId:string; intent:string }
 | { type:'cancelCreate'; requestId:string; intent:string }
 | (ReservationRequest & { type:'join'; invite:string })
 | { type:'leave'; requestId:string; intent:string }
 | { type:'close'; requestId:string }
 | { type:'kick'; requestId:string }
 | { type:'rename'; requestId:string; label:string }
 | { type:'nickname'; requestId:string; nickname:string }
 | { type:'visibility'; requestId:string; visibility:Visibility }
 | { type:'file'; requestId:string; fingerprint:Fingerprint };
export type RoomData = { chatAck?:ChatAck; directory?:RoomPreview[]; session?:SessionInfo; room?:RoomView; preview?:RoomPreview };
export type RoomEvent =
 | ChatEvent
 | { type:'result'; requestId:string; ok:true; data:RoomData }
 | { type:'result'; requestId:string; ok:false; error:string; retryAfterMs?:number }
 | { type:'directory'; rooms:RoomPreview[] }
 | { type:'room'; room:RoomView }
 | { type:'ended'; reason:string };

function object(value:unknown): value is Record<string,unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function keys(value:Record<string,unknown>, required:string[], optional:string[] = []) { return required.every(key => Object.hasOwn(value,key)) && Object.keys(value).every(key => required.includes(key) || optional.includes(key)); }
const text = (value:unknown, max:number) => typeof value === 'string' && value.trim().length > 0 && value.length <= max && !/[\u0000-\u001f\u007f]/u.test(value);
const token = (value:unknown) => typeof value === 'string' && /^[A-Za-z0-9_-]{22,64}$/.test(value);

export function parseRoomCommand(value:unknown): RoomCommand | undefined {
 if(!object(value) || typeof value.type !== 'string' || !token(value.requestId)) return;
 const base = ['type','requestId'];
 let valid = false;
 switch(value.type) {
  case 'chat': valid=keys(value,[...base,'roomId','membership','clientId','text']) && token(value.roomId) && token(value.membership) && token(value.clientId) && validChatText(value.text);break;
  case 'hello': valid = keys(value,base,['token']) && (value.token === undefined || token(value.token)); break;
  case 'directory': case 'heartbeat': case 'close': case 'kick': valid = keys(value,base); break;
  case 'lookupCode': valid = keys(value,[...base,'code']) && typeof value.code === 'string' && !!publicCode(value.code); break;
  case 'joinCode': valid = keys(value,[...base,'code','intent']) && typeof value.code === 'string' && !!publicCode(value.code) && token(value.intent); break;
  case 'preview': valid = keys(value,[...base,'invite']) && token(value.invite); break;
  case 'join': valid = keys(value,[...base,'invite','intent']) && token(value.invite) && token(value.intent); break;
  case 'leave': valid = keys(value,[...base,'intent']) && token(value.intent); break;
  case 'create': valid = keys(value,[...base,'intent','visibility','fingerprint']) && token(value.intent) && ['public','unlisted'].includes(value.visibility as string) && validFingerprint(value.fingerprint); break;
  case 'confirmCreate': case 'cancelCreate': valid = keys(value,[...base,'intent']) && token(value.intent); break;
  case 'rename': valid = keys(value,[...base,'label']) && text(value.label,80); break;
  case 'nickname': valid = keys(value,[...base,'nickname']) && text(value.nickname,32); break;
  case 'visibility': valid = keys(value,[...base,'visibility']) && ['public','unlisted'].includes(value.visibility as string); break;
  case 'file': valid = keys(value,[...base,'fingerprint']) && validFingerprint(value.fingerprint); break;
 }
 if(!valid) return;
 return (value.type === 'lookupCode' || value.type === 'joinCode' ? {...value,code:publicCode(value.code as string)!} : value) as RoomCommand;
}
