import {CheckpointReceiver,CheckpointSender,checkpointDigest} from './checkpoint.ts';
import {parseCheckpointMetadata,decodeCheckpointChunk,CHECKPOINT_TIMEOUT_MS,CHECKPOINT_BUFFER_BYTES,CHECKPOINT_CHUNK_BYTES,CHECKPOINT_MAX_BYTES,type CheckpointMetadata} from '../../../packages/contracts/src/checkpoint.ts';
import {gameplayProtocol,gameplayLimits,parseGamePacket,type ControllerAssignment,type GameCommand,type GameEvent,type GamePacket,type GameReason,type CartridgeCandidate,type LeasePacket} from '../../../packages/contracts/src/gameplay.ts';
import {matchesFile,type Fingerprint,type RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {LocalPlayer} from './player.ts';
import type {SaveSlot} from './saves.ts';
import {GameScheduler} from './game-scheduler.ts';
type Command=GameCommand extends infer T?T extends GameCommand?Omit<T,'requestId'>:never:never;
type Spec=Extract<GameEvent,{type:'gameCheckpoint'}>;
type Capture=Awaited<ReturnType<LocalPlayer['exportPeerCheckpoint']>>;
type Outgoing={request:Extract<GameEvent,{type:'gameCapture'}>;capture?:Capture;digest?:string;spec?:Spec;timer:ReturnType<typeof setTimeout>;cursor?:number;sending?:boolean;exporting?:boolean;sendRequested?:boolean;checkpointStarted?:boolean;boundary?:{frame:number;hash:string};boundaryPending?:boolean;markerSent?:boolean;continuation?:ReturnType<typeof setTimeout>};
type ManualSave={record?:SaveSlot;capture:Capture;current:()=>Promise<boolean>;serial:number};
type Link={epoch:string;channel:RTCDataChannel;checkpoint?:RTCDataChannel;live:boolean;stream:string;inputReady:boolean;recovering:boolean;leaseAt:number;cursor?:number;continuation?:ReturnType<typeof setTimeout>};
export type GameplayState={status:string;frame:number;hash?:string;busy:boolean;synchronizing?:boolean;intent?:boolean;observing?:boolean;preparationError?:string};
/** One local emulator; the authority owns at most four independently bounded replica links. */
export class GameClient {
 private inputLease?:LeasePacket;private inputSequence=0;private inputMask=0;private inputSentAt=0;private receiveStream?:string;private catchupHash?:string;private catchupChecking=false;private frozenRecovery=false;
 private manualLoadRequest?:symbol;private manualSave?:ManualSave;
 private candidateAcquisition?:AbortController;
 private replacementCompletion?:{intent:string;resolve:()=>void;reject:(error:Error)=>void};
 private loadAttempt?:{id:string;room:string;member:string;replacement?:CartridgeCandidate;candidateRequired?:boolean};private loadEvents=Promise.resolve();private loadHold?:Extract<GameEvent,{type:'gameLoadHold'}>;private announcedLoad?:{event:Extract<GameEvent,{type:'gameLoadHold'}>;room:string;member:string;serial:number};
 private room?:RoomView;private file?:Fingerprint;private intent=false;private serial=0;private offered?:string;private offering=false;
 private links=new Map<string,Link>();private checkpointLinks=new Map<string,{epoch:string;channel:RTCDataChannel}>();
 private scheduler?:GameScheduler;private controllers:ControllerAssignment={owners:[null,null],revision:0};private prepared?:Extract<GameEvent,{type:'gamePrepare'|'gameStart'}>;
 private frozen=false;private fence?:number;private hashing=false;private missingSince=0;private pausedSent=false;
 private outgoing=new Map<string,Outgoing>();private exporting?:{epoch:string;promise:Promise<Capture>};private sender=new CheckpointSender();
 private observerCompletion?:Spec;private incoming?:Spec;private receiver=new CheckpointReceiver();private incomingTimer?:ReturnType<typeof setTimeout>;private receivedSerial=Promise.resolve();private queuedBytes=0;private queuedMessages=0;private catchupTarget?:number;private catchingUp=false;private observeRequested?:string;
 private committedEpoch?:string;private historyHashes=new Map<number,string>();private state:GameplayState={status:'Choose matching games to prepare shared play.',frame:0,busy:false};
 private player:()=>LocalPlayer|null;private send:(command:Command)=>Promise<unknown>;private update:(state:GameplayState)=>void;private acquireCartridge:(candidate:CartridgeCandidate,room:RoomView,signal:AbortSignal)=>Promise<File>;
 constructor(player:()=>LocalPlayer|null,send:(command:Command)=>Promise<unknown>,update:(state:GameplayState)=>void,acquireCartridge:(candidate:CartridgeCandidate,room:RoomView,signal:AbortSignal)=>Promise<File>=async()=>{throw Error('Cartridge acquisition is unavailable.');}){this.acquireCartridge=acquireCartridge;this.player=player;this.send=send;this.update=update;}
 private publish(patch:Partial<GameplayState>){this.state={...this.state,...patch};this.update(this.state);}
 private self(){return this.room?.chatMembership??'';}
 private authority(){return !!this.room&&this.self()===this.room.hostMembership;}
 private observerSlot(){return this.room?.slots.find(slot=>slot.member?.id===this.self())?.role==='observer';}
 private ownsInput(controllers=this.controllers){return controllers.owners.includes(this.self());}
 private loaded(){return !!this.room?.fingerprint&&!!this.file&&this.room.matches&&matchesFile(this.room.fingerprint,this.file)&&!!this.player()?.isLoaded(this.file);}
 enter(room?:RoomView){
  const prior=this.room;if(prior&&(!room||room.id!==prior.id||room.chatMembership!==prior.chatMembership))this.clear('Lobby membership changed. Your game is preserved.',true);
  if(room&&(!prior||room.id!==prior.id||room.chatMembership!==prior.chatMembership)){this.intent=false;this.offered=undefined;this.publish({intent:false,preparationError:undefined});}
  this.room=room;if(!room)return;
  const announcement=this.announcedLoad;if(announcement){this.announcedLoad=undefined;if(announcement.room===room.id&&announcement.member===this.self()&&announcement.serial===this.serial&&room.game.load?.id===announcement.event.transactionId)this.handle(announcement.event);}
  // A room revision can change the roster or roles while a local checksum is
  // still being prepared. That earlier click does not authorize a new offer.
  if(prior&&prior.id===room.id&&prior.chatMembership===room.chatMembership&&prior.revision!==room.revision&&!room.started){
   ++this.serial;this.intent=false;this.offered=undefined;this.offering=false;
   this.publish({intent:false,busy:false,preparationError:undefined,status:'Lobby changed. Choose Ready again.'});
  }
  for(const member of this.links.keys())if(!room.slots.some(slot=>slot.member?.id===member))this.closed(member);
  if(prior?.game.controllers.revision!==room.game.controllers.revision){this.offered=undefined;this.observeRequested=undefined;this.inputLease=undefined;this.controllers=room.game.controllers;this.scheduler?.configure(room.game.controllers.owners.map(owner=>owner??undefined) as [string|undefined,string|undefined],room.game.controllers.revision);this.player()?.setGameInputOwner(!this.incoming&&this.ownsInput());if(this.scheduler?.authority)for(const [member,link] of this.links){link.leaseAt=0;if(room.game.status==='playing'&&room.game.controllers.owners.includes(member)&&!prior?.game.controllers.owners.includes(member))this.isolate(member,'Player assignment changed.');else link.inputReady=link.inputReady&&!link.recovering;}}
  if(room.game.status==='resume_ready'&&(this.incoming?.purpose==='controller'||[...this.outgoing.values()].some(value=>value.request.purpose==='controller'))){if(this.incoming?.purpose==='controller')this.cancelIncoming();for(const outgoing of [...this.outgoing.values()])if(outgoing.request.purpose==='controller')this.cancelOutgoing(outgoing);this.publish({busy:false,synchronizing:false,status:'Paused game synchronized. The host can resume.'});}
  if(prior&&!this.loadAttempt?.replacement&&prior.game.epoch!==room.game.epoch&&!this.authority()&&!room.game.controllers.owners.includes(this.self()))this.clear('Game roles changed. Synchronizing the current game.');
  if(room.game.status==='playing'&&!this.authority()&&this.loaded()&&!this.scheduler&&!this.incoming&&!this.observeRequested)this.observe();
  // A paused Prepare click may precede the service's file-match confirmation.
  if(this.intent&&(!room.started||(!prior?.matches&&room.matches&&['paused','failed','waiting'].includes(room.game.status))))void this.offer();
 }
 selected(file:Fingerprint){if(this.file&&this.room&&(this.offered||this.offering||this.incoming||this.scheduler)){const revision=this.room.game.controllers.revision;this.clear('Game selection changed. Prepare the matching game again.');void this.send({type:'gameUnready',revision}).catch(()=>{});}this.file=file;this.offered=undefined;if(this.state.preparationError)this.publish({preparationError:undefined});if(this.room?.game.status==='playing'&&!this.authority())this.observe();else if(this.intent)void this.offer();}
 playIntent(){this.intent=true;this.offered=undefined;this.publish({intent:true,preparationError:undefined});if(this.room?.game.status==='playing'&&!this.authority())this.observe();else void this.offer();}
 retry(){if(this.room?.game.status==='playing'&&!this.authority())this.observe();else this.playIntent();}
 retryConnection(){if(this.room?.game.status==='playing'&&!this.authority())this.observe();}
 async resumeReady(){if(this.room?.game.status==='playing'&&!this.authority()){this.observe();return;}this.intent=true;this.offered=undefined;this.publish({intent:true,preparationError:undefined});await this.offer();}
 async resumeTogether(){const epoch=this.room?.game.epoch;if(epoch)try{await this.send({type:'gameResume',epoch});}catch(error){this.publish({status:String(error),busy:false});}}
 async loadSaved(record:SaveSlot,current:()=>Promise<boolean>){
  const room=this.room,player=this.player();if(!room||!player||!this.authority()||!this.loaded())throw Error('Only the host can load saved progress after the matching game is loaded.');
  if(room.game.load||this.manualSave||this.manualLoadRequest||room.game.pending)throw Error('Another game change is pending.');
  const request=Symbol(),serial=this.serial;this.manualLoadRequest=request;let owned:ManualSave|undefined;
  try{
   const info=await player.inspectSave(record.bytes),valid=await current();if(serial!==this.serial||this.manualLoadRequest!==request||!valid)throw Error('Saved progress changed. Choose Load again.');
   if(info.identity!==record.identity)throw Error('This save does not match the selected game.');
   if(record.hash!==undefined&&record.hash!==info.hash)throw Error('Saved progress is damaged.');
   const capture:Capture={type:'peer-checkpoint-exported',requestId:0,bytes:record.bytes.slice(0),identity:info.identity,hash:info.hash,frame:record.frame??0,epoch:''};
   owned={record,capture,current,serial};this.manualSave=owned;
   await this.send({type:'gameLoadPropose',revision:room.game.controllers.revision,roomRevision:room.revision,frame:capture.frame,hash:capture.hash,identity:capture.identity,savedAt:record.savedAt});
  }catch(error){if(owned&&this.manualSave===owned)this.manualSave=undefined;throw error;}
  finally{if(this.manualLoadRequest===request)this.manualLoadRequest=undefined;}
 }
 async replaceCartridge(intent:string,current:()=>boolean){
  const room=this.room,player=this.player();if(!room||!player||!this.authority()||room.game.load||this.manualSave||this.manualLoadRequest)throw Error('Another game change is pending.');
  const captured=await player.captureCartridge();if(!current())throw Error('Game selection changed.');
  const capture:Capture={...captured,type:'peer-checkpoint-exported',epoch:''};this.manualSave={capture,current:async()=>current(),serial:this.serial};
  const completion=new Promise<void>((resolve,reject)=>{this.replacementCompletion={intent,resolve,reject};});void completion.catch(()=>{});
  try{await this.send({type:'gameLoadPropose',revision:room.game.controllers.revision,roomRevision:room.revision,frame:captured.frame,hash:captured.hash,identity:captured.identity,savedAt:Date.now(),selectionIntent:intent});await completion;}
  catch(error){this.replacementCompletion=undefined;this.manualSave=undefined;throw error;}
 }
 private async ensureCartridge(current:()=>boolean){const candidate=this.loadAttempt?.replacement,room=this.room;if(!candidate||!room||this.authority())return;const controller=new AbortController();this.candidateAcquisition=controller;try{const file=await this.acquireCartridge(candidate,room,controller.signal);if(!current())throw Error('Game selection changed.');await this.player()!.prepareCartridge(file,current);}finally{controller.abort();if(this.candidateAcquisition===controller)this.candidateAcquisition=undefined;}}
 // Ready revisions do not revoke the native rollback obligation of the same room transaction.
 private ownsLoad(id:string){const attempt=this.loadAttempt;return !!attempt&&attempt.id===id&&attempt.room===this.room?.id&&attempt.member===this.self()&&(!!attempt.replacement||this.loaded());}
 private loadFailure(id:string,error:unknown){if(!this.ownsLoad(id))return;this.publish({busy:false,status:String(error)});void this.send({type:'gameLoadFailed',transactionId:id}).catch(()=>{});}
 private async completeLoadHold(event:Extract<GameEvent,{type:'gameLoadHold'}>){
  if(!this.ownsLoad(event.transactionId)||this.loadHold!==event)return;
  this.loadHold=undefined;const info=await this.player()!.holdForGame(false);if(!this.ownsLoad(event.transactionId))return;
  if(this.room?.game.load?.freezeRequired?.includes(this.self())!==false&&event.frame!==undefined&&info.frame<event.frame){this.loadHold=event;this.frozenRecovery=true;await this.send({type:'gameObserve',revision:this.controllers.revision});return;}
  if(this.room?.game.load?.freezeRequired?.includes(this.self())!==false&&event.frame!==undefined&&(info.frame!==event.frame||info.hash!==event.hash))throw Error('Players could not reach the same pause boundary.');
  this.frozen=true;this.cancelIncoming();this.player()!.stopGame('Preparing to load saved progress.');this.loadHold=undefined;
  await this.send({type:'gameLoadBoundary',transactionId:event.transactionId,frame:info.frame,hash:info.hash});
 }
 private async handleLoad(event:Extract<GameEvent,{type:'gameLoadHold'|'gameLoadStage'|'gameLoadCommit'|'gameLoadRollback'|'gameLoadFinish'}>){
  if(event.type==='gameLoadHold'){
   if(!this.room||!this.loaded())return;
   this.loadAttempt={id:event.transactionId,room:this.room.id,member:this.self(),replacement:this.room.game.load?.replacement,candidateRequired:this.room.game.load?.required.includes(this.self())};this.loadHold=event;if(this.loadAttempt.replacement&&this.loadAttempt.candidateRequired)this.player()?.ownCartridge(event.transactionId);this.intent=false;this.offered=undefined;this.publish({busy:true,status:'Preparing to load saved progress.'});
   if(this.room.game.load?.freezeRequired?.includes(this.self())!==false&&event.frame!==undefined&&this.scheduler&&this.scheduler.frame<event.frame){this.fence=event.frame;this.frozen=false;this.player()?.drainGame();return;}
   await this.completeLoadHold(event);return;
  }
  if(!this.ownsLoad(event.transactionId))return;
  const current=()=>this.ownsLoad(event.transactionId);
  if(event.type==='gameLoadStage'){
   for(const outgoing of [...this.outgoing.values()])if(outgoing.request.purpose==='controller')this.cancelOutgoing(outgoing);if(this.incoming?.purpose==='controller')this.cancelIncoming();const save=this.manualSave;if(!this.authority()||!save||save.serial!==this.serial||!await save.current()||!current())throw Error('Saved progress changed. Load again.');
   const prepared=await this.player()!.prepareSharedSave(event.transactionId,event.epoch,event.frame,save.capture.bytes,save.capture.identity,event.hash,current);if(current())await this.send({type:'gameLoadPrepared',transactionId:event.transactionId,frame:prepared.frame,hash:prepared.hash});return;
  }
  if(event.type==='gameLoadCommit'){
   if(this.authority()&&(!this.manualSave||!await this.manualSave.current()||!current()))throw Error('Saved progress changed. Load again.');
   const result=await this.player()!.commitSharedSave(event.transactionId,current);if(result.frame!==event.frame||result.hash!==event.hash)throw Error('Loaded progress did not match the saved state.');
   if(current())await this.send({type:'gameLoadCommitted',transactionId:event.transactionId,frame:result.frame,hash:result.hash});return;
  }
  if(event.type==='gameLoadRollback'){
   this.loadHold=undefined;this.cancelAllTransfers();const cartridge=this.loadAttempt?.replacement;const staged=this.loadAttempt?.candidateRequired;const info=cartridge?await this.player()!.rollbackCartridge(event.transactionId,!!staged,current):await this.player()!.rollbackSharedSave(event.transactionId,current);if(!current())return;
   if(info.frame!==event.frame||info.hash!==event.hash)throw Error('Previous progress could not be restored. Keep the game paused.');
   this.manualSave=undefined;await this.send({type:'gameLoadRolledBack',transactionId:event.transactionId,frame:info.frame,hash:info.hash});this.replacementCompletion?.reject(Error(event.reason));this.replacementCompletion=undefined;return;
  }
  const replacement=this.loadAttempt?.replacement,required=this.loadAttempt?.candidateRequired;
  const attempt=this.loadAttempt,player=this.player();
  if(!replacement||required)await player!.finishSharedSave(event.transactionId,()=>this.loadAttempt===attempt&&current());
  if(this.loadAttempt!==attempt||!current())return;
  this.manualSave=undefined;this.loadAttempt=undefined;this.loadHold=undefined;this.cancelAllTransfers();
  if(this.replacementCompletion&&replacement&&this.replacementCompletion.intent===replacement.intent){this.replacementCompletion.resolve();this.replacementCompletion=undefined;}this.publish({busy:false,status:replacement?'NES game replaced. Choose Prepare.':'Saved progress loaded.'});
 }
 requestPause(){this.pause('user');}
 observe(){const room=this.room;if(!room||!this.loaded()||room.game.status!=='playing'||this.authority()||this.links.get(room.hostMembership)?.channel.readyState!=='open'||room.peers.find(peer=>peer.member===room.hostMembership)?.status!=='connected'||room.slots.find(slot=>slot.member?.id===this.self())?.member?.acquisition!=='loaded')return;this.intent=true;const epoch=room.game.epoch!;this.observeRequested=epoch;this.publish({busy:true,synchronizing:true,intent:true,status:'Requesting the current game for observation…'});void this.send({type:'gameObserve',revision:room.game.controllers.revision}).catch(error=>{if(this.observeRequested===epoch){this.observeRequested=undefined;this.publish({busy:false,synchronizing:false,status:String(error)});}});}
 cancelIntent(){const room=this.room;if(!room){this.intent=false;this.offered=undefined;this.publish({intent:false});return;}this.clear('Synchronization cancelled. Game progress is preserved.');void this.send({type:'gameUnready',revision:room.game.controllers.revision}).catch(()=>{});}
 private async offer(){
  const room=this.room;if(!room||!this.intent||this.offering||this.incoming||room.game.pending||room.game.load||(['playing','starting','countdown','pausing'].includes(room.game.status)&&room.game.controllers.owners.includes(this.self())))return;
  if(!this.loaded()){this.publish({busy:false,status:'Waiting for the matching lobby game to finish loading…'});return;}
  if(!this.authority()&&this.links.get(room.hostMembership)?.channel.readyState!=='open'){this.publish({busy:false,status:'Waiting for the host connection. Retry connection if it fails.'});return;}
  const key=room.id+room.revision+room.game.controllers.revision+(room.game.epoch??'initial');if(this.offered===key)return;
  const serial=this.serial;this.offering=true;this.offered=key;this.publish({busy:true,preparationError:undefined,status:'Checking the completed machine state…'});
  try{const info=await this.player()!.holdForGame(room.game.controllers.owners.includes(this.self()));if(serial!==this.serial)return;
   await this.send({type:'gameReady',revision:room.game.controllers.revision,roomRevision:room.revision,...info,protocol:gameplayProtocol});
   if(serial===this.serial)this.publish({busy:false,status:'Ready. Waiting for everyone.'});
  }catch(error){if(serial===this.serial){const message=error instanceof Error?error.message:String(error);const code=error instanceof Error?(error as Error & {code?:string}).code:undefined;
   const display=code==='room_changed'?'Lobby changed. Try again.':message.startsWith('The lobby service did not respond.')?'Lobby service did not respond. Try again.':message;
   this.offered=undefined;this.intent=false;this.publish({busy:false,intent:false,preparationError:display,status:message});}}finally{if(serial===this.serial)this.offering=false;}
 }
 ready(member:string,channel:RTCDataChannel,epoch:string){
  clearTimeout(this.links.get(member)?.continuation);const checkpoint=this.checkpointLinks.get(member);this.links.set(member,{epoch,channel,checkpoint:checkpoint?.epoch===epoch?checkpoint.channel:undefined,live:false,stream:this.scheduler?.epoch??epoch,inputReady:true,recovering:false,leaseAt:0});channel.bufferedAmountLowThreshold=16*1024;
  channel.onmessage=({data})=>{if(this.links.get(member)?.channel===channel)this.receive(member,data);};channel.onbufferedamountlow=()=>{const link=this.links.get(member);if(link?.channel===channel&&link.live)this.pumpLink(member,link);for(const outgoing of this.outgoing.values())if(outgoing.request.recipient===member)this.catchup(outgoing);};
  if(this.intent)void this.offer();if(this.room?.game.status==='playing'&&!this.scheduler&&!this.authority())this.observe();
 }
 closed(member:string,epoch?:string){const link=this.links.get(member);if(epoch&&link?.epoch!==epoch)return;clearTimeout(link?.continuation);this.links.delete(member);this.checkpointLinks.delete(member);
  for(const outgoing of [...this.outgoing.values()])if(outgoing.request.recipient===member)this.failOutgoing(outgoing,'Observer connection changed.');
  if(member===this.room?.hostMembership)this.clear('Host connection changed. Progress is preserved; synchronize after reconnecting.');
  else if(this.authority())this.scheduler?.revoke(member);
 }
 handle(event:GameEvent){
  if(event.type==='gameLoadRollback'&&!this.loadAttempt&&this.room?.game.load?.id===event.transactionId&&this.loaded())this.loadAttempt={id:event.transactionId,room:this.room.id,member:this.self()};
  if(event.type==='gameLoadHold'&&this.room?.game.load?.id!==event.transactionId){if(this.room)this.announcedLoad={event,room:this.room.id,member:this.self(),serial:this.serial};return;}
  if(event.type==='gameLoadHold'||event.type==='gameLoadStage'||event.type==='gameLoadCommit'||event.type==='gameLoadRollback'||event.type==='gameLoadFinish'){const loadEvent=event;this.loadEvents=this.loadEvents.then(()=>this.handleLoad(loadEvent)).catch(error=>this.loadFailure(loadEvent.transactionId,error));return;}
  if(event.type==='gamePrepare'&&this.loadAttempt){this.loadEvents=this.loadEvents.then(()=>{if(!this.loadAttempt)this.handle(event);});return;}
  if(event.type==='gameInspect'){this.intent=true;this.offered=undefined;void this.offer();return;}
  if(event.type==='gameCapture'){this.capture(event);return;}
  if(event.type==='gameCheckpoint'){
   if(event.sender!==this.room?.hostMembership||!this.room.slots.some(slot=>slot.member?.id===event.recipient))return;
   if(this.authority()){const outgoing=this.outgoing.get(event.transferId);if(outgoing)outgoing.spec=event;}else if(event.recipient===this.self())void this.beginIncoming(event);return;
  }
  if(event.type==='gameCheckpointSend'){const outgoing=this.outgoing.get(event.transferId);if(outgoing&&outgoing.request.recipient===event.recipient){outgoing.sendRequested=true;this.sendCheckpoint(outgoing);}return;}
  if(event.type==='gameCatchup'){const outgoing=this.outgoing.get(event.transferId);if(outgoing){outgoing.cursor=event.frame;this.catchup(outgoing);}return;}
  if(event.type==='gameSyncStop'){
   if(this.observerCompletion?.transferId===event.transferId)this.observerCompletion=undefined;
   const outgoing=this.outgoing.get(event.transferId);if(outgoing)this.cancelOutgoing(outgoing);
   if(this.incoming?.transferId===event.transferId||!this.incoming&&this.observeRequested===event.epoch&&!this.scheduler){this.cancelIncoming();this.scheduler=undefined;this.player()?.stopGame(event.reason);this.publish({busy:false,synchronizing:false,observing:false,status:event.reason});}return;
  }
  if(event.type==='gameLive'){if(this.authority()){const outgoing=this.outgoing.get(event.transferId),link=this.links.get(event.recipient);if(outgoing&&link&&outgoing.boundary?.frame===event.frame&&outgoing.boundary.hash===event.hash){this.cancelOutgoing(outgoing);link.inputReady=true;link.recovering=false;link.leaseAt=0;this.renewInputs();}}else if(event.recipient===this.self()&&this.incoming?.transferId===event.transferId&&event.frame===this.catchupTarget&&event.hash===this.catchupHash){this.cancelIncoming();this.player()?.setGameInputOwner(this.ownsInput());this.observeRequested=undefined;this.publish({busy:false,synchronizing:false,observing:this.observerSlot(),status:this.ownsInput()?'Playing together.':'Observing the current game.'});}return;}
  if(event.type==='gameStop'){this.clear(event.reason);return;}
  if(event.type==='gameFreeze'){
   if(!this.authority()||event.epoch!==this.room?.game.epoch)return;if(this.room.game.pending||this.room.game.load)this.cancelAllTransfers();this.frozen=true;const serial=this.serial;this.publish({busy:true,status:event.reason});
   void this.player()!.holdForGame(false).then(info=>{if(serial!==this.serial)return;this.player()?.releaseControllers();return this.send({type:'gameFrozen',epoch:event.epoch,frame:info.frame,hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'network');});return;
  }
  if(event.type==='gamePauseAt'){
   if(this.scheduler?.epoch!==event.epoch&&this.incoming?.epoch!==event.epoch)return;this.fence=event.frame;this.frozen=false;this.publish({status:event.reason,busy:true});if(this.scheduler?.frame===event.frame)void this.finishPause();else this.player()?.drainGame();return;
  }
  if(!this.room||!this.loaded())return;
  if(event.type==='gamePrepare'){
   this.cancelAllTransfers();for(const link of this.links.values()){clearTimeout(link.continuation);link.continuation=undefined;}++this.serial;this.offering=false;const serial=this.serial;this.prepared=event;this.receiveStream=event.epoch;this.controllers=event.controllers;this.scheduler=this.makeScheduler(event.epoch,event.frame,event.controllers,false);this.frozen=true;this.historyHashes.clear();
   this.publish({busy:true,status:'Starting together…'});
   void this.player()!.holdForGame(this.ownsInput()).then(async info=>{if(serial!==this.serial)return;if(info.frame!==event.frame||info.hash!==event.hash)throw Error('State changed before shared start');await this.player()!.bindGameEpoch(event.epoch,event.frame,event.hash);if(serial!==this.serial)return;return this.send({type:'gameAck',epoch:event.epoch,hash:info.hash});}).catch(error=>{if(serial===this.serial)this.fail(String(error),'mismatch');});return;
  }
  if(event.type==='gameStart'){
   if(this.prepared?.epoch!==event.epoch)return;for(const [member,link] of this.links){link.live=event.controllers.owners.includes(member);link.inputReady=link.live;link.cursor=event.frame;link.stream=event.epoch;link.leaseAt=0;}
   this.install(event.epoch,event.frame,event.controllers,false);
  }
 }
 private makeScheduler(epoch:string,frame:number,controllers:ControllerAssignment,observer:boolean){return new GameScheduler(epoch,{local:this.self(),authority:this.room!.hostMembership,revision:controllers.revision,controllers:controllers.owners.map(owner=>owner??undefined) as [string|undefined,string|undefined],observer},packet=>this.sendPacket(packet),frame);}
 private install(epoch:string,frame:number,controllers:ControllerAssignment,observer:boolean){
  this.controllers=controllers;if(observer||this.scheduler?.epoch!==epoch)this.scheduler=this.makeScheduler(epoch,frame,controllers,observer);
  this.receiveStream=this.incoming?.transferId??epoch;this.inputLease=undefined;this.frozen=false;if(!observer)this.fence=undefined;this.hashing=false;this.pausedSent=false;this.missingSince=0;
  this.player()!.startGame({epoch,next:mask=>this.next(mask),committed:frame=>this.committed(frame),pause:reason=>this.pause(reason),draining:()=>this.catchingUp||this.fence!==undefined,silent:()=>this.catchingUp,sample:(mask,release)=>this.sampleControls(mask,release),ownsInput:!observer&&this.ownsInput()});
  this.publish({status:observer?'Catching up with the current game…':'Playing together.',busy:observer,synchronizing:observer,observing:observer,frame});
 }
 private renewInputs(){const scheduler=this.scheduler;if(!scheduler?.authority||this.frozen)return;
  const now=performance.now();for(const [member,link] of this.links){if(!link.inputReady||link.channel.readyState!=='open'||link.channel.bufferedAmount>32*1024)continue;
   if(now-link.leaseAt<gameplayLimits.leaseRenewMs&&scheduler.lease(member))continue;const lease=scheduler.grant(member,link.epoch,crypto.randomUUID());if(lease){link.leaseAt=now;try{link.channel.send(JSON.stringify(lease));}catch{this.isolate(member,'Player input connection changed.');}}
  }
 }
 private sampleControls(mask:number,release=false){const scheduler=this.scheduler;if(!scheduler||this.frozen)return;
  scheduler.sample(mask,release);if(this.authority()){this.renewInputs();return;}
  const lease=this.inputLease,link=this.links.get(this.room!.hostMembership);if(!lease||!link||lease.generation!==link.epoch||lease.revision!==this.controllers.revision||!this.ownsInput())return;
  const now=performance.now();if(!release&&mask===this.inputMask&&now-this.inputSentAt<gameplayLimits.inputHeartbeatMs)return;
  this.inputMask=mask;this.inputSentAt=now;const packet:GamePacket={kind:'input',epoch:scheduler.epoch,revision:lease.revision,generation:lease.generation,lease:lease.lease,sequence:++this.inputSequence,mask:release?0:mask,release};
  this.sendPacket(packet);
 }
 private isolate(member:string,status:string){const link=this.links.get(member);this.scheduler?.revoke(member);if(!link)return;clearTimeout(link.continuation);link.continuation=undefined;link.live=false;link.inputReady=false;
  if(link.recovering||!this.room||this.room.game.status!=='playing')return;link.recovering=true;
  void this.send({type:'gameResynchronize',epoch:this.scheduler!.epoch,revision:this.controllers.revision,recipient:member}).catch(()=>{if(this.links.get(member)===link){link.recovering=false;this.publish({status,busy:false});}});
 }
 private pumpLink(member:string,link:Link){const scheduler=this.scheduler;if(this.links.get(member)!==link||!scheduler?.authority||!link.live||link.cursor===undefined)return;
  if(link.channel.readyState!=='open'||link.channel.bufferedAmount>64*1024){this.isolate(member,'Guest delivery stopped draining.');return;}
  try{let count=0;while(link.cursor<scheduler.frame&&count++<gameplayLimits.catchupBatch){if(link.channel.bufferedAmount>32*1024)return;const packet=scheduler.historyFrame(link.cursor);if(!packet)throw Error('Guest delivery fell outside retained history.');link.channel.send(JSON.stringify({...packet,stream:link.stream}));link.cursor++;
    const hash=link.cursor%gameplayLimits.hashInterval===0?this.historyHashes.get(link.cursor):undefined;if(hash)link.channel.send(JSON.stringify({kind:'hash',epoch:scheduler.epoch,stream:link.stream,frame:link.cursor,hash}));
   }
   if(link.cursor<scheduler.frame)link.continuation??=setTimeout(()=>{link.continuation=undefined;if(this.scheduler===scheduler)this.pumpLink(member,link);},0);
  }catch{this.isolate(member,'Guest connection changed.');}
 }
 private sendPacket(packet:GamePacket){
  if(this.authority()){
   if(packet.kind==='hash'){this.historyHashes.set(packet.frame,packet.hash);for(const frame of this.historyHashes.keys())if(frame<packet.frame-gameplayLimits.historyFrames)this.historyHashes.delete(frame);}
   // Drain healthy replicas independently. A slow replica owns its cursor and recovery.
   for(const [member,link] of [...this.links].sort((a,b)=>a[1].channel.bufferedAmount-b[1].channel.bufferedAmount))if(link.live){this.pumpLink(member,link);if(packet.kind==='hash'&&link.live&&link.cursor===packet.frame)try{link.channel.send(JSON.stringify({...packet,stream:link.stream}));}catch{this.isolate(member,'Guest connection changed.');}}
  }else {const channel=this.links.get(this.room!.hostMembership)?.channel;if(channel?.readyState!=='open'||channel.bufferedAmount>64*1024){this.inputLease=undefined;return;}try{channel.send(JSON.stringify(packet.kind==='hash'?{...packet,stream:this.receiveStream}:packet));}catch{this.inputLease=undefined;}}
 }
 private receive(member:string,raw:unknown){
  if(typeof raw==='string'&&raw.length<gameplayLimits.packetBytes){try{const marker=JSON.parse(raw);if(marker.kind==='live'&&member===this.room?.hostMembership&&this.incoming?.transferId===marker.transferId&&marker.epoch===this.scheduler?.epoch&&Number.isSafeInteger(marker.frame)&&typeof marker.hash==='string'&&/^[a-f0-9]{64}$/.test(marker.hash)){this.catchupTarget=marker.frame;this.catchupHash=marker.hash;this.finishCatchup();return;}}catch{}}
  const packet=parseGamePacket(raw);if(!packet){if(this.authority())this.isolate(member,'Invalid guest gameplay packet.');else if(member===this.room?.hostMembership)this.fail('Invalid authoritative gameplay packet.','network');return;}
  const scheduler=this.scheduler;if(!scheduler||packet.epoch!==scheduler.epoch)return;
  if(packet.kind==='lease'){const link=this.links.get(member);if(this.authority()||member!==this.room?.hostMembership||packet.generation!==link?.epoch||packet.revision!==this.controllers.revision||this.catchingUp)return;this.inputLease=packet;this.inputSentAt=0;this.sampleControls(this.player()?.sampleGameInput()??0);return;}
  if(!this.authority()&&'stream' in packet&&packet.stream!==this.receiveStream)return;if(this.authority()&&packet.kind==='hash'&&packet.stream!==this.links.get(member)?.stream)return;
  try{scheduler.receive(packet,member);for(const peer of scheduler.takeFaults())this.isolate(peer,'Guest state needs synchronization.');this.player()?.wakeGame(packet.epoch);}catch(error){if(this.authority())this.isolate(member,String(error));else this.fail(String(error),'mismatch');}
 }
 private next(mask:number){const scheduler=this.scheduler;if(!scheduler||this.frozen||this.hashing||this.pausedSent)return;if(this.fence!==undefined&&scheduler.frame>=this.fence){void this.finishPause();return;}
  try{this.sampleControls(this.fence!==undefined?0:mask);if(this.catchingUp&&this.catchupTarget!==undefined&&scheduler.frame>=this.catchupTarget){this.finishCatchup();return;}const value=scheduler.next();if(!value){this.missingSince ||=performance.now();if(!this.authority()&&this.fence!==undefined&&performance.now()-this.missingSince>gameplayLimits.stallMs&&!this.frozenRecovery){this.frozenRecovery=true;void this.send({type:'gameObserve',revision:this.controllers.revision}).catch(error=>this.fail(String(error),'network'));}else if(!this.catchingUp&&this.room?.game.status==='playing'&&performance.now()-this.missingSince>gameplayLimits.catchupMs)this.fail('Observation stopped receiving frames. Choose Observe game to synchronize again.','network');return;}this.missingSince=0;return {frame:scheduler.frame,p1:value[0],p2:value[1]};}catch(error){this.fail(String(error),'network');}}
 private committed(frame:number){const scheduler=this.scheduler;if(!scheduler||frame!==scheduler.frame)return;try{scheduler.commit();this.committedEpoch=scheduler.epoch;}catch(error){this.fail(String(error),'network');return;}this.publish({frame:scheduler.frame});for(const outgoing of this.outgoing.values())if(!outgoing.capture&&!outgoing.exporting)this.exportCapture(outgoing);
  if(this.fence===scheduler.frame){void this.finishPause();return;}
  // Pause takes over native hash ownership; late interval replies belong to the closed run.
  if(scheduler.frame%gameplayLimits.hashInterval===0){this.hashing=true;const current=()=>this.scheduler===scheduler&&!this.pausedSent;void this.player()!.stateHash().then(info=>{if(current()){scheduler.hash(info.hash);for(const member of scheduler.takeFaults())this.isolate(member,'Guest state needs synchronization.');this.publish({hash:info.hash});}}).catch(error=>{if(current())this.fail(String(error),'mismatch');}).finally(()=>{if(current()){this.hashing=false;for(const outgoing of this.outgoing.values())this.catchup(outgoing);this.finishCatchup();this.player()?.wakeGame(scheduler.epoch);}});}else{for(const outgoing of this.outgoing.values())this.catchup(outgoing);this.finishCatchup();}
 }
 private pause(reason:GameReason){if(reason!=='user'&&!this.authority()){this.fail('Guest emulator interrupted. Retry synchronization.','network');return;}const scheduler=this.scheduler;if(!scheduler||this.frozen||this.fence!==undefined)return;if(!this.authority()&&!this.ownsInput()){this.fail('Observation interrupted. Retry synchronization.','network');return;}this.frozen=true;void this.send({type:'gamePause',epoch:scheduler.epoch,frame:scheduler.frame,reason}).catch(error=>{if(this.scheduler===scheduler)this.fail(String(error),'network');});}
 private async finishPause(){const scheduler=this.scheduler;if(!scheduler||this.pausedSent)return;this.pausedSent=true;this.hashing=false;try{const info=await this.player()!.holdForGame(false);if(this.scheduler!==scheduler)return;this.historyHashes.set(info.frame,info.hash);for(const outgoing of this.outgoing.values())this.catchup(outgoing);this.finishCatchup();this.player()!.stopGame('Paused. Prepare to resume.');this.publish({busy:false,status:'Paused. Prepare to resume.'});await this.send({type:'gamePaused',epoch:scheduler.epoch,frame:info.frame,hash:info.hash});if(this.loadHold)await this.completeLoadHold(this.loadHold);}catch(error){if(this.scheduler===scheduler)this.fail(String(error),'mismatch');}}
 checkpointChannel(member:string,channel:RTCDataChannel,epoch:string){
  this.checkpointLinks.set(member,{epoch,channel});const link=this.links.get(member);if(link?.epoch===epoch)link.checkpoint=channel;channel.binaryType='arraybuffer';channel.bufferedAmountLowThreshold=CHECKPOINT_BUFFER_BYTES/2;
  channel.onbufferedamountlow=()=>{for(const outgoing of this.outgoing.values())if(outgoing.request.recipient===member&&outgoing.sending)this.pump(outgoing);};
  const flush=()=>{if(this.checkpointLinks.get(member)?.channel!==channel||this.checkpointLinks.get(member)?.epoch!==epoch||channel.readyState!=='open')return;for(const outgoing of this.outgoing.values())if(outgoing.request.recipient===member&&outgoing.sendRequested&&!outgoing.checkpointStarted)this.sendCheckpoint(outgoing);};
  channel.addEventListener('open',flush);flush();
  channel.onmessage=({data})=>{const spec=this.incoming;if(!spec||member!==spec.sender||this.checkpointLinks.get(member)?.channel!==channel)return;const bytes=typeof data==='string'?data.length:data instanceof ArrayBuffer?data.byteLength:Infinity;
   if(bytes>(typeof data==='string'?2048:CHECKPOINT_CHUNK_BYTES)||this.queuedBytes+bytes>CHECKPOINT_MAX_BYTES+64*1024||this.queuedMessages>=256){this.failIncoming(spec,'Checkpoint queue exceeded its limit.');return;}
   try{const transfer=typeof data==='string'?parseCheckpointMetadata(data)?.transferId:decodeCheckpointChunk(data).transferId;if(transfer&&transfer!==spec.transferId)return;}catch{this.failIncoming(spec,'Malformed checkpoint data.');return;}
   this.queuedBytes+=bytes;this.queuedMessages++;this.receivedSerial=this.receivedSerial.then(async()=>{if(this.incoming!==spec)return;if(typeof data==='string'){const metadata=parseCheckpointMetadata(data);if(!metadata)throw Error('Invalid checkpoint metadata');this.receiver.begin(metadata,value=>this.authorized(value,spec));return;}
    const result=await this.receiver.accept(data,value=>this.authorized(value,spec));if(!result)return;const current=()=>this.incoming===spec&&this.authorized(result.metadata,spec);const restored=spec.purpose==='load'?await this.player()!.prepareSharedSave(this.loadAttempt!.id,spec.epoch,spec.frame,result.bytes,result.metadata.identity,spec.hash,current):await this.player()!.importPeerCheckpoint(spec.epoch,spec.frame,result.bytes,result.metadata.identity,spec.hash,current);if(!current())return;
    if(spec.purpose==='live'){this.catchingUp=true;this.catchupTarget=undefined;this.install(spec.epoch,spec.frame,this.room!.game.controllers,true);clearTimeout(this.incomingTimer);this.incomingTimer=setTimeout(()=>this.failIncoming(spec,'Observer catch-up timed out. Retry synchronization.'),gameplayLimits.catchupMs);}
    await this.send({type:'gameCheckpointAck',epoch:spec.epoch,transferId:spec.transferId,frame:restored.frame,hash:restored.hash});
   }).catch(error=>{if(this.incoming===spec)this.failIncoming(spec,String(error));}).finally(()=>{this.queuedBytes-=bytes;this.queuedMessages--;});
  };
 }
 private authorized(metadata:CheckpointMetadata,spec:Spec){return this.incoming===spec&&this.loaded()&&(spec.purpose==='load'?this.room?.game.load?.epoch===spec.epoch&&this.ownsLoad(this.room.game.load.id):this.room?.game.epoch===spec.epoch)&&metadata.transferId===spec.transferId&&metadata.sender===spec.sender&&metadata.recipient===this.self()&&metadata.epoch===spec.epoch&&metadata.frame===spec.frame&&metadata.hash===spec.hash;}
 private async beginIncoming(spec:Spec){if(!this.loaded()||(spec.purpose==='load'?spec.epoch!==this.room?.game.load?.epoch||!this.ownsLoad(this.room.game.load.id):spec.epoch!==this.room?.game.epoch))return;this.cancelIncoming();this.incoming=spec;this.intent=true;this.frozen=true;this.publish({busy:true,synchronizing:true,status:'Synchronizing the host’s current game…'});this.incomingTimer=setTimeout(()=>this.failIncoming(spec,'Synchronization timed out. Retry.'),CHECKPOINT_TIMEOUT_MS);
  try{await this.ensureCartridge(()=>this.incoming===spec&&this.ownsLoad(this.loadAttempt!.id));await this.player()!.holdForGame(false);if(this.incoming!==spec)return;this.scheduler=undefined;await this.send({type:'gameCheckpointReady',epoch:spec.epoch,transferId:spec.transferId});}catch(error){if(this.incoming===spec)this.failIncoming(spec,String(error));}
 }
 private capture(request:Extract<GameEvent,{type:'gameCapture'}>){const link=this.links.get(request.recipient);if(request.purpose==='live'&&link){link.live=false;link.inputReady=false;link.stream=request.transferId;this.scheduler?.revoke(request.recipient);}if(!this.authority()||(request.purpose==='load'?request.epoch!==this.room?.game.load?.epoch:request.epoch!==this.room?.game.epoch)||this.outgoing.size>=4||[...this.outgoing.values()].some(value=>value.request.recipient===request.recipient))return;
  if(request.purpose==='controller')this.publish({busy:true,synchronizing:true,status:'Synchronizing the assigned player from the preserved host game…'});
  const outgoing:Outgoing={request,timer:setTimeout(()=>this.failOutgoing(outgoing,'Checkpoint transfer timed out.'),CHECKPOINT_TIMEOUT_MS)};this.outgoing.set(request.transferId,outgoing);if(request.purpose==='live'&&this.committedEpoch!==request.epoch)return;this.exportCapture(outgoing);
 }
 private exportCapture(outgoing:Outgoing){const request=outgoing.request,scheduler=this.scheduler;outgoing.exporting=true;
  if(request.purpose==='load'){const saved=this.manualSave,capture=saved?.capture;if(!capture){this.failOutgoing(outgoing,'Saved progress is no longer available.');return;}void checkpointDigest(capture.bytes).then(async digest=>{const valid=await saved.current();if(this.outgoing.get(request.transferId)!==outgoing||!this.room?.game.load||!this.ownsLoad(this.room.game.load.id))return;if(!valid)throw Error('Saved progress changed. Load again.');outgoing.capture={...capture,epoch:request.epoch};outgoing.digest=digest;await this.send({type:'gameCaptured',epoch:request.epoch,transferId:request.transferId,frame:capture.frame,hash:capture.hash});}).catch(error=>this.failOutgoing(outgoing,String(error)));return;}
  if(!this.exporting||this.exporting.epoch!==request.epoch){const promise=this.player()!.exportPeerCheckpoint(request.epoch);this.exporting={epoch:request.epoch,promise};void promise.finally(()=>{if(this.exporting?.promise===promise)this.exporting=undefined;}).catch(()=>{});}
  void this.exporting.promise.then(async capture=>{const digest=await checkpointDigest(capture.bytes);if(this.outgoing.get(request.transferId)!==outgoing||request.purpose==='live'&&this.scheduler!==scheduler)return;outgoing.capture=capture;outgoing.digest=digest;await this.send({type:'gameCaptured',epoch:request.epoch,transferId:request.transferId,frame:capture.frame,hash:capture.hash});}).catch(error=>{if(this.outgoing.get(request.transferId)===outgoing)this.failOutgoing(outgoing,String(error));});
 }
 private sendCheckpoint(outgoing:Outgoing){try{const {spec,capture,digest}=outgoing,channel=this.checkpointLinks.get(outgoing.request.recipient)?.channel;if(this.outgoing.get(outgoing.request.transferId)!==outgoing||outgoing.checkpointStarted||!outgoing.sendRequested)return;
  if(!spec||!capture||!digest)throw Error('Checkpoint data unavailable.');
  // Signaling/control readiness does not imply the independent checkpoint channel is open.
  // Keep the authorized transfer within its existing deadline until its current channel opens.
  if(!channel||channel.readyState==='connecting')return;
  if(channel.readyState!=='open')throw Error('Checkpoint transport unavailable.');const metadata:CheckpointMetadata={transferId:spec.transferId,epoch:spec.epoch,frame:spec.frame,hash:spec.hash,sender:spec.sender,recipient:spec.recipient,identity:capture.identity,digest,byteLength:capture.bytes.byteLength};channel.send(JSON.stringify(metadata));outgoing.checkpointStarted=true;this.sender.begin(metadata,capture.bytes,channel);outgoing.sending=true;this.pump(outgoing);}catch(error){this.failOutgoing(outgoing,String(error));}}
 private pump(outgoing:Outgoing){try{if(this.sender.pump(outgoing.request.recipient,metadata=>this.outgoing.get(metadata.transferId)===outgoing)==='complete')outgoing.sending=false;}catch(error){this.failOutgoing(outgoing,String(error));}}
 private catchup(outgoing:Outgoing){if(this.outgoing.get(outgoing.request.transferId)!==outgoing)return;const scheduler=this.scheduler,link=this.links.get(outgoing.request.recipient);if(outgoing.cursor===undefined||!scheduler||!link||outgoing.request.epoch!==scheduler.epoch||outgoing.markerSent)return;
  if(!outgoing.boundary){if(outgoing.boundaryPending||this.hashing)return;outgoing.boundaryPending=true;const known=this.historyHashes.get(scheduler.frame);void (known?Promise.resolve({frame:scheduler.frame,hash:known}):this.player()!.stateHash()).then(async info=>{if(this.outgoing.get(outgoing.request.transferId)!==outgoing||this.scheduler!==scheduler)return;outgoing.boundary={frame:info.frame,hash:info.hash};await this.send({type:'gameCatchupBoundary',epoch:scheduler.epoch,transferId:outgoing.request.transferId,frame:info.frame,hash:info.hash});if(this.outgoing.get(outgoing.request.transferId)===outgoing){outgoing.boundaryPending=false;this.catchup(outgoing);}}).catch(error=>this.failOutgoing(outgoing,String(error)));return;}
  if(outgoing.boundaryPending)return;
  try{let count=0;while(outgoing.cursor<outgoing.boundary.frame&&count++<gameplayLimits.catchupBatch){if(link.channel.bufferedAmount>32*1024)return;const packet=scheduler.historyFrame(outgoing.cursor);if(!packet)throw Error('Guest fell outside retained history. Retry synchronization.');const next:number=outgoing.cursor+1,hash=next%gameplayLimits.hashInterval===0?this.historyHashes.get(next):undefined;link.channel.send(JSON.stringify({...packet,stream:link.stream}));if(hash)link.channel.send(JSON.stringify({kind:'hash',epoch:scheduler.epoch,stream:link.stream,frame:next,hash}));outgoing.cursor=next;}
   if(outgoing.cursor!==outgoing.boundary.frame){outgoing.continuation??=setTimeout(()=>{outgoing.continuation=undefined;this.catchup(outgoing);},0);return;}
   link.channel.send(JSON.stringify({kind:'live',epoch:scheduler.epoch,transferId:outgoing.request.transferId,...outgoing.boundary}));outgoing.markerSent=true;
   link.cursor=outgoing.boundary.frame;link.live=true;this.pumpLink(outgoing.request.recipient,link);
  }catch(error){this.failOutgoing(outgoing,String(error));}
 }
 private finishCatchup(){const spec=this.incoming,scheduler=this.scheduler;if(!this.catchingUp||!spec||!scheduler||this.catchupTarget===undefined||scheduler.frame!==this.catchupTarget||this.hashing||this.catchupChecking)return;
  this.catchupChecking=true;const boundary=this.catchupTarget,hash=this.catchupHash;
  void this.player()!.stateHash().then(async info=>{if(this.incoming!==spec||this.scheduler!==scheduler)return;if(info.frame!==boundary||info.hash!==hash)throw Error('Catch-up state differs at its confirmed boundary.');this.catchingUp=false;this.player()?.resumeGamePresentation();this.observerCompletion=spec;await this.send({type:'gameObserved',epoch:spec.epoch,transferId:spec.transferId,frame:boundary,hash:info.hash});}).catch(error=>{if(this.incoming===spec)this.failIncoming(spec,String(error));}).finally(()=>{this.catchupChecking=false;if(this.scheduler===scheduler)this.player()?.wakeGame(scheduler.epoch);});
 }
 private cancelOutgoing(outgoing:Outgoing){clearTimeout(outgoing.timer);clearTimeout(outgoing.continuation);this.sender.cancel(outgoing.request.recipient);this.outgoing.delete(outgoing.request.transferId);}
 private failOutgoing(outgoing:Outgoing,status:string){if(this.outgoing.get(outgoing.request.transferId)!==outgoing)return;this.cancelOutgoing(outgoing);const link=this.links.get(outgoing.request.recipient);if(link)link.live=false;void this.send({type:'gameCheckpointFailed',epoch:outgoing.request.epoch,transferId:outgoing.request.transferId}).catch(()=>{});if(outgoing.request.purpose==='controller')this.publish({busy:false,status});}
 private cancelIncoming(){this.observerCompletion=undefined;clearTimeout(this.incomingTimer);this.incoming=undefined;this.receiver.cancel();this.player()?.cancelPeerCheckpoint();this.catchingUp=false;this.catchupTarget=undefined;this.catchupHash=undefined;this.catchupChecking=false;}
 private failIncoming(spec:Spec,status:string){if(this.incoming!==spec)return;this.cancelIncoming();this.scheduler=undefined;this.player()?.stopGame(status);this.publish({busy:false,synchronizing:false,observing:false,status});void this.send({type:'gameCheckpointFailed',epoch:spec.epoch,transferId:spec.transferId}).catch(()=>{});}
 private cancelAllTransfers(){this.cancelIncoming();for(const outgoing of [...this.outgoing.values()])this.cancelOutgoing(outgoing);}
 private clear(status:string,leave=false){for(const link of this.links.values()){clearTimeout(link.continuation);link.continuation=undefined;}this.inputLease=undefined;this.receiveStream=undefined;this.frozenRecovery=false;const attempt=this.loadAttempt;this.candidateAcquisition?.abort();this.candidateAcquisition=undefined;this.replacementCompletion?.reject(Error(status));this.replacementCompletion=undefined;this.loadAttempt=undefined;this.loadHold=undefined;this.announcedLoad=undefined;this.manualLoadRequest=undefined;this.manualSave=undefined;if(attempt?.replacement)this.player()?.cancelCartridge(attempt.id,leave);else if(attempt)void this.player()?.rollbackSharedSave(attempt.id,()=>false).catch(()=>{});this.cancelAllTransfers();++this.serial;this.intent=false;this.offered=undefined;this.offering=false;this.prepared=undefined;this.scheduler=undefined;this.frozen=false;this.fence=undefined;this.hashing=false;this.observeRequested=undefined;this.player()?.stopGame(status,leave);if(leave)this.player()?.allowLocalPlay();this.publish({status,busy:false,synchronizing:false,intent:false,observing:false,preparationError:undefined});}
 private fail(status:string,reason:GameReason){const epoch=this.scheduler?.epoch??this.room?.game.epoch,spec=this.incoming;if(spec){this.failIncoming(spec,status);return;}this.clear(status);if(epoch&&!this.authority()&&this.room?.game.status==='playing')this.observeRequested=epoch;if(epoch)void this.send({type:'gameAbort',epoch,reason}).catch(()=>{});}
 dispose(){this.clear('Shared game closed.',true);this.links.clear();this.checkpointLinks.clear();}
}
