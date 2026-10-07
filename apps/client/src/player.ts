import {LOCAL_SCHEMA,LOCAL_SETTINGS,type Fingerprint as LocalFingerprint} from '../../../packages/contracts/src/fingerprint.ts';
import type { WorkerRequest, WorkerResponse, LocalFileRequest, PeerCheckpointRequest, LocalFileInfo, StateHash, RewindInfo } from '../../../packages/contracts/src/index.ts';
import {gameplayLimits,type GameReason } from '../../../packages/contracts/src/gameplay.ts';
import { defaults, inputMask, GamepadInput, rapidMask, type Controls } from './controls.ts';
import { createAudioQueue } from '../../../spikes/d02/demo/runtime/audio.js';
import {readStored,putBattery,validSavedAt,sameRecord,type BatteryRecord} from './saves.ts';
import { inspectCartridge, hex } from './cartridge.ts';
import {matchesFile} from '../../../packages/contracts/src/rooms.ts';

type FileCommand<Request = LocalFileRequest | PeerCheckpointRequest> = Request extends LocalFileRequest | PeerCheckpointRequest ? Omit<Request,'requestId'> : never;
type BatterySession={worker:Worker;info:LocalFileInfo;generation:number;record?:BatteryRecord;enabled:boolean;writing?:Promise<void>};
const disconnectedMessage = 'Controller unavailable. Keyboard and on-screen controls are ready.';

