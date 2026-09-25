import {useId} from 'react';
import type {VoiceSession,VoiceState} from './voice.ts';
export function VoiceControls({state,voice,compact=false,onSettings,talkBinding}:{state?:VoiceState;voice?:VoiceSession;compact?:boolean;onSettings?:()=>void;talkBinding?:string}){
 const id=useId();if(!state||!voice)return compact?<section className="voice-card" aria-label="Voice controls"><h2>Voice <span role="status">· Connecting</span></h2><button disabled>Enable voice</button><button className="text-action voice-settings" onClick={onSettings}>Voice settings</button></section>:<p>Voice is off.</p>;
 const mic=state.microphone;
 const talk=<button disabled={mic.phase!=='ready'||mic.muted} onPointerDown={event=>{event.currentTarget.setPointerCapture(event.pointerId);voice.hold(true);}} onPointerUp={()=>voice.hold(false)} onPointerCancel={()=>voice.hold(false)} onLostPointerCapture={()=>voice.hold(false)} onKeyDown={event=>{if(event.code==='Space'||event.code==='Enter'){event.preventDefault();voice.hold(true);}}} onKeyUp={event=>{if(event.code==='Space'||event.code==='Enter'){event.preventDefault();voice.hold(false);}}} onBlur={()=>voice.hold(false)}>Hold to talk</button>;
 if(compact) {
  const status=state.connectionError?'Connection unavailable':mic.phase==='requesting'?'Requesting microphone…':mic.phase==='error'?'Mic unavailable':!state.connected?'Connecting':mic.phase==='off'?'Off':mic.muted?'Muted':mic.mode==='push'?(mic.transmitting?'Talking':'Hold to talk'):'Mic on';
  return <section className="voice-card" aria-label="Voice controls">
   <h2>Voice <span role="status" data-testid="microphone-status">· {status}</span></h2>
   {mic.error&&<p>{mic.error} {mic.error.includes('denied')&&'Review microphone permission in your browser’s site settings, then try again.'}</p>}
   {state.connectionError&&<p>{state.connectionError} <button className="text-action" onClick={()=>voice.retryBinding()}>Retry voice connection</button></p>}
   {state.playbackError&&<p>{state.playbackError} <button className="text-action" onClick={()=>voice.retrySound()}>Enable voice sound</button></p>}
   {mic.phase==='requesting'?<button onClick={()=>voice.microphone.disable()}>Cancel microphone request</button>:mic.phase==='off'||mic.phase==='error'?<button disabled={!state.connected||!!state.connectionError} onClick={()=>void voice.enable()}>{mic.phase==='error'?'Try microphone again':'Enable voice'}</button>:mic.mode==='push'&&!mic.muted?talk:<button onClick={()=>voice.microphone.mute(!mic.muted)}>{mic.muted?'Unmute microphone':'Mute microphone'}</button>}
   {mic.mode==='push'&&<p className="talk-binding">Push to talk · {talkBinding}</p>}
   <button className="text-action voice-settings" onClick={onSettings}>Voice settings</button>
  </section>;
 }

 return <section className="voice-panel" aria-label="Voice controls">
  <h3 tabIndex={-1}>Voice</h3><p role="status" data-testid="microphone-status">{mic.phase==='requesting'?'Microphone permission pending…':mic.phase==='error'?'Microphone unavailable':mic.phase==='off'?'Microphone off':mic.muted?'Microphone muted':mic.transmitting?'Transmitting microphone audio':'Listening · hold to talk'}</p>
  {!state.connected && <p>Connect to the other player to enable voice. Text chat works before voice is ready.</p>}
  {(mic.phase==='off'||mic.phase==='error') && <button disabled={!state.connected||!!state.connectionError} onClick={()=>void voice.enable()}>{mic.phase==='error'?'Try microphone again':'Enable voice'}</button>}
  {mic.phase==='requesting' && <button onClick={()=>voice.microphone.disable()}>Cancel microphone request</button>}
  {mic.phase==='ready' && <><button onClick={()=>voice.microphone.mute(!mic.muted)}>{mic.muted?'Unmute microphone':'Mute microphone'}</button><button onClick={()=>voice.microphone.disable()}>Disable microphone</button></>}
  {mic.error && <p>{mic.error} {mic.error.includes('denied') && 'Review microphone permission in your browser’s site settings, then try again.'}</p>}
  {state.connectionError && <p>{state.connectionError} <button onClick={()=>voice.retryBinding()}>Retry voice connection</button></p>}
  <label htmlFor={`${id}-mode`}>Voice mode</label><select id={`${id}-mode`} value={mic.mode} onChange={event=>voice.microphone.mode(event.target.value as 'open'|'push')}><option value="open">Open microphone</option><option value="push">Push to talk</option></select>
  {mic.mode==='push' && <><p>Hold the button or your mapped Push to talk input. Remap it in Controls. Typing in a text field does not press it.</p>{talk}</>}
  <label htmlFor={`${id}-device`}>Microphone device</label><select id={`${id}-device`} disabled={mic.phase==='requesting'} value={mic.device} onChange={event=>void voice.device(event.target.value)}><option value="default">Default microphone</option>{mic.device!=='default' && !state.devices.some(device=>device.id===mic.device) && <option value={mic.device} disabled>Selected microphone (unavailable)</option>}{state.devices.map(device=><option key={device.id} value={device.id}>{device.label}</option>)}</select><button onClick={()=>void voice.listDevices()}>Refresh microphones</button>
  {state.deviceError && <p>{state.deviceError}</p>}
  <button aria-pressed={state.remoteMuted} onClick={()=>voice.remoteMute(!state.remoteMuted)}>{state.remoteMuted?'Unmute remote voice':'Mute remote voice'}</button>
  <label htmlFor={`${id}-volume`}>Remote voice volume {Math.round(state.volume*100)}%</label><input id={`${id}-volume`} type="range" min="0" max="100" value={Math.round(state.volume*100)} onChange={event=>voice.volume(Number(event.target.value)/100)}/>
  {state.playbackError && <p>{state.playbackError}<button onClick={()=>voice.retrySound()}>Enable voice sound</button></p>}
  <p className="hint">Switching windows mutes your microphone. Unmute deliberately when you return. Device replacement also stays muted. Browser echo cancellation and noise suppression are best effort; headphones can help. No recording or transcription.</p>
 </section>;
}
