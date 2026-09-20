import {object,keys,integer} from './protocol-validation.ts';
/** Exact browser-local cartridge identity shared by player and room compatibility. */
export const LOCAL_SCHEMA = 1;
export const LOCAL_SETTINGS = 'auto-region;zero-ram;48000hz;standard-p1-p2';
export type Cartridge = {format:'iNES'|'NES 2.0';mapper:number;submapper:number;region:string;bytes:number};
export type Fingerprint = {
 romSha256: string; coreSha256: string; localSchema: typeof LOCAL_SCHEMA;
 settings: typeof LOCAL_SETTINGS;
 cartridge: Cartridge;
};

export function validFingerprint(value:unknown): value is Fingerprint {
 if(!object(value) || !keys(value,['romSha256','coreSha256','localSchema','settings','cartridge'])) return false;
 const cart = value.cartridge;
 return [value.romSha256,value.coreSha256].every(hash => typeof hash === 'string' && /^[a-f0-9]{64}$/.test(hash)) && value.localSchema === LOCAL_SCHEMA && value.settings === LOCAL_SETTINGS && object(cart) && keys(cart,['format','mapper','submapper','region','bytes']) && ['iNES','NES 2.0'].includes(cart.format as string) && integer(cart.mapper,0,4095) && integer(cart.submapper,0,15) && ['NTSC','PAL','Multi-region','Dendy'].includes(cart.region as string) && integer(cart.bytes,16,Number.MAX_SAFE_INTEGER);
}
export function matchesFile(a:Fingerprint,b:Fingerprint) { return a.romSha256 === b.romSha256 && a.coreSha256 === b.coreSha256 && a.localSchema === b.localSchema && a.settings === b.settings; }
