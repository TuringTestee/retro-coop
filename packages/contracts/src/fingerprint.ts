import {object,keys,integer,sha256} from './protocol-validation.ts';
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
 return [value.romSha256,value.coreSha256].every(sha256) && value.localSchema === LOCAL_SCHEMA && value.settings === LOCAL_SETTINGS && object(cart) && keys(cart,['format','mapper','submapper','region','bytes']) && ['iNES','NES 2.0'].includes(cart.format as string) && integer(cart.mapper,0,4095) && integer(cart.submapper,0,15) && ['NTSC','PAL','Multi-region','Dendy'].includes(cart.region as string) && integer(cart.bytes,16,Number.MAX_SAFE_INTEGER);
}
export function fileIdentity(value:Fingerprint) {return JSON.stringify([value.romSha256,value.coreSha256,value.localSchema,value.settings]);}
export function matchesFile(a:Fingerprint,b:Fingerprint) { return fileIdentity(a)===fileIdentity(b); }

/** Structural admission shared by browser selection and coordinator upload. */
export function inspectCartridge(bytes: Uint8Array,totalBytes=bytes.length): Cartridge {
 if (bytes.length < 16 || bytes[0] !== 0x4e || bytes[1] !== 0x45 || bytes[2] !== 0x53 || bytes[3] !== 0x1a) {
  throw Error('This is not an NES cartridge. Choose an uncompressed .nes file; archives and disk images are not supported.');
 }
 const nes2 = (bytes[7] & 12) === 8;
 if (!nes2 && (bytes[7] & 12) !== 0) throw Error('This NES header format is unsupported. Choose an iNES or NES 2.0 cartridge.');
 const size = (low: number, high: number, unit: number) => high === 15 ? 2 ** (low >> 2) * ((low & 3) * 2 + 1) : (low + high * 256) * unit;
 const prg = size(bytes[4], nes2 ? bytes[9] & 15 : 0, 16384);
 const chr = size(bytes[5], nes2 ? bytes[9] >> 4 : 0, 8192);
 const required = 16 + (bytes[6] & 4 ? 512 : 0) + prg + chr;
 if (!prg || !Number.isSafeInteger(required) || required > totalBytes) throw Error('This cartridge is incomplete or declares more data than the file contains. Choose a complete .nes file.');
 return { format: nes2 ? 'NES 2.0' : 'iNES', mapper: (bytes[6] >> 4) | (bytes[7] & 240) | (nes2 ? (bytes[8] & 15) << 8 : 0), submapper: nes2 ? bytes[8] >> 4 : 0, region: nes2 ? ['NTSC','PAL','Multi-region','Dendy'][bytes[12] & 3] : bytes[9] & 1 ? 'PAL' : 'NTSC', bytes: totalBytes };
}
