/** Header admission only: the pinned emulator remains the authority on hardware support. */
export type {Cartridge} from '../../../packages/contracts/src/fingerprint.ts';
export {inspectCartridge} from '../../../packages/contracts/src/fingerprint.ts';
export function neutralDefaults(random: Uint32Array = crypto.getRandomValues(new Uint32Array(2))) {
 const colors = ['Amber','Azure','Coral','Indigo','Jade','Lilac','Silver','Teal'];
 const places = ['Arcade','Garden','Harbor','Lounge','Meadow','Orbit','Studio','Terrace'];
 return { guest: `Guest ${colors[random[0] % colors.length]} ${random[0] % 10000}`, room: `${colors[(random[1] >>> 8) % colors.length]} ${places[random[1] % places.length]}` };
}
export const hex = (bytes: ArrayBuffer) => [...new Uint8Array(bytes)].map(value => value.toString(16).padStart(2,'0')).join('');
