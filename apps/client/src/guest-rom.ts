import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import {clientConfig} from './config.ts';
import {verifiedDownload} from './verified-download.ts';
import {acquireVerifiedRom,type AcquiredRom} from './rom-acquisition.ts';

export type GuestRomResult=AcquiredRom;

/** RT4 supplies current() from its room and operation generation before loading or preparing. */
export async function acquireGuestRom(room:RoomView,token:string,signal:AbortSignal,progress:(bytes:number)=>void,current:()=>boolean,fetcher:typeof fetch=fetch):Promise<GuestRomResult> {
 if(room.role!=='guest' || room.catalogId)throw Error('This room does not have a host-shared game.');
 const membership=room.chatMembership,expected=room.fingerprint;
 const check=()=>{signal.throwIfAborted();if(!current())throw Error('The room changed. Return to rooms and join again.');};
 return acquireVerifiedRom({bytes:expected.cartridge.bytes,sha256:expected.romSha256},'room-game.nes',signal,current,async()=>{
  check();const endpoint=new URL(clientConfig.coordinatorUrl,location.href);endpoint.pathname=endpoint.pathname.replace(/\/$/,'')+`/rooms/${encodeURIComponent(room.id)}/rom`;endpoint.search='';endpoint.hash='';
  let response:Response;
  try{response=await fetcher(endpoint,{method:'GET',headers:{Authorization:`Bearer ${token}`,'X-Room-Membership':membership},signal,credentials:'omit',redirect:'error',cache:'no-store'});}catch(error){check();throw Error('The room game could not download. Retry download.',{cause:error});}
  check();if(!response.ok)throw Error(response.status===403?'Your room place expired. Return to rooms.':'The room game could not download. Retry download.');
  return verifiedDownload(response,{bytes:expected.cartridge.bytes,sha256:expected.romSha256},signal,progress);
 });
}
