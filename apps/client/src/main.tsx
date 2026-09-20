import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { WorkerRequest, WorkerResponse } from '../../../packages/contracts/src/index.ts';
import { keyMap, gamepadMask } from '../../../spikes/d02/demo/runtime/input.js';
import { createAudioQueue } from '../../../spikes/d02/demo/runtime/audio.js';
import './style.css';
import { clientConfig } from './config.ts';

function App() {
 const canvas = useRef<HTMLCanvasElement>(null);
 const runtime = useRef<{pause():void; dispose():void} | null>(null);
 const [status,setStatus] = useState('Ready to test local emulation.');
 const [running,setRunning] = useState(false);
 const [frames,setFrames] = useState(0);
 const [muted,setMuted] = useState(true);
 const gain = useRef<GainNode | null>(null);
 useEffect(() => () => runtime.current?.dispose(), []);
 async function start() {
  runtime.current?.dispose(); setRunning(true); setFrames(0); setStatus('Loading the original diagnostic…');
  const worker = new Worker(new URL('./worker.ts',import.meta.url), {type:'module'});
  const context = new AudioContext(); const output = context.createGain(); output.gain.value = muted ? 0 : 1; output.connect(context.destination); gain.current = output;
  const audio = createAudioQueue(() => context, () => true, () => output);
  let disposed = false, ready = false, initialized = false, paused = false, busy = false, keys = 0, count = 0, fps = 60, last = 0, animation = 0;
  const send = (message: WorkerRequest, transfer: Transferable[] = []) => worker.postMessage(message, transfer);
  const pause = () => { paused = true; ready = false; keys = 0; audio.flush(); if(initialized) send({type:'pause'}); setRunning(false); };
  const down = (event: KeyboardEvent) => { const bit = keyMap[event.code as keyof typeof keyMap]; if (bit && document.activeElement === canvas.current) { event.preventDefault(); keys |= bit; } };
  const up = (event: KeyboardEvent) => { keys &= ~(keyMap[event.code as keyof typeof keyMap] ?? 0); };
  const blur = () => { keys = 0; };
  const hidden = () => { if (document.hidden) pause(); };
  window.addEventListener('keydown',down); window.addEventListener('keyup',up); window.addEventListener('blur',pause);
  canvas.current?.addEventListener('blur',blur); document.addEventListener('visibilitychange',hidden);
  runtime.current = {pause,dispose() { disposed = true; worker.terminate(); cancelAnimationFrame(animation); audio.flush(); void context.close(); window.removeEventListener('keydown',down); window.removeEventListener('keyup',up); window.removeEventListener('blur',pause); canvas.current?.removeEventListener('blur',blur); document.removeEventListener('visibilitychange',hidden); }};
  function tick(now:number) {
   animation = requestAnimationFrame(tick);
   if (!ready || busy || now-last < 1000/fps) return;
   last = now-(now-last)%(1000/fps); busy = true;
   send({type:'frame',p1:keys | gamepadMask([...navigator.getGamepads()].find(Boolean)),p2:0});
  }
  worker.onmessage = ({data}: MessageEvent<WorkerResponse>) => {
   if (disposed) return;
   if (data.type === 'ready') { initialized = true; fps = data.fps; if(paused) send({type:'pause'}); else { ready = true; setStatus('Diagnostic running locally'); canvas.current?.focus(); } }
   else if (data.type === 'frame') {
    busy = false; canvas.current?.getContext('2d')?.putImageData(new ImageData(new Uint8ClampedArray(data.pixels),256,240),0,0);
    if (ready) audio.play(data.audio); setFrames(++count);
   } else if (data.type === 'paused') setStatus('Paused. Run diagnostic to restart.');
   else { ready = false; setRunning(false); audio.flush(); setStatus(data.message); }
  };
  worker.onerror = () => { ready = false; setRunning(false); audio.flush(); setStatus('Emulator stopped. Run diagnostic to retry.'); };
  try {
   await context.resume();
   const response = await fetch('/generated/diagnostic.nes');
   if (!response.ok) throw Error('Prepare the diagnostic assets before running.');
   const rom = await response.arrayBuffer();
   if (disposed) return; send({type:'load',rom},[rom]); animation = requestAnimationFrame(tick);
  } catch (error) { if (!disposed) { setStatus(error instanceof Error ? error.message : 'Unable to start'); setRunning(false); runtime.current?.dispose(); } }
 }
 return <main data-coordinator={clientConfig.coordinatorUrl}>
  <header><a href="/" className="brand">RETRO COOP</a><span>Local foundation</span></header>
  <section className="intro"><p className="eyebrow">A place to play together</p><h1>Classic games.<br/>Shared moments.</h1><p>We’re building browser-local NES multiplayer. This early build tests the emulator, controls, and sound.</p></section>
  <section className="panel" aria-labelledby="diagnostic-title">
   <div><p className="eyebrow">Development preview</p><h2 id="diagnostic-title">Local diagnostic</h2><p>An original test cartridge checks the player foundation. Online rooms and your game library are coming later.</p>
   <div className="controls"><button onClick={() => void start()} disabled={running}>Run diagnostic</button><button onClick={() => runtime.current?.pause()} disabled={!running}>Pause</button><button aria-pressed={muted} onClick={() => { const value = !muted; setMuted(value); if(gain.current) gain.current.gain.value = value ? 0 : 1; }}>{muted ? 'Unmute' : 'Mute'}</button></div>
   <p role="status">{status}</p><p className="hint">Focus the screen. Arrow keys move · X / Z · Enter starts</p><output aria-label="Rendered frames" data-testid="frames">{frames} frames</output></div>
   <canvas ref={canvas} width="256" height="240" tabIndex={0} aria-label="Local diagnostic screen" />
  </section><footer>Your game runs in this browser. No account needed.</footer>
 </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
