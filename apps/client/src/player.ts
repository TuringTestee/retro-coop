import {LOCAL_SCHEMA,LOCAL_SETTINGS,type Fingerprint as LocalFingerprint} from '../../../packages/contracts/src/fingerprint.ts';
import type { WorkerRequest, WorkerResponse, LocalFileRequest, LocalFileInfo, StateHash } from '../../../packages/contracts/src/index.ts';
import {gameplayLimits,type GameReason } from '../../../packages/contracts/src/gameplay.ts';
import { defaults, inputMask, padInputs, type Controls } from './controls.ts';
import { createAudioQueue } from '../../../spikes/d02/demo/runtime/audio.js';
import {readStored,putBattery,validSavedAt,sameRecord,type BatteryRecord} from './saves.ts';
import { inspectCartridge, hex } from './cartridge.ts';

type FileCommand<Request = LocalFileRequest> = Request extends LocalFileRequest ? Omit<Request,'requestId'> : never;
type BatterySession={worker:Worker;info:LocalFileInfo;generation:number;record?:BatteryRecord;enabled:boolean;writing?:Promise<void>};
const disconnectedMessage = 'Controller disconnected. Reconnect it, or use the keyboard.';

export type {Fingerprint as LocalFingerprint} from '../../../packages/contracts/src/fingerprint.ts';
export type GameDriver={epoch:string;next:(mask:number)=>{frame:number;p1:number;p2:number}|undefined;committed:(frame:number)=>void;pause:(reason:GameReason)=>void;draining:()=>boolean};
export type PlayerState = { shared?:boolean; status: string; loading: boolean; running: boolean; loaded: boolean; frames: number; audioIssue?: string; audioState?: AudioContextState; inputIssue?: string; storageIssue?:string; batteryAvailable?:boolean; fingerprint?: LocalFingerprint };
/** Owns browser-local resources. A candidate replaces the active worker only after initialization succeeds. */
export class LocalPlayer {
 private active?: Worker;
 private game?:GameDriver;
 private gameTimer?:ReturnType<typeof setTimeout>;
 private gameStarted=0;private gameFrames=0;
 private shared=false;
 private expectedFrame?:{epoch:string;frame:number};
 private batterySession?:BatterySession;
 private persistenceTimer=0;
 private pagehide=()=>{void this.persistBattery();};
 private nextRequest = 0;
 private pending = new Map<number,{worker:Worker;resolve:(value:WorkerResponse)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
 private rejectPending(message:string) {for(const request of this.pending.values()){clearTimeout(request.timer);request.reject(new DOMException(message,'AbortError'));}this.pending.clear();}
 private fileRequest(message:FileCommand,target?:Worker):Promise<WorkerResponse> {
  const worker=target ?? this.active;
  if(!worker || this.disposed || !target && this.state.loading || worker!==this.active && worker!==this.candidate)return Promise.reject(Error('Wait for a game to finish loading.'));
  const requestId=++this.nextRequest;
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{this.pending.delete(requestId);reject(Error('The save operation timed out. Try again.'));},10000);
   this.pending.set(requestId,{worker,resolve,reject,timer});
   try {this.send(worker,{...message,requestId} as LocalFileRequest);} catch(error){clearTimeout(timer);this.pending.delete(requestId);reject(error);}
  });
 }
 async stateHash():Promise<StateHash> {const reply=await this.fileRequest({type:'state-hash'});if(reply.type!=='state-hash')throw Error('Unexpected state hash response');return reply.info;}
 async holdForGame() {if(!this.inputDevice().available||document.hidden||!this.windowFocused)throw Error('Return to the game and reconnect your controller before shared play.');this.shared=true;this.suspend();return this.stateHash();}
 startGame(driver:GameDriver) {if(!this.active||this.state.loading||!this.inputDevice().available||document.hidden||!this.windowFocused)throw Error('Return to the game with a connected controller before starting.');clearTimeout(this.gameTimer);this.game=driver;this.gameStarted=performance.now();this.gameFrames=0;this.shared=true;this.last=0;this.publish({shared:true,running:true,status:'Playing together.'});this.canvas.focus();this.pumpGame();}
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
  if(!session?.enabled || session.worker!==this.active || this.disposed)return Promise.resolve();
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
 async exportSave():Promise<ArrayBuffer> {const reply=await this.fileRequest({type:'state-export'});if(reply.type!=='state-exported')throw Error('Unexpected save response');return reply.bytes;}
 async validateSave(bytes:ArrayBuffer) {await this.fileRequest({type:'state-validate',bytes});}
 async loadSave(bytes:ArrayBuffer) {
  if(this.disposed || this.state.loading)throw Error('Wait for a game to finish loading.');
  if(this.shared)throw Error('Shared save loading is not available yet. Leave the room before loading a local save.');
  this.pause();
  await this.fileRequest({type:'state-import',bytes});
  this.audio.flush();this.release();this.publish({status:'Save loaded. Resume whenever you’re ready.'});
 }

 private candidate?: Worker;
 private reader?: FileReader;
 private generation = 0;
 private disposed = false;
 private windowFocused=true;
 private keys = new Set<string>();
 private controls: Controls = defaults();
 private volume = 1;
 private busy = false;
 private last = 0;
 private fps = 60;
 private animation = 0;
 private context?: AudioContext;
 private gain?: GainNode;
 private muted = true;
 private audio = createAudioQueue(() => this.context, () => this.state.running, () => this.gain);
 private state: PlayerState = {status:'Choose a game to start playing.',loading:false,running:false,loaded:false,frames:0};
 constructor(private canvas: HTMLCanvasElement, private update: (state: PlayerState) => void) {
  this.persistenceTimer=window.setInterval(()=>{void this.persistBattery();},10000);window.addEventListener('pagehide',this.pagehide);
  window.addEventListener('keydown',this.down); window.addEventListener('keyup',this.up);
  window.addEventListener('blur',this.blur);window.addEventListener('focus',this.focus); document.addEventListener('visibilitychange',this.hidden);
  canvas.addEventListener('blur',this.canvasBlur);
  this.animation = requestAnimationFrame(this.tick);
 }
 private publish(patch: Partial<PlayerState>) { if(this.disposed) return; this.state = {...this.state,...patch}; this.update(this.state); }
 private send(worker: Worker, message: WorkerRequest, transfer: Transferable[] = []) { worker.postMessage(message,transfer); }
 private release = () => { this.keys.clear(); };
 private down = (event: KeyboardEvent) => {
  if(!this.controls.device && document.activeElement === this.canvas && this.state.running && Object.values(this.controls.keyboard).some(bindings=>bindings.includes(event.code))) {
   event.preventDefault(); this.keys.add(event.code);
  }
 };
 private up = (event: KeyboardEvent) => { this.keys.delete(event.code); };
 configureControls(controls: Controls) { this.controls = controls; this.release(); this.publish({inputIssue:undefined}); }
 useKeyboard() { this.configureControls({...this.controls,device:null}); this.publish({status:'Keyboard selected. Resume whenever you’re ready.'}); }
 setVolume(value:number) { if(!Number.isFinite(value) || value<0 || value>1) throw Error('Volume must be between 0 and 1'); this.volume=value; if(this.gain) this.gain.gain.value=this.muted ? 0 : value; }
 private canvasBlur = () => {this.release();};
 private focus = () => {this.windowFocused=true;};
 private blur = () => { this.windowFocused=false;this.pause('focus'); void this.persistBattery(); };
 private hidden = () => { if(document.hidden) {this.pause('focus');void this.persistBattery();} void this.persistBattery(); };
 private inputDevice() {
  const selected = this.controls.device;
  const pad = selected ? navigator.getGamepads()[selected.index] : undefined;
  return {pad,available:!selected || !!pad && pad.id===selected.id && pad.connected};
 }
 private controllerMask(pad:Gamepad|null|undefined) {
  const selected=this.controls.device;
  const pressed=document.activeElement===this.canvas?(selected?padInputs(pad):this.keys):new Set<string>();
  return inputMask(selected?this.controls.gamepad:this.controls.keyboard,pressed);
 }
 private tick = (now: number) => {
  this.animation = requestAnimationFrame(this.tick);
  const {pad,available} = this.inputDevice();
  if(!available) {
   if(this.state.running) this.pause('device');
   if(!this.state.inputIssue) this.publish({inputIssue:disconnectedMessage});
   return;
  }
  if(this.state.inputIssue) this.publish({inputIssue:undefined,status:'Controller reconnected. Resume whenever you’re ready.'});
  if(this.game || !this.active || !this.state.running || this.busy || now-this.last < 1000/this.fps) return;
  this.last = now-(now-this.last)%(1000/this.fps);
  const mask=this.controllerMask(pad);
  this.busy=true;this.send(this.active,{type:'frame',p1:mask,p2:0});
 };
 // As in the qualified D02 scheduler, wall time sets an absolute target. Input
 // waits retain debt; each worker request still commits exactly one known frame.
 private pumpGame = () => {
  if(!this.game||this.disposed)return;
  this.gameTimer=setTimeout(this.pumpGame,2);
  if(!this.active||!this.state.running)return;
  if(this.game.draining()){this.drainGame();return;}
  const {pad,available}=this.inputDevice();
  if(!available||document.hidden||!this.windowFocused){this.pause(available?'focus':'device');return;}
  const elapsed=performance.now()-this.gameStarted;
  if(elapsed-this.gameFrames*1000/this.fps>gameplayLimits.stallMs){this.pause('network');return;}
  if(this.busy||this.gameFrames>=Math.floor(elapsed*this.fps/1000))return;
  const next=this.game.next(this.controllerMask(pad));if(!next)return;
  this.busy=true;this.expectedFrame={epoch:this.game.epoch,frame:next.frame};this.send(this.active,{type:'frame',...next,epoch:this.game.epoch});
 };

 drainGame() {
  if(!this.game?.draining()||!this.active||this.busy)return;
  const next=this.game.next(0);if(!next)return;this.busy=true;this.expectedFrame={epoch:this.game.epoch,frame:next.frame};this.send(this.active,{type:'frame',...next,epoch:this.game.epoch});
 }
 private abandonCandidate() { this.rejectPending('Game selection changed. Try again for the current game.'); ++this.generation; this.reader?.abort(); this.reader = undefined; this.candidate?.terminate(); this.candidate = undefined; }
 rejectSelection(message: string) { this.abandonCandidate(); this.publish({loading:false,status:message}); }
 cancel() {
  this.abandonCandidate();
  this.publish({loading:false,status:this.state.loaded ? 'Selection cancelled. Your previous game is still here.' : 'Selection cancelled. Choose a game whenever you’re ready.'});
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
  if(!this.active || this.state.loading) return false;
  if(this.shared) {this.publish({status:'Shared play is paused. Use the room’s shared controls, or leave the room before resuming locally.'});return false;}
  if(!this.inputDevice().available) { this.publish({inputIssue:disconnectedMessage}); return false; }
  this.activateAudio(); this.last = 0; this.publish({running:true,inputIssue:undefined,status:'Playing locally. Your file stays in this browser.'}); this.canvas.focus();return true;
 }
 setMuted(value: boolean) { this.muted = value; if(this.gain) this.gain.gain.value = value ? 0 : this.volume; this.audio.flush(); if(!value) this.activateAudio(); }
 retryAudio() { this.activateAudio(); }
 private activateAudio() {
  try {
   if(!this.context) { this.context = new AudioContext(); this.gain = this.context.createGain(); this.gain.gain.value = this.muted ? 0 : this.volume; this.gain.connect(this.context.destination); this.context.onstatechange=()=>this.publish({audioState:this.context?.state}); }
   void this.context.resume().then(() => this.publish({audioIssue:this.context?.state === 'running' ? undefined : 'Sound is blocked. Retry sound to allow it; your game can continue.'})).catch(() => this.publish({audioIssue:'Sound could not start. Retry sound; your game can continue.'}));
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
 async load(file?: File, approve?: (fingerprint:LocalFingerprint,isCurrent:()=>boolean)=>Promise<boolean>,startPaused=false) {
  if(!file || this.disposed) return; // A chooser cancellation does not replace the valid selection.
  this.abandonCandidate(); const request = this.generation;
  this.activateAudio(); this.publish({loading:true,status:'Reading your file locally…'});
  try {
   const rom = await this.read(file);
   if(request !== this.generation || this.disposed) return;
   const cartridge = inspectCartridge(new Uint8Array(rom));
   this.publish({status:'Checking the exact file fingerprint…'});
   const romSha256 = hex(await crypto.subtle.digest('SHA-256',rom));
   if(request !== this.generation || this.disposed) return;
   this.publish({status:'Starting your game…'});
   const worker = new Worker(new URL('./worker.ts',import.meta.url),{type:'module'}); this.candidate = worker;
   const fail = (message: string) => {
    if(this.disposed) return;
    if(this.candidate === worker) { this.candidate = undefined; worker.terminate(); this.publish({loading:false,status:`Unable to load: ${message} Choose another file.${this.state.loaded ? ' Your previous game is preserved.' : ''}`}); }
    else if(this.active === worker) { this.rejectPending('The emulator stopped.'); this.active = undefined; worker.terminate(); this.busy = false; this.audio.flush(); this.publish({loaded:false,running:false,status:`The emulator stopped: ${message} Choose another file to retry.`}); }
   };
   worker.onerror = () => fail('This cartridge could not run in the emulator.');
   worker.onmessage = async ({data}: MessageEvent<WorkerResponse>) => {
    if(this.disposed) return;
    if('requestId' in data) {
     const pending=this.pending.get(data.requestId);
     if(pending?.worker===worker) {clearTimeout(pending.timer);this.pending.delete(data.requestId);if(data.type.endsWith('-error'))pending.reject(Error('message' in data ? data.message : 'Save failed'));else pending.resolve(data);}
     return;
    }
    if(data.type === 'error') { fail(data.message); return; }
    if(data.type === 'ready') {
     if(request !== this.generation || this.candidate !== worker) { worker.terminate(); return; }
     const fingerprint:LocalFingerprint = {romSha256,coreSha256:data.coreSha256,localSchema:LOCAL_SCHEMA,settings:LOCAL_SETTINGS,cartridge};
     const isCurrent=()=>request===this.generation && this.candidate===worker && !this.disposed;
     try {
      if(approve && !await approve(fingerprint,isCurrent)) {if(isCurrent()) this.cancel();return;}
     }catch {if(isCurrent()) fail('Unable to confirm the room change.');return;}
     if(!isCurrent()) {worker.terminate();return;}
     // Flush the old game before reading its identity again for a replacement.
     await this.persistBattery();
     if(!isCurrent()){worker.terminate();return;}
     const battery=data.battery ? await this.prepareBattery(worker,isCurrent) : {};
     if(!isCurrent()) {worker.terminate();return;}
     this.active?.terminate(); this.batterySession=battery.session; this.active = worker; this.candidate = undefined;
     this.audio.flush(); this.release(); this.busy = false; this.last = 0; this.fps = data.fps;
     const {available} = this.inputDevice();
     this.publish({loading:false,loaded:true,running:available&&!startPaused,frames:0,storageIssue:battery.issue,batteryAvailable:data.battery,inputIssue:available ? undefined : disconnectedMessage,status:startPaused ? 'Game loaded. Preparing shared play…' : available ? 'Playing locally. Your file stays in this browser.' : 'Game loaded paused. Reconnect your controller or use the keyboard, then Resume.',fingerprint});
     this.canvas.focus(); return;
    }
    if(this.active !== worker) return;
    if(data.type === 'frame') {
     this.busy = false;
     if(data.epoch!==undefined && (data.epoch!==this.expectedFrame?.epoch||data.frame!==this.expectedFrame.frame))return;
     const committed=this.expectedFrame;this.expectedFrame=undefined;
     this.canvas.getContext('2d')?.putImageData(new ImageData(new Uint8ClampedArray(data.pixels),256,240),0,0);
     if(this.state.running) this.audio.play(data.audio);
     this.publish({frames:this.state.frames+1});
     if(committed && this.game?.epoch===committed.epoch){this.gameFrames++;this.game.committed(committed.frame);}
     if(this.game?.draining())this.drainGame();
    }
   };
   this.send(worker,{type:'load',rom},[rom]);
  } catch(error) {
   if(request === this.generation && !this.disposed) this.publish({loading:false,status:`${error instanceof Error ? error.message : 'Unable to read this file.'}${this.state.loaded ? ' Your previous game is preserved.' : ''}`});
  }
 }
 dispose() {
  clearInterval(this.persistenceTimer);window.removeEventListener('pagehide',this.pagehide);
  this.disposed = true; clearTimeout(this.gameTimer); this.abandonCandidate(); this.active?.terminate(); cancelAnimationFrame(this.animation); this.audio.flush(); void this.context?.close();
  window.removeEventListener('keydown',this.down); window.removeEventListener('keyup',this.up); window.removeEventListener('blur',this.blur);window.removeEventListener('focus',this.focus); document.removeEventListener('visibilitychange',this.hidden); this.canvas.removeEventListener('blur',this.canvasBlur);
 }
}
