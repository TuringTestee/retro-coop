import { useEffect, useRef, useState } from 'react';
import { actions, labels, defaults, conflict, inputMask, padInputs, bindingLabel, type Action, type Controls } from './controls.ts';

type Props = {
 open:boolean; close():void; controls:Controls; change(value:Controls):void;
 filter:'nearest'|'scanlines'; setFilter(value:'nearest'|'scanlines'):void;
 volume:number; setVolume(value:number):void; muted:boolean; audioIssue?:string; audioState?:AudioContextState; retryAudio():void;
};
export function Settings(props:Props) {
 const dialog = useRef<HTMLDialogElement>(null), captureBox = useRef<HTMLDivElement>(null);
 const [source,setSource] = useState<'keyboard'|'gamepad'>('keyboard');
 const [pads,setPads] = useState<{index:number;id:string}[]>([]);
 const [capture,setCapture] = useState<Action|null>(null), [binding,setBinding] = useState<string|null>(null);
 const [confirm,setConfirm] = useState(false), [tested,setTested] = useState(0);
 const returnFocus=useRef<HTMLElement|null>(null);
 useEffect(()=>{if(!capture && !confirm){returnFocus.current?.focus();returnFocus.current=null;}},[capture,confirm]);
 const held = useRef(new Set<string>()), previousPad = useRef(new Set<string>());
 const endCapture = () => {setCapture(null);setBinding(null);};
 useEffect(()=>{
  if(props.open) dialog.current?.showModal(); else dialog.current?.close();
  if(!props.open) {endCapture();setConfirm(false);held.current.clear();setTested(0);}
 },[props.open]);
 useEffect(()=>{if(capture) captureBox.current?.focus();},[capture]);
 useEffect(()=>{
  if(!props.open) return;
  let animation=0;
  const tick=()=>{
   const available=[...navigator.getGamepads()].filter((pad):pad is Gamepad=>!!pad && pad.connected);
   setPads(old=>JSON.stringify(old)===JSON.stringify(available.map(({index,id})=>({index,id}))) ? old : available.map(({index,id})=>({index,id})));
   const pad=available.find(pad=>pad.index===props.controls.device?.index && pad.id===props.controls.device?.id);
   const pressed=padInputs(pad);
   if(capture && source==='gamepad') {
    const next=[...pressed].find(input=>!previousPad.current.has(input));
    if(next) setBinding(next);
   }
   previousPad.current=pressed;
   const mask=inputMask(props.controls[source],source==='keyboard' ? held.current : pressed);
   setTested(old=>old===mask ? old : mask);
   animation=requestAnimationFrame(tick);
  };
  animation=requestAnimationFrame(tick);
  const release=()=>{held.current.clear();};
  const keyup=(event:KeyboardEvent)=>held.current.delete(event.code);
  window.addEventListener('keyup',keyup);window.addEventListener('blur',release);
  return ()=>{cancelAnimationFrame(animation);window.removeEventListener('keyup',keyup);window.removeEventListener('blur',release);};
 },[props.open,props.controls,source,capture]);
 const duplicate=capture && binding ? conflict(props.controls[source],capture,binding) : undefined;
 return <dialog ref={dialog} className="settings" aria-labelledby="settings-title" onClose={props.close} onCancel={event=>{if(capture || confirm){event.preventDefault();endCapture();setConfirm(false);}}}>
  <button className="settings-close" aria-label="Close settings" onClick={()=>dialog.current?.close()}>Close</button>
  <h2 id="settings-title">Local settings</h2><p>Controls, picture and sound affect only this browser. Your game keeps its progress.</p>
  <label>Input device <select aria-label="Input device" value={props.controls.device ? String(props.controls.device.index) : 'keyboard'} onChange={event=>{
   const device=pads.find(pad=>String(pad.index)===event.target.value) ?? null;
   props.change({...props.controls,device});setSource(device ? 'gamepad' : 'keyboard');endCapture();
  }}><option value="keyboard">Keyboard</option>{pads.map(pad=><option key={`${pad.index}:${pad.id}`} value={pad.index}>{pad.id} (controller {pad.index+1})</option>)}</select></label>
  <p className="hint">Press a controller button if it is not listed. Disconnecting the selected controller pauses play; reconnect and Resume, or choose Keyboard.</p>
  <label>Edit mappings <select aria-label="Edit mappings" value={source} onChange={event=>{setSource(event.target.value as typeof source);endCapture();}}><option value="keyboard">Keyboard</option><option value="gamepad">Gamepad</option></select></label>
  <div className="mapping-list">{actions.map(action=><div className="mapping" key={action}><span>{labels[action]}</span><span>{props.controls[source][action].map(bindingLabel).join(' / ')}</span><button disabled={!!capture} onClick={event=>{returnFocus.current=event.currentTarget;setConfirm(false);setCapture(action);setBinding(null);}}>Change {labels[action]}</button></div>)}</div>
  <p className="hint">Push-to-talk reserves a binding for future voice controls. No microphone is activated here.</p>
  {capture && <section className="capture" aria-labelledby="capture-title"><h3 id="capture-title">Map {labels[capture]}</h3>
   <div ref={captureBox} tabIndex={0} className="input-test" aria-label="Capture input" onKeyDown={event=>{
    if(event.code==='Escape'){event.preventDefault();event.stopPropagation();endCapture();return;}
    if(source==='keyboard' && event.code!=='Tab') {event.preventDefault();event.stopPropagation();if(!event.metaKey && !event.ctrlKey && !event.altKey) setBinding(event.code);}
   }}> {source==='keyboard' ? 'Press a single key here, without Ctrl/Alt/Meta shortcuts. Tab and Escape stay reserved for navigation.' : 'Release, then press a button or move an axis on the selected gamepad.'}</div>
   <p role="status">{duplicate ? `${bindingLabel(binding!)} is already used for ${labels[duplicate]}. Choose another input.` : binding ? `New input: ${bindingLabel(binding)}` : 'Waiting for input…'}</p>
   <button disabled={!binding || !!duplicate} onClick={()=>{props.change({...props.controls,[source]:{...props.controls[source],[capture]:[binding!]}});endCapture();}}>Apply mapping</button><button onClick={endCapture}>Cancel mapping</button>
  </section>}
  <button onClick={event=>{returnFocus.current=event.currentTarget;endCapture();setConfirm(true);}}>Restore {source} defaults</button>
  {confirm && <section aria-label="Confirm mapping reset"><p>Replace all {source} mappings, including the reserved push-to-talk binding? Other local settings stay the same.</p><button onClick={()=>{props.change({...props.controls,[source]:defaults()[source]});setConfirm(false);}}>Confirm restore</button><button onClick={()=>setConfirm(false)}>Keep mappings</button></section>}
  <div className="input-test" tabIndex={0} aria-label="Test mapped input" onKeyDown={event=>{if(event.code!=='Tab' && event.code!=='Escape'){event.preventDefault();held.current.add(event.code);}}} onBlur={()=>held.current.clear()}>
   Focus here to test {source} input: <span data-testid="input-test">{actions.slice(0,8).filter((_,index)=>tested & (1<<index)).map(action=>labels[action]).join(', ') || 'None'}</span>
  </div>
  <fieldset><legend>Picture and sound</legend><label>Display filter <select value={props.filter} onChange={event=>props.setFilter(event.target.value as Props['filter'])}><option value="nearest">Nearest neighbor</option><option value="scanlines">Scanlines</option></select></label>
   <label>Game volume {Math.round(props.volume*100)}% <input type="range" min="0" max="100" value={Math.round(props.volume*100)} onChange={event=>props.setVolume(Number(event.target.value)/100)}/></label>
   <p>Audio: {props.audioState ?? 'not started'}. {props.muted ? 'Game output is muted. Unmute from the player when ready.' : 'Game output is enabled.'}</p>
   {props.audioIssue && <p>{props.audioIssue} <button onClick={props.retryAudio}>Retry game audio</button></p>}
  </fieldset>
  <button onClick={()=>dialog.current?.close()}>Done</button>
 </dialog>;
}
