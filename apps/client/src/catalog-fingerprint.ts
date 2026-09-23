import coreUrl from './generated/retro_coop_d02.wasm?url';
import {catalogEntry,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {LOCAL_SCHEMA,LOCAL_SETTINGS,type Fingerprint} from '../../../packages/contracts/src/fingerprint.ts';
import {hex} from './cartridge.ts';

let coreHash:Promise<string>|undefined;
async function loadedCoreHash():Promise<string> {
 coreHash??=fetch(coreUrl,{credentials:'omit',redirect:'error'}).then(async response=>{
  if(!response.ok)throw Error('The emulator is unavailable. Retry joining this room.');
  return hex(await crypto.subtle.digest('SHA-256',await response.arrayBuffer()));
 }).catch(error=>{coreHash=undefined;throw error;});
 return coreHash;
}

/** Claim Host before downloading a ROM, using the same immutable file/core identity the worker later checks. */
export async function catalogFingerprint(id:CatalogId):Promise<Fingerprint> {
 const entry=catalogEntry(id);
 return {romSha256:entry.sha256,coreSha256:await loadedCoreHash(),localSchema:LOCAL_SCHEMA,settings:LOCAL_SETTINGS,cartridge:{format:entry.format,mapper:entry.mapper,submapper:entry.submapper,region:entry.region,bytes:entry.bytes}};
}
