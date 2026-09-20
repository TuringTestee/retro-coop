import {useEffect,useRef,useState} from 'react';
import type {LocalPlayer} from './player.ts';
import type {RewindInfo} from '../../../packages/contracts/src/index.ts';

/** Solo confirmation only; the shared-game barrier owns multiplayer timeline changes. */
export function Rewind({open,close,player}:{open:boolean;close:()=>void;player:LocalPlayer|null}) {
 const dialog=useRef<HTMLDialogElement>(null),epoch=useRef(0),requestButton=useRef<HTMLButtonElement>(null);
 const [info,setInfo]=useState<RewindInfo|null>(null),[seconds,setSeconds]=useState(1),[confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 useEffect(()=>{
  const token=++epoch.current;if(!open){dialog.current?.close();return;}
  const focus=document.activeElement as HTMLElement;dialog.current?.showModal();setInfo(null);setConfirm(false);setMessage('Reading rewind history…');setBusy(true);player?.pause();
  void player?.history().then(value=>{if(token===epoch.current){setInfo(value);setSeconds(1);setMessage(value.issue ?? 'Game paused. Choose how far to go back.');}}).catch(error=>{if(token===epoch.current)setMessage(error instanceof Error ? error.message : 'Rewind unavailable.');}).finally(()=>{if(token===epoch.current)setBusy(false);});
  return()=>{++epoch.current;dialog.current?.close();requestAnimationFrame(()=>focus?.focus());};
 },[open,player]);
 const cancel=()=>{setConfirm(false);requestAnimationFrame(()=>requestButton.current?.focus());};
 const apply=async()=>{
  const token=epoch.current;setBusy(true);setConfirm(false);
  try{await player!.rewind(seconds);const current=await player!.history();if(token===epoch.current){setInfo(current);setMessage(`Rewound ${seconds} seconds. Future history was discarded. Close this panel and Resume to play.`);}}
  catch(error){if(token===epoch.current)setMessage(error instanceof Error ? error.message : 'Rewind failed.');}
  finally{if(token===epoch.current)setBusy(false);}
 };
 return <dialog ref={dialog} className="settings rewind" aria-labelledby="rewind-title" onCancel={event=>{event.preventDefault();if(confirm)cancel();else close();}}>
  <h2 id="rewind-title">Rewind local game</h2>
  <p role="status" data-testid="rewind-status">{message}</p>
  {info && <p data-testid="rewind-history">{info.availableSeconds.toFixed(2)} seconds available</p>}
  {confirm ? <section role="alertdialog" aria-label="Confirm rewind"><p>Replace current progress by rewinding {seconds} seconds? Later history will be discarded. Export a save first if you want to keep this progress.</p><button autoFocus disabled={busy} onClick={()=>void apply()}>Confirm rewind</button><button onClick={cancel}>Cancel</button></section> : <>
   <label>Seconds to rewind <select value={seconds} disabled={busy || !info || !!info.issue} onChange={event=>setSeconds(Number(event.target.value))}>{Array.from({length:Math.floor(info?.maxSeconds ?? 0)},(_,i)=>i+1).map(value=><option key={value} value={value} disabled={value>(info?.availableSeconds ?? 0)}>{value} seconds</option>)}</select></label>
   {info && !info.issue && info.availableSeconds<1 && <p>Not enough history yet. Resume and play longer to build it.</p>}
   <button ref={requestButton} disabled={busy || !info || !!info.issue || seconds>info.availableSeconds} onClick={()=>setConfirm(true)}>Rewind {seconds} seconds</button>
  </>}
  <button disabled={busy} onClick={close}>Close rewind</button>
 </dialog>;
}
