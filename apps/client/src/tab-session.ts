/** A duplicated browser tab copies sessionStorage, but must not take over its source tab's room session. */
export class TabSession {
 private channel?:BroadcastChannel;
 private readonly id=crypto.randomUUID();
 private readonly opened=performance.timeOrigin;
 private pending=new Map<string,(claimed:boolean)=>void>();
 constructor(private token:()=>string|undefined) {
  if(typeof BroadcastChannel==='undefined')return;
  this.channel=new BroadcastChannel('retro-coop-room-tabs');
  this.channel.onmessage=({data})=>{
   if(!data||data.token!==this.token()||data.sender===this.id)return;
   if(data.type==='probe'&&typeof data.request==='string') {
    // The older tab keeps its session, including when both tabs open at once.
    if(this.opened<data.opened||this.opened===data.opened&&this.id<data.sender)
     this.channel?.postMessage({type:'claimed',token:data.token,request:data.request,sender:this.id});
   } else if(data.type==='claimed'&&typeof data.request==='string')this.pending.get(data.request)?.(true);
  };
 }
 async alreadyClaimed(token:string):Promise<boolean> {
  if(!this.channel)return false;
  const request=crypto.randomUUID();
  return new Promise(resolve=>{
   const timer=setTimeout(()=>{this.pending.delete(request);resolve(false);},120);
   this.pending.set(request,claimed=>{clearTimeout(timer);this.pending.delete(request);resolve(claimed);});
   this.channel!.postMessage({type:'probe',token,request,sender:this.id,opened:this.opened});
  });
 }
 close(){this.channel?.close();this.channel=undefined;for(const done of this.pending.values())done(false);this.pending.clear();}
}
