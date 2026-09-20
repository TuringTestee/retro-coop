import {useId} from 'react';
import type {VoiceSession,VoiceState} from './voice.ts';
export function VoiceControls({state,voice}:{state?:VoiceState;voice?:VoiceSession}){
 const id=useId();if(!state||!voice)return <p>Voice is off.</p>;
 const mic=state.microphone;
 return <section className="voice-panel" aria-label="Voice controls">
  <h3>Voice</h3><p role="status" data-testid="microphone-status">{mic.phase==='requesting'?'Microphone permission pending…':mic.phase==='error'?'Microphone unavailable':mic.phase==='off'?'Microphone off':mic.muted?'Microphone muted':mic.transmitting?'Transmitting microphone audio':'Listening · hold to talk'}</p>
  {!state.connected && <p>Connect to the other player to enable voice. Text chat works before voice is ready.</p>}
  {(mic.phase==='off'||mic.phase==='error') && <button disabled={!state.connected||!!state.connectionError} onClick={()=>void voice.enable()}>{mic.phase==='error'?'Try microphone again':'Enable voice'}</button>}
  {mic.phase==='requesting' && <button onClick={()=>voice.microphone.disable()}>Cancel microphone request</button>}
  {mic.phase==='ready' && <><button onClick={()=>voice.microphone.mute(!mic.muted)}>{mic.muted?'Unmute microphone':'Mute microphone'}</button><button onClick={()=>voice.microphone.disable()}>Disable microphone</button></>}
  {mic.error && <p>{mic.error} {mic.error.includes('denied') && 'Review microphone permission in your browser’s site settings, then try again.'}</p>}
  {state.connectionError && <p>{state.connectionError}</p>}
  <label htmlFor={`${id}-mode`}>Voice mode</label><select id={`${id}-mode`} value={mic.mode} onChange={event=>voice.microphone.mode(event.target.value as 'open'|'push')}><option value="open">Open microphone</option><option value="push">Push to talk</option></select>
  {mic.mode==='push' && <><p>Hold the button or your mapped Push to talk input. Remap it in Controls. Typing in a text field does not press it.</p><button disabled={mic.phase!=='ready'||mic.muted} onPointerDown={event=>{event.currentTarget.setPointerCapture(event.pointerId);voice.hold(true);}} onPointerUp={()=>voice.hold(false)} onPointerCancel={()=>voice.hold(false)} onLostPointerCapture={()=>voice.hold(false)} onKeyDown={event=>{if(event.code==='Space'||event.code==='Enter'){event.preventDefault();voice.hold(true);}}} onKeyUp={event=>{if(event.code==='Space'||event.code==='Enter'){event.preventDefault();voice.hold(false);}}} onBlur={()=>voice.hold(false)}>Hold to talk</button></>}
  <label htmlFor={`${id}-device`}>Microphone device</label><select id={`${id}-device`} disabled={mic.phase==='requesting'} value={mic.device} onChange={event=>void voice.device(event.target.value)}><option value="default">Default microphone</option>{state.devices.map(device=><option key={device.id} value={device.id}>{device.label}</option>)}</select><button onClick={()=>void voice.listDevices()}>Refresh microphones</button>
  {state.deviceError && <p>{state.deviceError}</p>}
  <button aria-pressed={state.remoteMuted} onClick={()=>voice.remoteMute(!state.remoteMuted)}>{state.remoteMuted?'Unmute remote voice':'Mute remote voice'}</button>
  <label htmlFor={`${id}-volume`}>Remote voice volume {Math.round(state.volume*100)}%</label><input id={`${id}-volume`} type="range" min="0" max="100" value={Math.round(state.volume*100)} onChange={event=>voice.volume(Number(event.target.value)/100)}/>
  {state.playbackError && <p>{state.playbackError}<button onClick={()=>voice.retrySound()}>Enable voice sound</button></p>}
  <p className="hint">Switching windows mutes your microphone. Unmute deliberately when you return. Device replacement also stays muted. Browser echo cancellation and noise suppression are best effort; headphones can help. No recording or transcription.</p>
 </section>;
}
