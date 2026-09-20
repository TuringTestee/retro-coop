import type {Fingerprint} from './fingerprint.ts';

/** One pinned, user-authorized included artifact; never accepts arbitrary download URLs. */
export const featuredGame = Object.freeze({
 id:'from-below-1.0', title:'From Below', bytes:40976,
 sha256:'1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555',
} as const);
export type CatalogId = typeof featuredGame.id;
export const featuredAssetPath = `/catalog/from-below-${featuredGame.sha256}.nes`;
export function catalogId(fingerprint:Fingerprint):CatalogId|undefined {
 const c=fingerprint.cartridge;
 return fingerprint.romSha256===featuredGame.sha256 && c.bytes===featuredGame.bytes && c.format==='iNES' && c.mapper===0 && c.submapper===0 && c.region==='NTSC' ? featuredGame.id : undefined;
}
