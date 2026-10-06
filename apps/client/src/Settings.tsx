import React,{useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {actions,labels,defaults,conflict,padInputs,availableGamepads,modifiedKey,bindingLabel,bindingSummary,type Action,type Controls} from './controls.ts';
import type {VoiceSession,VoiceState} from './voice.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import {GameShortcuts} from './GameShortcuts.tsx';

type Props={
 voiceState?:VoiceState;voiceSession?:VoiceSession;localData?:()=>void;room?:RoomView;
 idle:boolean;gameLoaded?:boolean;onSave?:()=>void;onLoad?:()=>void;timelineBusy?:boolean;
 open:boolean;inline?:boolean;controls:Controls;change(value:Controls):void;
 save(value:Controls,current:()=>boolean):Promise<boolean>;editing:boolean;onEditing:(editing:boolean)=>void;contextKey:string;storageIssue?:string;
 filter:'nearest'|'scanlines';setFilter(value:'nearest'|'scanlines'):void;
 volume:number;setVolume(value:number):void;muted:boolean;toggleMute():void;audioIssue?:string;audioState?:AudioContextState;retryAudio():void;
};
const deviceValue=(device:{index:number;id:string}|null)=>device?`${device.index}:${device.id}`:'keyboard';

export function Settings(props:Props){
 const [section,setSection]=useState<'controls'|'audio'>('controls');
 const [pads,setPads]=useState<{index:number;id:string}[]>([]),[capture,setCapture]=useState<{action:Action;source:'keyboard'|'gamepad'}>(),[binding,setBinding]=useState<string>(),[saving,setSaving]=useState(false),[error,setError]=useState('');
 const [resetSource,setResetSource]=useState<'keyboard'|'gamepad'>();
 const [audioPage,setAudioPage]=useState<'game'|'voice'>('game');
 const captureBox=useRef<HTMLDivElement>(null),resetCancel=useRef<HTMLButtonElement>(null),returnFocus=useRef<HTMLElement|null>(null),generation=useRef(0),previousPad=useRef(new Set<string>());
 const dismiss=()=>{++generation.current;setCapture(undefined);setResetSource(undefined);setBinding(undefined);setSaving(false);setError('');};
 useEffect(()=>{dismiss();},[props.contextKey,props.controls.device?.index,props.controls.device?.id,props.open]);
 useEffect(()=>()=>{++generation.current;},[]);
 useEffect(()=>{
  props.onEditing(!!capture||!!resetSource);
  if(capture)captureBox.current?.focus();else if(resetSource)resetCancel.current?.focus();
  return()=>props.onEditing(false);
 },[!!capture,!!resetSource]);
 useEffect(()=>{
  // Focus returns only after the parent has released its inert backdrop.
  if(capture||resetSource||props.editing)return;
  const target=returnFocus.current;returnFocus.current=null;if(target?.isConnected)target.focus();
 },[!!capture,!!resetSource,props.editing]);
 useEffect(()=>{
  if(!props.open)return;
  let animation=0;
  const tick=()=>{const available=availableGamepads(),listed=available.map(({index,id})=>({index,id}));setPads(old=>JSON.stringify(old)===JSON.stringify(listed)?old:listed);
   const pad=available.find(value=>value.index===props.controls.device?.index&&value.id===props.controls.device?.id),pressed=padInputs(pad);
   if(capture?.source==='gamepad'&&!saving){const next=[...pressed].find(input=>!previousPad.current.has(input));if(next)setBinding(next);}
   previousPad.current=pressed;animation=requestAnimationFrame(tick);};
  animation=requestAnimationFrame(tick);return()=>cancelAnimationFrame(animation);
 },[props.open,props.controls.device?.index,props.controls.device?.id,capture,saving]);
 if(!props.open)return null;
 const duplicate=capture&&binding?conflict(props.controls[capture.source],capture.action,binding):undefined;
 const openCapture=(action:Action,event:React.MouseEvent<HTMLButtonElement>)=>{++generation.current;returnFocus.current=event.currentTarget;setError('');setBinding(undefined);setCapture({action,source:'keyboard'});};
 const persist=async(value:Controls)=>{if(saving)return;const serial=generation.current,current=()=>serial===generation.current;setSaving(true);const ok=await props.save(value,current);if(!current())return;setSaving(false);if(ok)dismiss();else setError('Could not save controls. Try again.');};
 const save=()=>{if(capture&&binding&&!duplicate)void persist({...props.controls,[capture.source]:{...props.controls[capture.source],[capture.action]:[binding]}});};
 const dialog=capture||resetSource?createPortal(<div className="rc-dialog-layer" onKeyDown={event=>{if(event.code==='Escape'){event.preventDefault();event.stopPropagation();dismiss();}else if(event.code==='Tab'){const items=[...event.currentTarget.querySelectorAll<HTMLElement>('[tabindex]:not([tabindex="-1"]),button:not(:disabled),select:not(:disabled)')],index=items.indexOf(document.activeElement as HTMLElement),next=items[(index+(event.shiftKey?-1:1)+items.length)%items.length];event.preventDefault();next?.focus();}}}>{resetSource?<div className="rc-dialog-card rc-binding-dialog" role="alertdialog" aria-modal="true" aria-labelledby="rc-reset-title"><h2 id="rc-reset-title">Restore {resetSource} mappings?</h2><p>This replaces all {resetSource} bindings, including push to talk. The other input device stays unchanged.</p>{(error||props.storageIssue)&&<p role="status">{error||props.storageIssue}</p>}<div className="rc-dialog-actions"><button ref={resetCancel} onClick={dismiss}>Cancel</button><button disabled={saving} onClick={()=>void persist({...props.controls,[resetSource]:defaults()[resetSource]})}>{saving?'Restoring…':'Restore'}</button></div></div>:capture&&<div className="rc-dialog-card rc-binding-dialog" role="dialog" aria-modal="true" aria-labelledby="rc-binding-title"><h2 id="rc-binding-title">Map {labels[capture.action]}</h2>{props.controls.device&&actions.indexOf(capture.action)<9&&<select aria-label="Binding device" disabled={saving} value={capture.source} onChange={event=>{if(saving)return;++generation.current;setBinding(undefined);setError('');setCapture({...capture,source:event.target.value as 'keyboard'|'gamepad'});requestAnimationFrame(()=>captureBox.current?.focus());}}><option value="keyboard">Keyboard</option><option value="gamepad">Gamepad</option></select>}<p>Current: {props.controls[capture.source][capture.action].map(bindingLabel).join(' / ')||'Unbound'}</p><div ref={captureBox} tabIndex={saving?-1:0} aria-disabled={saving} className="rc-capture" aria-label="Capture input" onKeyDown={event=>{if(event.code==='Tab'||event.code==='Escape')return;event.preventDefault();event.stopPropagation();if(!saving&&capture.source==='keyboard'&&!modifiedKey(event))setBinding(event.code);}}>{capture.source==='keyboard'?'Press the replacement key.':'Release, then press a gamepad button or move an axis.'}</div><p role="status">{duplicate?`${bindingLabel(binding!)} is used for ${labels[duplicate]}. Choose another.`:error||props.storageIssue|| (binding?`New input: ${bindingLabel(binding)}`:'Waiting for input…')}</p><div className="rc-dialog-actions"><button onClick={dismiss}>Cancel</button><button disabled={saving||!binding||!!duplicate} onClick={()=>void save()}>{saving?'Saving…':'Save'}</button></div></div>}</div>,document.body):null;
 return <section className={props.inline?'rc-inline-settings':'rc-tool-page rc-settings'} aria-label="Game settings">
  <div className="rc-tool-heading"><h2>Settings</h2><nav aria-label="Settings sections">{(['controls','audio'] as const).map(item=><button key={item} aria-current={section===item?'page':undefined} onClick={()=>setSection(item)}>{item==='controls'?'Controls':'Audio'}</button>)}</nav><select className="rc-settings-select" aria-label="Settings section" value={section} onChange={event=>setSection(event.target.value as typeof section)}><option value="controls">Controls</option><option value="audio">Audio</option></select></div>
  <div className="rc-tool-body">
   {section==='controls'?<div className="rc-controls-settings"><div className="rc-controls-options"><select aria-label="Input device" title={props.controls.device?.id??'Keyboard'} value={deviceValue(props.controls.device)} onChange={event=>props.change({...props.controls,device:pads.find(pad=>deviceValue(pad)===event.target.value)??null})}><option value="keyboard">Keyboard</option>{props.controls.device&&!pads.some(pad=>deviceValue(pad)===deviceValue(props.controls.device))&&<option value={deviceValue(props.controls.device)} disabled>Gamepad {props.controls.device.index+1} (not connected)</option>}{pads.map(pad=><option key={deviceValue(pad)} value={deviceValue(pad)}>Gamepad {pad.index+1}</option>)}</select><select aria-label="Display filter" value={props.filter} onChange={event=>props.setFilter(event.target.value as Props['filter'])}><option value="nearest">Nearest neighbor</option><option value="scanlines">Scanlines</option></select>{props.localData&&<button onClick={props.localData}>Local data</button>}<button aria-label="Restore defaults" title="Restore mappings for the selected input device" onClick={event=>{++generation.current;returnFocus.current=event.currentTarget;setError('');setResetSource(props.controls.device?'gamepad':'keyboard');}}>Reset</button></div><div className="rc-binding-inventory" aria-label="Current bindings">{actions.map(action=>{const text=bindingSummary(props.controls.keyboard[action])||'Unbound';return <button key={action} type="button" aria-label={`Map ${labels[action]}: ${text}`} title={`${labels[action]}: ${text}`} onClick={event=>openCapture(action,event)}><span>{labels[action]}</span><strong>{text}</strong></button>;})}</div><GameShortcuts idle={props.idle} controls={props.controls} onSave={props.onSave} onLoad={props.onLoad} busy={props.timelineBusy||!props.gameLoaded} host={!props.room||props.room.role==='host'}/></div>:<div className="rc-audio-settings"><select aria-label="Audio setting" value={audioPage} onChange={event=>setAudioPage(event.target.value as typeof audioPage)}><option value="game">Game sound</option><option value="voice">Voice</option></select>{audioPage==='game'?<div className="rc-tool-stack"><label>Game volume {Math.round(props.volume*100)}%<input type="range" min="0" max="100" value={Math.round(props.volume*100)} onChange={event=>props.setVolume(Number(event.target.value)/100)}/></label><button className="rc-mute-action" aria-label={props.muted?'Unmute game':'Mute game'} onClick={props.toggleMute}>{props.muted?'Unmute game':'Mute game'}{props.idle&&<small className="rc-input-hint">{props.controls.keyboard.mute.map(bindingLabel).join(' / ')||'Unbound'}</small>}</button>{props.audioIssue&&<p role="status">{props.audioIssue} <button onClick={props.retryAudio}>Retry game audio</button></p>}</div>:<VoiceSettings voice={props.voiceSession} state={props.voiceState}/>}</div>}
  </div>{dialog}
 </section>;
}

function VoiceSettings({voice,state}:{voice?:VoiceSession;state?:VoiceState}){
 const [mobilePage,setMobilePage]=useState<'mic'|'sound'|'devices'>('mic');
 const mic=state?.microphone;
 if(!voice||!state||!mic)return <div className="rc-tool-stack"><p>Voice is off.</p></div>;
 return <div className="rc-tool-stack rc-voice-settings rc-voice-compact">
  <select className="rc-voice-mobile-select" aria-label="Voice setting" value={mobilePage} onChange={event=>setMobilePage(event.target.value as typeof mobilePage)}><option value="mic">Microphone</option><option value="sound">Other players</option><option value="devices">Devices</option></select>
  {mobilePage==='mic'&&<><div className="rc-tool-actions">{mic.phase==='requesting'?<button onClick={()=>voice.microphone.disable()}>Cancel request</button>:mic.phase==='off'||mic.phase==='error'?<button disabled={!state.connected||!!state.connectionError} onClick={()=>void voice.enable()}>{mic.phase==='error'?'Try microphone again':'Enable voice'}</button>:<><button onClick={()=>voice.microphone.mute(!mic.muted)}>{mic.muted?'Unmute mic':'Mute mic'}</button><button onClick={()=>voice.microphone.disable()}>Disable voice</button></>}</div>{mic.phase!=='off'&&mic.phase!=='requesting'&&<select aria-label="Voice mode" value={mic.mode} onChange={event=>voice.microphone.mode(event.target.value as 'open'|'push')}><option value="open">Open microphone</option><option value="push">Push to talk</option></select>}</>}
  {mobilePage==='sound'&&<><label>Other players' volume {Math.round(state.volume*100)}%<input type="range" min="0" max="100" value={Math.round(state.volume*100)} onChange={event=>voice.volume(Number(event.target.value)/100)}/></label><button onClick={()=>voice.remoteMute(!state.remoteMuted)}>{state.remoteMuted?'Unmute others':'Mute others'}</button></>}
  {mobilePage==='devices'&&<><select aria-label="Microphone" value={mic.device} onChange={event=>void voice.device(event.target.value)}><option value="default">Default microphone</option>{mic.device!=='default'&&!state.devices.some(device=>device.id===mic.device)&&<option value={mic.device} disabled>Selected microphone unavailable</option>}{state.devices.map(device=><option key={device.id} value={device.id}>{device.label}</option>)}</select><button onClick={()=>void voice.listDevices()}>Refresh devices</button></>}
  <VoiceRecovery voice={voice} state={state} microphoneActionShown={mobilePage==='mic'&&mic.phase==='error'} deviceActionShown={mobilePage==='devices'}/>
 </div>;
}

function VoiceRecovery({voice,state,microphoneActionShown,deviceActionShown}:{voice:VoiceSession;state:VoiceState;microphoneActionShown:boolean;deviceActionShown:boolean}){
 const mic=state.microphone;
 // Select feedback and its action together: concurrent failures must not mix owners.
 const recovery=state.connectionError?{message:state.connectionError,label:'Retry voice connection',retry:()=>voice.retryBinding()}:
  state.playbackError?{message:state.playbackError,label:'Enable voice sound',retry:()=>voice.retrySound()}:
  mic.error?{message:mic.error,label:mic.connectionFailure?'Retry microphone':mic.phase==='error'&&!microphoneActionShown?'Try microphone again':undefined,retry:()=>void (mic.connectionFailure?voice.microphone.retryConnection():voice.enable())}:
  state.deviceError?{message:state.deviceError,label:deviceActionShown?undefined:'Refresh devices',retry:()=>void voice.listDevices()}:undefined;
 if(!recovery)return null;
 return <div className="rc-voice-recovery"><p role="status">{recovery.message}</p>{recovery.label&&<button onClick={recovery.retry}>{recovery.label}</button>}</div>;
}
