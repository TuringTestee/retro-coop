import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { LocalPlayer, type PlayerState } from './player.ts';
import { neutralDefaults } from './cartridge.ts';
import { clientConfig } from './config.ts';
import './style.css';

function App() {
 const canvas = useRef<HTMLCanvasElement>(null), picker = useRef<HTMLInputElement>(null);
 const runtime = useRef<LocalPlayer | null>(null);
 const [identity] = useState(neutralDefaults);
 const [state,setState] = useState<PlayerState>({status:'Choose a game to start playing.',loading:false,running:false,loaded:false,frames:0});
 const [muted,setMuted] = useState(true), [drag,setDrag] = useState(false);
 useEffect(() => { const player = new LocalPlayer(canvas.current!,setState); runtime.current = player; return () => { player.dispose(); runtime.current = null; }; },[]);
 const choose = () => { picker.current!.value = ''; picker.current!.click(); };
 return <main data-coordinator={clientConfig.coordinatorUrl}>
  <header><a href="/" className="brand">RETRO COOP</a><span data-testid="guest">{identity.guest}</span></header>
  <section className="intro"><p className="eyebrow">Your game. Your browser.</p><h1>Pick a classic.<br/>Press play.</h1><p>Bring an NES cartridge file and jump straight into local play. No account, setup form, or upload.</p></section>
  <section className={`panel ${drag ? 'drag' : ''}`} aria-labelledby="player-title" onDragOver={event => {event.preventDefault(); setDrag(true);}} onDragLeave={event => {if(!event.currentTarget.contains(event.relatedTarget as Node)) setDrag(false);}} onDrop={event => {event.preventDefault();setDrag(false);if(event.dataTransfer.files.length === 1) void runtime.current?.load(event.dataTransfer.files[0]); else setState(old => ({...old,status:'Choose one NES cartridge at a time.'}));}}>
   <div><p className="eyebrow">Local play · Player 1</p><h2 id="player-title">{state.loaded ? identity.room : 'Drop your NES game here'}</h2>
   <p>{state.loaded ? 'A neutral session name, just for this tab. Online rooms are coming next.' : 'Choose a file, or drop it anywhere in this panel. Your file stays on this device.'}</p>
   <input ref={picker} type="file" accept=".nes" hidden aria-label="NES cartridge file" onChange={event => void runtime.current?.load(event.target.files?.[0])}/>
   <div className="controls"><button onClick={choose}>{state.loaded ? 'Choose another file' : 'Choose NES file'}</button>{state.loading && <button onClick={() => runtime.current?.cancel()}>Cancel loading</button>}<button disabled={!state.loaded} onClick={() => state.running ? runtime.current?.pause() : runtime.current?.resume()}>{state.running ? 'Pause' : 'Resume'}</button><button aria-pressed={muted} onClick={() => {const value = !muted;setMuted(value);runtime.current?.setMuted(value);}}>{muted ? 'Unmute' : 'Mute'}</button></div>
   <p role="status" aria-live="polite">{state.status}</p>
   <p className="hint">Uncompressed iNES / NES 2.0 cartridges. No title allowlist. Available memory and emulator hardware support determine what can load; archives and disk images cannot.</p>
   <p className="hint">Experimental compatibility: a loaded game is not a guarantee that every mapper feature works.</p>
   <details><summary>Controls &amp; local file details</summary><p className="hint">Focus the screen to play. Arrow keys: move · X: A · Z: B · Enter: Start · Shift: Select. Standard gamepad buttons and D-pad work too. Switching windows pauses play.</p>
   {state.fingerprint && <dl data-testid="fingerprint"><dt>Cartridge</dt><dd>{state.fingerprint.cartridge.format} · mapper {state.fingerprint.cartridge.mapper} / {state.fingerprint.cartridge.submapper} · {state.fingerprint.cartridge.region} · {state.fingerprint.cartridge.bytes} bytes</dd><dt>Exact file SHA-256</dt><dd>{state.fingerprint.romSha256}</dd><dt>Emulator build SHA-256</dt><dd>{state.fingerprint.coreSha256}</dd><dt>Local settings (schema {state.fingerprint.localSchema})</dt><dd>{state.fingerprint.settings}</dd></dl>}</details>
   <output aria-label="Rendered frames" data-testid="frames">{state.frames} frames</output></div>
   <div className="screen"><canvas ref={canvas} width="256" height="240" tabIndex={0} aria-label="Local game screen"/>{!state.loaded && <p>YOUR NEXT ADVENTURE<br/><span>starts with a file</span></p>}</div>
  </section><footer>Your game runs in this browser. Nothing is published or saved to a server.</footer>
 </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
