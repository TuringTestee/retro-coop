import {useEffect,useRef,useState} from 'react';
import {actions,labels,defaults,conflict,inputMask,padInputs,bindingLabel,type Action,type Controls} from './controls.ts';
import type {VoiceSession,VoiceState} from './voice.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {RoomClient} from './room-client.ts';
import {LobbyOptions} from './LobbyOptions.tsx';
import {PlayingTools} from './PlayingTools.tsx';

type Props={
 connection?:string;voiceState?:VoiceState;voiceSession?:VoiceSession;localData?:()=>void;
 room?:RoomView;onAct?:RoomClient['act'];
 localGame?:boolean;
 pauseActionLabel?:string;
 initialSection?:'game'|'lobby'|'controls'|'voice';
 open:boolean;inline?:boolean;controls:Controls;change(value:Controls):void;
 filter:'nearest'|'scanlines';setFilter(value:'nearest'|'scanlines'):void;
 volume:number;setVolume(value:number):void;muted:boolean;toggleMute():void;audioIssue?:string;audioState?:AudioContextState;retryAudio():void;
};
type Section='game'|'lobby'|'controls'|'picture'|'voice'|'profile';
export function Settings(props:Props){
 const [section,setSection]=useState<Section>(props.initialSection??'controls'),[page,setPage]=useState(0),[source,setSource]=useState<'keyboard'|'gamepad'>('keyboard');
 const [compact,setCompact]=useState(()=>matchMedia('(max-width: 650px)').matches);
 const [pads,setPads]=useState<{index:number;id:string}[]>([]),[capture,setCapture]=useState<Action|null>(null),[binding,setBinding]=useState<string|null>(null),[confirm,setConfirm]=useState(false),[tested,setTested]=useState(0);
 const captureBox=useRef<HTMLDivElement>(null),returnFocus=useRef<HTMLElement|null>(null),held=useRef(new Set<string>()),previousPad=useRef(new Set<string>());
 useEffect(()=>{const query=matchMedia('(max-width: 650px)'),changed=()=>{setCompact(query.matches);setPage(0);};query.addEventListener('change',changed);return()=>query.removeEventListener('change',changed);},[]);
 useEffect(()=>{if(!props.open){setCapture(null);setBinding(null);setConfirm(false);held.current.clear();setTested(0);}},[props.open]);
 useEffect(()=>{if(capture)captureBox.current?.focus();else if(!confirm){returnFocus.current?.focus();returnFocus.current=null;}},[capture,confirm]);
 useEffect(()=>{
  if(!props.open)return;
  let animation=0;
  const tick=()=>{const available=[...navigator.getGamepads()].filter((pad):pad is Gamepad=>!!pad&&pad.connected),listed=available.map(({index,id})=>({index,id}));setPads(old=>JSON.stringify(old)===JSON.stringify(listed)?old:listed);
   const pad=available.find(value=>value.index===props.controls.device?.index&&value.id===props.controls.device?.id),pressed=padInputs(pad);
   if(capture&&source==='gamepad'){const next=[...pressed].find(input=>!previousPad.current.has(input));if(next)setBinding(next);}
   previousPad.current=pressed;const mask=inputMask(props.controls[source],source==='keyboard'?held.current:pressed);setTested(old=>old===mask?old:mask);animation=requestAnimationFrame(tick);};
  animation=requestAnimationFrame(tick);const release=()=>held.current.clear(),keyup=(event:KeyboardEvent)=>held.current.delete(event.code);
  addEventListener('keyup',keyup);addEventListener('blur',release);
  return()=>{cancelAnimationFrame(animation);removeEventListener('keyup',keyup);removeEventListener('blur',release);};
 },[props.open,props.controls,source,capture]);
 if(!props.open)return null;
 const voice=props.voiceSession,state=props.voiceState,mic=state?.microphone;
 const duplicate=capture&&binding?conflict(props.controls[source],capture,binding):undefined;
 const mappingPageSize=compact?1:3,mappingPages=Math.ceil(actions.length/mappingPageSize);
 const switchSection=(next:Section)=>{setSection(next);setCapture(null);setBinding(null);setConfirm(false);};
 const sections:Section[]=[...(props.room?.started||props.localGame?['game' as const]:[]),...(props.room?.role==='host'?['lobby' as const]:[]),'controls','picture','voice','profile'];
 return <section className={props.inline?'rc-inline-settings':'rc-tool-page rc-settings'} aria-label="Game settings">
  <div className="rc-tool-heading"><h2>Settings</h2><nav aria-label="Settings sections">{sections.map(item=><button key={item} aria-current={section===item?'page':undefined} onClick={()=>switchSection(item)}>{item==='picture'?'Sound':item[0].toUpperCase()+item.slice(1)}</button>)}</nav><select className="rc-settings-select" aria-label="Settings section" value={section} onChange={event=>switchSection(event.target.value as Section)}>{sections.map(item=><option key={item} value={item}>{item==='picture'?'Sound':item[0].toUpperCase()+item.slice(1)}</option>)}</select></div>
  <div className="rc-tool-body">
   {section==='game'&&<PlayingTools controls={props.controls} local={!!props.localGame} pauseActionLabel={props.pauseActionLabel}/>}
   {section==='lobby'&&props.room&&props.onAct&&<LobbyOptions room={props.room} onAct={props.onAct}/>}
   {section==='controls'&&(capture?<div className="rc-tool-stack"><h3>Map {labels[capture]}</h3><div ref={captureBox} tabIndex={0} className="rc-capture" aria-label="Capture input" onKeyDown={event=>{if(event.code==='Escape'){event.preventDefault();event.stopPropagation();setCapture(null);setBinding(null);return;}if(source==='keyboard'&&event.code!=='Tab'){event.preventDefault();event.stopPropagation();if(!event.metaKey&&!event.ctrlKey&&(!event.altKey||event.code==='AltLeft'||event.code==='AltRight'))setBinding(event.code);}}}>{source==='keyboard'?'Press one key here. Tab and Escape remain for navigation.':'Release, then press a button or move an axis on your gamepad.'}</div><p role="status">{duplicate?`${bindingLabel(binding!)} is used for ${labels[duplicate]}. Choose another.`:binding?`New input: ${bindingLabel(binding)}`:'Waiting for input…'}</p><div className="rc-tool-actions"><button disabled={!binding||!!duplicate} onClick={()=>{props.change({...props.controls,[source]:{...props.controls[source],[capture]:[binding!]}});setCapture(null);setBinding(null);}}>Apply mapping</button><button onClick={()=>{setCapture(null);setBinding(null);}}>Cancel</button></div></div>:confirm?<div className="rc-tool-stack" role="alertdialog" aria-label="Confirm mapping reset"><h3>Restore {source} mappings?</h3><p>This replaces every mapping, including push to talk.</p><div className="rc-tool-actions"><button onClick={()=>{props.change({...props.controls,[source]:defaults()[source]});setConfirm(false);}}>Restore</button><button onClick={()=>setConfirm(false)}>Keep mappings</button></div></div>:<div className="rc-tool-stack"><div className="rc-tool-inline"><label>Input device<select aria-label="Input device" value={props.controls.device?String(props.controls.device.index):'keyboard'} onChange={event=>{const device=pads.find(pad=>String(pad.index)===event.target.value)??null;props.change({...props.controls,device});setSource(device?'gamepad':'keyboard');}}><option value="keyboard">Keyboard</option>{pads.map(pad=><option key={`${pad.index}:${pad.id}`} value={pad.index}>{pad.id}</option>)}</select></label><label>Edit mappings<select aria-label="Edit mappings" value={source} onChange={event=>{setSource(event.target.value as typeof source);setPage(0);}}><option value="keyboard">Keyboard</option><option value="gamepad">Gamepad</option></select></label></div><div className="rc-mapping-list">{actions.slice(page*mappingPageSize,page*mappingPageSize+mappingPageSize).map(action=><div className="rc-mapping" key={action}><strong>{labels[action]}</strong><span title={props.controls[source][action].map(bindingLabel).join(' / ')}>{props.controls[source][action].map(bindingLabel).join(' / ')||'Unbound'}</span><button onClick={event=>{returnFocus.current=event.currentTarget;setCapture(action);setBinding(null);}}>Change</button></div>)}</div><div className="rc-tool-actions rc-mapping-actions"><button aria-label="Previous" disabled={page===0} onClick={()=>setPage(page-1)}>{compact?'‹':'Previous'}</button><span>{page+1}/{mappingPages}</span><button aria-label="Next" disabled={page>=mappingPages-1} onClick={()=>setPage(page+1)}>{compact?'›':'Next'}</button><button aria-label="Restore defaults" onClick={event=>{returnFocus.current=event.currentTarget;setConfirm(true);}}>{compact?'Reset':'Restore defaults'}</button></div><div className="rc-input-test" tabIndex={0} aria-label="Test mapped input" onKeyDown={event=>{if(event.code!=='Tab'&&event.code!=='Escape'){event.preventDefault();held.current.add(event.code);}}} onBlur={()=>held.current.clear()}>Test input: {actions.slice(0,8).filter((_,index)=>tested&(1<<index)).map(action=>labels[action]).join(', ')||'None'}</div></div>)}
   {section==='picture'&&<div className="rc-tool-stack"><label>Display filter<select value={props.filter} onChange={event=>props.setFilter(event.target.value as Props['filter'])}><option value="nearest">Nearest neighbor</option><option value="scanlines">Scanlines</option></select></label><label>Game volume {Math.round(props.volume*100)}%<input type="range" min="0" max="100" value={Math.round(props.volume*100)} onChange={event=>props.setVolume(Number(event.target.value)/100)}/></label><button onClick={props.toggleMute}>{props.muted?'Unmute game':'Mute game'}</button>{props.audioIssue&&<p role="status">{props.audioIssue} <button onClick={props.retryAudio}>Retry game audio</button></p>}</div>}
   {section==='voice'&&<VoiceSettings voice={voice} state={state} compact={compact}/>}
   {section==='profile'&&<div className="rc-tool-stack">{props.localData&&<button onClick={props.localData}>Local data</button>}</div>}
  </div>
 </section>;
}