export type {Fingerprint as LocalFingerprint} from '../../../packages/contracts/src/fingerprint.ts';
export type GameDriver={epoch:string;next:(mask:number)=>{frame:number;p1:number;p2:number}|undefined;committed:(frame:number)=>void;pause:(reason:GameReason)=>void;draining:()=>boolean;ownsInput?:boolean;sample?:(mask:number,release?:boolean)=>void;silent?:()=>boolean};
export type GameSelectionResult={ok:boolean;uncertain?:boolean;message?:string};
type PreparedSelection={worker:Worker;current:()=>boolean;commit:()=>void;publishCommit:()=>void;fail:(message:string)=>void};
export type PlayerState = { shared?:boolean; status: string; loading: boolean; selectionVersion?:number; selectionPhase?:'loading'|'uncertain'|'loaded'|'failed'|'cancelled'; running: boolean; loaded: boolean; frames: number; previewImage?:string; audioIssue?: string; audioState?: AudioContextState; inputIssue?: string; rewind?:RewindInfo; storageIssue?:string; batteryAvailable?:boolean; fingerprint?: LocalFingerprint };
/** Owns browser-local resources. A candidate replaces the active worker only after initialization succeeds. */
export class LocalPlayer {
 isLoaded(fingerprint?:LocalFingerprint):boolean {return !!this.active && this.state.loaded && (!this.state.loading||this.shared) && (!fingerprint || !!this.state.fingerprint && matchesFile(this.state.fingerprint,fingerprint));}
 selectionVersion(){return this.generation;}
 private active?: Worker;
 private cartridgeTransaction?:{id:string;worker:Worker;prepared:PreparedSelection;previous?:{worker:Worker;rom?:ArrayBuffer;battery?:BatterySession;state:PlayerState;fps:number};complete?:(result:GameSelectionResult)=>void};
 private selectedRom?:ArrayBuffer;
 private game?:GameDriver;
 private gameTimer?:ReturnType<typeof setTimeout>;
 private gameProgressAt=0;
 private gameLastPumpAt=0;private gameInputAt=0;
 private gameStarted=0;private gameFrames=0;
 private shared=false;
 private expectedFrame?:{epoch:string;frame:number};
 private batterySession?:BatterySession;
 private persistenceTimer=0;
 private backgroundTimer?:ReturnType<typeof setInterval>;
 private pagehide=()=>{void this.persistBattery();};
 private nextRequest = 0;
 private pending = new Map<number,{worker:Worker;resolve:(value:WorkerResponse)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
 // Candidate changes retain requests owned by the active emulator until it is retired.
 private rejectPending(message:string,retainedWorker?:Worker) {for(const [id,request] of this.pending){if(request.worker===retainedWorker)continue;clearTimeout(request.timer);this.pending.delete(id);request.reject(new DOMException(message,'AbortError'));}}
 private fileRequest(message:FileCommand,target?:Worker):Promise<WorkerResponse> {
  const worker=target ?? this.active;
  if(!worker || this.disposed || !target && this.state.loading && !this.shared || worker!==this.active && worker!==this.candidate && worker!==this.cartridgeTransaction?.previous?.worker)return Promise.reject(Error('Wait for a game to finish loading.'));
  const requestId=++this.nextRequest;
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{this.pending.delete(requestId);reject(Error('The save operation timed out. Try again.'));},10000);
   this.pending.set(requestId,{worker,resolve,reject,timer});
   try {this.send(worker,{...message,requestId} as LocalFileRequest | PeerCheckpointRequest);} catch(error){clearTimeout(timer);this.pending.delete(requestId);reject(error);}
  });
 }
 async stateHash():Promise<StateHash> {const reply=await this.fileRequest({type:'state-hash'});if(reply.type!=='state-hash')throw Error('Unexpected state hash response');return reply.info;}
 frameRate(){return this.fps;}
 async holdForGame(_ownsInput=true) {this.shared=true;this.suspend();return this.stateHash();}
 startGame(driver:GameDriver) {if(!this.active||this.state.loading)throw Error('Wait for the game to finish loading.');clearTimeout(this.gameTimer);this.game=driver;this.gameStarted=performance.now();this.gameProgressAt=this.gameStarted;this.gameLastPumpAt=this.gameStarted;this.gameFrames=0;this.shared=true;this.last=0;this.publish({shared:true,running:true,status:'Playing together.'});if(!document.hidden&&driver.ownsInput!==false)this.canvas.focus();this.pumpGame();}
 allowLocalPlay(){this.shared=false;this.publish({shared:false});}
 stopGame(status:string,leave=false) {clearTimeout(this.gameTimer);this.game=undefined;this.expectedFrame=undefined;if(leave)this.shared=false;this.suspend();this.publish({status});}
 private async prepareBattery(worker:Worker,isCurrent:()=>boolean):Promise<{session?:BatterySession;issue?:string}> {
  let session:BatterySession|undefined;
  try {
   const reply=await this.fileRequest({type:'battery-info'},worker);
   if(reply.type!=='battery-info' || !isCurrent())return {};
   session={worker,info:reply.info,generation:0,enabled:false};
   const stored=await readStored<BatteryRecord>('batteries',reply.info.identity);
   if(!isCurrent())return {};
   session.generation=stored.generation;session.record=stored.record;
   if(stored.record) {
    if(!validSavedAt(stored.record.savedAt) || !(stored.record.bytes instanceof ArrayBuffer) || stored.record.bytes.byteLength>reply.info.limit)throw Error('Stored battery data is invalid.');
    await this.fileRequest({type:'battery-import',bytes:stored.record.bytes},worker);
   }
   session.enabled=true;return {session};
  } catch(error) {return {session,issue:`Battery progress could not be restored. Your game can still run; existing data is preserved in Local data. ${error instanceof Error ? error.message : 'Storage unavailable.'}`};}
 }
 persistBattery(session=this.batterySession):Promise<void> {
  if(session?.writing)return session.writing;
  if(!session?.enabled || session.worker!==this.active || this.disposed || this.cartridgeTransaction?.worker===session.worker)return Promise.resolve();
  session.writing=this.captureBattery(session).finally(()=>{session.writing=undefined;});
  return session.writing;
 }
 private async captureBattery(session:BatterySession) {
  try {
   const reply=await this.fileRequest({type:'battery-export'},session.worker);
   if(reply.type!=='battery-exported' || session!==this.batterySession)return;
   const record={identity:session.info.identity,savedAt:Date.now(),bytes:reply.bytes};
   await putBattery(record,session.record,session.generation);
   session.record=record;
   if(session===this.batterySession)this.publish({storageIssue:undefined});
  } catch(error) {
   if(error instanceof DOMException && error.name==='AbortError')return;
   session.enabled=false;
   if(session===this.batterySession)this.publish({storageIssue:`Couldn't save battery progress on this device. Export a backup or open Local data. ${error instanceof Error ? error.message : ''}`});
  }
 }
 async exportBattery():Promise<ArrayBuffer> {const reply=await this.fileRequest({type:'battery-export'});if(reply.type!=='battery-exported')throw Error('Unexpected battery response');return reply.bytes;}
 async batteryInfo():Promise<LocalFileInfo> {const reply=await this.fileRequest({type:'battery-info'});if(reply.type!=='battery-info')throw Error('Unexpected battery response');return reply.info;}
 async retryBatteryPersistence() {
  const session=this.batterySession;if(!session || session.worker!==this.active)return;
  const stored=await readStored<BatteryRecord>('batteries',session.info.identity);
  if(session!==this.batterySession)return;
  // Never replace a corrupt/conflicting existing record merely by retrying.
  if(stored.record && (!sameRecord(stored.record,session.record) || !session.enabled))throw Error('Existing battery data needs attention. Export or delete it in Local data, then retry.');
  session.generation=stored.generation;session.record=stored.record;session.enabled=true;await this.persistBattery(session);
 }
 stopPersistence() {if(this.batterySession)this.batterySession.enabled=false;}
 async saveInfo():Promise<LocalFileInfo> {const reply=await this.fileRequest({type:'state-info'});if(reply.type!=='state-info')throw Error('Unexpected save response');return reply.info;}
 async loadRecovery(file:File,current:()=>boolean){
  await new Promise<void>((resolve,reject)=>{
   const finish=(error?:Error)=>{clearTimeout(timer);this.selectionListeners.delete(loaded);error?reject(error):resolve();};
   const loaded=()=>{if(!current())finish(Error('Restoration cancelled.'));else if(!this.state.loading&&this.state.selectionPhase==='failed')finish(Error(this.state.status));else if(!this.state.loading&&this.state.selectionPhase==='loaded')finish();};
   const timer=setTimeout(()=>finish(Error('The game did not load. Load a NES file normally.')),15000);
   this.selectionListeners.add(loaded);void this.load(file,undefined,true,current).catch(error=>finish(error));
  });
 }
 // loadRecovery resolves only after the active candidate is initialized.
 recoveryFingerprint(){return this.state.fingerprint;}
 /** Prepare a fresh OSS machine without replacing the active timeline. */
 async freshCartridge(current:()=>boolean){
  const rom=this.selectedRom?.slice(0),version=this.generation;if(!rom||!this.active||this.state.loading)throw Error('Load a cartridge before restarting.');
  const worker=new Worker(new URL('./worker.ts',import.meta.url),{type:'module'});
  try{return await new Promise<Extract<WorkerResponse,{type:'state-captured'}>>((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('Cartridge restart preparation timed out. Previous progress is preserved.')),10000);
   const fail=(message:string)=>{clearTimeout(timer);reject(Error(message));};
   worker.onerror=()=>fail('Could not restart this cartridge. Previous progress is preserved.');
   worker.onmessage=({data}:MessageEvent<WorkerResponse>)=>{
    if(!current()||this.generation!==version||this.disposed){fail('The game changed. Restart cancelled.');return;}
    if(data.type==='ready'){worker.postMessage({type:'state-capture',requestId:1});return;}
    if(data.type==='state-captured'){clearTimeout(timer);resolve(data);return;}
    if(data.type==='error'||data.type==='state-error')fail(data.message);
   };
   worker.postMessage({type:'load',rom},[rom]);
  });}finally{worker.terminate();}
 }
 async captureRecovery(){const reply=await this.fileRequest({type:'state-capture'});if(reply.type!=='state-captured')throw Error('Unexpected recovery response');return reply;}
 async exportSave():Promise<ArrayBuffer> {const reply=await this.fileRequest({type:'state-export'});if(reply.type!=='state-exported')throw Error('Unexpected save response');return reply.bytes;}
 async validateSave(bytes:ArrayBuffer) {await this.fileRequest({type:'state-validate',bytes});}
 async loadSave(bytes:ArrayBuffer) {
  if(this.disposed || this.state.loading)throw Error('Wait for a game to finish loading.');
  if(this.shared)throw Error('Only the host can load shared progress.');
  const running=this.state.running;this.pause();
  await this.fileRequest({type:'state-import',bytes});
  this.audio.flush();this.release();this.publish({rewind:undefined,status:'Paused. Resume whenever you’re ready.'});
  if(running)this.resume();
 }

 setGameInputOwner(ownsInput:boolean){if(this.game){this.game.ownsInput=ownsInput;if(!ownsInput)this.release();}}
 sampleGameInput(){return this.controllerMask(this.inputDevice().pressed);}
 async bindGameEpoch(epoch:string,frame:number,hash:string){
  if(!this.shared||this.state.running||this.busy)throw Error('Pause before preparing shared play.');
  const reply=await this.fileRequest({type:'peer-checkpoint-bind',epoch,frame,hash});if(reply.type!=='peer-checkpoint-bound')throw Error('Unexpected game epoch response');
 }
 async exportPeerCheckpoint(epoch:string,frame?:number){
  if(!this.shared||frame!==undefined&&(this.state.running||this.busy))throw Error('Pause at a completed frame before synchronization.');
  const reply=await this.fileRequest({type:'peer-checkpoint-export',epoch,frame});
  if(reply.type!=='peer-checkpoint-exported')throw Error('Unexpected checkpoint export');return reply;
 }
 private checkpointOperation?:string;
 cancelPeerCheckpoint(){const operationId=this.checkpointOperation;this.checkpointOperation=undefined;if(operationId)void this.fileRequest({type:'peer-checkpoint-cancel',operationId}).catch(()=>{});}
 async importPeerCheckpoint(epoch:string,frame:number,bytes:ArrayBuffer,identity:string,hash:string,isCurrent:()=>boolean|Promise<boolean>){
  if(!this.shared||this.state.running||this.busy||!await isCurrent())throw Error('Synchronization authorization changed.');
  this.cancelPeerCheckpoint();const operationId=crypto.randomUUID();this.checkpointOperation=operationId;
  try{
   const prepared=await this.fileRequest({type:'peer-checkpoint-prepare',operationId,epoch,frame,bytes,identity,hash});
   if(prepared.type!=='peer-checkpoint-prepared'||!await isCurrent()||this.checkpointOperation!==operationId)throw Error('Synchronization authorization changed.');
   const reply=await this.fileRequest({type:'peer-checkpoint-commit',operationId});
   if(reply.type!=='peer-checkpoint-imported')throw Error('Unexpected checkpoint import');
   // An authorized native commit is atomic; late delivery must not affect a newer UI/input owner.
   if(!await isCurrent()||this.checkpointOperation!==operationId)return reply;
   this.audio.flush();this.release();this.expectedFrame=undefined;
   this.publish({frames:frame,rewind:undefined,status:'Paused game synchronized. Waiting for shared resume.'});return reply;
  }finally{if(this.checkpointOperation===operationId)this.cancelPeerCheckpoint();}
 }
 async inspectSave(bytes:ArrayBuffer){const reply=await this.fileRequest({type:'state-inspect',bytes});if(reply.type!=='state-inspected')throw Error('Unexpected save validation response');return reply;}
 async captureCartridge(){const worker=this.preparedSelection?.worker;if(!worker)throw Error('Wait for the cartridge candidate.');const capture=await this.fileRequest({type:'state-capture'},worker);if(capture.type!=='state-captured')throw Error('No cartridge capture.');const info=await this.fileRequest({type:'state-hash'},worker);if(info.type!=='state-hash'||!info.info.fresh||info.info.frame!==0||info.info.hash!==capture.hash)throw Error('The candidate cartridge is not fresh.');return capture;}
 async prepareCartridge(file:File,current:()=>boolean){
  return new Promise<void>((resolve,reject)=>{
   const end=(error?:Error)=>{clearTimeout(timer);this.selectionListeners.delete(check);error?reject(error):resolve();};
   const check=()=>{if(!current())end(Error('Game selection changed.'));else if(this.state.selectionPhase==='failed')end(Error(this.state.status));};
   const timer=setTimeout(()=>end(Error('The candidate cartridge timed out. Retry.')),10000);this.selectionListeners.add(check);
   void this.load(file,async()=>current(),true,current,async()=>{end();return new Promise<GameSelectionResult>(complete=>{this.cartridgeCompletion=complete;});},undefined,this.cartridgeOwner).catch(error=>end(error instanceof Error?error:Error(String(error))));
  });
 }
 private cartridgeOwner?:string;
 ownCartridge(id:string){if(this.cartridgeOwner&&this.cartridgeOwner!==id)throw Error('Another cartridge change owns the candidate.');this.cartridgeOwner=id;}
 cancelCartridge(id:string,terminal=false){if(this.cartridgeOwner!==id)return;this.abandonCandidate(terminal);this.publish({loading:false,selectionPhase:'cancelled',...(terminal?{loaded:false,running:false}:{}),status:'Game change cancelled. Previous progress is preserved.'});}
 private cartridgeCompletion?:(result:GameSelectionResult)=>void;
 async prepareSharedSave(transactionId:string,epoch:string,frame:number,bytes:ArrayBuffer,identity:string,hash:string,current:()=>boolean){
  if(!this.shared||this.state.running||this.busy||!current())throw Error('Save load authorization changed');
  const candidate=this.preparedSelection;if(candidate){this.cartridgeTransaction={id:transactionId,worker:candidate.worker,prepared:candidate,complete:this.cartridgeCompletion};}
  const reply=await this.fileRequest({type:'peer-checkpoint-prepare',operationId:transactionId,transactionId,epoch,frame,bytes,identity,hash,...(candidate?{initial:true}:{})},candidate?.worker);
  if(reply.type!=='peer-checkpoint-prepared'||!current())throw Error('Save load authorization changed');return reply;
 }
 async commitSharedSave(transactionId:string,current:()=>boolean){
  if(!current())throw Error('Save load authorization changed');const cartridge=this.cartridgeTransaction?.id===transactionId?this.cartridgeTransaction:undefined;const reply=await this.fileRequest({type:'peer-checkpoint-commit',operationId:transactionId},cartridge?.worker);
  if(reply.type!=='peer-checkpoint-imported'||!current())throw Error('Save load authorization changed');if(cartridge){cartridge.prepared.commit();return reply;}this.audio.flush();this.release();this.expectedFrame=undefined;this.publish({frames:reply.frame,rewind:undefined,status:'Saved game loaded. Waiting for everyone.'});return reply;
 }
 async rollbackCartridge(transactionId:string,staged:boolean,current:()=>boolean){if(this.cartridgeTransaction?.id===transactionId)return this.rollbackSharedSave(transactionId,current);if(staged){const complete=this.cartridgeCompletion;this.cartridgeCompletion=undefined;this.rejectSelection('Game change failed. Previous progress is preserved.');complete?.({ok:false,message:'Game change failed.'});}return this.stateHash();}
 async rollbackSharedSave(transactionId:string,current:()=>boolean=()=>true){
  const cartridge=this.cartridgeTransaction?.id===transactionId?this.cartridgeTransaction:undefined;
  if(cartridge){
   if(!current()||this.cartridgeOwner!==transactionId)return this.stateHash();
   const old=cartridge.previous;if(old){this.active=old.worker;this.selectedRom=old.rom;this.batterySession=old.battery;this.fps=old.fps;this.state=old.state;}
   this.rejectPending('Game change rolled back.',this.active);cartridge.worker.terminate();this.candidate=undefined;
   // Keep the selection lease until the retained machine proves its boundary.
   // Revoking it sooner lets the UI cancel this very rollback hash request.
   const info=await this.stateHash();if(!current()||this.cartridgeTransaction!==cartridge)return info;
   this.cartridgeTransaction=undefined;this.cartridgeOwner=undefined;this.preparedSelection=undefined;this.selectionLock=false;this.cartridgeCompletion=undefined;
   cartridge.complete?.({ok:false,message:'Game change failed. Previous progress is preserved.'});
   this.publish({loading:false,selectionPhase:'failed',running:false,status:'Previous progress preserved. Prepare to resume.'});return {type:'peer-checkpoint-rolled-back' as const,frame:info.frame,hash:info.hash};
  }
  const reply=await this.fileRequest({type:'peer-checkpoint-rollback',operationId:transactionId});if(reply.type!=='peer-checkpoint-rolled-back')throw Error('Unexpected rollback response');if(!current())return reply;this.audio.flush();this.release();this.expectedFrame=undefined;this.publish({frames:reply.frame,rewind:undefined,status:'Previous progress preserved. Prepare to resume.'});return reply;
 }
 async finishSharedSave(transactionId:string,current:()=>boolean=()=>true){const cartridge=this.cartridgeTransaction?.id===transactionId?this.cartridgeTransaction:undefined;const reply=await this.fileRequest({type:'peer-checkpoint-finish',operationId:transactionId});if(reply.type!=='peer-checkpoint-finished')throw Error('Unexpected save commit response');if(cartridge){if(!current()||this.cartridgeTransaction!==cartridge||this.cartridgeOwner!==transactionId)return;this.cartridgeTransaction=undefined;this.cartridgeOwner=undefined;this.rejectPending('Game replaced.',this.active);cartridge.previous?.worker.terminate();this.preparedSelection=undefined;this.selectionLock=false;this.cartridgeCompletion=undefined;cartridge.prepared.publishCommit();cartridge.complete?.({ok:true});}}
 async history():Promise<RewindInfo> {const reply=await this.fileRequest({type:'state-history'});if(reply.type!=='state-history')throw Error('Unexpected history response');return reply.info;}
 async rewind(seconds:number) {
  if(this.shared)throw Error('Shared rewind is not available yet. Leave the lobby before rewinding locally.');
  if(this.disposed || this.state.loading)throw Error('Wait for a game to finish loading.');
  this.pause();
  const reply=await this.fileRequest({type:'state-rewind',seconds});
  if(reply.type!=='state-rewound')throw Error('Unexpected rewind response');
  this.audio.flush();this.release();
  this.canvas.getContext('2d')?.putImageData(new ImageData(new Uint8ClampedArray(reply.pixels),256,240),0,0);
  this.publish({rewind:reply.info,frames:reply.info.frame+1,status:`Rewound ${seconds} second${seconds===1 ? '' : 's'}. Resume whenever you’re ready.`});
 }

 private candidate?: Worker;
 private selectionLock=false;
 selectionLocked(){return this.selectionLock;}
 setSelectionFinishing(){if(this.preparedSelection)this.selectionLock=true;}
 private preparedSelection?:PreparedSelection;
 selectionCompletion(){const prepared=this.preparedSelection;return (result:GameSelectionResult)=>this.finishSelection(result,prepared);}
 private finishSelection(result:GameSelectionResult,prepared:PreparedSelection|undefined){if(!prepared||prepared!==this.preparedSelection)return;if(!prepared.current()){this.abandonCandidate();this.publish({loading:false,selectionPhase:'cancelled'});return;}if(result.ok){this.selectionLock=false;this.preparedSelection=undefined;prepared.commit();}else if(result.uncertain)this.publish({loading:true,selectionPhase:'uncertain',status:result.message??'Game selection needs confirmation.'});else{this.selectionLock=false;this.preparedSelection=undefined;prepared.fail(result.message??'Could not prepare the lobby game. Retry.');}}
 private reader?: FileReader;
 private generation = 0;
 private disposed = false;
 private keys = new Set<string>();
 private rapidStarted=new Map<string,number>();
 private controls: Controls = defaults();
 private volume = 1;
 private busy = false;
 private last = 0;
 private fps = 60;
 private animation = 0;
 private context?: AudioContext;
 private gain?: GainNode;
 private backgroundClock?:AudioWorkletNode;
 private backgroundClockStarting=false;
 private backgroundClockFailed=false;
 private muted = false;
 private audio = createAudioQueue(() => this.context, () => this.state.running, () => this.gain);
 private state: PlayerState = {status:'Choose a game to start playing.',loading:false,running:false,loaded:false,frames:0};
 private canvas:HTMLCanvasElement;private update:(state:PlayerState)=>void;
 constructor(canvas: HTMLCanvasElement, update: (state: PlayerState) => void) {
  this.canvas=canvas;this.update=update;
  this.persistenceTimer=window.setInterval(()=>{void this.persistBattery();},10000);window.addEventListener('pagehide',this.pagehide);
  window.addEventListener('keydown',this.down); window.addEventListener('keyup',this.up);
  window.addEventListener('gamepadconnected',this.deviceChanged);window.addEventListener('gamepaddisconnected',this.deviceChanged);
  window.addEventListener('blur',this.blur);window.addEventListener('resize',this.release);document.addEventListener('visibilitychange',this.hidden);
  document.addEventListener('focusin',this.focusChanged);
  this.animation = requestAnimationFrame(this.tick);
 }
 private selectionListeners=new Set<()=>void>();
 private publish(patch: Partial<PlayerState>) { if(this.disposed) return; this.state = {...this.state,...patch,selectionVersion:this.generation}; this.update(this.state);for(const listener of this.selectionListeners)listener(); }
 private send(worker: Worker, message: WorkerRequest, transfer: Transferable[] = []) { worker.postMessage(message,transfer); }
 private gamepadInput=new GamepadInput();
 private deviceChanged=(event:GamepadEvent)=>{if(this.controls.device?.index===event.gamepad.index&&this.controls.device.id===event.gamepad.id)this.gamepadInput.release(this.controls.device);};
 private virtualMask=0;
 private inputBlocked=false;
 blockGameInput(blocked:boolean){this.inputBlocked=blocked;if(blocked)this.release();}
 private inputFocused(){const active=document.activeElement;return !this.inputBlocked&&(active===this.canvas || !!active?.closest('[data-game-input] button, [data-game-input] [tabindex]'));}
 setVirtualInput(mask:number){this.virtualMask=this.state.running&&!document.hidden&&this.inputFocused()&&this.game?.ownsInput!==false?mask&255:0;this.game?.sample?.(this.sampleGameInput());}
 private release = () => { this.virtualMask=0;this.keys.clear();this.rapidStarted.clear();this.gamepadInput.release(this.controls.device);this.game?.sample?.(0,true); };
 releaseControllers(){this.release();}
 private down = (event: KeyboardEvent) => {
  if(!event.repeat && this.inputFocused() && this.state.running && !((event.target as Element)?.closest('[data-game-input] button')&&['Enter','Space'].includes(event.code))) {
   const mapped=Object.values(this.controls.keyboard).some(bindings=>bindings.includes(event.code));
   if(mapped){event.preventDefault();this.keys.add(event.code);if(this.controls.keyboard.rapidA.includes(event.code)||this.controls.keyboard.rapidB.includes(event.code))this.rapidStarted.set(event.code,performance.now());this.game?.sample?.(this.sampleGameInput());}
  }
 };
 private up = (event: KeyboardEvent) => { this.keys.delete(event.code);this.rapidStarted.delete(event.code);this.game?.sample?.(this.sampleGameInput()); };
 configureControls(controls: Controls) { this.controls = controls; this.release(); this.publish({inputIssue:undefined}); }
 setVolume(value:number) { if(!Number.isFinite(value) || value<0 || value>1) throw Error('Volume must be between 0 and 1'); this.volume=value; if(this.gain) this.gain.gain.value=this.muted ? 0 : value; }
 private focusChanged = () => {if(!this.inputFocused())this.release();};
 private blur = () => { this.release();void this.persistBattery(); };
 private hidden = () => {
  if(document.hidden){
   this.release();
   this.backgroundTimer ??=setInterval(()=>this.stepLocal(performance.now()),16);
  }else {clearInterval(this.backgroundTimer);this.backgroundTimer=undefined;}
  void this.persistBattery();
 };
 private inputDevice() {
  const device=this.gamepadInput.sample(this.controls.device);
  const inputIssue=device.available?undefined:disconnectedMessage;
  if(this.state.inputIssue!==inputIssue)this.publish({inputIssue});
  return device;
 }
 private controllerMask(pressed:ReadonlySet<string>) {
  if(!this.inputFocused())return 0;
  return inputMask(this.controls.keyboard,this.keys) | inputMask(this.controls.gamepad,pressed) | this.virtualMask | rapidMask(this.controls.keyboard,this.rapidStarted,performance.now());
 }
 private tick = (now: number) => {
  this.animation = requestAnimationFrame(this.tick);
  this.stepLocal(now);
 };
 private stepLocal(now:number) {
  const {pressed} = this.inputDevice();
  if(this.game || !this.active || !this.state.running || this.busy || now-this.last < 1000/this.fps) return;
  this.last = now-(now-this.last)%(1000/this.fps);
  const mask=this.controllerMask(pressed);
  this.busy=true;this.send(this.active,{type:'frame',p1:mask,p2:0});
 }
 // As in the qualified D02 scheduler, wall time sets an absolute target. Input
 // delivery retains debt; each worker request still commits one immutable command.
 private pumpGame = () => {
  clearTimeout(this.gameTimer);
  if(!this.game||this.disposed)return;
  this.gameTimer=setTimeout(this.pumpGame,2);
  if(!this.active||!this.state.running)return;
  const now=performance.now(),{pressed}=this.inputDevice();if(now-this.gameInputAt>=1000/this.fps){this.gameInputAt=now;this.game.sample?.(this.game.ownsInput===false?0:this.controllerMask(pressed));}
  if(this.game.draining()){this.drainGame();return;}
  const gap=now-this.gameLastPumpAt;
  this.gameLastPumpAt=now;
  // A suspended tab resumes with wall-time debt, not evidence of lost input.
  // Missing peer input is timed by GameClient; only a worker that remains busy
  // through active pump ticks needs this local stall check.
  if(gap>250)this.gameProgressAt=now;
  if(this.busy&&now-this.gameProgressAt>gameplayLimits.stallMs){this.pause('network');return;}
  const elapsed=now-this.gameStarted;
  if(this.busy||this.gameFrames>=Math.floor(elapsed*this.fps/1000))return;
  const next=this.game.next(this.game.ownsInput===false?0:this.controllerMask(pressed));if(!next)return;
  this.busy=true;this.expectedFrame={epoch:this.game.epoch,frame:next.frame};this.send(this.active,{type:'frame',...next,epoch:this.game.epoch});
 };

 resumeGamePresentation(){this.gameStarted=performance.now();this.gameFrames=0;this.gameProgressAt=this.gameLastPumpAt=this.gameStarted;this.audio.flush();}
 wakeGame(epoch:string) {if(this.game?.epoch===epoch)this.pumpGame();}

 drainGame() {
  if(!this.game?.draining()||!this.active||this.busy)return;
  const next=this.game.next(0);if(!next)return;this.busy=true;this.expectedFrame={epoch:this.game.epoch,frame:next.frame};this.send(this.active,{type:'frame',...next,epoch:this.game.epoch});
 }
 private abandonCandidate(terminal=false) {
  const cartridge=this.cartridgeTransaction,complete=this.cartridgeCompletion;this.cartridgeTransaction=undefined;this.cartridgeOwner=undefined;this.cartridgeCompletion=undefined;
  if(cartridge){const previous=cartridge.previous;if(previous&&!terminal&&this.active===cartridge.worker){this.active=previous.worker;this.selectedRom=previous.rom;this.batterySession=previous.battery;this.state=previous.state;this.fps=previous.fps;}else previous?.worker.terminate();if(this.active===cartridge.worker){cartridge.worker.terminate();this.active=undefined;}else cartridge.worker.terminate();}
  complete?.({ok:false,message:'Game selection cancelled.'});
  this.selectionLock=false;this.preparedSelection=undefined; this.rejectPending('Game selection changed. Try again for the current game.',terminal?undefined:this.active); ++this.generation; this.reader?.abort(); this.reader = undefined; this.candidate?.terminate(); this.candidate = undefined; }
 rejectSelection(message: string) { this.abandonCandidate(); this.publish({loading:false,selectionPhase:'failed',status:message}); }
 cancel() {
  if(this.selectionLock)return;
  this.abandonCandidate();
  this.publish({loading:false,selectionPhase:'cancelled',status:this.state.loaded ? 'Selection cancelled. Your previous game is still here.' : 'Selection cancelled. Choose a game whenever you’re ready.'});
 }
 /** End the local session after a successful room exit or before opening the directory. */
 async quit() {
  this.pause();
  this.abandonCandidate(true);
  await this.persistBattery();
  this.rejectPending('Game closed.');
  this.active?.terminate();this.active=undefined;this.selectedRom=undefined;this.batterySession=undefined;
  this.game=undefined;clearTimeout(this.gameTimer);this.shared=false;this.busy=false;
  this.audio.flush();this.release();
  this.canvas.getContext('2d')?.clearRect(0,0,this.canvas.width,this.canvas.height);
  this.publish({loaded:false,loading:false,selectionPhase:undefined,running:false,shared:false,frames:0,fingerprint:undefined,previewImage:undefined,rewind:undefined,batteryAvailable:false,storageIssue:undefined,status:'Choose a game to start playing.'});
 }
 pause(reason:GameReason='user') {
  if(this.state.loading) this.cancel();
  if(this.game){this.release();this.audio.flush();this.game.pause(reason);return;}this.suspend();
 }
 private suspend() {
  this.release(); this.audio.flush();
  if(this.active) { this.send(this.active,{type:'pause'}); this.publish({running:false,status:'Paused. Resume whenever you’re ready.'}); }
 }
 resume():boolean {
  if(!this.active || this.state.loading&&!this.shared) return false;
  if(this.shared) {this.publish({status:'Shared play is paused. Use the lobby’s shared controls, or leave the lobby before resuming locally.'});return false;}
  this.activateAudio(); this.last = 0; this.inputDevice(); this.publish({running:true,status:'Playing locally. The game runs in this browser.'}); this.canvas.focus();return true;
 }
 setMuted(value: boolean) { this.muted = value; if(this.gain) this.gain.gain.value = value ? 0 : this.volume; this.audio.flush(); if(!value) this.activateAudio(); }
 retryAudio() { this.activateAudio(); }
 private ensureBackgroundClock(context:AudioContext) {
  if(this.backgroundClock||this.backgroundClockStarting)return;
  if(!context.audioWorklet){this.backgroundClockFailed=true;this.publish({audioIssue:'Background play may slow because the audio clock is unavailable. Keep this tab active.'});return;}
  this.backgroundClockStarting=true;
  void context.audioWorklet.addModule(new URL('./background-clock.js',import.meta.url)).then(()=>{
   if(this.disposed||this.context!==context)return;
   const clock=new AudioWorkletNode(context,'retro-coop-background-clock',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[1]});
   clock.port.onmessage=()=>{if(!this.state.running)return;const now=performance.now();if(this.game)this.pumpGame();else this.stepLocal(now);};
   clock.connect(this.gain!);this.backgroundClock=clock;this.backgroundClockFailed=false;if(context.state==='running')this.publish({audioIssue:undefined});
  }).catch(()=>{if(!this.disposed){this.backgroundClockFailed=true;this.publish({audioIssue:'Background play may slow because the audio clock is unavailable. Retry sound or keep this tab active.'});}}).finally(()=>{this.backgroundClockStarting=false;});
 }
 private activateAudio() {
  try {
   if(!this.context) { this.context = new AudioContext(); this.gain = this.context.createGain(); this.gain.gain.value = this.muted ? 0 : this.volume; this.gain.connect(this.context.destination); this.context.onstatechange=()=>this.publish({audioState:this.context?.state}); }
   this.ensureBackgroundClock(this.context);
   void this.context.resume().then(() => this.publish({audioIssue:this.context?.state !== 'running' ? 'Sound is blocked. Retry sound to allow it; your game can continue.' : this.backgroundClockFailed ? 'Background play may slow because the audio clock is unavailable. Retry sound or keep this tab active.' : undefined})).catch(() => this.publish({audioIssue:'Sound could not start. Retry sound; your game can continue.'}));
  } catch { this.publish({audioIssue:'Sound is unavailable in this browser. Your game can continue.'}); }
 }
 private read(file: File): Promise<ArrayBuffer> {
  return new Promise((resolve,reject) => {
   const reader = new FileReader(); this.reader = reader;
   reader.onload = () => resolve(reader.result as ArrayBuffer);
   reader.onerror = () => reject(Error('The file could not be read. Choose it again from your device.'));
   reader.onabort = () => reject(Error('Selection cancelled.'));
   reader.readAsArrayBuffer(file);
  });
 }
 async load(file?: File, approve?: (fingerprint:LocalFingerprint,isCurrent:()=>boolean)=>Promise<boolean>,startPaused=false,selectionCurrent:()=>boolean=()=>true,prepare?:(fingerprint:LocalFingerprint,current:()=>boolean)=>Promise<GameSelectionResult>,committed?:(fingerprint:LocalFingerprint)=>void,cartridgeOwner?:string) {
  if(!file || this.disposed || this.selectionLock || !selectionCurrent()) return; // A chooser cancellation does not replace the valid selection.
  this.abandonCandidate();this.cartridgeOwner=cartridgeOwner; const request = this.generation;
  this.activateAudio(); this.publish({loading:true,selectionPhase:'loading',status:'Reading your file locally…'});
  try {
   const rom = await this.read(file);
   if(request !== this.generation || this.disposed || !selectionCurrent()) return;
   const cartridge = inspectCartridge(new Uint8Array(rom));
   this.publish({status:'Checking this NES game…'});
   const romSha256 = hex(await crypto.subtle.digest('SHA-256',rom));
   if(request !== this.generation || this.disposed || !selectionCurrent()) return;
   this.publish({status:'Starting your game…'});
   const worker = new Worker(new URL('./worker.ts',import.meta.url),{type:'module'}); this.candidate = worker;
   const fail = (message: string) => {
    if(this.disposed) return;
    if(this.candidate === worker) { this.candidate = undefined; worker.terminate(); this.publish({loading:false,selectionPhase:'failed',status:`Unable to load: ${message} Choose another file.${this.state.loaded ? ' Your previous game is preserved.' : ''}`}); }
    else if(this.active === worker) { this.rejectPending('The emulator stopped.'); this.active = undefined; worker.terminate(); this.busy = false; this.audio.flush(); this.publish({loaded:false,running:false,status:`The emulator stopped: ${message} Choose another file to retry.`}); }
   };
   worker.onerror = () => fail('This cartridge could not run in the emulator.');
   worker.onmessage = async ({data}: MessageEvent<WorkerResponse>) => {
    if(this.disposed) return;
    if('requestId' in data) {
     const pending=this.pending.get(data.requestId);
     if(pending?.worker===worker) {clearTimeout(pending.timer);this.pending.delete(data.requestId);if(data.type.endsWith('-error'))pending.reject(Object.assign(Error('message' in data ? data.message : 'Save failed'),{code:'code' in data?data.code:undefined}));else pending.resolve(data);}
     return;
    }
    if(data.type === 'error') { fail(data.message); return; }
    if(data.type === 'ready') {
     if(request !== this.generation || this.candidate !== worker || !selectionCurrent()) { worker.terminate(); return; }
     const fingerprint:LocalFingerprint = {romSha256,coreSha256:data.coreSha256,localSchema:LOCAL_SCHEMA,settings:LOCAL_SETTINGS,cartridge};
     const isCurrent=()=>request===this.generation && (this.candidate===worker||this.cartridgeTransaction?.worker===worker) && !this.disposed && selectionCurrent();
     try {
      if(approve && !await approve(fingerprint,isCurrent)) {if(isCurrent()) this.cancel();return;}
     }catch {if(isCurrent()) fail('Unable to confirm the lobby change.');return;}
     if(!isCurrent()) {worker.terminate();return;}
     // Flush the old game before reading its identity again for a replacement.
     await this.persistBattery();
     if(!isCurrent()){worker.terminate();return;}
     const battery=data.battery ? await this.prepareBattery(worker,isCurrent) : {};
     if(!isCurrent()) {worker.terminate();return;}
     this.publish({status:'Preparing the game preview…'});
     let preview:WorkerResponse|undefined,previewBefore:StateHash|undefined;
     try {
      const before=await this.fileRequest({type:'state-hash'},worker);
      if(before.type!=='state-hash')throw Error('The emulator returned no state hash.');
      previewBefore=before.info;
      preview=await this.fileRequest({type:'state-preview'},worker);
      if(preview.type!=='state-preview')throw Error('The emulator returned no game preview.');
     }catch{
      if(!isCurrent()){worker.terminate();return;}
      // A preview is optional. Keep the game only if the emulator proves the
      // failed attempt left its state untouched.
      try {
       const after=await this.fileRequest({type:'state-hash'},worker);
       if(!previewBefore||after.type!=='state-hash'||after.info.hash!==previewBefore.hash||after.info.frame!==previewBefore.frame||after.info.fresh!==previewBefore.fresh)throw Error('Preview changed game state');
       preview=undefined;
      }catch{if(isCurrent())fail('The emulator could not safely prepare this game.');return;}
     }
     if(!isCurrent()) {worker.terminate();return;}
     let previewImage:string|undefined;
     try {if(preview?.type==='state-preview'){
      const surface=document.createElement('canvas');surface.width=256;surface.height=240;
      const context=surface.getContext('2d');if(!context)throw Error('The game preview could not be drawn.');
      context.putImageData(new ImageData(new Uint8ClampedArray(preview.pixels),256,240),0,0);
      previewImage=surface.toDataURL('image/png');
      if(!previewImage.startsWith('data:image/png'))throw Error('The game preview could not be saved.');
     }}catch{previewImage=undefined;}
     if(!isCurrent()) {worker.terminate();return;}
     this.inputDevice();
     let committedWorker=false;
     const publishCommit=()=>{this.publish({loading:false,selectionPhase:'loaded',loaded:true,running:!startPaused,frames:0,rewind:undefined,storageIssue:battery.issue,batteryAvailable:data.battery,status:startPaused?'Game loaded. Resume whenever you’re ready.':'Playing locally. The game runs in this browser.',fingerprint,previewImage});committed?.(fingerprint);if(!startPaused)this.canvas.focus();};
     const commit=()=>{if(committedWorker)return;committedWorker=true;
     const cartridge=this.cartridgeTransaction?.worker===worker?this.cartridgeTransaction:undefined;
     if(cartridge&&this.active)cartridge.previous={worker:this.active,rom:this.selectedRom,battery:this.batterySession,state:{...this.state},fps:this.fps};else {this.rejectPending('Game replaced.',worker);this.active?.terminate();} this.batterySession=battery.session; this.active = worker; this.candidate = undefined;this.selectedRom=rom;
     this.audio.flush(); this.release(); this.busy = false; this.last = 0; this.fps = data.fps;
     if(!cartridge)publishCommit();
     };
     if(prepare){
      const prepared={worker,current:isCurrent,commit,publishCommit,fail};this.preparedSelection=prepared;
      try{this.finishSelection(await prepare(fingerprint,isCurrent),prepared);}catch(error){this.finishSelection({ok:false,message:error instanceof Error?error.message:'Could not prepare the lobby game.'},prepared);}
     }else commit();
     return;
    }
    if(this.active !== worker) return;
    if(data.type === 'frame') {
     this.busy = false;
     if(data.epoch!==undefined && (data.epoch!==this.expectedFrame?.epoch||data.frame!==this.expectedFrame.frame))return;
     const committed=this.expectedFrame;this.expectedFrame=undefined;
     this.canvas.getContext('2d')?.putImageData(new ImageData(new Uint8ClampedArray(data.pixels),256,240),0,0);
     if(this.state.running&&!this.game?.silent?.())this.audio.play(data.audio);
     this.publish({frames:data.frame===undefined?this.state.frames+1:data.frame+1,rewind:data.rewind});
     if(committed && this.game?.epoch===committed.epoch){this.gameFrames++;this.gameProgressAt=performance.now();this.game.committed(committed.frame);}
     if(this.game?.draining())this.drainGame();
     else if(this.game)this.pumpGame();
     else if(document.hidden)this.stepLocal(performance.now());
    }
   };
   this.send(worker,{type:'load',rom});
  } catch(error) {
   if(request === this.generation && !this.disposed) this.publish({loading:false,selectionPhase:'failed',status:`${error instanceof Error ? error.message : 'Unable to read this file.'}${this.state.loaded ? ' Your previous game is preserved.' : ''}`});
  }
 }
 dispose() {
  clearInterval(this.persistenceTimer);clearInterval(this.backgroundTimer);window.removeEventListener('pagehide',this.pagehide);
  this.disposed = true; clearTimeout(this.gameTimer); this.backgroundClock?.disconnect();this.backgroundClock?.port.close();this.abandonCandidate(true); this.active?.terminate(); cancelAnimationFrame(this.animation); this.audio.flush(); void this.context?.close();
  window.removeEventListener('gamepadconnected',this.deviceChanged);window.removeEventListener('gamepaddisconnected',this.deviceChanged);
  window.removeEventListener('keydown',this.down); window.removeEventListener('keyup',this.up); window.removeEventListener('blur',this.blur);window.removeEventListener('resize',this.release);document.removeEventListener('visibilitychange',this.hidden); document.removeEventListener('focusin',this.focusChanged);
 }
}
