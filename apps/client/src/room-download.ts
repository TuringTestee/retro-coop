import type {RoomPreview} from '../../../packages/contracts/src/rooms.ts';

export const gameSize=(bytes:number)=>bytes<1_000_000?`${Math.max(1,Math.ceil(bytes/1000))} KB`:`${(bytes/1_000_000).toFixed(1)} MB`;

export function roomDownloadLabel(room:RoomPreview) {
 if(room.catalogId)return '';
 const bytes='romBytes' in room?room.romBytes:undefined;
 return `Host's game file · ${bytes?`${gameSize(bytes)} `:''}download`;
}
