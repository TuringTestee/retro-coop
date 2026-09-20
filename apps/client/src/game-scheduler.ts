import {gameplayLimits,type GamePacket} from '../../../packages/contracts/src/gameplay.ts';
/** Keep the fixed proposal within the approved bounds; reserve two frames beyond
 * the observed transport round trip so uneven worker progress has input headroom. */
export function proposeInputDelay(roundTripMs:number,fps:number) {
 if(!Number.isFinite(roundTripMs)||roundTripMs<0||!Number.isFinite(fps)||fps<=0)return gameplayLimits.delayDefault;
 return Math.min(gameplayLimits.delayMax,Math.max(gameplayLimits.delayDefault,Math.ceil(roundTripMs*fps/1000)+2));
}
/** Deterministic frame admission. Missing input never predicts or advances a frame. */
export class GameScheduler {
 private local=new Map<number,number>();
 private remote=new Map<number,number>();
 private hashes=new Map<number,string>();
 private peerHashes=new Map<number,string>();
 private sent=0;private receivedHash=0;
 frame=0;
 readonly epoch:string;readonly delay:number;private send:(packet:GamePacket)=>void;
 constructor(epoch:string,delay:number,send:(packet:GamePacket)=>void) {
  this.epoch=epoch;this.delay=delay;this.send=send;
  if(!Number.isInteger(delay)||delay<gameplayLimits.delayMin||delay>gameplayLimits.delayMax) throw Error('Invalid input delay');
 }
 sample(mask:number) {
  // Each sampled input becomes immutable once sent; seed only the negotiated delay with zero.
  while(this.sent<=this.frame+this.delay) {const frame=this.sent++,value=frame<this.delay?0:mask;this.local.set(frame,value);this.send({kind:'input',epoch:this.epoch,frame,mask:value});}
 }
 receive(packet:GamePacket) {
  if(packet.epoch!==this.epoch) return; // A prior timeline has no authority over this one.
  if(packet.kind==='input') {
   if(packet.frame<this.frame||packet.frame>this.frame+gameplayLimits.inputWindow||this.remote.has(packet.frame)) throw Error('Invalid or duplicate frame input');
   this.remote.set(packet.frame,packet.mask);
  } else {
   if(packet.frame!==this.receivedHash+gameplayLimits.hashInterval||packet.frame<this.frame-gameplayLimits.inputWindow||packet.frame>this.frame+gameplayLimits.inputWindow||this.peerHashes.has(packet.frame)) throw Error('Invalid or duplicate frame hash');
   this.receivedHash=packet.frame;this.peerHashes.set(packet.frame,packet.hash);this.compare(packet.frame);
  }
 }
 next():[number,number]|undefined {const local=this.local.get(this.frame),remote=this.remote.get(this.frame);return local===undefined||remote===undefined?undefined:[local,remote];}
 commit() {if(!this.next()) throw Error('Cannot commit missing input');this.local.delete(this.frame);this.remote.delete(this.frame);this.frame++;}
 hash(hash:string) {if(this.hashes.size>=2) throw Error('Peer state hashes stopped arriving');if(this.frame%gameplayLimits.hashInterval!==0) throw Error('Hash outside committed interval');this.hashes.set(this.frame,hash);this.send({kind:'hash',epoch:this.epoch,frame:this.frame,hash});this.compare(this.frame);}
 private compare(frame:number) {const ours=this.hashes.get(frame),theirs=this.peerHashes.get(frame);if(ours&&theirs) {if(ours!==theirs) throw Error('Canonical state mismatch');this.hashes.delete(frame);this.peerHashes.delete(frame);}}
}
