import {gameplayLimits,type GamePacket,type FramePacket,type LeasePacket,type InputPacket} from '../../../packages/contracts/src/gameplay.ts';
export type TimelineMembers={local:string;authority:string;controllers:readonly [string|undefined,string|undefined];revision:number;observer?:boolean};
type Control={held:number;press?:number;expiresAt:number;sequence:number;generation:string;lease:string};
/** The host chooses immutable native commands. Peer input and hashes never gate dispatch. */
export class GameScheduler {
 readonly epoch:string;readonly authority:boolean;
 frame:number;
 private head:number;private start:number;private historyStart:number;
 private members:TimelineMembers;private assignment?:{controllers:TimelineMembers['controllers'];revision:number};
 private local={held:0,press:undefined as number|undefined};
 private leases=new Map<string,LeasePacket>();private controls=new Map<string,Control>();
 private frames=new Map<number,FramePacket>();private dispatched?:FramePacket;
 private hashes=new Map<number,string>();private peerHashes=new Map<string,Map<number,string>>();private receivedHashes=new Map<string,number>();private faults=new Set<string>();
 private historyFrames=new Float64Array(gameplayLimits.historyFrames);private historyRevisions=new Float64Array(gameplayLimits.historyFrames);
 private historyMasks=new Uint8Array(gameplayLimits.historyFrames*2);
 private send:(packet:GamePacket)=>void;private now:()=>number;
 constructor(epoch:string,members:TimelineMembers,send:(packet:GamePacket)=>void,start=0,now=()=>performance.now()) {
  this.members=members;this.send=send;this.now=now;this.epoch=epoch;
  this.frame=this.head=this.start=this.historyStart=start;this.authority=members.local===members.authority;
  if(!Number.isSafeInteger(start)||start<0||!Number.isSafeInteger(members.revision)||members.revision<0||!members.local||!members.authority)throw Error('Invalid timeline configuration');
 }
 configure(controllers:TimelineMembers['controllers'],revision:number){
  if(revision<this.members.revision)throw Error('Superseded controller assignment');
  this.assignment={controllers,revision};if(!this.dispatched)this.applyAssignment();
 }
 private applyAssignment(){const assignment=this.assignment;if(!assignment)return;this.assignment=undefined;
  const changed=assignment.controllers.some((owner,index)=>owner!==this.members.controllers[index]);
  if(changed||assignment.revision!==this.members.revision){this.leases.clear();this.controls.clear();this.releaseLocal();}
  this.members={...this.members,...assignment};
 }
 get revision(){return this.members.revision;}
 sample(mask:number,release=false){
  if(!this.members.controllers.includes(this.members.local))return;
  if(release){this.releaseLocal();return;}
  if(mask&~this.local.held)this.local.press=mask;
  this.local.held=mask;
 }
 releaseLocal(){this.local={held:0,press:undefined};}
 revoke(member:string){this.controls.delete(member);this.leases.delete(member);this.peerHashes.delete(member);this.receivedHashes.delete(member);}
 grant(member:string,generation:string,lease:string):LeasePacket|undefined {
  if(!this.authority||!this.members.controllers.includes(member)||member===this.members.local)return;
  const packet:LeasePacket={kind:'lease',epoch:this.epoch,revision:this.revision,generation,lease,expiresAt:this.now()+gameplayLimits.leaseMs};
  this.leases.set(member,packet);return packet;
 }
 lease(member:string){return this.leases.get(member);}
 private acceptInput(packet:InputPacket,member:string){
  if(!this.authority||!this.members.controllers.includes(member)||member===this.members.local)throw Error('Input sender has no controller authority');
  const grant=this.leases.get(member),previous=this.controls.get(member);
  if(!grant||packet.revision!==this.revision||packet.generation!==grant.generation||packet.lease!==grant.lease||this.now()>=grant.expiresAt||previous?.generation===packet.generation&&packet.sequence<=previous.sequence)return false;
  const held=previous&&previous.expiresAt>this.now()?previous.held:0;
  const press=packet.release?undefined:(packet.mask&~held)?packet.mask:previous&&previous.lease===packet.lease&&previous.expiresAt>this.now()?previous.press:undefined;
  this.controls.set(member,{held:packet.mask,press,expiresAt:grant.expiresAt,sequence:packet.sequence,generation:packet.generation,lease:packet.lease});return true;
 }
 receive(packet:GamePacket,member:string){
  if(packet.epoch!==this.epoch)return false;
  if(packet.kind==='input')return this.acceptInput(packet,member);
  if(packet.kind==='lease')throw Error('Lease belongs to the input transport');
  if(packet.kind==='frame'){
   if(this.authority||member!==this.members.authority)throw Error('Only the host can commit frames');
   if(packet.frame!==this.head||packet.frame>=this.frame+gameplayLimits.historyFrames)throw Error('Invalid or duplicate committed frame');
   this.frames.set(packet.frame,packet);this.head++;return true;
  }
  if(!this.authority&&member!==this.members.authority)return false;
  const previous=this.receivedHashes.get(member)??0;
  if(packet.frame<=previous) return false;
  if(packet.frame<this.frame-gameplayLimits.historyFrames)return false;
  if(packet.frame>(this.authority?this.frame:this.head))throw Error('Hash exceeds confirmed history');
  this.receivedHashes.set(member,packet.frame);let hashes=this.peerHashes.get(member);if(!hashes)this.peerHashes.set(member,hashes=new Map());
  hashes.set(packet.frame,packet.hash);this.prune();this.compare(packet.frame);return true;
 }
 next():[number,number]|undefined {
  if(this.dispatched)return [this.dispatched.p1,this.dispatched.p2];
  if(!this.authority){const packet=this.frames.get(this.frame);if(packet){this.dispatched=packet;return [packet.p1,packet.p2];}return;}
  this.applyAssignment();const masks=this.members.controllers.map(owner=>{
   if(!owner)return 0;
   if(owner===this.members.local){const mask=this.local.press??this.local.held;this.local.press=undefined;return mask;}
   const control=this.controls.get(owner);if(!control||control.expiresAt<=this.now()){this.controls.delete(owner);return 0;}
   const mask=control.press??control.held;control.press=undefined;return mask;
  });
  this.dispatched=Object.freeze({kind:'frame',epoch:this.epoch,stream:this.epoch,revision:this.revision,frame:this.frame,p1:masks[0],p2:masks[1]});
  return [masks[0],masks[1]];
 }
 commit(){
  const packet=this.dispatched;if(!packet||packet.frame!==this.frame)throw Error('Cannot commit an undispatched frame');
  this.dispatched=undefined;const frame=this.frame++;
  if(this.authority){const i=frame%gameplayLimits.historyFrames;this.historyFrames[i]=frame;this.historyRevisions[i]=packet.revision;this.historyMasks[i*2]=packet.p1;this.historyMasks[i*2+1]=packet.p2;this.historyStart=Math.max(this.start,this.frame-gameplayLimits.historyFrames);this.send(packet);}
  else this.frames.delete(frame);
  this.applyAssignment();this.prune();
 }
 historyFrame(frame:number):FramePacket|undefined {
  if(!this.authority||frame<this.historyStart||frame>=this.frame)return;const i=frame%gameplayLimits.historyFrames;if(this.historyFrames[i]!==frame)return;
  return {kind:'frame',epoch:this.epoch,stream:this.epoch,revision:this.historyRevisions[i],frame,p1:this.historyMasks[i*2],p2:this.historyMasks[i*2+1]};
 }
 historySince(frame:number):FramePacket[]|undefined {
  if(!this.authority||frame<this.historyStart||frame>this.frame)return;const result:FramePacket[]=[];
  for(let f=frame;f<this.frame;f++){const packet=this.historyFrame(f);if(!packet)return;result.push(packet);}return result;
 }
 hash(hash:string){
  if(this.frame%gameplayLimits.hashInterval!==0)throw Error('Hash outside committed interval');
  this.hashes.set(this.frame,hash);this.prune();this.send({kind:'hash',epoch:this.epoch,stream:this.epoch,frame:this.frame,hash});this.compare(this.frame);
 }
 takeFaults(){const peers=[...this.faults];this.faults.clear();return peers;}
 private prune(){const oldest=this.frame-gameplayLimits.historyFrames;for(const frame of this.hashes.keys())if(frame<oldest)this.hashes.delete(frame);for(const hashes of this.peerHashes.values())for(const frame of hashes.keys())if(frame<oldest)hashes.delete(frame);}
 private compare(frame:number){const ours=this.hashes.get(frame);if(!ours)return;
  for(const [member,hashes] of this.peerHashes){const theirs=hashes.get(frame);if(theirs===undefined)continue;hashes.delete(frame);if(ours!==theirs){if(this.authority)this.faults.add(member);else throw Error('Canonical state mismatch');}}
 }
}
