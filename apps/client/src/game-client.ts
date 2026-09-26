import {CheckpointReceiver,CheckpointSender,checkpointDigest} from './checkpoint.ts';
import {parseCheckpointMetadata,CHECKPOINT_TIMEOUT_MS,CHECKPOINT_BUFFER_BYTES,CHECKPOINT_CHUNK_BYTES,CHECKPOINT_MAX_BYTES,type CheckpointMetadata} from '../../../packages/contracts/src/checkpoint.ts';
import {defaultControllers,gameplayLimits,parseGamePacket,type ControllerAssignment,type GameCommand,type GameEvent,type GamePacket,type GameReason} from '../../../packages/contracts/src/gameplay.ts';
import {matchesFile,type Fingerprint,type RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {LocalPlayer} from './player.ts';
import {GameScheduler,proposeInputDelay} from './game-scheduler.ts';
type Command=GameCommand extends infer T?T extends GameCommand?Omit<T,'requestId'>:never:never;
export type GameplayState={status:string;frame:number;delay?:number;hash?:string;busy:boolean;intent?:boolean};
/** Coordinates one installed peer receiver, one worker and one acknowledged timeline. */
export class GameClient {
 private room?:RoomView;private file?:Fingerprint;private intent=false;private renew=false;
 private checkpointTransport?:RTCDataChannel;private checkpointPeerEpoch?:string;private checkpointSpec?:Extract<GameEvent,{type:'gameCheckpoint'}>;
 private checkpointSender=new CheckpointSender();private checkpointReceiver=new CheckpointReceiver();private checkpointTimer?:ReturnType<typeof setTimeout>;private checkpointSerial=Promise.resolve();private checkpointQueuedBytes=0;private checkpointQueuedMessages=0;private checkpointExporting?:string;
 private roundTripMs=0;private channel?:RTCDataChannel;private peerEpoch?:string;private inspect?:string;
 private controllers:ControllerAssignment={...defaultControllers};
 private scheduler?:GameScheduler;private prepared?:{epoch:string;delay:number;frame:number};private early:GamePacket[]=[];
 private serial=0;private offeringSerial?:number;private offered?:string;private controlled=false;
 private fence?:number;private awaitingFence=false;private pausedSent=false;private hashing=false;private missingSince=0;
 private state:GameplayState={status:'Choose matching games to prepare shared play.',frame:0,busy:false};
 private player:()=>LocalPlayer|null;private send:(command:Command)=>Promise<unknown>;private update:(state:GameplayState)=>void;
 constructor(player:()=>LocalPlayer|null,send:(command:Command)=>Promise<unknown>,update:(state:GameplayState)=>void){this.player=player;this.send=send;this.update=update;}
 private publish(patch:Partial<GameplayState>){this.state={...this.state,...patch};this.update(this.state);}
 enter(room?:RoomView){
  const previous=this.room;
  if(previous && (!room||previous.id!==room.id||previous.role!==room.role||(previous.role==='guest'&&previous.reservationIntent!==room.reservationIntent)))this.clear('Room membership changed. Shared play stopped.',true);
  if(previous?.role==='host'&&previous.guest&&room?.id===previous.id&&!room.guest)this.clear('Guest left. Resume local play whenever you are ready.',true);
  if(previous?.id===room?.id&&previous?.game?.controllers?.revision!==room?.game?.controllers?.revision){this.clear('Controller assignment changed. Both players must accept and prepare to resume.');this.player()?.releaseControllers();}
  this.room=room;if(!room)return;
  if(this.checkpointSpec&&room.game?.status==='resume_ready'){this.cancelCheckpoint();this.publish({busy:false,status:'Paused game synchronized. The host can resume.'});}
  void this.offerGuest();
 }
 selected(file:Fingerprint){if(this.room?.role==='guest'&&this.file)this.cancelIntent();this.file=file;this.intent=this.room?.role!=='guest';this.offered=undefined;this.publish({intent:this.intent});void this.offerGuest();}
 playIntent(){this.intent=true;this.offered=undefined;this.publish({intent:true,status:this.channel?.readyState==='open'?'Preparing your game for shared play…':'Waiting for the peer connection before preparation can finish…'});void this.offerGuest();}
 cancelIntent(){if(this.checkpointSpec){const peerEpoch=this.peerEpoch;this.clear('Synchronization cancelled. Game progress is preserved.');if(peerEpoch)void this.send({type:'gameUnready',peerEpoch}).catch(()=>{});return;}if(!this.room?.established){const epoch=this.peerEpoch,shouldRevoke=this.room?.role==='guest'&&!!this.offered&&!!epoch;this.intent=false;++this.serial;this.offered=undefined;this.publish({intent:false});if(shouldRevoke)void this.send({type:'gameUnready',peerEpoch:epoch}).catch(()=>{});}}
 retry(){void this.renewOffer();}
 retryConnection(){this.renew=true;}
 ready(channel:RTCDataChannel,epoch:string,roundTripMs=0){
  this.roundTripMs=roundTripMs;
  this.channel=channel;this.peerEpoch=epoch;if(this.renew){this.intent=true;this.renew=false;}
  channel.onmessage=({data})=>{if(this.channel===channel&&this.peerEpoch===epoch)this.receive(data);};
  if(this.inspect===epoch){this.inspect=undefined;void this.offer();}else void this.offerGuest();
 }
 closed(epoch?:string){if(epoch&&epoch===this.peerEpoch){this.checkpointTransport=undefined;this.checkpointPeerEpoch=undefined;this.peerEpoch=undefined;this.channel=undefined;this.clear('Connection changed. Shared play is paused; retry explicitly.');}}
 private clear(status:string,leave=false){
  this.cancelCheckpoint();++this.serial;this.intent=false;this.offered=undefined;this.offeringSerial=undefined;this.prepared=undefined;this.scheduler=undefined;this.early=[];this.fence=undefined;this.awaitingFence=false;this.hashing=false;
  if(this.controlled)this.player()?.stopGame(status,leave);if(leave)this.player()?.allowLocalPlay();this.controlled=false;this.publish({status,busy:false,intent:false});
 }
 private eligible(){return !!this.intent&&!!this.room&&!!this.file&&matchesFile(this.room.fingerprint,this.file)&&this.room.matches&&!this.room.game?.controllerProposal&&this.channel?.readyState==='open'&&this.peerEpoch===this.room.peer.epoch;}
 private async offerGuest(){if(this.room?.role==='guest'&&!this.room.established&&this.eligible())await this.offer();}
 private async offer(){
  const room=this.room,peerEpoch=this.peerEpoch,player=this.player();if(!room||!peerEpoch||!player||!this.eligible()||this.offeringSerial===this.serial)return;
  const key=room.id+peerEpoch+this.file!.romSha256;if(this.offered===key)return;
  this.offered=key;const serial=this.serial;this.offeringSerial=serial;this.controlled=true;
  this.publish({busy:true,status:'Checking the committed machine state…'});
  try{
   const info=await player.holdForGame(this.ownsInput());if(serial!==this.serial||!this.eligible())return;
   await this.send({type:'gameReady',peerEpoch,...info,controllerRevision:room.game?.controllers?.revision??0,delay:proposeInputDelay(this.roundTripMs,player.frameRate())});
   if(serial!==this.serial)return;
   this.publish({busy:false,status:room.established?'Ready to resume. Waiting for the host and other player.':'Waiting for the matching initial-state barrier…'});
  }catch(error){if(serial===this.serial)this.clear(error instanceof Error?error.message:'Shared game could not prepare.',!room.established);}
  finally{if(this.offeringSerial===serial)this.offeringSerial=undefined;}
 }
 private async renewOffer(){this.intent=true;if(this.offeringSerial===this.serial)return;this.offered=undefined;await this.offer();}
 async resumeReady(){await this.renewOffer();}
 async resumeTogether(){const epoch=this.room?.game?.epoch,serial=this.serial;if(epoch)try{await this.send({type:'gameResume',epoch});}catch(error){if(serial===this.serial)this.publish({status:String(error),busy:false});}}
 handle(event:GameEvent){
  if(event.type==='gameInspect') {if(this.peerEpoch!==event.peerEpoch){this.inspect=event.peerEpoch;return;}void this.offer();return;}
  if(event.type==='gameCheckpoint'){this.beginCheckpoint(event);return;}
  if(event.type==='gameCheckpointSend'){const spec=this.checkpointSpec;if(spec&&spec.epoch===event.epoch&&spec.transferId===event.transferId)this.sendCheckpoint(spec);return;}
  if(event.type==='gameFreeze'){
   const scheduler=this.scheduler;if(!scheduler||!scheduler.authority||event.epoch!==scheduler.epoch)return;
   this.awaitingFence=true;const serial=this.serial;this.publish({busy:true,status:event.reason});
   void this.player()!.holdForGame(false).then(info=>{if(serial!==this.serial||this.scheduler!==scheduler)return;if(info.frame!==scheduler.frame)throw Error('Worker frame does not match completed authority state');return this.send({type:'gameFrozen',epoch:event.epoch,frame:info.frame,hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'network');});return;
  }
  if(event.type==='gameStop'){
   this.clear(event.reason);
   return;
  }
  if(event.type==='gamePauseAt'){
   const scheduler=this.scheduler;if(!scheduler||event.epoch!==scheduler.epoch)return;
   if(event.frame<scheduler.frame||event.frame>scheduler.frame+gameplayLimits.inputWindow){this.fail('Invalid pause boundary.','network');return;}
   this.fence=event.frame;this.awaitingFence=false;this.publish({status:event.reason,busy:true});if(scheduler.frame===event.frame)void this.finishPause();else this.player()?.drainGame();return;
  }
  if(event.peerEpoch!==this.peerEpoch||!this.eligible())return;
  if(event.type==='gamePrepare'){
   const serial=this.serial;this.controllers={...(event.controllers??defaultControllers)};this.prepared={epoch:event.epoch,delay:event.delay,frame:event.frame??0};this.early=[];this.publish({status:'Starting together…',busy:true});
   void this.player()!.holdForGame(this.ownsInput()).then(info=>{if(serial!==this.serial||this.prepared?.epoch!==event.epoch)return;if(info.hash!==event.hash||info.frame!==(event.frame??0)){this.fail('State changed during the start barrier.','mismatch');return;}return this.send({type:'gameAck',epoch:event.epoch,hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'network');});
  }else if(event.type==='gameStart'){
   if(this.prepared?.epoch!==event.epoch)return;
   const scheduler=new GameScheduler(event.epoch,event.delay,this.members(),packet=>this.sendPacket(packet),event.frame??0);this.scheduler=scheduler;
   this.fence=undefined;this.awaitingFence=false;this.pausedSent=false;this.hashing=false;this.missingSince=0;
   try{for(const packet of this.early)scheduler.receive(packet,this.remoteMember());this.early=[];
    this.player()!.startGame({epoch:event.epoch,next:mask=>this.next(mask),committed:frame=>this.committed(frame),pause:reason=>this.pause(reason),draining:()=>this.fence!==undefined,ownsInput:this.ownsInput()});
    this.publish({status:'Playing together.',frame:scheduler.frame,delay:event.delay,busy:false});
   }catch(error){this.fail(String(error),'network');}
  }
 }
 private member(role:'host'|'guest'){const id=role==='host'?this.room?.hostMembership:this.room?.guestMembership;if(!id)throw Error('Missing game membership');return id;}
 private remoteMember(){return this.member(this.room?.role==='host'?'guest':'host');}
 private members(){const assignment=this.controllers;return {local:this.member(this.room!.role),authority:this.member('host'),controllers:[this.member(assignment.p1),assignment.mode==='shared'?undefined:this.member(assignment.p1==='host'?'guest':'host')] as const};}
 private ownsInput(){const assignment=this.room?.game?.controllers??this.controllers;return assignment.mode!=='shared'||this.room?.role===assignment.p1;}
 private sendPacket(packet:GamePacket){const channel=this.channel;if(channel?.readyState!=='open'||channel.bufferedAmount>64*1024)throw Error('Game transport is not draining');channel.send(JSON.stringify(packet));}
 checkpointChannel(channel:RTCDataChannel,peerEpoch:string){
  this.cancelCheckpoint();this.checkpointTransport=channel;this.checkpointPeerEpoch=peerEpoch;channel.binaryType='arraybuffer';channel.bufferedAmountLowThreshold=CHECKPOINT_BUFFER_BYTES/2;
  channel.onbufferedamountlow=()=>{if(this.checkpointTransport===channel)this.pumpCheckpoint();};
  channel.onmessage=({data})=>{if(this.checkpointTransport!==channel||this.checkpointPeerEpoch!==peerEpoch)return;
   const bytes=typeof data==='string'?data.length*2:data instanceof ArrayBuffer?data.byteLength:Infinity;
   if(bytes>(typeof data==='string'?2048:CHECKPOINT_CHUNK_BYTES)||this.checkpointQueuedBytes+bytes>CHECKPOINT_MAX_BYTES+64*1024||this.checkpointQueuedMessages>=256){this.fail('Checkpoint receive queue exceeded its limit.','network');return;}
   this.checkpointQueuedBytes+=bytes;this.checkpointQueuedMessages++;
   this.checkpointSerial=this.checkpointSerial.then(async()=>{
    if(this.checkpointTransport!==channel||this.checkpointPeerEpoch!==peerEpoch)return;
    if(typeof data==='string'){const metadata=parseCheckpointMetadata(data);if(!metadata||this.room?.role!=='guest')throw Error('Invalid checkpoint metadata');this.checkpointReceiver.begin(metadata,m=>this.authorizedCheckpoint(m));return;}
    if(!(data instanceof ArrayBuffer))throw Error('Invalid checkpoint bytes');
    const result=await this.checkpointReceiver.accept(data,m=>this.authorizedCheckpoint(m));if(!result)return;
    const spec=this.checkpointSpec!,current=()=>this.checkpointSpec===spec&&this.authorizedCheckpoint(result.metadata);
    const restored=await this.player()!.importPeerCheckpoint(spec.epoch,spec.frame,result.bytes,result.metadata.identity,spec.hash,current);
    if(!current())return;await this.send({type:'gameCheckpointAck',epoch:spec.epoch,transferId:spec.transferId,frame:restored.frame,hash:restored.hash});
   }).catch(error=>{if(this.checkpointTransport===channel&&this.checkpointSpec)this.fail(String(error),'mismatch');}).finally(()=>{this.checkpointQueuedBytes-=bytes;this.checkpointQueuedMessages--;});
  };
 }
 private authorizedCheckpoint(metadata:CheckpointMetadata){
  const spec=this.checkpointSpec;return !!spec&&!!this.intent&&this.checkpointPeerEpoch===this.peerEpoch&&this.room?.peer.epoch===this.peerEpoch&&metadata.transferId===spec.transferId&&metadata.epoch===spec.epoch&&metadata.frame===spec.frame&&metadata.hash===spec.hash&&metadata.sender===this.room?.hostMembership&&metadata.recipient===this.room?.guestMembership;
 }
 private cancelCheckpoint(){this.checkpointExporting=undefined;this.player()?.cancelPeerCheckpoint();clearTimeout(this.checkpointTimer);this.checkpointTimer=undefined;this.checkpointSpec=undefined;this.checkpointReceiver.cancel();this.checkpointSender.cancel();}
 private beginCheckpoint(spec:Extract<GameEvent,{type:'gameCheckpoint'}>){
  if(!this.eligible()||this.peerEpoch!==spec.peerEpoch||this.room?.game?.epoch!==spec.epoch)return;
  this.cancelCheckpoint();this.checkpointSpec=spec;this.publish({busy:true,status:'Synchronizing the host’s paused game…'});
  this.checkpointTimer=setTimeout(()=>{if(this.checkpointSpec===spec){this.checkpointReceiver.expire();this.checkpointSender.expire();this.fail('Game synchronization timed out. Prepare again to retry.','network');}},CHECKPOINT_TIMEOUT_MS);
  if(this.room?.role==='guest')void this.send({type:'gameCheckpointReady',epoch:spec.epoch,transferId:spec.transferId}).catch(error=>this.fail(String(error),'network'));
 }
 private sendCheckpoint(spec:Extract<GameEvent,{type:'gameCheckpoint'}>){
  if(this.room?.role!=='host'||this.checkpointSender.retainedBytes||this.checkpointExporting===spec.transferId)return;this.checkpointExporting=spec.transferId;
  void (async()=>{
   const exported=await this.player()!.exportPeerCheckpoint(spec.epoch,spec.frame),digest=await checkpointDigest(exported.bytes);
   const metadata:CheckpointMetadata={transferId:spec.transferId,sender:this.member('host'),recipient:this.member('guest'),epoch:spec.epoch,frame:spec.frame,identity:exported.identity,hash:exported.hash,digest,byteLength:exported.bytes.byteLength};
   if(this.checkpointSpec!==spec)return;if(!this.authorizedCheckpoint(metadata))throw Error('Checkpoint source state changed');
   const channel=this.checkpointTransport;if(channel?.readyState!=='open')throw Error('Checkpoint transport is unavailable. Prepare again to retry.');
   channel.send(JSON.stringify(metadata));this.checkpointSender.begin(metadata,exported.bytes,channel);this.pumpCheckpoint();
  })().catch(error=>{if(this.checkpointSpec===spec)this.fail(String(error),'mismatch');});
 }
 private pumpCheckpoint(){if(!this.checkpointSpec||this.room?.role!=='host'||!this.checkpointSender.retainedBytes)return;try{this.checkpointSender.pump(this.member('guest'),m=>this.authorizedCheckpoint(m));}catch(error){this.fail(String(error),'network');}}
 private receive(raw:unknown){
  const packet=parseGamePacket(raw);if(!packet){this.fail('Invalid gameplay message.','network');return;}
  if(packet.epoch!==this.prepared?.epoch)return;
  try{
   if(this.scheduler){this.scheduler.receive(packet,this.remoteMember());if(packet.kind==='frame'&&!this.scheduler.authority&&this.fence===undefined)this.scheduler.sample(this.player()?.sampleGameInput()??0);this.player()?.wakeGame(packet.epoch);}
   else {if(this.early.length>=gameplayLimits.inputWindow||packet.frame>(this.prepared?.frame??0)+gameplayLimits.inputWindow)throw Error('Too much input before start');this.early.push(packet);}
  }catch(error){this.fail(String(error),'mismatch');}
 }
 private next(mask:number){
  const scheduler=this.scheduler;if(!scheduler||this.awaitingFence||this.hashing||this.pausedSent)return;
  if(this.fence!==undefined&&scheduler.frame>=this.fence){void this.finishPause();return;}
  try{
   scheduler.sample(this.fence!==undefined?0:mask);const input=scheduler.next();
   if(!input){this.missingSince ||= performance.now();this.publish({status:'Waiting for the other player’s input. Emulation is stopped.'});if(performance.now()-this.missingSince>gameplayLimits.stallMs)this.pause('network');return;}
   if(this.missingSince)this.publish({status:'Playing together.'});this.missingSince=0;return {frame:scheduler.frame,p1:input[0],p2:input[1]};
  }catch(error){this.fail(String(error),'network');}
 }
 private committed(frame:number){
  const scheduler=this.scheduler;if(!scheduler||frame!==scheduler.frame)return;
  try{scheduler.commit();}catch(error){this.fail(String(error),'network');return;}this.publish({frame:scheduler.frame});
  if(this.fence!==undefined&&scheduler.frame===this.fence){void this.finishPause();return;}
  if(scheduler.frame%gameplayLimits.hashInterval===0){this.hashing=true;const serial=this.serial;
   void this.player()!.stateHash().then(info=>{if(serial!==this.serial)return;scheduler.hash(info.hash);this.publish({hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'mismatch');}).finally(()=>{if(serial===this.serial){this.hashing=false;this.player()?.wakeGame(scheduler.epoch);}});
  }
 }
 private pause(reason:GameReason){
  const scheduler=this.scheduler;if(!scheduler||this.awaitingFence||this.fence!==undefined)return;
  this.awaitingFence=true;this.publish({status:'Pausing both players at a common frame…',busy:true});
  // The authority chooses its reachable completed boundary, including a stalled timeline.
  void this.send({type:'gamePause',epoch:scheduler.epoch,frame:scheduler.frame,reason}).catch(error=>{if(this.scheduler===scheduler)this.fail(String(error),'network');});
 }
 private async finishPause(){
  const scheduler=this.scheduler;if(!scheduler||this.pausedSent)return;this.pausedSent=true;
  try{const info=await this.player()!.stateHash();if(this.scheduler!==scheduler)return;this.player()!.stopGame('Paused at the shared frame. Both players must acknowledge readiness.');await this.send({type:'gamePaused',epoch:scheduler.epoch,frame:scheduler.frame,hash:info.hash});}
  catch(error){if(this.scheduler===scheduler)this.fail(String(error),'mismatch');}
 }
 private fail(status:string,reason:GameReason){const epoch=this.scheduler?.epoch??this.prepared?.epoch??this.checkpointSpec?.epoch;this.clear(status);if(epoch)void this.send({type:'gameAbort',epoch,reason}).catch(()=>{});}
 dispose(){this.clear('Shared game closed.',true);this.channel=undefined;}
}
