import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {readSave,putSave,listLocalData,validSavedAt,clearLocalData,deleteSave,deleteBattery,deletePreferences,deleteRom,downloadSave,type LocalData as Data} from './saves.ts';
import {createPortal} from 'react-dom';
import type {LocalPlayer} from './player.ts';
import {safeLabel} from './rom-library.ts';

export function LocalData({open,player,preferencesIdentity,beforeClear,afterClear,timelineBusy,batteryAvailable}:{open:boolean;player:LocalPlayer|null;preferencesIdentity?:string;beforeClear:()=>void;afterClear:()=>void;timelineBusy?:boolean;batteryAvailable?:boolean}) {
 const picker=useRef<HTMLInputElement>(null),pendingTimeline=useRef(timelineBusy);pendingTimeline.current=timelineBusy;
 const page=useRef<HTMLElement>(null),epoch=useRef(0),confirmFocus=useRef<HTMLElement|null>(null);
 const [data,setData]=useState<Data|null>(null),[current,setCurrent]=useState<string[]>([]),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
 const [confirmation,setConfirmationState]=useState<{label:string;action:()=>Promise<void>}|null>(null),[backup,setBackup]=useState<{bytes:ArrayBuffer;kind:'state'|'battery'|'preferences'}|null>(null),[exportFailed,setExportFailed]=useState(false),[focusRevision,setFocusRevision]=useState(0);
 const [category,setCategory]=useState<'current'|'games'|'saves'|'battery'|'preferences'>('games'),[record,setRecord]=useState(0);
 const restoreFocus=()=>{const target=confirmFocus.current;confirmFocus.current=null;if(!target||!open)return;const connected=target.isConnected&&page.current?.contains(target)&&!target.closest('[hidden]');(connected?target:page.current?.querySelector<HTMLElement>('#local-data-title'))?.focus();};
 const setConfirmation=(value:typeof confirmation)=>{if(value)confirmFocus.current=document.activeElement as HTMLElement;setConfirmationState(value);if(!value)requestAnimationFrame(restoreFocus);};
 useLayoutEffect(()=>{if(focusRevision)restoreFocus();},[focusRevision]);
 useEffect(()=>{
  const token=++epoch.current;if(!open)return;
  setData(null);setCurrent([]);setConfirmation(null);setMessage('Reading local data…');setBusy(true);
  void (async()=>{
   try{const records=await listLocalData();if(token!==epoch.current)return;setData(records);setMessage('');}
   catch(error){if(token===epoch.current)setMessage(text(error));}
   finally{if(token===epoch.current)setBusy(false);}
   const identities=await Promise.allSettled([player?.saveInfo(),player?.batteryInfo()]);
   if(token===epoch.current)setCurrent(identities.flatMap(result=>result.status==='fulfilled' && result.value ? [result.value.identity] : []));
  })();
  return ()=>{++epoch.current;};
 },[open,player,preferencesIdentity]);
 const run=async(action:()=>Promise<void>)=>{
  const token=epoch.current;setBusy(true);setConfirmationState(null);setMessage('');
  try{await action();const records=await listLocalData();if(token===epoch.current){setData(records);setMessage('Local data updated.');}}
  catch(error){if(token===epoch.current){setMessage(text(error));try{const records=await listLocalData();if(token===epoch.current)setData(records);}catch{/* Preserve the original recovery error. */}}}
  finally{if(token===epoch.current){setBusy(false);setFocusRevision(value=>value+1);}}
 };
 const exportRecord=(bytes:ArrayBuffer,kind:'state'|'battery'|'preferences')=>{setBackup({bytes,kind});try{downloadSave(bytes,undefined,kind);setExportFailed(false);setMessage('Backup export requested.');}catch(error){setExportFailed(true);setMessage(`Could not export. The backup remains in memory; retry export. ${text(error)}`);}};
 const currentOperation=()=>{const token=epoch.current,version=player?.selectionVersion();return ()=>epoch.current===token&&!!player?.isLoaded()&&player.selectionVersion()===version&&!pendingTimeline.current;};
 const exportCurrent=async(kind:'state'|'battery')=>{const valid=currentOperation();setBusy(true);try{if(!player||!valid())throw Error('Load a game first.');const bytes=kind==='state'?await player.exportSave():await player.exportBattery();if(valid())exportRecord(bytes,kind);}catch(error){if(valid())setMessage(text(error));}finally{if(valid())setBusy(false);}};
 const importCurrent=async(file?:File)=>{
  if(!file||!player)return;const valid=currentOperation();setBusy(true);setMessage('');
  try{const info=await player.saveInfo();if(!valid())return;if(!file.size||file.size>info.limit)throw Error('This save file is empty or exceeds the supported size.');
   const prior=await readSave(info.identity,1),bytes=await file.arrayBuffer();if(!valid())return;
   const inspected=await player.inspectSave(bytes);if(!valid())return;if(inspected.identity!==info.identity)throw Error('This save does not match the selected game.');
   const action=async()=>{if(!valid())throw Error('Game changed. Import again.');await putSave({identity:info.identity,slot:1,savedAt:Date.now(),bytes,hash:inspected.hash},prior.record,prior.generation,valid);};
   if(prior.record)setConfirmation({label:'Replace saved Slot 1 with this imported copy? Your current game will not change.',action});else await run(action);
  }catch(error){if(valid())setMessage(text(error));}finally{if(valid())setBusy(false);}
 };
 const group=(identity:string)=>current.includes(identity) || identity===preferencesIdentity ? 'Current game and build' : 'Other game or build';
 const count=data?(category==='games'?data.roms.length:category==='saves'?data.saves.length:category==='battery'?data.batteries.length:data.preferences.length):0;
 const index=Math.min(record,Math.max(0,count-1));
 const rom=category==='games'?data?.roms[index]:undefined,save=category==='saves'?data?.saves[index]:undefined,battery=category==='battery'?data?.batteries[index]:undefined,preference=category==='preferences'?data?.preferences[index]:undefined;
 if(!open)return null;
 return <section ref={page} className="rc-tool-page rc-local-data" aria-labelledby="local-data-title" inert={!!confirmation}>
  <div className="rc-tool-heading"><h2 id="local-data-title" tabIndex={-1}>Local data</h2><nav aria-label="Local data sections">{(['current','games','saves','battery','preferences'] as const).map(item=><button key={item} aria-current={category===item?'page':undefined} onClick={()=>{setCategory(item);setRecord(0);}}>{item==='preferences'?'Settings':item[0].toUpperCase()+item.slice(1)}</button>)}</nav></div>
  <div className="rc-tool-body"><div className="rc-tool-stack">
   <>
    {!message&&!exportFailed&&<p>Data is stored in this browser. Export backups before deleting.</p>}
     {category==='current'&&<div className="rc-tool-actions"><button disabled={busy||timelineBusy||!player?.isLoaded()} onClick={()=>void exportCurrent('state')}>Export current save</button><button disabled={busy||timelineBusy||!player?.isLoaded()} onClick={()=>{picker.current!.value='';picker.current!.click();}}>Import save</button><button disabled={busy||timelineBusy||!batteryAvailable||!player?.isLoaded()} onClick={()=>void exportCurrent('battery')}>Export battery backup</button><button disabled={busy||timelineBusy||!batteryAvailable||!player?.isLoaded()} onClick={()=>void run(async()=>{await player!.retryBatteryPersistence();})}>Retry battery saving</button></div>}
    {!data?<p role="status">{message}</p>:<>
     {category!=='current'&&<div className="rc-tool-actions"><button disabled={index===0} onClick={()=>setRecord(index-1)}>Previous</button><span>{count?`${index+1} of ${count}`:'No records'}</span><button disabled={index+1>=count} onClick={()=>setRecord(index+1)}>Next</button></div>}
     {rom&&<><h3>{safeLabel(rom.label??'NES game')}</h3><p>{rom.size<1_000_000?`${Math.max(1,Math.ceil(rom.size/1000))} KB`:`${(rom.size/1_000_000).toFixed(1)} MB`} · {when(rom.savedAt)}</p><button disabled={busy} onClick={()=>setConfirmation({label:'Delete this saved game? Current play stays in memory. Add the file again or download it from a lobby to reuse it later.',action:()=>deleteRom(rom.sha256,data.generation)})}>Delete game</button></>}
     {save&&<><h3>Save Slot {save.slot}</h3><p>{group(save.identity)} · {when(save.savedAt)}</p><div className="rc-tool-actions"><button disabled={busy} onClick={()=>exportRecord(save.bytes,'state')}>Export save</button><button disabled={busy} onClick={()=>setConfirmation({label:`Delete Save Slot ${save.slot} from ${when(save.savedAt)}? This cannot be undone.`,action:()=>deleteSave(save)})}>Delete save</button></div></>}
     {battery&&<><h3>Battery progress</h3><p>{group(battery.identity)} · {when(battery.savedAt)}</p><div className="rc-tool-actions"><button disabled={busy} onClick={()=>exportRecord(battery.bytes,'battery')}>Export battery</button><button disabled={busy} onClick={()=>setConfirmation({label:`Delete battery progress from ${when(battery.savedAt)}? The current game stays in memory; select the ROM again to start without this battery data.`,action:()=>deleteBattery(battery)})}>Delete battery</button></div></>}
     {preference&&<><h3>Saved settings</h3><p>{group(preference.identity)} · {when(preference.savedAt)}</p><div className="rc-tool-actions"><button disabled={busy} onClick={()=>exportRecord(new TextEncoder().encode(JSON.stringify(preference)).buffer,'preferences')}>Export settings</button><button disabled={busy} onClick={()=>setConfirmation({label:`Delete settings from ${when(preference.savedAt)}? Current controls remain until you select a game again.`,action:()=>deletePreferences(preference)})}>Delete settings</button></div></>}
     <button disabled={busy} onClick={()=>setConfirmation({label:'Delete all local data on this device? This cannot be undone.',action:async()=>{beforeClear();await clearLocalData(data.generation);afterClear();}})}>Delete all local data</button>
    </>}
    {backup&&exportFailed&&<button disabled={busy} onClick={()=>exportRecord(backup.bytes,backup.kind)}>Retry export</button>}
    {message&&data&&<p role="status" data-testid="local-data-status">{message}</p>}
   </>
  </div></div>
  <input ref={picker} type="file" hidden aria-label="Save file" accept=".rcstate" onChange={event=>void importCurrent(event.target.files?.[0])}/>
  {confirmation&&createPortal(<div className="rc-dialog-layer"><div className="rc-dialog-card" role="alertdialog" aria-modal="true" aria-label="Confirm local data action"><p>{confirmation.label}</p><div className="rc-dialog-actions"><button autoFocus disabled={busy} onClick={()=>void run(confirmation.action)}>Confirm</button><button onClick={()=>setConfirmation(null)}>Cancel</button></div></div></div>,document.body)}
 </section>;
}
function text(error:unknown){return error instanceof Error ? error.message : 'Local data is unavailable. Retry later.';}
function when(value:number){return validSavedAt(value) ? new Date(value).toLocaleString() : 'Unknown time';}
