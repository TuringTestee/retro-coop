import {useEffect,useRef,useState} from 'react';
import type {LocalPlayer} from './player.ts';
import type {LocalFileInfo} from '../../../packages/contracts/src/index.ts';
import {listSaves,putSave,deleteSave,downloadSave,type SaveSlot} from './saves.ts';

type Confirmation={label:string;action:()=>Promise<void>};
export function Saves({open,player,game,shared,batteryAvailable,storageIssue}:{open:boolean;player:LocalPlayer|null;game:string;shared:boolean;batteryAvailable:boolean;storageIssue?:string}) {
 const picker=useRef<HTMLInputElement>(null),epoch=useRef(0),previousGame=useRef(game),confirmFocus=useRef<HTMLElement|null>(null);
 const [info,setInfo]=useState<LocalFileInfo|null>(null),[rows,setRows]=useState<SaveSlot[]>([]),[slot,setSlot]=useState(1);
 const [listed,setListed]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[confirmation,setConfirmationState]=useState<Confirmation|null>(null);
 const [view,setView]=useState<'current'|'backups'|'stored'>('current');
 const setConfirmation=(value:Confirmation|null)=>{if(value)confirmFocus.current=document.activeElement as HTMLElement;setConfirmationState(value);};
 useEffect(()=>{if(!confirmation && confirmFocus.current){const target=confirmFocus.current;confirmFocus.current=null;requestAnimationFrame(()=>target.focus());}},[confirmation]);
 const [backup,setBackup]=useState<ArrayBuffer|null>(null),[exportFailed,setExportFailed]=useState(false);
 useEffect(()=>{
  const token=++epoch.current;setConfirmation(null);setBusy(false);
  if(previousGame.current!==game){previousGame.current=game;setBackup(null);setExportFailed(false);}
  if(!open)return;
  setInfo(null);setRows([]);setListed(false);setMessage('Checking saves for this game…');
  void (async()=>{
   try {
    if(!player)throw Error('Load a game first.');
    const current=await player.saveInfo();if(token!==epoch.current)return;setInfo(current);
    try {const stored=await listSaves(current.identity);if(token===epoch.current){setRows(stored);setListed(true);setMessage(stored.length ? '' : 'No saves for this game yet.');}}
    catch(error){if(token===epoch.current)setMessage(storageError(error));}
   } catch(error){if(token===epoch.current)setMessage(errorText(error));}
  })();
  return ()=>{++epoch.current;};
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
 const selected=rows.find(row=>row.slot===slot);
 if(!open)return null;
 return <section className="rc-tool-page rc-saves" aria-labelledby="saves-title">
  <div className="rc-tool-heading"><h2 id="saves-title" tabIndex={-1}>Saves on this device</h2><nav aria-label="Save sections"><button aria-current={view==='current'?'page':undefined} onClick={()=>setView('current')}>Current game</button><button aria-current={view==='backups'?'page':undefined} onClick={()=>setView('backups')}>Backups</button><button aria-current={view==='stored'?'page':undefined} onClick={()=>setView('stored')}>Saved slots</button></nav></div>
  <div className="rc-tool-body"><div className="rc-tool-stack">
   {confirmation?<div className="rc-tool-stack" role="alertdialog" aria-label="Confirm save action"><p>{confirmation.label}</p><div className="rc-tool-actions"><button autoFocus disabled={busy} onClick={()=>void confirmation.action()}>Confirm</button><button onClick={()=>setConfirmation(null)}>Cancel</button></div></div>:<>
    <label>Save slot<select aria-label="Save slot" disabled={busy||!info} value={slot} onChange={event=>setSlot(Number(event.target.value))}>{[1,2,3].map(number=><option key={number} value={number}>Slot {number}</option>)}</select></label>
    {view==='current'?<>
     <p>Save this game's progress to this browser. Export a backup to keep it.</p>
     <div className="rc-tool-actions"><button disabled={busy||!info||!listed} onClick={chooseSave}>Save current point</button><button disabled={busy||!info||!listed} onClick={()=>{picker.current!.value='';picker.current!.click();}}>Import save</button></div>
     <input ref={picker} type="file" hidden aria-label="Save file" accept=".rcstate" onChange={event=>importFile(event.target.files?.[0])}/>
     {batteryAvailable&&storageIssue&&<button onClick={()=>void run(async current=>{await player!.retryBatteryPersistence();if(current())setMessage('Battery saving is working again.');})} disabled={busy}>Retry battery saving</button>}
    </>:view==='backups'?<>
     <p>Export a copy you can keep outside this browser.</p>
     <div className="rc-tool-actions"><button disabled={busy||!info} onClick={()=>void run(async current=>{const bytes=await player!.exportSave();if(current())exportBytes(bytes);})}>Export current save</button>{batteryAvailable&&<button disabled={busy} onClick={()=>void run(async current=>{const bytes=await player!.exportBattery();if(current()){downloadSave(bytes,undefined,'battery');setMessage('Battery backup requested.');}})}>Export battery backup</button>}</div>
    </>:<>
     <p>{selected?`Slot ${slot} · ${new Date(selected.savedAt).toLocaleString()}`:`Slot ${slot} is empty.`}</p>
     {selected&&<div className="rc-tool-actions">{!shared&&<button disabled={busy} onClick={()=>setConfirmation({label:`Load Slot ${slot}? Current unsaved progress will be replaced.`,action:()=>run(async current=>{if(!current())return;await player!.loadSave(selected.bytes);if(current())setMessage('Save loaded. Back to game and Resume whenever you’re ready.');})})}>Load Slot {slot}</button>}<button disabled={busy} onClick={()=>exportBytes(selected.bytes,slot)}>Export Slot {slot}</button><button disabled={busy} onClick={()=>setConfirmation({label:`Delete Slot ${slot}? This cannot be undone.`,action:()=>run(async current=>{await deleteSave(selected);if(current()){await refresh(current);setMessage(`Deleted Slot ${slot}.`);}})})}>Delete Slot {slot}</button></div>}
    </>}
    {backup&&(exportFailed||message.startsWith("Couldn't save"))&&<button disabled={busy} onClick={()=>exportBytes(backup)}>{exportFailed?'Retry export':'Export memory backup'}</button>}
    {message&&<p role="status" data-testid="save-status">{message}</p>}
   </>}
  </div></div>
 </section>;
}
function errorText(error:unknown){return error instanceof Error ? error.message : 'The save operation failed. Try again.';}
function storageError(error:unknown){return `Couldn't save on this device. Export current save to keep a backup, or manage local saves below. ${errorText(error)}`;}
