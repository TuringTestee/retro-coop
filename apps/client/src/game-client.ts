import {gameplayLimits,parseGamePacket,type GameCommand,type GameEvent,type GamePacket,type GameReason} from '../../../packages/contracts/src/gameplay.ts';
import {matchesFile,type Fingerprint,type RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {LocalPlayer} from './player.ts';
import {GameScheduler} from './game-scheduler.ts';
type Command=GameCommand extends infer T?T extends GameCommand?Omit<T,'requestId'>:never:never;
export type GameplayState={status:string;frame:number;delay?:number;hash?:string;busy:boolean};
/** Coordinates one installed peer receiver, one worker and one acknowledged timeline. */
export class GameClient {
 private room?:RoomView;private file?:Fingerprint;private intent=false;private renew=false;
 private channel?:RTCDataChannel;private peerEpoch?:string;private inspect?:string;
 private scheduler?:GameScheduler;private prepared?:{epoch:string;delay:number};private early:GamePacket[]=[];
 private serial=0;private offering=false;private offered?:string;private controlled=false;
 private fence?:number;private awaitingFence=false;private pausedSent=false;private hashing=false;private missingSince=0;
 private state:GameplayState={status:'Choose matching games to prepare shared play.',frame:0,busy:false};
 constructor(private player:()=>LocalPlayer|null,private send:(command:Command)=>Promise<unknown>,private update:(state:GameplayState)=>void){}
 private publish(patch:Partial<GameplayState>){this.state={...this.state,...patch};this.update(this.state);}
 enter(room?:RoomView){
  const previous=this.room;
  if(previous && (!room||previous.id!==room.id||previous.role!==room.role||(previous.role==='guest'&&previous.reservationIntent!==room.reservationIntent)))this.clear('Room membership changed. Shared play stopped.',true);
  this.room=room;if(!room)return;
  void this.offerGuest();
 }
 selected(file:Fingerprint){this.file=file;this.intent=true;this.offered=undefined;void this.offerGuest();}
 playIntent(){this.intent=true;this.offered=undefined;void this.offerGuest();}
 cancelIntent(){if(!this.room?.established){this.intent=false;++this.serial;this.offered=undefined;}}
 retry(){this.intent=true;this.offered=undefined;void this.offerGuest();}
 retryConnection(){this.renew=true;}
 ready(channel:RTCDataChannel,epoch:string){
  this.channel=channel;this.peerEpoch=epoch;if(this.renew){this.intent=true;this.renew=false;}
  channel.onmessage=({data})=>this.receive(data);
  if(this.inspect===epoch){this.inspect=undefined;void this.offer();}else void this.offerGuest();
 }
 closed(epoch?:string){if(epoch&&epoch===this.peerEpoch){this.peerEpoch=undefined;this.channel=undefined;this.clear('Connection changed. Shared play is paused; retry explicitly.');}}
 private clear(status:string,leave=false){
  ++this.serial;this.intent=false;this.offered=undefined;this.offering=false;this.prepared=undefined;this.scheduler=undefined;this.early=[];this.fence=undefined;this.awaitingFence=false;this.hashing=false;
  if(this.controlled)this.player()?.stopGame(status,leave);if(leave)this.player()?.allowLocalPlay();this.controlled=false;this.publish({status,busy:false});
 }
 private eligible(){return !!this.intent&&!!this.room&&!!this.file&&matchesFile(this.room.fingerprint,this.file)&&this.room.matches&&this.channel?.readyState==='open'&&this.peerEpoch===this.room.peer.epoch;}
 private async offerGuest(){if(this.room?.role==='guest'&&!this.room.established&&this.eligible())await this.offer();}
 private async offer(){
  const room=this.room,peerEpoch=this.peerEpoch,player=this.player();if(!room||!peerEpoch||!player||!this.eligible()||this.offering)return;
  const key=room.id+peerEpoch+this.file!.romSha256;if(this.offered===key)return;
  this.offered=key;this.offering=true;const serial=this.serial;this.controlled=true;
  this.publish({busy:true,status:'Checking the committed machine state…'});
  try{
   const info=await player.holdForGame();if(serial!==this.serial||!this.eligible())return;
   await this.send({type:'gameReady',peerEpoch,...info,delay:gameplayLimits.delayDefault});
   this.publish({busy:false,status:room.established?'Ready to resume. Waiting for the host and other player.':'Waiting for the matching initial-state barrier…'});
  }catch(error){if(serial===this.serial)this.clear(error instanceof Error?error.message:'Shared game could not prepare.',!room.established);}
  finally{if(serial===this.serial)this.offering=false;}
 }
 async resumeReady(){this.intent=true;this.offered=undefined;await this.offer();}
 async resumeTogether(){const epoch=this.room?.game?.epoch;if(epoch)try{await this.send({type:'gameResume',epoch});}catch(error){this.publish({status:String(error),busy:false});}}
 handle(event:GameEvent){
  if(event.type==='gameInspect') {if(this.peerEpoch!==event.peerEpoch){this.inspect=event.peerEpoch;return;}void this.offer();return;}
  if(event.type==='gameStop'){this.clear(event.reason);return;}
  if(event.type==='gamePauseAt'){
   const scheduler=this.scheduler;if(!scheduler||event.epoch!==scheduler.epoch)return;
   if(event.frame<scheduler.frame||event.frame>scheduler.frame+gameplayLimits.inputWindow){this.fail('Invalid pause boundary.','network');return;}
   this.fence=event.frame;this.awaitingFence=false;this.publish({status:event.reason,busy:true});this.player()?.drainGame();return;
  }
  if(event.peerEpoch!==this.peerEpoch||!this.eligible())return;
  if(event.type==='gamePrepare'){
   const serial=this.serial;this.prepared={epoch:event.epoch,delay:event.delay};this.early=[];this.publish({status:'Starting together…',busy:true});
   void this.player()!.holdForGame().then(info=>{if(serial!==this.serial||this.prepared?.epoch!==event.epoch)return;if(info.hash!==event.hash)throw Error('State changed during the start barrier.');return this.send({type:'gameAck',epoch:event.epoch,hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'mismatch');});
  }else if(event.type==='gameStart'){
   if(this.prepared?.epoch!==event.epoch)return;
   const scheduler=new GameScheduler(event.epoch,event.delay,packet=>this.channel!.send(JSON.stringify(packet)));this.scheduler=scheduler;
   this.fence=undefined;this.awaitingFence=false;this.pausedSent=false;this.hashing=false;this.missingSince=0;
   try{for(const packet of this.early)scheduler.receive(packet);this.early=[];
    this.player()!.startGame({epoch:event.epoch,next:mask=>this.next(mask),committed:frame=>this.committed(frame),pause:reason=>this.pause(reason),draining:()=>this.fence!==undefined});
    this.publish({status:'Playing together.',frame:0,delay:event.delay,busy:false});
   }catch(error){this.fail(String(error),'network');}
  }
 }
 private receive(raw:unknown){
  const packet=parseGamePacket(raw);if(!packet){this.fail('Invalid gameplay message.','network');return;}
  if(packet.epoch!==this.prepared?.epoch)return;
  try{
   if(this.scheduler){this.scheduler.receive(packet);if(this.fence!==undefined)this.player()?.drainGame();}
   else {if(this.early.length>=gameplayLimits.inputWindow||packet.frame>gameplayLimits.inputWindow)throw Error('Too much input before start');this.early.push(packet);}
  }catch(error){this.fail(String(error),'mismatch');}
 }
 private next(mask:number){
  const scheduler=this.scheduler;if(!scheduler||this.awaitingFence||this.hashing||this.pausedSent)return;
  if(this.fence!==undefined&&scheduler.frame>=this.fence){void this.finishPause();return;}
  try{
   scheduler.sample(this.fence!==undefined?0:mask);const input=scheduler.next();
   if(!input){this.missingSince ||= performance.now();this.publish({status:'Waiting for the other player’s input. Emulation is stopped.'});if(performance.now()-this.missingSince>gameplayLimits.stallMs)this.fail('Input stream stalled. Shared play is paused.','network');return;}
   if(this.missingSince)this.publish({status:'Playing together.'});this.missingSince=0;return {frame:scheduler.frame,p1:input[this.room?.role==='host'?0:1],p2:input[this.room?.role==='host'?1:0]};
  }catch(error){this.fail(String(error),'network');}
 }
 private committed(frame:number){
  const scheduler=this.scheduler;if(!scheduler||frame!==scheduler.frame)return;
  scheduler.commit();this.publish({frame:scheduler.frame});
  if(this.fence!==undefined&&scheduler.frame===this.fence){void this.finishPause();return;}
  if(scheduler.frame%gameplayLimits.hashInterval===0){this.hashing=true;const serial=this.serial;
   void this.player()!.stateHash().then(info=>{if(serial!==this.serial)return;scheduler.hash(info.hash);this.publish({hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'mismatch');}).finally(()=>{if(serial===this.serial){this.hashing=false;if(this.fence!==undefined)this.player()?.drainGame();}});
  }
 }
 private pause(reason:GameReason){
  const scheduler=this.scheduler;if(!scheduler||this.awaitingFence||this.fence!==undefined)return;
  this.awaitingFence=true;this.publish({status:'Pausing both players at a common frame…',busy:true});
  void this.send({type:'gamePause',epoch:scheduler.epoch,frame:scheduler.frame+scheduler.delay+1,reason}).catch(error=>this.fail(String(error),'network'));
 }
 private async finishPause(){
  const scheduler=this.scheduler;if(!scheduler||this.pausedSent)return;this.pausedSent=true;
  try{const info=await this.player()!.stateHash();if(this.scheduler!==scheduler)return;this.player()!.stopGame('Paused at the shared frame. Both players must acknowledge readiness.');await this.send({type:'gamePaused',epoch:scheduler.epoch,frame:scheduler.frame,hash:info.hash});}
  catch(error){if(this.scheduler===scheduler)this.fail(String(error),'mismatch');}
 }
 private fail(status:string,reason:GameReason){const epoch=this.scheduler?.epoch??this.prepared?.epoch;this.clear(status);if(epoch)void this.send({type:'gameAbort',epoch,reason}).catch(()=>{});}
 dispose(){this.clear('Shared game closed.',true);this.channel=undefined;}
}
