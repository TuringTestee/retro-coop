import {useEffect,useRef,useState} from 'react';
import {listLocalData,clearLocalData,deleteSave,deleteBattery,deletePreferences,downloadSave,type LocalData as Data} from './saves.ts';
import type {LocalPlayer} from './player.ts';

export function LocalData({open,close,player,preferencesIdentity,beforeClear,afterClear}:{open:boolean;close:()=>void;player:LocalPlayer|null;preferencesIdentity?:string;beforeClear:()=>void;afterClear:()=>void}) {
 const dialog=useRef<HTMLDialogElement>(null),epoch=useRef(0),confirmFocus=useRef<HTMLElement|null>(null);
 const [data,setData]=useState<Data|null>(null),[current,setCurrent]=useState<string[]>([]),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 const [confirmation,setConfirmationState]=useState<{label:string;action:()=>Promise<void>}|null>(null),[backup,setBackup]=useState<{bytes:ArrayBuffer;kind:'state'|'battery'|'preferences'}|null>(null);
 const setConfirmation=(value:typeof confirmation)=>{if(value)confirmFocus.current=document.activeElement as HTMLElement;setConfirmationState(value);};
 useEffect(()=>{if(!confirmation && confirmFocus.current){const target=confirmFocus.current;confirmFocus.current=null;requestAnimationFrame(()=>target.focus());}},[confirmation]);
 useEffect(()=>{
  const token=++epoch.current;if(!open){dialog.current?.close();return;}
  const focus=document.activeElement as HTMLElement;dialog.current?.showModal();setData(null);setCurrent([]);setConfirmation(null);setMessage('Reading local data…');setBusy(true);
  void (async()=>{
   try{const records=await listLocalData();if(token!==epoch.current)return;setData(records);setMessage('');}
   catch(error){if(token===epoch.current)setMessage(text(error));}
   finally{if(token===epoch.current)setBusy(false);}
   const identities=await Promise.allSettled([player?.saveInfo(),player?.batteryInfo()]);
   if(token===epoch.current)setCurrent(identities.flatMap(result=>result.status==='fulfilled' && result.value ? [result.value.identity] : []));
  })();
  return ()=>{++epoch.current;dialog.current?.close();requestAnimationFrame(()=>focus?.focus());};
 },[open,player,preferencesIdentity]);
 const run=async(action:()=>Promise<void>)=>{
  const token=epoch.current;setBusy(true);setConfirmation(null);setMessage('');
  try{await action();const records=await listLocalData();if(token===epoch.current){setData(records);setMessage('Local data updated.');}}
  catch(error){if(token===epoch.current){setMessage(text(error));try{const records=await listLocalData();if(token===epoch.current)setData(records);}catch{/* Preserve the original recovery error. */}}}
  finally{if(token===epoch.current)setBusy(false);}
 };
 const exportRecord=(bytes:ArrayBuffer,kind:'state'|'battery'|'preferences')=>{setBackup({bytes,kind});try{downloadSave(bytes,undefined,kind);setMessage('Backup export requested.');}catch(error){setMessage(`Could not export. The backup remains in memory; retry export. ${text(error)}`);}};
 const group=(identity:string)=>current.includes(identity) || identity===preferencesIdentity ? 'Current game and build' : 'Other game or build';
 return <dialog ref={dialog} className="settings local-data" aria-labelledby="local-data-title" onCancel={event=>{event.preventDefault();if(confirmation)setConfirmation(null);else close();}}>
  <h2 id="local-data-title">Local data</h2><p>Saves and preferences live on this device. Your ROMs are never stored here. Export backups before deleting data; browser eviction or site-data removal can erase it.</p>
  {message && <p role="status" data-testid="local-data-status">{message}</p>}
  {confirmation && <section role="alertdialog" aria-label="Confirm local data action"><p>{confirmation.label}</p><button autoFocus disabled={busy} onClick={()=>void run(confirmation.action)}>Confirm</button><button onClick={()=>setConfirmation(null)}>Cancel</button></section>}
  <div hidden={!!confirmation}>
  {data && !data.saves.length && !data.batteries.length && !data.preferences.length && <p>No local data yet.</p>}
  <ul>{data?.saves.map(row=><li key={`save:${row.identity}:${row.slot}`}><span>Save Slot {row.slot} · {group(row.identity)} · {when(row.savedAt)}</span><button disabled={busy} onClick={()=>exportRecord(row.bytes,'state')}>Export save</button><button disabled={busy} onClick={()=>setConfirmation({label:`Delete Save Slot ${row.slot} from ${when(row.savedAt)}? This cannot be undone.`,action:()=>deleteSave(row)})}>Delete save</button></li>)}</ul>
  <ul>{data?.batteries.map(row=><li key={`battery:${row.identity}`}><span>Battery progress · {group(row.identity)} · {when(row.savedAt)}</span><button disabled={busy} onClick={()=>exportRecord(row.bytes,'battery')}>Export battery</button><button disabled={busy} onClick={()=>setConfirmation({label:`Delete battery progress from ${when(row.savedAt)}? The current game stays in memory; select the ROM again to start without this battery data.`,action:()=>deleteBattery(row)})}>Delete battery</button></li>)}</ul>
  <ul>{data?.preferences.map(row=><li key={`preferences:${row.identity}`}><span>Preferences · {group(row.identity)} · {when(row.savedAt)}</span><button disabled={busy} onClick={()=>exportRecord(new TextEncoder().encode(JSON.stringify(row)).buffer,'preferences')}>Export preferences</button><button disabled={busy} onClick={()=>setConfirmation({label:`Delete preferences from ${when(row.savedAt)}? Current controls remain until you select a game again.`,action:()=>deletePreferences(row)})}>Delete preferences</button></li>)}</ul>
  <button disabled={busy || !data} onClick={()=>setConfirmation({label:'Delete all local saves, battery progress and preferences, including other games and builds? This cannot be undone. Export backups first. Current play stays in memory; automatic persistence stops until you explicitly retry or select a game again. No server account is deleted.',action:async()=>{beforeClear();await clearLocalData(data!.generation);afterClear();}})}>Delete local data</button>
  </div>
  {backup && <button disabled={busy} onClick={()=>exportRecord(backup.bytes,backup.kind)}>Retry export</button>}
  <button onClick={close}>Close local data</button>
 </dialog>;
}
function text(error:unknown){return error instanceof Error ? error.message : 'Local data is unavailable. Retry later.';}
function when(value:number){const date=new Date(value);return Number.isFinite(date.getTime()) ? date.toLocaleString() : 'Unknown time';}
