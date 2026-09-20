import {useEffect,useRef,useState} from 'react';
import type {LocalPlayer} from './player.ts';
import type {StateInfo} from '../../../packages/contracts/src/index.ts';
import {listSaves,putSave,deleteSave,downloadSave,type SaveSlot} from './saves.ts';

type Confirmation={label:string;action:()=>Promise<void>};
export function Saves({open,close,player,game}:{open:boolean;close:()=>void;player:LocalPlayer|null;game:string}) {
 const dialog=useRef<HTMLDialogElement>(null),picker=useRef<HTMLInputElement>(null),epoch=useRef(0),previousGame=useRef(game),confirmFocus=useRef<HTMLElement|null>(null);
 const [info,setInfo]=useState<StateInfo|null>(null),[rows,setRows]=useState<SaveSlot[]>([]),[slot,setSlot]=useState(1);
 const [listed,setListed]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[confirmation,setConfirmationState]=useState<Confirmation|null>(null);
 const setConfirmation=(value:Confirmation|null)=>{if(value)confirmFocus.current=document.activeElement as HTMLElement;setConfirmationState(value);};
 useEffect(()=>{if(!confirmation && confirmFocus.current){const target=confirmFocus.current;confirmFocus.current=null;requestAnimationFrame(()=>target.focus());}},[confirmation]);
 const [backup,setBackup]=useState<ArrayBuffer|null>(null),[exportFailed,setExportFailed]=useState(false);
 useEffect(()=>{
  const token=++epoch.current;setConfirmation(null);setBusy(false);
  if(previousGame.current!==game){previousGame.current=game;setBackup(null);setExportFailed(false);}
  if(!open){dialog.current?.close();return;}
  const returnFocus=document.activeElement as HTMLElement|null;
  dialog.current?.showModal();setInfo(null);setRows([]);setListed(false);setMessage('Checking saves for this game…');
  void (async()=>{
   try {
    if(!player)throw Error('Load a game first.');
    const current=await player.saveInfo();if(token!==epoch.current)return;setInfo(current);
    try {const stored=await listSaves(current.identity);if(token===epoch.current){setRows(stored);setListed(true);setMessage(stored.length ? '' : 'No saves for this game yet.');}}
    catch(error){if(token===epoch.current)setMessage(storageError(error));}
   } catch(error){if(token===epoch.current)setMessage(errorText(error));}
  })();
  return ()=>{++epoch.current;dialog.current?.close();returnFocus?.focus();};
 },[open,game,player]);
 const run=async(action:(current:()=>boolean)=>Promise<void>)=>{
  const token=epoch.current;setBusy(true);setConfirmation(null);setMessage('');
  try{await action(()=>epoch.current===token);}catch(error){if(epoch.current===token)setMessage(errorText(error));}
  finally{if(epoch.current===token)setBusy(false);}
 };
 const refresh=async(current:()=>boolean)=>{const stored=await listSaves(info!.identity);if(current())setRows(stored);};
 const persist=async(bytes:ArrayBuffer,current:()=>boolean)=>{
  if(!current())return;setBackup(bytes);
  try{await putSave({identity:info!.identity,slot,savedAt:Date.now(),bytes},rows.find(row=>row.slot===slot));}
  catch(error){if(current())setMessage(storageError(error));return;}
  if(current()){await refresh(current);setMessage(`Saved in Slot ${slot} on this device.`);}
 };
 const save=()=>run(async current=>{const bytes=await player!.exportSave();await persist(bytes,current);});
 const chooseSave=()=>rows.some(row=>row.slot===slot) ? setConfirmation({label:`Overwrite Slot ${slot}? Its saved progress will be replaced.`,action:save}) : void save();
 const importFile=(file?:File)=>{
  if(!file || !info)return;
  void run(async current=>{
   if(file.size===0 || file.size>info.limit)throw Error('This save file is empty or exceeds the supported size.');
   const bytes=await file.arrayBuffer();if(!current())return;
   await player!.validateSave(bytes);if(!current())return;
   const insert=()=>run(next=>persist(bytes,next));
   if(rows.some(row=>row.slot===slot))setConfirmation({label:`Import into Slot ${slot}? Its saved progress will be replaced. Your running game will not change.`,action:insert});
   else await persist(bytes,current);
  });
 };
 const exportBytes=(bytes:ArrayBuffer,slot?:number)=>{setBackup(bytes);try{downloadSave(bytes,slot);setExportFailed(false);setMessage('Save export requested. Keep the backup somewhere safe.');}catch(error){setExportFailed(true);setMessage(`Couldn't export. Your backup remains in memory. Retry export. ${errorText(error)}`);}};
 return <dialog ref={dialog} className="settings saves" aria-labelledby="saves-title" onCancel={event=>{event.preventDefault();if(confirmation)setConfirmation(null);else close();}}>
  <h2 id="saves-title">Saves on this device</h2><p>Compatible saves for your current game. Your game file is never stored or included in exports.</p>
  <p>Saves can be removed by your browser. Export a backup.</p>
  {message && <p role="status" data-testid="save-status">{message}</p>}
  {confirmation && <section role="alertdialog" aria-label="Confirm save action"><p>{confirmation.label}</p><button autoFocus disabled={busy} onClick={()=>void confirmation.action()}>Confirm</button><button onClick={()=>setConfirmation(null)}>Cancel</button></section>}<div hidden={!!confirmation}>
   <label>Save slot <select aria-label="Save slot" disabled={busy || !info} value={slot} onChange={event=>setSlot(Number(event.target.value))}>{[1,2,3].map(number=><option key={number} value={number}>Slot {number}</option>)}</select></label>
   <button disabled={busy || !info || !listed} onClick={chooseSave}>Save current point</button>
   <button disabled={busy || !info || !listed} onClick={()=>{picker.current!.value='';picker.current!.click();}}>Import save</button>
   {open && <input ref={picker} type="file" hidden aria-label="Save file" accept=".rcstate" onChange={event=>importFile(event.target.files?.[0])}/>}
   <ul>{rows.map(row=><li key={row.slot}>Slot {row.slot} · <time dateTime={new Date(row.savedAt).toISOString()}>{new Date(row.savedAt).toLocaleString()}</time>
    <button disabled={busy} onClick={()=>setConfirmation({label:`Load Slot ${row.slot}? Current unsaved progress will be replaced.`,action:()=>run(async current=>{if(!current())return;await player!.loadSave(row.bytes);if(current())setMessage('Save loaded. Close this panel and Resume whenever you’re ready.');})})}>Load Slot {row.slot}</button>
    <button disabled={busy} onClick={()=>exportBytes(row.bytes,row.slot)}>Export Slot {row.slot}</button>
    <button disabled={busy} onClick={()=>setConfirmation({label:`Delete Slot ${row.slot}? This cannot be undone. Export a backup first if you need it.`,action:()=>run(async current=>{await deleteSave(row);if(current()){await refresh(current);setMessage(`Deleted Slot ${row.slot}.`);}})})}>Delete Slot {row.slot}</button>
   </li>)}</ul>
  </div>
  <button disabled={busy || !info} onClick={()=>void run(async current=>{const bytes=await player!.exportSave();if(current())exportBytes(bytes);})}>Export current save</button>
  {backup && <button disabled={busy} onClick={()=>exportBytes(backup)}>{exportFailed ? 'Retry export' : 'Export memory backup'}</button>}
  <p className="hint">Manage local saves using the export and delete actions above.</p>
  <button onClick={close}>Close saves</button>
 </dialog>;
}
function errorText(error:unknown){return error instanceof Error ? error.message : 'The save operation failed. Try again.';}
function storageError(error:unknown){return `Couldn't save on this device. Export current save to keep a backup, or manage local saves below. ${errorText(error)}`;}
