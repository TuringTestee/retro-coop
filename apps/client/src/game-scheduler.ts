import {gameplayLimits,type GamePacket,type FramePacket} from '../../../packages/contracts/src/gameplay.ts';
export function proposeInputDelay(roundTripMs:number,fps:number) {
 if(!Number.isFinite(roundTripMs)||roundTripMs<0||!Number.isFinite(fps)||fps<=0)return gameplayLimits.delayDefault;
 return Math.min(gameplayLimits.delayMax,Math.max(gameplayLimits.delayDefault,Math.ceil(roundTripMs*fps/1000)+2));
}
export type TimelineMembers={local:string;authority:string;controllers:readonly [string|undefined,string|undefined]};
/** The host admits assigned input; replicas execute only completed authoritative frames. */
export class GameScheduler {
 readonly epoch:string;readonly delay:number;readonly authority:boolean;
 frame:number;
 private start:number;private head:number;private sent:number;
 private owners:Set<string>;private inputs=new Map<string,Map<number,number>>();
 private frames=new Map<number,FramePacket>();private hashes=new Map<number,string>();
 private peerHashes=new Map<string,Map<number,string>>();private receivedHashes=new Map<string,number>();
 private historyFrames=new Float64Array(gameplayLimits.historyFrames);
 private historyMasks=new Uint8Array(gameplayLimits.historyFrames*2);private historyStart:number;
 private members:TimelineMembers;private send:(packet:GamePacket)=>void;
 constructor(epoch:string,delay:number,members:TimelineMembers,send:(packet:GamePacket)=>void,start=0) {
  this.members=members;this.send=send;
  this.epoch=epoch;this.delay=delay;this.frame=this.head=this.sent=this.start=this.historyStart=start;this.authority=members.local===members.authority;
  if(!Number.isInteger(delay)||delay<gameplayLimits.delayMin||delay>gameplayLimits.delayMax||!Number.isSafeInteger(start)||start<0||!members.local||!members.authority)throw Error('Invalid timeline configuration');
  this.owners=new Set(members.controllers.filter((id):id is string=>id!==undefined));
  for(const owner of this.owners)this.inputs.set(owner,new Map());
 }
 sample(mask:number) {
  if(!this.owners.has(this.members.local))return;
  const target=(this.authority?this.frame:this.head)+this.delay;
  while(this.sent<=target){const frame=this.sent++,value=frame<this.start+this.delay?0:mask;
   if(this.authority)this.inputs.get(this.members.local)!.set(frame,value);
   else this.send({kind:'input',epoch:this.epoch,frame,mask:value});
  }
 }
 receive(packet:GamePacket,member:string) {
  if(packet.epoch!==this.epoch)return false;
  if(packet.kind==='input') {
   if(!this.authority||!this.owners.has(member)||member===this.members.local)throw Error('Input sender has no controller authority');
   const queue=this.inputs.get(member)!;
   if(packet.frame<this.frame||packet.frame>this.frame+gameplayLimits.inputWindow||queue.has(packet.frame))throw Error('Invalid or duplicate frame input');
   queue.set(packet.frame,packet.mask);
  } else if(packet.kind==='frame') {
   if(this.authority||member!==this.members.authority)throw Error('Only the host can commit frames');
   if(packet.frame!==this.head||packet.frame>=this.frame+gameplayLimits.inputWindow)throw Error('Invalid or duplicate committed frame');
   this.frames.set(packet.frame,packet);this.head++;
  } else {
   const expected=this.authority?this.owners.has(member)&&member!==this.members.local:member===this.members.authority;
   if(!expected)return false;
   const previous=this.receivedHashes.get(member)??Math.floor(this.start/gameplayLimits.hashInterval)*gameplayLimits.hashInterval;
   if(packet.frame!==previous+gameplayLimits.hashInterval||packet.frame<this.frame-gameplayLimits.inputWindow||packet.frame>this.frame+gameplayLimits.inputWindow)throw Error('Invalid or duplicate frame hash');
   this.receivedHashes.set(member,packet.frame);
   let hashes=this.peerHashes.get(member);if(!hashes)this.peerHashes.set(member,hashes=new Map());hashes.set(packet.frame,packet.hash);this.compare(packet.frame);
  }
  return true;
 }
 next():[number,number]|undefined {
  if(!this.authority){const packet=this.frames.get(this.frame);return packet?[packet.p1,packet.p2]:undefined;}
  const masks:number[]=[];
  for(const owner of this.members.controllers){const mask=owner===undefined?0:this.inputs.get(owner)?.get(this.frame);if(mask===undefined)return;masks.push(mask);}
  return masks as [number,number];
 }
 commit() {
  const next=this.next();if(!next)throw Error('Cannot commit missing input');const frame=this.frame++;
  if(this.authority){for(const queue of this.inputs.values())queue.delete(frame);const i=frame%gameplayLimits.historyFrames;this.historyFrames[i]=frame;this.historyMasks[i*2]=next[0];this.historyMasks[i*2+1]=next[1];this.historyStart=Math.max(this.start,this.frame-gameplayLimits.historyFrames);this.send({kind:'frame',epoch:this.epoch,frame,p1:next[0],p2:next[1]});}
  else this.frames.delete(frame);
 }
 /** A fixed 20 KiB ring owns catch-up history; no observer can extend retention. */
 historySince(frame:number):FramePacket[]|undefined {
  if(!this.authority||frame<this.historyStart||frame>this.frame)return;
  const result:FramePacket[]=[];
  for(let f=frame;f<this.frame;f++){const i=f%gameplayLimits.historyFrames;if(this.historyFrames[i]!==f)return;result.push({kind:'frame',epoch:this.epoch,frame:f,p1:this.historyMasks[i*2],p2:this.historyMasks[i*2+1]});}
  return result;
 }
 hash(hash:string) {
  if(this.hashes.size>=2)throw Error('Peer state hashes stopped arriving');
  if(this.frame%gameplayLimits.hashInterval!==0)throw Error('Hash outside committed interval');
  this.hashes.set(this.frame,hash);
  if(this.authority||this.owners.has(this.members.local))this.send({kind:'hash',epoch:this.epoch,frame:this.frame,hash});
  this.compare(this.frame);
 }
 private compare(frame:number) {
  const ours=this.hashes.get(frame);if(!ours)return;
  const expected=this.authority?[...this.owners].filter(member=>member!==this.members.local):[this.members.authority];
  if(expected.some(member=>!this.peerHashes.get(member)?.has(frame)))return;
  for(const member of expected){const theirs=this.peerHashes.get(member)!.get(frame);if(ours!==theirs)throw Error('Canonical state mismatch');this.peerHashes.get(member)!.delete(frame);}
  this.hashes.delete(frame);
 }
}