function VoiceSettings({voice,state,compact}:{voice?:VoiceSession;state?:VoiceState;compact:boolean}){
 const [page,setPage]=useState<'sound'|'devices'>('sound');
 const [mobilePage,setMobilePage]=useState<'mic'|'sound'|'devices'>('mic');
 const mic=state?.microphone;
 if(!voice||!state||!mic)return <div className="rc-tool-stack"><p>Voice is off.</p></div>;
 const issue=mic.error||state.connectionError||state.playbackError||state.deviceError;
 if(compact)return <div className="rc-tool-stack rc-voice-settings rc-voice-compact">
  <select className="rc-voice-mobile-select" aria-label="Voice setting" value={mobilePage} onChange={event=>setMobilePage(event.target.value as typeof mobilePage)}><option value="mic">Microphone</option><option value="sound">Other players</option><option value="devices">Devices</option></select>
  {mobilePage==='mic'&&<><div className="rc-tool-actions">{mic.phase==='requesting'?<button onClick={()=>voice.microphone.disable()}>Cancel request</button>:mic.phase==='off'||mic.phase==='error'?<button disabled={!state.connected||!!state.connectionError} onClick={()=>void voice.enable()}>{mic.phase==='error'?'Try microphone again':'Enable voice'}</button>:<><button onClick={()=>voice.microphone.mute(!mic.muted)}>{mic.muted?'Unmute mic':'Mute mic'}</button><button onClick={()=>voice.microphone.disable()}>Disable voice</button></>}</div>{mic.phase!=='off'&&mic.phase!=='requesting'&&<select aria-label="Voice mode" value={mic.mode} onChange={event=>voice.microphone.mode(event.target.value as 'open'|'push')}><option value="open">Open microphone</option><option value="push">Push to talk</option></select>}</>}
  {mobilePage==='sound'&&<><label>Other players' volume {Math.round(state.volume*100)}%<input type="range" min="0" max="100" value={Math.round(state.volume*100)} onChange={event=>voice.volume(Number(event.target.value)/100)}/></label><button onClick={()=>voice.remoteMute(!state.remoteMuted)}>{state.remoteMuted?'Unmute others':'Mute others'}</button></>}
  {mobilePage==='devices'&&<><select aria-label="Microphone" value={mic.device} onChange={event=>void voice.device(event.target.value)}><option value="default">Default microphone</option>{mic.device!=='default'&&!state.devices.some(device=>device.id===mic.device)&&<option value={mic.device} disabled>Selected microphone unavailable</option>}{state.devices.map(device=><option key={device.id} value={device.id}>{device.label}</option>)}</select><button onClick={()=>void voice.listDevices()}>Refresh devices</button></>}
  <VoiceRecovery voice={voice} state={state} issue={issue}/>
 </div>;
 return <div className="rc-tool-stack rc-voice-settings">
  <p role="status">{mic.phase==='ready'?(mic.muted?'Microphone muted':'Microphone on'):mic.phase==='requesting'?'Requesting microphone…':mic.phase==='error'?'Microphone unavailable':'Microphone off'}</p>
  <div className="rc-tool-actions">{mic.phase==='requesting'?<button onClick={()=>voice.microphone.disable()}>Cancel microphone request</button>:mic.phase==='off'||mic.phase==='error'?<button disabled={!state.connected||!!state.connectionError} onClick={()=>void voice.enable()}>{mic.phase==='error'?'Try microphone again':'Enable voice'}</button>:<><button onClick={()=>voice.microphone.mute(!mic.muted)}>{mic.muted?'Unmute microphone':'Mute microphone'}</button><button onClick={()=>voice.microphone.disable()}>Disable microphone</button></>}</div>
  <nav className="rc-voice-pages" aria-label="Voice options"><button aria-current={page==='sound'?'page':undefined} onClick={()=>setPage('sound')}>Sound</button><button aria-current={page==='devices'?'page':undefined} onClick={()=>setPage('devices')}>Devices</button></nav>
  {page==='sound'&&!issue&&<><label>Voice mode<select value={mic.mode} onChange={event=>voice.microphone.mode(event.target.value as 'open'|'push')}><option value="open">Open microphone</option><option value="push">Push to talk</option></select></label><label>Other players' volume {Math.round(state.volume*100)}%<input type="range" min="0" max="100" value={Math.round(state.volume*100)} onChange={event=>voice.volume(Number(event.target.value)/100)}/></label><button onClick={()=>voice.remoteMute(!state.remoteMuted)}>{state.remoteMuted?'Unmute others':'Mute others'}</button></>}
  {page==='devices'&&<><label>Microphone<select value={mic.device} onChange={event=>void voice.device(event.target.value)}><option value="default">Default microphone</option>{mic.device!=='default'&&!state.devices.some(device=>device.id===mic.device)&&<option value={mic.device} disabled>Selected microphone unavailable</option>}{state.devices.map(device=><option key={device.id} value={device.id}>{device.label}</option>)}</select></label><button onClick={()=>void voice.listDevices()}>Refresh devices</button></>}
  <VoiceRecovery voice={voice} state={state} issue={issue}/>
 </div>;
}

function VoiceRecovery({voice,state,issue}:{voice:VoiceSession;state:VoiceState;issue?:string}){
 const mic=state.microphone;
 if(!issue)return null;
 return <div className="rc-voice-recovery"><p role="status">{issue}</p>{state.connectionError?<button onClick={()=>voice.retryBinding()}>Retry voice connection</button>:state.playbackError?<button onClick={()=>voice.retrySound()}>Enable voice sound</button>:mic.connectionFailure?<button onClick={()=>void voice.microphone.retryConnection()}>Retry microphone</button>:state.deviceError?<button onClick={()=>void voice.listDevices()}>Refresh devices</button>:null}</div>;
}
