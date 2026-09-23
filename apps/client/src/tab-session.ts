/** Hold an origin-wide lock so a copied tab cannot take over an active room session. */
export class TabSession {
 private token?:string;
 private release?:()=>void;
 private generation=0;
 async claim(token:string):Promise<boolean> {
  if(this.token===token)return true;
  this.close();
  if(!navigator.locks)return false;
  const generation=this.generation;
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token));
  if(generation!==this.generation)return false;
  const name='retro-coop-session-'+Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
  return new Promise(resolve=>{
   let settled=false;
   const finish=(claimed:boolean)=>{if(!settled){settled=true;resolve(claimed);}};
   void navigator.locks.request(name,{ifAvailable:true},async lock=>{
    if(!lock||generation!==this.generation){finish(false);return;}
    this.token=token;
    await new Promise<void>(release=>{this.release=release;finish(true);});
   }).catch(()=>finish(false));
  });
 }
 close(){++this.generation;this.release?.();this.release=undefined;this.token=undefined;}
}
