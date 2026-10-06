import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import {clientConfig} from './config.ts';
import {verifiedDownload} from './verified-download.ts';
import {acquireVerifiedRom,type AcquiredRom} from './rom-acquisition.ts';

export type MemberRomResult=AcquiredRom;
export class MemberReservationExpiredError extends Error {}

/** RT4 supplies current() from its room and operation generation before loading or preparing. */
export async function acquireMemberRom(room:RoomView,token:string,signal:AbortSignal,progress:(bytes:number)=>void,current:()=>boolean,fetcher:typeof fetch=fetch):Promise<MemberRomResult> {
 if(room.catalogId)throw Error('This lobby does not have a host-shared game.');
 const membership=room.chatMembership,expected=room.fingerprint;
 if(!expected)throw Error('Waiting for the host to choose a game.');
 const check=()=>{signal.throwIfAborted();if(!current())throw Error('The lobby changed. Return to lobbies and join again.');};
 return acquireVerifiedRom({bytes:expected.cartridge.bytes,sha256:expected.romSha256},'room-game.nes',signal,current,async()=>{
  check();const endpoint=new URL(clientConfig.coordinatorUrl,location.href);endpoint.pathname=endpoint.pathname.replace(/\/$/,'')+`/rooms/${encodeURIComponent(room.id)}/rom`;endpoint.search='';endpoint.hash='';
  let response:Response;
  try{response=await fetcher(endpoint,{method:'GET',headers:{Authorization:`Bearer ${token}`,'X-Room-Membership':membership},signal,credentials:'omit',redirect:'error',cache:'no-store'});}catch(error){check();throw Error('The lobby game could not download. Retry download.',{cause:error});}
  check();if(!response.ok)throw response.status===403?new MemberReservationExpiredError('Your lobby place expired. Return to lobbies.'):Error('The lobby game could not download. Retry download.');
  return verifiedDownload(response,{bytes:expected.cartridge.bytes,sha256:expected.romSha256},signal,progress);
 });
}
