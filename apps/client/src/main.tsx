import {ConnectionPolicyControl,readConnectionPolicy,rememberConnectionPolicy} from './ConnectionPolicy.tsx';
import type {ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { LocalPlayer, type PlayerState } from './player.ts';
import { neutralDefaults } from './cartridge.ts';
import { clientConfig } from './config.ts';
import './style.css';
import {RoomPanel, type RoomPanelHandle} from './RoomPanel.tsx';
import { Settings } from './Settings.tsx';
import { defaults, type Controls } from './controls.ts';

function App() {
 const canvas = useRef<HTMLCanvasElement>(null), picker = useRef<HTMLInputElement>(null);
 const runtime = useRef<LocalPlayer | null>(null);
 const panel = useRef<HTMLElement>(null);
 const [controls,setControls] = useState<Controls>(defaults), [settings,setSettings] = useState(false);
 const [filter,setFilter] = useState<'nearest'|'scanlines'>('nearest'), [volume,setVolume] = useState(1);
 const [fullscreen,setFullscreen] = useState(false), [fullscreenIssue,setFullscreenIssue] = useState('');
 useEffect(()=>{const changed=()=>setFullscreen(!!document.fullscreenElement);document.addEventListener('fullscreenchange',changed);return ()=>document.removeEventListener('fullscreenchange',changed);},[]);
 const changeControls=(value:Controls)=>{setControls(value);runtime.current?.configureControls(value);};
 const toggleFullscreen=async()=>{try{setFullscreenIssue('');if(document.fullscreenElement) await document.exitFullscreen();else await panel.current?.requestFullscreen();}catch{setFullscreenIssue('Fullscreen was declined. You can keep playing in this window.');}};
 const [identity] = useState(neutralDefaults);
 const [guest,setGuest] = useState(identity.guest);
 const rooms = useRef<RoomPanelHandle>(null);
 const [policy,setPolicy]=useState<ConnectionPolicy>(readConnectionPolicy),[connection,setConnection]=useState('No peer connection.');
 const changePolicy=(value:ConnectionPolicy)=>{runtime.current?.pause();rememberConnectionPolicy(value);setPolicy(value);};
 const load = (file?:File) => {if(file && rooms.current?.beforeSelection() !== false) void runtime.current?.load(file,(fingerprint,isCurrent)=>rooms.current?.approveSelection(fingerprint,isCurrent) ?? Promise.resolve(isCurrent()));};
 const [state,setState] = useState<PlayerState>({status:'Choose a game to start playing.',loading:false,running:false,loaded:false,frames:0});
 const [muted,setMuted] = useState(true), [drag,setDrag] = useState(false);
 useEffect(() => { const player = new LocalPlayer(canvas.current!,setState); runtime.current = player; return () => { player.dispose(); runtime.current = null; }; },[]);
 const choose = () => { picker.current!.value = ''; picker.current!.click(); };
 return <main data-coordinator={clientConfig.coordinatorUrl}>
  <header><a href="/" className="brand">RETRO COOP</a><span data-testid="guest">{guest}</span></header>
  <section className="intro"><p className="eyebrow">Your game. Your browser.</p><h1>Pick a classic.<br/>Press play.</h1><p>Bring an NES cartridge file and jump straight into local play. No account, setup form, or upload.</p></section>
  <RoomPanel ref={rooms} fingerprint={state.fingerprint} onNickname={setGuest} policy={policy} changePolicy={changePolicy} onConnection={setConnection}/>
  <section ref={panel} className={`panel ${drag ? 'drag' : ''}`} aria-labelledby="player-title" onDragOver={event => {event.preventDefault(); setDrag(true);}} onDragLeave={event => {if(!event.currentTarget.contains(event.relatedTarget as Node)) setDrag(false);}} onDrop={event => {event.preventDefault();setDrag(false);if(event.dataTransfer.files.length === 1) load(event.dataTransfer.files[0]); else runtime.current?.rejectSelection('Choose one NES cartridge at a time. Your previous game is preserved.');}}>
   <div><p className="eyebrow">Local practice · your controls</p><h2 id="player-title">{state.loaded ? 'Your local game' : 'Drop your NES game here'}</h2>
   <p>{state.loaded ? 'Your local game stays available if the room service cannot connect.' : 'Choose a file, or drop it anywhere in this panel. Your file stays on this device.'}</p>
   <input ref={picker} type="file" accept=".nes" hidden aria-label="NES cartridge file" onChange={event => load(event.target.files?.[0])}/>
   <div className="controls"><button onClick={choose}>{state.loaded ? 'Choose another file' : 'Choose NES file'}</button>{state.loading && <button onClick={() => {runtime.current?.cancel();rooms.current?.cancelCreation();}}>Cancel loading</button>}<button disabled={!state.loaded || state.loading} onClick={() => state.running ? runtime.current?.pause() : runtime.current?.resume()}>{state.running ? 'Pause' : 'Resume'}</button><button aria-pressed={muted} onClick={() => {const value = !muted;setMuted(value);runtime.current?.setMuted(value);}}>{muted ? 'Unmute' : 'Mute'}</button></div>
   <div className="controls"><button onClick={()=>setSettings(true)}>Settings</button><button onClick={()=>void toggleFullscreen()}>{fullscreen ? 'Exit fullscreen' : 'Fullscreen'}</button></div>
   {fullscreen && <p className="hint">Press Esc or Exit fullscreen to return.</p>}{fullscreenIssue && <p role="status">{fullscreenIssue}</p>}
   {state.inputIssue && <p role="alert">{state.inputIssue} <button onClick={()=>{changeControls({...controls,device:null});runtime.current?.useKeyboard();}}>Use keyboard</button></p>}
   <p role="status" data-testid="player-status" aria-live="polite">{state.status}</p>{state.audioIssue && <p className="hint">{state.audioIssue} <button onClick={() => runtime.current?.retryAudio()}>Retry sound</button></p>}
   <p className="hint">Uncompressed iNES / NES 2.0 cartridges. Support varies by cartridge hardware and available memory. Archives and disk images cannot load.</p>
   <p className="hint">Experimental compatibility: a loaded game is not a guarantee that every mapper feature works.</p>
   <details><summary>Controls &amp; local file details</summary><p className="hint">Focus the screen to play. Default arrows: move · X: A · Z: B · Enter: Start · Shift: Select. Open Settings to choose a controller, remap buttons, and test inputs. Switching windows pauses play.</p>
   {state.fingerprint && <dl data-testid="fingerprint"><dt>Cartridge</dt><dd>{state.fingerprint.cartridge.format} · mapper {state.fingerprint.cartridge.mapper} / {state.fingerprint.cartridge.submapper} · {state.fingerprint.cartridge.region} · {state.fingerprint.cartridge.bytes} bytes</dd><dt>Exact file SHA-256</dt><dd>{state.fingerprint.romSha256}</dd><dt>Emulator build SHA-256</dt><dd>{state.fingerprint.coreSha256}</dd><dt>Local settings (schema {state.fingerprint.localSchema})</dt><dd>{state.fingerprint.settings}</dd></dl>}</details>
   <span aria-label="Rendered frames" data-testid="frames">{state.frames} frames</span></div>
   <div className={`screen ${filter}`}><canvas ref={canvas} width="256" height="240" tabIndex={0} aria-label="Local game screen"/>{!state.loaded && <p>YOUR NEXT ADVENTURE<br/><span>starts with a file</span></p>}</div>
  </section>
  <Settings connection={<><ConnectionPolicyControl policy={policy} change={changePolicy}/><p>{connection}</p></>} open={settings} close={()=>setSettings(false)} controls={controls} change={changeControls} filter={filter} setFilter={setFilter} volume={volume} setVolume={value=>{setVolume(value);runtime.current?.setVolume(value);}} muted={muted} audioIssue={state.audioIssue} audioState={state.audioState} retryAudio={()=>runtime.current?.retryAudio()}/>
  <footer>Your game runs in this browser. Room metadata and connection signaling go to the service; your game file stays here.</footer>
 </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
