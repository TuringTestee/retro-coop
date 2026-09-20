import type { WorkerRequest, WorkerResponse } from '../../../packages/contracts/src/index.ts';
import { keyMap, gamepadMask } from '../../../spikes/d02/demo/runtime/input.js';
import { createAudioQueue } from '../../../spikes/d02/demo/runtime/audio.js';
import { inspectCartridge, hex, type Cartridge } from './cartridge.ts';

export type LocalFingerprint = { romSha256: string; coreSha256: string; localSchema: 1; settings: 'auto-region;zero-ram;48000hz;standard-p1-p2'; cartridge: Cartridge };
export type PlayerState = { status: string; loading: boolean; running: boolean; loaded: boolean; frames: number; audioIssue?: string; fingerprint?: LocalFingerprint };
/** Owns browser-local resources. A candidate replaces the active worker only after initialization succeeds. */
export class LocalPlayer {
 private active?: Worker;
 private candidate?: Worker;
 private reader?: FileReader;
 private generation = 0;
 private disposed = false;
 private keys = 0;
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
  window.addEventListener('keydown',this.down); window.addEventListener('keyup',this.up);
  window.addEventListener('blur',this.blur); document.addEventListener('visibilitychange',this.hidden);
  canvas.addEventListener('blur',this.release);
  this.animation = requestAnimationFrame(this.tick);
 }
 private publish(patch: Partial<PlayerState>) { if(this.disposed) return; this.state = {...this.state,...patch}; this.update(this.state); }
 private send(worker: Worker, message: WorkerRequest, transfer: Transferable[] = []) { worker.postMessage(message,transfer); }
 private release = () => { this.keys = 0; };
 private down = (event: KeyboardEvent) => { const bit = keyMap[event.code as keyof typeof keyMap]; if(bit && document.activeElement === this.canvas && this.state.running) { event.preventDefault(); this.keys |= bit; } };
 private up = (event: KeyboardEvent) => { this.keys &= ~(keyMap[event.code as keyof typeof keyMap] ?? 0); };
 private blur = () => { this.pause(); };
 private hidden = () => { if(document.hidden) this.pause(); };
 private tick = (now: number) => {
  this.animation = requestAnimationFrame(this.tick);
  if(!this.active || !this.state.running || this.busy || now-this.last < 1000/this.fps) return;
  this.last = now-(now-this.last)%(1000/this.fps); this.busy = true;
  // Gamepads obey the same focus boundary as keyboard input, including when editing text.
  const pad = document.activeElement === this.canvas ? gamepadMask([...navigator.getGamepads()].find(Boolean)) : 0;
  this.send(this.active,{type:'frame',p1:this.keys | pad,p2:0});
 };
 private abandonCandidate() { ++this.generation; this.reader?.abort(); this.reader = undefined; this.candidate?.terminate(); this.candidate = undefined; }
 rejectSelection(message: string) { this.abandonCandidate(); this.publish({loading:false,status:message}); }
 cancel() {
  this.abandonCandidate();
  this.publish({loading:false,status:this.state.loaded ? 'Selection cancelled. Your previous game is still here.' : 'Selection cancelled. Choose a game whenever you’re ready.'});
 }
 pause() {
  if(this.state.loading) this.cancel();
  this.release(); this.audio.flush();
  if(this.active) { this.send(this.active,{type:'pause'}); this.publish({running:false,status:'Paused. Resume whenever you’re ready.'}); }
 }
 resume() {
  if(!this.active || this.state.loading) return;
  this.activateAudio(); this.last = 0; this.publish({running:true,status:'Playing locally. Your file stays in this browser.'}); this.canvas.focus();
 }
 setMuted(value: boolean) { this.muted = value; if(this.gain) this.gain.gain.value = value ? 0 : 1; this.audio.flush(); if(!value) this.activateAudio(); }
 retryAudio() { this.activateAudio(); }
 private activateAudio() {
  try {
   if(!this.context) { this.context = new AudioContext(); this.gain = this.context.createGain(); this.gain.gain.value = this.muted ? 0 : 1; this.gain.connect(this.context.destination); }
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
 async load(file?: File) {
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
    else if(this.active === worker) { this.active = undefined; worker.terminate(); this.busy = false; this.audio.flush(); this.publish({loaded:false,running:false,status:`The emulator stopped: ${message} Choose another file to retry.`}); }
   };
   worker.onerror = () => fail('This cartridge could not run in the emulator.');
   worker.onmessage = ({data}: MessageEvent<WorkerResponse>) => {
    if(this.disposed) return;
    if(data.type === 'error') { fail(data.message); return; }
    if(data.type === 'ready') {
     if(request !== this.generation || this.candidate !== worker) { worker.terminate(); return; }
     this.active?.terminate(); this.active = worker; this.candidate = undefined;
     this.audio.flush(); this.release(); this.busy = false; this.last = 0; this.fps = data.fps;
     this.publish({loading:false,loaded:true,running:true,frames:0,status:'Playing locally. Your file stays in this browser.',fingerprint:{romSha256,coreSha256:data.coreSha256,localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge}});
     this.canvas.focus(); return;
    }
    if(this.active !== worker) return;
    if(data.type === 'frame') {
     this.busy = false;
     this.canvas.getContext('2d')?.putImageData(new ImageData(new Uint8ClampedArray(data.pixels),256,240),0,0);
     if(this.state.running) this.audio.play(data.audio);
     this.publish({frames:this.state.frames+1});
    }
   };
   this.send(worker,{type:'load',rom},[rom]);
  } catch(error) {
   if(request === this.generation && !this.disposed) this.publish({loading:false,status:`${error instanceof Error ? error.message : 'Unable to read this file.'}${this.state.loaded ? ' Your previous game is preserved.' : ''}`});
  }
 }
 dispose() {
  this.disposed = true; this.abandonCandidate(); this.active?.terminate(); cancelAnimationFrame(this.animation); this.audio.flush(); void this.context?.close();
  window.removeEventListener('keydown',this.down); window.removeEventListener('keyup',this.up); window.removeEventListener('blur',this.blur); document.removeEventListener('visibilitychange',this.hidden); this.canvas.removeEventListener('blur',this.release);
 }
}
