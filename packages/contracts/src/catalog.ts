import type {Fingerprint} from './fingerprint.ts';

export const catalog = Object.freeze([
 Object.freeze({id:'super-tilt-bro-pal',title:'Super Tilt Bro',mode:'Platform fighter · 1–2 players',bytes:524304,sha256:'847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d',format:'NES 2.0',mapper:2,submapper:1,region:'PAL',assetName:'super-tilt-bro-e',instructions:'Use the game menu to choose a mode. Focus the screen; arrows move, X is A, Z is B, Enter is Start, and Shift is Select.',credits:'Super Tilt Bro by sgadrat. The game contains its own additional credits.',license:'License information for this supplied build has not been verified.'}),
 Object.freeze({id:'from-below-1.0',title:'From Below',mode:'Puzzle · 1 player',bytes:40976,sha256:'1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555',format:'iNES',mapper:0,submapper:0,region:'NTSC',assetName:'from-below-1.0',instructions:'Choose a mode in the game menu. Focus the screen; arrows move, X is A, Z is B, Enter is Start, and Shift is Select.',credits:'Game by Matt Hughson. Music and sound effects by Tui. Art by Haller Zoltan. Box art and manual by Dejah Payne.',license:'License information for this supplied build has not been verified.'}),
] as const);
export type CatalogEntry = typeof catalog[number];
export type CatalogId = CatalogEntry['id'];
export const catalogEntry=(id:CatalogId)=>catalog.find(entry=>entry.id===id)!;
export const catalogAssetPath=(entry:CatalogEntry)=>`/catalog/${entry.assetName}-${entry.sha256}.nes`;
export function catalogId(fingerprint:Fingerprint):CatalogId|undefined {const c=fingerprint.cartridge;return catalog.find(entry=>fingerprint.romSha256===entry.sha256&&c.bytes===entry.bytes&&c.format===entry.format&&c.mapper===entry.mapper&&c.submapper===entry.submapper&&c.region===entry.region)?.id;}
