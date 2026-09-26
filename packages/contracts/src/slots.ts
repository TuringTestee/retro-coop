import {catalog,type CatalogId} from './catalog.ts';
/** Physical lobby positions and controller capabilities have separate identities. */
export const SLOT_IDS=['slot-1','slot-2','slot-3','slot-4','slot-5'] as const;
export type SlotId=typeof SLOT_IDS[number];
export type PlayerRole='player1'|'player2';
export type SlotRole=PlayerRole|'observer';
export type AcquisitionPhase='checking'|'downloading'|'loading'|'loaded'|'failed';
export type RoomMember={id:string;nickname:string;connected:boolean;matches:boolean;acquisition:AcquisitionPhase;reconnectUntil?:number};
export type RoomSlot={id:SlotId;role:SlotRole;open:boolean;revision:number;member?:RoomMember};
export const validSlotId=(value:unknown):value is SlotId=>typeof value==='string'&&(SLOT_IDS as readonly string[]).includes(value);
export const validSlotRole=(value:unknown):value is SlotRole=>value==='observer'||value==='player1'||value==='player2';
export function controllerRoles(catalogId?:CatalogId):PlayerRole[]{const count=catalog.find(entry=>entry.id===catalogId)?.controllers??2;return count===1?['player1']:['player1','player2'];}
export function controllerOwners(slots:readonly RoomSlot[]):[string|null,string|null]{return [slots.find(slot=>slot.role==='player1')?.member?.id??null,slots.find(slot=>slot.role==='player2')?.member?.id??null];}
