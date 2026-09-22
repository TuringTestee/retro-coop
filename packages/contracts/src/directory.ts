import type {ReservationRequest,RoomPreview,Fingerprint} from './rooms.ts';
/** Public codes identify listings; invitations and session tokens confer separate access. */
export const PUBLIC_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
export const PUBLIC_CODE_LENGTH = 8;
export function publicCode(value:string):string|undefined {
 const code=value.trim().toUpperCase();
 return code.length===PUBLIC_CODE_LENGTH && [...code].every(character=>PUBLIC_CODE_ALPHABET.includes(character)) ? code : undefined;
}
export type DirectoryCommand =
 | {type:'directory';requestId:string;includeEmptyOffers?:boolean}
 | {type:'lookupCode';requestId:string;code:string}
 | (ReservationRequest & {type:'joinCode';code:string})
 | (ReservationRequest & {type:'claimCode';code:string;fingerprint:Fingerprint});
export function matchingRooms(rooms:readonly RoomPreview[],query:string):RoomPreview[] {
 const text=query.trim().toLocaleLowerCase(),code=publicCode(query);
 return rooms.filter(room=>!text || room.label.toLocaleLowerCase().includes(text) || room.host.toLocaleLowerCase().includes(text) || !!code && room.code===code);
}
