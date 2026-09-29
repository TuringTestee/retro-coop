import {CheckpointReceiver,CheckpointSender,checkpointDigest} from './checkpoint.ts';
import {parseCheckpointMetadata,decodeCheckpointChunk,CHECKPOINT_TIMEOUT_MS,CHECKPOINT_BUFFER_BYTES,CHECKPOINT_CHUNK_BYTES,CHECKPOINT_MAX_BYTES,type CheckpointMetadata} from '../../../packages/contracts/src/checkpoint.ts';
import {gameplayLimits,parseGamePacket,type ControllerAssignment,type GameCommand,type GameEvent,type GamePacket,type GameReason} from '../../../packages/contracts/src/gameplay.ts';
import {matchesFile,type Fingerprint,type RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {LocalPlayer} from './player.ts';
import {GameScheduler,proposeInputDelay} from './game-scheduler.ts';
type Command=GameCommand extends infer T?T extends GameCommand?Omit<T,'requestId'>:never:never;
type Spec=Extract<GameEvent,{type:'gameCheckpoint'}>;
type Capture=Awaited<ReturnType<LocalPlayer['exportPeerCheckpoint']>>;
type Outgoing={request:Extract<GameEvent,{type:'gameCapture'}>;capture?:Capture;digest?:string;spec?:Spec;timer:ReturnType<typeof setTimeout>;cursor?:number;sending?:boolean;exporting?:boolean};
type Link={epoch:string;channel:RTCDataChannel;roundTripMs:number;checkpoint?:RTCDataChannel;live:boolean};
export type GameplayState={status:string;frame:number;delay?:number;hash?:string;busy:boolean;synchronizing?:boolean;intent?:boolean;observing?:boolean};
/** One local emulator; the authority owns at most four independently bounded replica links. */
export class GameClient {
 private room?:RoomView;private file?:Fingerprint;private intent=false;private serial=0;private offered?:string;private offering=false;
 private links=new Map<string,Link>();private checkpointLinks=new Map<string,{epoch:string;channel:RTCDataChannel}>();
 private scheduler?:GameScheduler;private controllers:ControllerAssignment={owners:[null,null],revision:0};private prepared?:Extract<GameEvent,{type:'gamePrepare'|'gameStart'}>;
 private frozen=false;private fence?:number;private hashing=false;private missingSince=0;private pausedSent=false;
 private outgoing=new Map<string,Outgoing>();private exporting?:{epoch:string;promise:Promise<Capture>};private sender=new CheckpointSender();
 private incoming?:Spec;private receiver=new CheckpointReceiver();private incomingTimer?:ReturnType<typeof setTimeout>;private receivedSerial=Promise.resolve();private queuedBytes=0;private queuedMessages=0;private catchupTarget?:number;private catchingUp=false;private observeRequested?:string;
 private committedEpoch?:string;private historyHashes=new Map<number,string>();private state:GameplayState={status:'Choose matching games to prepare shared play.',frame:0,busy:false};
 private player:()=>LocalPlayer|null;private send:(command:Command)=>Promise<unknown>;private update:(state:GameplayState)=>void;
 constructor(player:()=>LocalPlayer|null,send:(command:Command)=>Promise<unknown>,update:(state:GameplayState)=>void){this.player=player;this.send=send;this.update=update;}
 private publish(patch:Partial<GameplayState>){this.state={...this.state,...patch};this.update(this.state);}
 private self(){return this.room?.chatMembership??'';}
 private authority(){return !!this.room&&this.self()===this.room.hostMembership;}
 private observerSlot(){return this.room?.slots.find(slot=>slot.member?.id===this.self())?.role==='observer';}
 private ownsInput(controllers=this.controllers){return controllers.owners.includes(this.self());}
 private loaded(){return !!this.room&&!!this.file&&this.room.matches&&matchesFile(this.room.fingerprint,this.file)&&!!this.player()?.isLoaded(this.file);}
 enter(room?:RoomView){
  const prior=this.room;if(prior&&(!room||room.id!==prior.id||room.chatMembership!==prior.chatMembership))this.clear('Room membership changed. Your game is preserved.',true);
  if(room&&(!prior||room.id!==prior.id||room.chatMembership!==prior.chatMembership)){this.intent=false;this.offered=undefined;this.publish({intent:false});}
  this.room=room;if(!room)return;
  for(const member of this.links.keys())if(!room.slots.some(slot=>slot.member?.id===member))this.closed(member);
  if(prior?.game.controllers.revision!==room.game.controllers.revision){this.offered=undefined;this.observeRequested=undefined;}
  if(room.game.status==='resume_ready'&&(this.incoming?.purpose==='controller'||[...this.outgoing.values()].some(value=>value.request.purpose==='controller'))){if(this.incoming?.purpose==='controller')this.cancelIncoming();for(const outgoing of [...this.outgoing.values()])if(outgoing.request.purpose==='controller')this.cancelOutgoing(outgoing);this.publish({busy:false,synchronizing:false,status:'Paused game synchronized. The host can resume.'});}
  if(prior&&prior.game.epoch!==room.game.epoch&&!this.authority()&&!room.game.controllers.owners.includes(this.self()))this.clear('Game roles changed. Synchronizing the current game.');
  if(room.game.status==='playing'&&this.observerSlot()&&!this.authority()&&this.loaded()&&!this.scheduler&&!this.incoming&&!this.observeRequested)this.observe();
  if(this.intent&&!room.started)void this.offer();
 }
 selected(file:Fingerprint){if(this.file&&this.room&&(this.offered||this.offering||this.incoming||this.scheduler)){const revision=this.room.game.controllers.revision;this.clear('Game selection changed. Prepare the matching game again.');void this.send({type:'gameUnready',revision}).catch(()=>{});}this.file=file;this.offered=undefined;if(this.room?.started&&!this.authority()&&this.observerSlot())this.observe();else if(this.intent)void this.offer();}
 playIntent(){this.intent=true;this.offered=undefined;this.publish({intent:true});if(this.room?.started&&!this.authority()&&this.observerSlot())this.observe();else void this.offer();}
 retry(){this.playIntent();}
 retryConnection(){}
 async resumeReady(){this.intent=true;this.offered=undefined;await this.offer();}
 async resumeTogether(){const epoch=this.room?.game.epoch;if(epoch)try{await this.send({type:'gameResume',epoch});}catch(error){this.publish({status:String(error),busy:false});}}
 observe(){const room=this.room;if(!room||!this.loaded()||room.game.status!=='playing'||room.game.controllers.owners.includes(this.self())||this.authority()||this.links.get(room.hostMembership)?.channel.readyState!=='open'||room.peers.find(peer=>peer.member===room.hostMembership)?.status!=='connected'||room.slots.find(slot=>slot.member?.id===this.self())?.member?.acquisition!=='loaded')return;this.intent=true;const epoch=room.game.epoch!;this.observeRequested=epoch;this.publish({busy:true,synchronizing:true,intent:true,status:'Requesting the current game for observation…'});void this.send({type:'gameObserve',revision:room.game.controllers.revision}).catch(error=>{if(this.observeRequested===epoch){this.observeRequested=undefined;this.publish({busy:false,synchronizing:false,status:String(error)});}});}
 cancelIntent(){const room=this.room;if(!room){this.intent=false;this.offered=undefined;this.publish({intent:false});return;}this.clear('Synchronization cancelled. Game progress is preserved.');void this.send({type:'gameUnready',revision:room.game.controllers.revision}).catch(()=>{});}
 private async offer(){
  const room=this.room;if(!room||!this.intent||!this.loaded()||this.offering||this.incoming||room.game.pending||(['playing','starting','pausing'].includes(room.game.status)&&room.game.controllers.owners.includes(this.self())))return;
  if(!this.authority()&&this.links.get(room.hostMembership)?.channel.readyState!=='open')return;
  const key=room.id+room.revision+room.game.controllers.revision+(room.game.epoch??'initial');if(this.offered===key)return;
  const serial=this.serial;this.offering=true;this.offered=key;this.publish({busy:true,status:'Checking the completed machine state…'});
  try{const info=await this.player()!.holdForGame(room.game.controllers.owners.includes(this.self()));if(serial!==this.serial)return;
   const rtt=Math.max(0,...[...this.links.values()].map(link=>link.roundTripMs));await this.send({type:'gameReady',revision:room.game.controllers.revision,roomRevision:room.revision,...info,delay:proposeInputDelay(rtt,this.player()!.frameRate())});
   if(serial===this.serial)this.publish({busy:false,status:'Ready. Waiting for the assigned players and host.'});
  }catch(error){if(serial===this.serial){this.offered=undefined;this.publish({busy:false,status:String(error)});}}finally{if(serial===this.serial)this.offering=false;}
 }
 ready(member:string,channel:RTCDataChannel,epoch:string,roundTripMs=0){
  const checkpoint=this.checkpointLinks.get(member);this.links.set(member,{epoch,channel,roundTripMs,checkpoint:checkpoint?.epoch===epoch?checkpoint.channel:undefined,live:false});channel.bufferedAmountLowThreshold=16*1024;
  channel.onmessage=({data})=>{if(this.links.get(member)?.channel===channel)this.receive(member,data);};channel.onbufferedamountlow=()=>{for(const outgoing of this.outgoing.values())if(outgoing.request.recipient===member)this.catchup(outgoing);};
  if(this.intent)void this.offer();if(this.room?.game.status==='playing'&&!this.scheduler&&!this.authority()&&this.observerSlot())this.observe();
 }
 closed(member:string,epoch?:string){const link=this.links.get(member);if(epoch&&link?.epoch!==epoch)return;this.links.delete(member);this.checkpointLinks.delete(member);
  for(const outgoing of [...this.outgoing.values()])if(outgoing.request.recipient===member)this.failOutgoing(outgoing,'Observer connection changed.');
  if(member===this.room?.hostMembership)this.clear('Host connection changed. Progress is preserved; synchronize after reconnecting.');
  else if(this.authority()&&this.controllers.owners.includes(member))this.pause('network');
 }
 handle(event:GameEvent){
  if(event.type==='gameInspect'){this.intent=true;this.offered=undefined;void this.offer();return;}
  if(event.type==='gameCapture'){this.capture(event);return;}
  if(event.type==='gameCheckpoint'){
   if(event.sender!==this.room?.hostMembership||!this.room.slots.some(slot=>slot.member?.id===event.recipient))return;
   if(this.authority()){const outgoing=this.outgoing.get(event.transferId);if(outgoing)outgoing.spec=event;}else if(event.recipient===this.self())void this.beginIncoming(event);return;
  }
  if(event.type==='gameCheckpointSend'){const outgoing=this.outgoing.get(event.transferId);if(outgoing&&outgoing.request.recipient===event.recipient)this.sendCheckpoint(outgoing);return;}
  if(event.type==='gameCatchup'){const outgoing=this.outgoing.get(event.transferId);if(outgoing){outgoing.cursor=event.frame;this.catchup(outgoing);}return;}
  if(event.type==='gameSyncStop'){
   const outgoing=this.outgoing.get(event.transferId);if(outgoing)this.cancelOutgoing(outgoing);
   if(this.incoming?.transferId===event.transferId||!this.incoming&&this.observeRequested===event.epoch&&!this.scheduler){this.cancelIncoming();this.scheduler=undefined;this.player()?.stopGame(event.reason);this.publish({busy:false,synchronizing:false,observing:false,status:event.reason});}return;
  }
  if(event.type==='gameStop'){this.clear(event.reason);return;}
  if(event.type==='gameFreeze'){
   if(!this.authority()||event.epoch!==this.room?.game.epoch)return;this.frozen=true;const serial=this.serial;this.publish({busy:true,status:event.reason});
   void this.player()!.holdForGame(false).then(info=>{if(serial!==this.serial)return;this.player()?.releaseControllers();return this.send({type:'gameFrozen',epoch:event.epoch,frame:info.frame,hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'network');});return;
  }
  if(event.type==='gamePauseAt'){
   if(this.scheduler?.epoch!==event.epoch&&this.incoming?.epoch!==event.epoch)return;this.fence=event.frame;this.frozen=false;this.publish({status:event.reason,busy:true});if(this.scheduler?.frame===event.frame)void this.finishPause();else this.player()?.drainGame();return;
  }
  if(!this.room||!this.loaded())return;
  if(event.type==='gamePrepare'){
   this.cancelAllTransfers();++this.serial;this.offering=false;const serial=this.serial;this.prepared=event;this.controllers=event.controllers;this.scheduler=this.makeScheduler(event.epoch,event.frame,event.delay,event.controllers,false);this.frozen=true;this.historyHashes.clear();
   this.publish({busy:true,status:'Preparing assigned players…'});
   void this.player()!.holdForGame(this.ownsInput()).then(async info=>{if(serial!==this.serial)return;if(info.frame!==event.frame||info.hash!==event.hash)throw Error('State changed before shared start');await this.player()!.bindGameEpoch(event.epoch,event.frame,event.hash);if(serial!==this.serial)return;return this.send({type:'gameAck',epoch:event.epoch,hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'mismatch');});return;
  }
  if(event.type==='gameStart'){
   if(this.prepared?.epoch!==event.epoch)return;for(const [member,link] of this.links)link.live=event.controllers.owners.includes(member);
   this.install(event.epoch,event.frame,event.delay,event.controllers,false);
  }
 }
 private makeScheduler(epoch:string,frame:number,delay:number,controllers:ControllerAssignment,observer:boolean){return new GameScheduler(epoch,delay,{local:this.self(),authority:this.room!.hostMembership,controllers:controllers.owners.map(owner=>owner??undefined) as [string|undefined,string|undefined],observer},packet=>this.sendPacket(packet),frame);}
 private install(epoch:string,frame:number,delay:number,controllers:ControllerAssignment,observer:boolean){
  this.controllers=controllers;if(observer||this.scheduler?.epoch!==epoch)this.scheduler=this.makeScheduler(epoch,frame,delay,controllers,observer);
  this.frozen=false;if(!observer)this.fence=undefined;this.hashing=false;this.pausedSent=false;this.missingSince=0;
  this.player()!.startGame({epoch,next:mask=>this.next(mask),committed:frame=>this.committed(frame),pause:reason=>this.pause(reason),draining:()=>this.catchingUp||this.fence!==undefined,silent:()=>this.catchingUp,ownsInput:!observer&&this.ownsInput()});
  this.publish({status:observer?'Catching up with the current game…':'Playing together.',busy:observer,synchronizing:observer,observing:observer,frame,delay});
 }
 private sendPacket(packet:GamePacket){
  if(this.authority()){
   if(packet.kind==='hash'){this.historyHashes.set(packet.frame,packet.hash);for(const frame of this.historyHashes.keys())if(frame<packet.frame-gameplayLimits.historyFrames)this.historyHashes.delete(frame);}
   for(const [member,link] of this.links)if(link.live){if(link.channel.readyState!=='open'||link.channel.bufferedAmount>64*1024){if(this.controllers.owners.includes(member))throw Error('Controller transport stopped draining');link.live=false;continue;}link.channel.send(JSON.stringify(packet));}
  }else {const channel=this.links.get(this.room!.hostMembership)?.channel;if(channel?.readyState!=='open'||channel.bufferedAmount>64*1024)throw Error('Host transport stopped draining');channel.send(JSON.stringify(packet));}
 }
 private receive(member:string,raw:unknown){
  if(typeof raw==='string'&&raw.length<256){try{const marker=JSON.parse(raw);if(marker.kind==='live'&&member===this.room?.hostMembership&&this.incoming?.transferId===marker.transferId&&marker.epoch===this.scheduler?.epoch&&Number.isSafeInteger(marker.frame)){this.catchupTarget=marker.frame;this.finishCatchup();return;}}catch{}}
  const packet=parseGamePacket(raw);if(!packet){if(this.controllers.owners.includes(member)||member===this.room?.hostMembership)this.fail('Invalid gameplay packet.','network');return;}
  const scheduler=this.scheduler;if(!scheduler||packet.epoch!==scheduler.epoch)return;
  try{scheduler.receive(packet,member);if(!scheduler.authority&&packet.kind==='frame'&&!this.frozen&&!this.catchingUp&&this.fence===undefined)scheduler.sample(this.player()?.sampleGameInput()??0);this.player()?.wakeGame(packet.epoch);}catch(error){if(this.authority()&&!this.controllers.owners.includes(member)){this.links.get(member)!.live=false;return;}this.fail(String(error),'mismatch');}
 }
 private next(mask:number){const scheduler=this.scheduler;if(!scheduler||this.frozen||this.hashing||this.pausedSent)return;if(this.fence!==undefined&&scheduler.frame>=this.fence){void this.finishPause();return;}
  try{scheduler.sample(this.fence!==undefined?0:mask);const value=scheduler.next();if(!value){this.missingSince ||=performance.now();if(this.ownsInput()||this.authority()){if(performance.now()-this.missingSince>gameplayLimits.stallMs)this.pause('network');}else if(!this.catchingUp&&this.room?.game.status==='playing'&&performance.now()-this.missingSince>gameplayLimits.catchupMs)this.fail('Observation stopped receiving frames. Choose Observe game to synchronize again.','network');return;}this.missingSince=0;return {frame:scheduler.frame,p1:value[0],p2:value[1]};}catch(error){this.fail(String(error),'network');}}
 private committed(frame:number){const scheduler=this.scheduler;if(!scheduler||frame!==scheduler.frame)return;try{scheduler.commit();this.committedEpoch=scheduler.epoch;}catch(error){this.fail(String(error),'network');return;}this.publish({frame:scheduler.frame});for(const outgoing of this.outgoing.values())if(!outgoing.capture&&!outgoing.exporting)this.exportCapture(outgoing);
  if(this.fence===scheduler.frame){void this.finishPause();return;}
  if(scheduler.frame%gameplayLimits.hashInterval===0){this.hashing=true;void this.player()!.stateHash().then(info=>{if(this.scheduler===scheduler){scheduler.hash(info.hash);this.publish({hash:info.hash});}}).catch(error=>{if(this.scheduler===scheduler)this.fail(String(error),'mismatch');}).finally(()=>{if(this.scheduler===scheduler){this.hashing=false;for(const outgoing of this.outgoing.values())this.catchup(outgoing);this.finishCatchup();this.player()?.wakeGame(scheduler.epoch);}});}else this.finishCatchup();
 }
 private pause(reason:GameReason){const scheduler=this.scheduler;if(!scheduler||this.frozen||this.fence!==undefined)return;if(!this.authority()&&!this.ownsInput()){this.fail('Observation interrupted. Retry synchronization.','network');return;}this.frozen=true;void this.send({type:'gamePause',epoch:scheduler.epoch,frame:scheduler.frame,reason}).catch(error=>{if(this.scheduler===scheduler)this.fail(String(error),'network');});}
 private async finishPause(){const scheduler=this.scheduler;if(!scheduler||this.pausedSent)return;this.pausedSent=true;try{const info=await this.player()!.holdForGame(false);if(this.scheduler!==scheduler)return;this.finishCatchup();this.player()!.stopGame('Paused. Prepare to resume.');this.publish({busy:false,status:'Paused. Prepare to resume.'});await this.send({type:'gamePaused',epoch:scheduler.epoch,frame:info.frame,hash:info.hash});}catch(error){if(this.scheduler===scheduler)this.fail(String(error),'mismatch');}}
 checkpointChannel(member:string,channel:RTCDataChannel,epoch:string){
  this.checkpointLinks.set(member,{epoch,channel});const link=this.links.get(member);if(link?.epoch===epoch)link.checkpoint=channel;channel.binaryType='arraybuffer';channel.bufferedAmountLowThreshold=CHECKPOINT_BUFFER_BYTES/2;
  channel.onbufferedamountlow=()=>{for(const outgoing of this.outgoing.values())if(outgoing.request.recipient===member&&outgoing.sending)this.pump(outgoing);};
  channel.onmessage=({data})=>{const spec=this.incoming;if(!spec||member!==spec.sender||this.checkpointLinks.get(member)?.channel!==channel)return;const bytes=typeof data==='string'?data.length:data instanceof ArrayBuffer?data.byteLength:Infinity;
   if(bytes>(typeof data==='string'?2048:CHECKPOINT_CHUNK_BYTES)||this.queuedBytes+bytes>CHECKPOINT_MAX_BYTES+64*1024||this.queuedMessages>=256){this.failIncoming(spec,'Checkpoint queue exceeded its limit.');return;}
   try{const transfer=typeof data==='string'?parseCheckpointMetadata(data)?.transferId:decodeCheckpointChunk(data).transferId;if(transfer&&transfer!==spec.transferId)return;}catch{this.failIncoming(spec,'Malformed checkpoint data.');return;}
   this.queuedBytes+=bytes;this.queuedMessages++;this.receivedSerial=this.receivedSerial.then(async()=>{if(this.incoming!==spec)return;if(typeof data==='string'){const metadata=parseCheckpointMetadata(data);if(!metadata)throw Error('Invalid checkpoint metadata');this.receiver.begin(metadata,value=>this.authorized(value,spec));return;}
    const result=await this.receiver.accept(data,value=>this.authorized(value,spec));if(!result)return;const current=()=>this.incoming===spec&&this.authorized(result.metadata,spec);const restored=await this.player()!.importPeerCheckpoint(spec.epoch,spec.frame,result.bytes,result.metadata.identity,spec.hash,current);if(!current())return;
    if(spec.purpose==='observer'){this.catchingUp=true;this.catchupTarget=undefined;this.install(spec.epoch,spec.frame,this.room!.game.delay??gameplayLimits.delayDefault,this.room!.game.controllers,true);clearTimeout(this.incomingTimer);this.incomingTimer=setTimeout(()=>this.failIncoming(spec,'Observer catch-up timed out. Retry synchronization.'),gameplayLimits.catchupMs);}
    await this.send({type:'gameCheckpointAck',epoch:spec.epoch,transferId:spec.transferId,frame:restored.frame,hash:restored.hash});
   }).catch(error=>{if(this.incoming===spec)this.failIncoming(spec,String(error));}).finally(()=>{this.queuedBytes-=bytes;this.queuedMessages--;});
  };
 }
 private authorized(metadata:CheckpointMetadata,spec:Spec){return this.incoming===spec&&this.loaded()&&this.room?.game.epoch===spec.epoch&&metadata.transferId===spec.transferId&&metadata.sender===spec.sender&&metadata.recipient===this.self()&&metadata.epoch===spec.epoch&&metadata.frame===spec.frame&&metadata.hash===spec.hash;}
 private async beginIncoming(spec:Spec){if(!this.loaded()||spec.epoch!==this.room?.game.epoch)return;this.cancelIncoming();this.incoming=spec;this.intent=true;this.frozen=true;this.publish({busy:true,synchronizing:true,status:'Synchronizing the host’s current game…'});this.incomingTimer=setTimeout(()=>this.failIncoming(spec,'Synchronization timed out. Retry.'),CHECKPOINT_TIMEOUT_MS);
  try{await this.player()!.holdForGame(false);if(this.incoming!==spec)return;this.scheduler=undefined;await this.send({type:'gameCheckpointReady',epoch:spec.epoch,transferId:spec.transferId});}catch(error){if(this.incoming===spec)this.failIncoming(spec,String(error));}
 }
 private capture(request:Extract<GameEvent,{type:'gameCapture'}>){if(!this.authority()||request.epoch!==this.room?.game.epoch||this.outgoing.size>=4||[...this.outgoing.values()].some(value=>value.request.recipient===request.recipient))return;
  if(request.purpose==='controller')this.publish({busy:true,synchronizing:true,status:'Synchronizing the assigned player from the preserved host game…'});
  const outgoing:Outgoing={request,timer:setTimeout(()=>this.failOutgoing(outgoing,'Checkpoint transfer timed out.'),CHECKPOINT_TIMEOUT_MS)};this.outgoing.set(request.transferId,outgoing);if(request.purpose==='observer'&&this.committedEpoch!==request.epoch)return;this.exportCapture(outgoing);
 }
 private exportCapture(outgoing:Outgoing){const request=outgoing.request,scheduler=this.scheduler;outgoing.exporting=true;
  if(!this.exporting||this.exporting.epoch!==request.epoch){const promise=this.player()!.exportPeerCheckpoint(request.epoch);this.exporting={epoch:request.epoch,promise};void promise.finally(()=>{if(this.exporting?.promise===promise)this.exporting=undefined;}).catch(()=>{});}
  void this.exporting.promise.then(async capture=>{const digest=await checkpointDigest(capture.bytes);if(this.outgoing.get(request.transferId)!==outgoing||request.purpose==='observer'&&this.scheduler!==scheduler)return;outgoing.capture=capture;outgoing.digest=digest;await this.send({type:'gameCaptured',epoch:request.epoch,transferId:request.transferId,frame:capture.frame,hash:capture.hash});}).catch(error=>{if(this.outgoing.get(request.transferId)===outgoing)this.failOutgoing(outgoing,String(error));});
 }
 private sendCheckpoint(outgoing:Outgoing){try{const {spec,capture,digest}=outgoing,channel=this.checkpointLinks.get(outgoing.request.recipient)?.channel;if(!spec||!capture||!digest||channel?.readyState!=='open')throw Error('Checkpoint transport unavailable.');const metadata:CheckpointMetadata={transferId:spec.transferId,epoch:spec.epoch,frame:spec.frame,hash:spec.hash,sender:spec.sender,recipient:spec.recipient,identity:capture.identity,digest,byteLength:capture.bytes.byteLength};channel.send(JSON.stringify(metadata));this.sender.begin(metadata,capture.bytes,channel);outgoing.sending=true;this.pump(outgoing);}catch(error){this.failOutgoing(outgoing,String(error));}}
 private pump(outgoing:Outgoing){try{if(this.sender.pump(outgoing.request.recipient,metadata=>this.outgoing.get(metadata.transferId)===outgoing)==='complete')outgoing.sending=false;}catch(error){this.failOutgoing(outgoing,String(error));}}
 private catchup(outgoing:Outgoing){const scheduler=this.scheduler,link=this.links.get(outgoing.request.recipient);if(outgoing.cursor===undefined||!scheduler||!link||outgoing.request.epoch!==scheduler.epoch)return;
  try{while(outgoing.cursor<scheduler.frame){if(link.channel.bufferedAmount>32*1024)return;const packet=scheduler.historyFrame(outgoing.cursor);if(!packet)throw Error('Observer fell outside retained history.');const next:number=outgoing.cursor+1,hash=next%gameplayLimits.hashInterval===0?this.historyHashes.get(next):undefined;if(next%gameplayLimits.hashInterval===0&&!hash){if(this.hashing)return;throw Error('Observer hash history expired.');}link.channel.send(JSON.stringify(packet));if(hash)link.channel.send(JSON.stringify({kind:'hash',epoch:scheduler.epoch,frame:next,hash}));outgoing.cursor=next;}
   link.channel.send(JSON.stringify({kind:'live',epoch:scheduler.epoch,transferId:outgoing.request.transferId,frame:scheduler.frame}));link.live=true;this.cancelOutgoing(outgoing);
  }catch(error){this.failOutgoing(outgoing,String(error));}
 }
 private finishCatchup(){const spec=this.incoming,scheduler=this.scheduler;if(!this.catchingUp||!spec||!scheduler||this.catchupTarget===undefined||scheduler.frame<this.catchupTarget||this.hashing)return;this.catchingUp=false;this.player()?.resumeGamePresentation();clearTimeout(this.incomingTimer);this.incoming=undefined;this.receiver.cancel();this.publish({busy:false,synchronizing:false,status:'Observing the current game.'});void this.send({type:'gameObserved',epoch:spec.epoch,transferId:spec.transferId,frame:scheduler.frame}).catch(error=>{if(this.scheduler===scheduler)this.fail(String(error),'network');});}
 private cancelOutgoing(outgoing:Outgoing){clearTimeout(outgoing.timer);this.sender.cancel(outgoing.request.recipient);this.outgoing.delete(outgoing.request.transferId);}
 private failOutgoing(outgoing:Outgoing,status:string){if(this.outgoing.get(outgoing.request.transferId)!==outgoing)return;this.cancelOutgoing(outgoing);const link=this.links.get(outgoing.request.recipient);if(link)link.live=false;void this.send({type:'gameCheckpointFailed',epoch:outgoing.request.epoch,transferId:outgoing.request.transferId}).catch(()=>{});if(outgoing.request.purpose==='controller')this.publish({busy:false,status});}
 private cancelIncoming(){clearTimeout(this.incomingTimer);this.incoming=undefined;this.receiver.cancel();this.player()?.cancelPeerCheckpoint();this.catchingUp=false;this.catchupTarget=undefined;}
 private failIncoming(spec:Spec,status:string){if(this.incoming!==spec)return;this.cancelIncoming();this.scheduler=undefined;this.player()?.stopGame(status);this.publish({busy:false,synchronizing:false,observing:false,status});void this.send({type:'gameCheckpointFailed',epoch:spec.epoch,transferId:spec.transferId}).catch(()=>{});}
 private cancelAllTransfers(){this.cancelIncoming();for(const outgoing of [...this.outgoing.values()])this.cancelOutgoing(outgoing);}
 private clear(status:string,leave=false){this.cancelAllTransfers();++this.serial;this.intent=false;this.offered=undefined;this.offering=false;this.prepared=undefined;this.scheduler=undefined;this.frozen=false;this.fence=undefined;this.hashing=false;this.observeRequested=undefined;this.player()?.stopGame(status,leave);if(leave)this.player()?.allowLocalPlay();this.publish({status,busy:false,synchronizing:false,intent:false,observing:false});}
 private fail(status:string,reason:GameReason){const epoch=this.scheduler?.epoch??this.room?.game.epoch,spec=this.incoming;if(spec){this.failIncoming(spec,status);return;}this.clear(status);if(epoch)void this.send({type:'gameAbort',epoch,reason}).catch(()=>{});}
 dispose(){this.clear('Shared game closed.',true);this.links.clear();this.checkpointLinks.clear();}
}
