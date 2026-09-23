import {VoiceControls} from './VoiceControls.tsx';
import type {VoiceState} from './voice.ts';
import {ConnectionPolicyControl,readConnectionPolicy,rememberConnectionPolicy} from './ConnectionPolicy.tsx';
import type {ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { LocalPlayer, type PlayerState } from './player.ts';
import { neutralDefaults } from './cartridge.ts';
import { clientConfig } from './config.ts';
import './style.css';
import {RoomPanel, type RoomPanelHandle} from './RoomPanel.tsx';
import {LocalData} from './LocalData.tsx';
import {usePreferences} from './preferences.ts';
import {fileIdentity} from '../../../packages/contracts/src/fingerprint.ts';
import {downloadSave} from './saves.ts';
import { Rewind } from './Rewind.tsx';
import { Saves } from './Saves.tsx';
import { Settings } from './Settings.tsx';
import { defaults, type Controls } from './controls.ts';
import {catalogEntry,catalogId} from '../../../packages/contracts/src/catalog.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';

function App() {
 const canvas = useRef<HTMLCanvasElement>(null), picker = useRef<HTMLInputElement>(null), helpDialog=useRef<HTMLDialogElement>(null);
 const runtime = useRef<LocalPlayer | null>(null);
 const panel = useRef<HTMLElement>(null);
 const [rewind,setRewind]=useState(false),[help,setHelp]=useState(false);
 const [saves,setSaves]=useState(false),[localData,setLocalData]=useState(false),[returnSettings,setReturnSettings]=useState(false),[persistenceMessage,setPersistenceMessage]=useState('');
 const [controls,setControls] = useState<Controls>(defaults), [settings,setSettings] = useState(false);
 const [filter,setFilter] = useState<'nearest'|'scanlines'>('nearest'), [volume,setVolume] = useState(1);
 const [fullscreen,setFullscreen] = useState(false), [fullscreenIssue,setFullscreenIssue] = useState('');
 useEffect(()=>{const changed=()=>setFullscreen(!!document.fullscreenElement);document.addEventListener('fullscreenchange',changed);return ()=>document.removeEventListener('fullscreenchange',changed);},[]);
 useEffect(()=>{if(help){helpDialog.current?.showModal();}else helpDialog.current?.close();},[help]);
 const changeControls=(value:Controls)=>{setControls(value);runtime.current?.configureControls(value);preferences.remember({controls:value,filter,volume});};
 const toggleFullscreen=async()=>{try{setFullscreenIssue('');if(document.fullscreenElement) await document.exitFullscreen();else await panel.current?.requestFullscreen();}catch{setFullscreenIssue('Fullscreen was declined. You can keep playing in this window.');}};
 const [identity] = useState(neutralDefaults);
 const [guest,setGuest] = useState(identity.guest);
 const rooms = useRef<RoomPanelHandle>(null);
 const [voice,setVoice]=useState<VoiceState>();
 const [policy,setPolicy]=useState<ConnectionPolicy>(readConnectionPolicy),[connection,setConnection]=useState('No peer connection.');
 const changePolicy=(value:ConnectionPolicy)=>{runtime.current?.pause();rememberConnectionPolicy(value);setPolicy(value);};
 const load = (file?:File,selectionCurrent?:()=>boolean):boolean => {if(!file||!runtime.current||selectionCurrent&&!selectionCurrent()||!selectionCurrent&&rooms.current?.beforeSelection()===false)return false;void runtime.current.load(file,(fingerprint,isCurrent)=>rooms.current?.approveSelection(fingerprint,isCurrent,file) ?? Promise.resolve(isCurrent()),true,selectionCurrent);return true;};
 const [state,setState] = useState<PlayerState>({status:'Choose a game to start playing.',loading:false,running:false,loaded:false,frames:0});
 const [browsing,setBrowsing]=useState(false),[sessionOpen,setSessionOpen]=useState(false),[roomView,setRoomView]=useState<RoomView>();
 const [invitationHash,setInvitationHash]=useState(location.hash);
 useEffect(()=>{const sync=()=>{setInvitationHash(location.hash);if(new URLSearchParams(location.hash.slice(1)).has('invite'))setBrowsing(false);};addEventListener('hashchange',sync);addEventListener('popstate',sync);return()=>{removeEventListener('hashchange',sync);removeEventListener('popstate',sync);};},[]);
 const syncRoom=useCallback((room?:RoomView)=>{setRoomView(room);if(room)setBrowsing(false);},[]);
 const roomStartRequired=!!roomView&&!roomView.started;
 const [muted,setMuted] = useState(true), [drag,setDrag] = useState(false);
 const preferencesIdentity=state.fingerprint ? fileIdentity(state.fingerprint) : undefined;
 const preferences=usePreferences(preferencesIdentity,value=>{setControls(value.controls);runtime.current?.configureControls(value.controls);setFilter(value.filter);setVolume(value.volume);runtime.current?.setVolume(value.volume);});
 const openLocalData=(fromSettings=false)=>{setReturnSettings(fromSettings);setSettings(false);setLocalData(true);};
 const batteryAction=async(action:()=>Promise<void>)=>{try{await action();setPersistenceMessage('');}catch(error){setPersistenceMessage(error instanceof Error ? error.message : 'Battery operation failed.');}};

 useEffect(() => { const player = new LocalPlayer(canvas.current!,setState); runtime.current = player; return () => { player.dispose(); runtime.current = null; }; },[]);
 const choose = () => { picker.current!.value = ''; picker.current!.click(); };
 const invitationRequested=new URLSearchParams(invitationHash.slice(1)).has('invite');
 const showDiscovery=browsing||(!roomView&&(invitationRequested||!state.loaded)),showRoom=!!roomView&&!roomView.started&&!browsing,known=state.fingerprint?catalogId(state.fingerprint):undefined;
 const inviting=showDiscovery&&!roomView&&invitationRequested;
 return <main className={`${showDiscovery?'discovery':showRoom?'waiting-room':'playing'}${browsing?' browsing':''}${inviting?' inviting':''}${state.shared?' shared-session':''}${sessionOpen?' session-open':''}`} data-coordinator={clientConfig.coordinatorUrl}>
  <header><a href="/" className="brand">RETRO COOP</a><span data-testid="guest">{guest}</span>{!inviting&&(roomView||state.loaded)&&<button onClick={()=>{setBrowsing(value=>!value);setSessionOpen(false);}}>{browsing?roomView?'Return to room':'Return to game':'Public rooms'}</button>}{!browsing&&roomView?.started&&<button aria-expanded={sessionOpen} aria-controls="room-session" onClick={()=>{setSessionOpen(value=>!value);if(sessionOpen)canvas.current?.focus();}}>{sessionOpen?'Back to game':'Room'}</button>}<button onClick={()=>setSettings(true)}>Settings</button></header>
  <input ref={picker} type="file" accept=".nes" hidden aria-label="NES cartridge file" onChange={event => load(event.target.files?.[0])}/>
  <RoomPanel showDiscovery={showDiscovery} onChoose={choose} onBrowse={()=>setBrowsing(true)} onInvitationDismiss={()=>setInvitationHash('')} onAcquired={load} selectionLoading={state.loading} ref={rooms} controls={controls} onVoice={setVoice} player={()=>runtime.current} fingerprint={state.fingerprint} onNickname={setGuest} policy={policy} changePolicy={changePolicy} onConnection={setConnection} onRoomChange={syncRoom}/>
  {showDiscovery&&state.status!=='Choose a game to start playing.'&&<p className="selection-status" role="status">{state.status}</p>}
  <section ref={panel} className={`panel ${drag ? 'drag' : ''}`} aria-labelledby="player-title" onDragOver={event => {event.preventDefault(); setDrag(true);}} onDragLeave={event => {if(!event.currentTarget.contains(event.relatedTarget as Node)) setDrag(false);}} onDrop={event => {event.preventDefault();setDrag(false);if(event.dataTransfer.files.length === 1) load(event.dataTransfer.files[0]); else runtime.current?.rejectSelection('Choose one NES cartridge at a time. Your previous game is preserved.');}}>
   <div className="player-info"><p className="eyebrow">{state.shared?'Shared play · your controller':'Local practice · your controls'}</p><h2 id="player-title">{state.shared ? (state.running?'Playing together':'Shared game paused') : state.loaded ? 'Your local game' : 'Drop your NES game here'}</h2>
   <p>{state.shared ? 'The game runs in your browser. Saves keep a local copy of your progress.' : state.loaded ? 'Your local game stays available if the room service cannot connect.' : 'Choose a file, or drop it anywhere in this panel. Hosting uploads its bytes to the room server.'}</p>
   {state.loading&&<div className="controls"><button onClick={() => {runtime.current?.cancel();rooms.current?.cancelCreation();}}>Cancel loading</button></div>}
   {state.loaded&&<><div className="controls">{!roomView?.established&&<button onClick={choose}>Choose another file</button>}{!roomStartRequired&&!(state.shared&&!state.running&&sessionOpen)&&<button disabled={state.loading} onClick={() => state.running ? runtime.current?.pause() : state.shared ? rooms.current?.readyToResume() : runtime.current?.resume() && rooms.current?.localPlayIntent()}>{state.running ? 'Pause' : state.shared ? 'Ready to resume' : 'Resume'}</button>}<button aria-pressed={muted} onClick={() => {const value = !muted;setMuted(value);runtime.current?.setMuted(value);}}>{muted ? 'Unmute' : 'Mute'}</button></div>
   <div className="controls"><button onClick={()=>setSaves(true)}>Saves</button><button disabled={state.shared} onClick={()=>setRewind(true)}>Rewind</button><button onClick={()=>setHelp(true)}>Game help</button><button onClick={()=>void toggleFullscreen()}>{fullscreen ? 'Exit fullscreen' : 'Fullscreen'}</button></div></>}
   {fullscreen && <p className="hint">Press Esc or Exit fullscreen to return.</p>}{fullscreenIssue && <p role="status">{fullscreenIssue}</p>}
   {state.inputIssue && <p role="alert">{state.inputIssue} <button onClick={()=>{changeControls({...controls,device:null});runtime.current?.useKeyboard();}}>Use keyboard</button></p>}
   <p role="status" data-testid="player-status" aria-live="polite">{state.status}</p>{state.audioIssue && <p className="hint" role="status">{state.audioIssue} <button onClick={() => runtime.current?.retryAudio()}>Retry sound</button></p>}
   <p className="hint">Uncompressed iNES / NES 2.0 cartridges. Support varies by cartridge hardware and available memory. Archives and disk images cannot load.</p>
   <p className="hint">Experimental compatibility: a loaded game is not a guarantee that every mapper feature works.</p>
   <details><summary>Game details</summary><p className="hint">Focus the screen to control it. Default arrows: move · X: A · Z: B · Enter: Start · Shift is Select. Open Settings to choose a controller, remap buttons, and test inputs. Switching tabs releases held buttons while play continues.</p>
   {state.fingerprint && <dl data-testid="fingerprint"><dt>Cartridge</dt><dd>{state.fingerprint.cartridge.format} · mapper {state.fingerprint.cartridge.mapper} / {state.fingerprint.cartridge.submapper} · {state.fingerprint.cartridge.region} · {state.fingerprint.cartridge.bytes} bytes</dd><dt>Exact file SHA-256</dt><dd>{state.fingerprint.romSha256}</dd><dt>Emulator build SHA-256</dt><dd>{state.fingerprint.coreSha256}</dd><dt>Local settings (schema {state.fingerprint.localSchema})</dt><dd>{state.fingerprint.settings}</dd></dl>}</details>
   <span aria-label="Rendered frames" data-testid="frames">{state.frames} frames</span>
   {(state.storageIssue || preferences.issue || persistenceMessage) && <p role="status" data-testid="persistence-status">{state.storageIssue || preferences.issue || persistenceMessage} <button onClick={()=>openLocalData()}>Manage local data</button></p>}
   {state.batteryAvailable && <div className="battery-actions"><button onClick={()=>void batteryAction(async()=>{downloadSave(await runtime.current!.exportBattery(),undefined,'battery');})}>Export current battery</button>{state.storageIssue&&<button onClick={()=>void batteryAction(()=>runtime.current!.retryBatteryPersistence())}>Retry battery saving</button>}</div>}
   </div>
   <div className={`screen ${filter}`}><canvas ref={canvas} width="256" height="240" tabIndex={0} aria-label="Local game screen"/>{!state.loaded && <p>YOUR NEXT ADVENTURE<br/><span>starts with a file</span></p>}</div>
  </section>
  <LocalData open={localData} close={()=>{setLocalData(false);if(returnSettings)setSettings(true);}} player={runtime.current} preferencesIdentity={preferencesIdentity} beforeClear={()=>{runtime.current?.stopPersistence();preferences.stop();}} afterClear={()=>{preferences.dismiss();setPersistenceMessage('Local data deleted. Current progress remains in memory.');}}/>
  <Rewind open={rewind && state.loaded && !state.loading} close={()=>setRewind(false)} player={runtime.current}/>
  <Saves open={saves && state.loaded && !state.loading} close={()=>setSaves(false)} player={runtime.current} game={`${state.fingerprint?.romSha256}:${state.fingerprint?.coreSha256}`}/>
  <Settings voice={<VoiceControls state={voice} voice={rooms.current?.voice()}/>} localData={()=>openLocalData(true)} connection={<><ConnectionPolicyControl policy={policy} change={changePolicy}/><p>{connection}</p></>} open={settings} close={()=>setSettings(false)} controls={controls} change={changeControls} filter={filter} setFilter={value=>{setFilter(value);preferences.remember({controls,filter:value,volume});}} volume={volume} setVolume={value=>{setVolume(value);runtime.current?.setVolume(value);preferences.remember({controls,filter,volume:value});}} muted={muted} audioIssue={state.audioIssue} audioState={state.audioState} retryAudio={()=>runtime.current?.retryAudio()}/>
  <dialog ref={helpDialog} className="settings game-help" aria-labelledby="game-help-title" onClose={()=>setHelp(false)}><button autoFocus className="settings-close" onClick={()=>helpDialog.current?.close()}>Close</button><h2 id="game-help-title">Game help{known?` · ${catalogEntry(known).title}`:''}</h2><p>{known?catalogEntry(known).instructions:'Focus the screen to play. Default arrows move, X is A, Z is B, Enter is Start, and Shift is Select.'}</p><p>{known?catalogEntry(known).credits:'This local file was supplied by the player; consult its creator for game-specific instructions and credits.'}</p>{known&&<p>{catalogEntry(known).license}</p>}</dialog>
  <footer>Your game runs in this browser. Hosting a custom room uploads its game file to the room server while the room is open. Room details, connection signaling and temporary chat also go to the service. Optional voice goes to the other player through the peer connection.</footer>
 </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
