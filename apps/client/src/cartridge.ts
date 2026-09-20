/** Header admission only: the pinned emulator remains the authority on hardware support. */
import type {Cartridge} from '../../../packages/contracts/src/fingerprint.ts';
export type {Cartridge} from '../../../packages/contracts/src/fingerprint.ts';
export function inspectCartridge(bytes: Uint8Array): Cartridge {
 if (bytes.length < 16 || bytes[0] !== 0x4e || bytes[1] !== 0x45 || bytes[2] !== 0x53 || bytes[3] !== 0x1a) {
  throw Error('This is not an NES cartridge. Choose an uncompressed .nes file; archives and disk images are not supported.');
 }
 const nes2 = (bytes[7] & 12) === 8;
 if (!nes2 && (bytes[7] & 12) !== 0) throw Error('This NES header format is unsupported. Choose an iNES or NES 2.0 cartridge.');
 const size = (low: number, high: number, unit: number) => high === 15 ? 2 ** (low >> 2) * ((low & 3) * 2 + 1) : (low + high * 256) * unit;
 const prg = size(bytes[4], nes2 ? bytes[9] & 15 : 0, 16384);
 const chr = size(bytes[5], nes2 ? bytes[9] >> 4 : 0, 8192);
 const required = 16 + (bytes[6] & 4 ? 512 : 0) + prg + chr;
 if (!prg || !Number.isSafeInteger(required) || required > bytes.length) throw Error('This cartridge is incomplete or declares more data than the file contains. Choose a complete .nes file.');
 return { format: nes2 ? 'NES 2.0' : 'iNES', mapper: (bytes[6] >> 4) | (bytes[7] & 240) | (nes2 ? (bytes[8] & 15) << 8 : 0), submapper: nes2 ? bytes[8] >> 4 : 0, region: nes2 ? ['NTSC','PAL','Multi-region','Dendy'][bytes[12] & 3] : bytes[9] & 1 ? 'PAL' : 'NTSC', bytes: bytes.length };
}
export function neutralDefaults(random: Uint32Array = crypto.getRandomValues(new Uint32Array(2))) {
 const colors = ['Amber','Azure','Coral','Indigo','Jade','Lilac','Silver','Teal'];
 const places = ['Arcade','Garden','Harbor','Lounge','Meadow','Orbit','Studio','Terrace'];
 return { guest: `Guest ${colors[random[0] % colors.length]} ${random[0] % 10000}`, room: `${colors[(random[1] >>> 8) % colors.length]} ${places[random[1] % places.length]}` };
}
export const hex = (bytes: ArrayBuffer) => [...new Uint8Array(bytes)].map(value => value.toString(16).padStart(2,'0')).join('');
