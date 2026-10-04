import {useEffect,useRef,useState} from 'react';
import {migrateDefaultKeyboard,validControls,type Controls} from './controls.ts';
import {readStored,putPreferences,type PreferencesRecord} from './saves.ts';
export type Preferences={controls:Controls;filter:'nearest'|'scanlines';volume:number};
export function validPreferences(value:unknown):value is Preferences {
 if(!value || typeof value!=='object')return false;
 const candidate=value as Preferences;
 return Object.keys(candidate).length===3 && validControls(candidate.controls) && ['nearest','scanlines'].includes(candidate.filter) && Number.isFinite(candidate.volume) && candidate.volume>=0 && candidate.volume<=1;
}
type Context={identity:string;generation?:number;pending?:{value:Preferences;resolve:(saved:boolean)=>void};stopped:boolean;loading:boolean};
/** Restore never writes defaults; only an explicit user edit schedules persistence. */
export function usePreferences(identity:string|undefined,restore:(value:Preferences)=>void) {
 const [issue,setIssue]=useState('');
 const restoreRef=useRef(restore);restoreRef.current=restore;
 const context=useRef<Context|undefined>(undefined),writes=useRef(Promise.resolve());
 const write=(current:Context,value:Preferences)=>{
  const generation=current.generation;let saved=false;
  writes.current=writes.current.catch(()=>{}).then(async()=>{
   if(context.current!==current || current.stopped || generation===undefined || generation!==current.generation)return;
   try{await putPreferences({identity:current.identity,savedAt:Date.now(),value},generation);saved=true;if(context.current===current)setIssue('');}
   catch(error){if(context.current===current){current.generation=undefined;setIssue(`Preferences could not be saved. Export or manage Local data. ${error instanceof Error ? error.message : ''}`);}}
  });
  return writes.current.then(()=>saved);
 };
 const read=async(current:Context)=>{
  current.loading=true;
  try {
   const {generation,record}=await readStored<PreferencesRecord>('preferences',current.identity);
   if(context.current!==current || current.stopped)return;current.generation=generation;
   if(current.pending){const pending=current.pending;current.pending=undefined;pending.resolve(await write(current,pending.value));return;}
   if(record){if(validPreferences(record.value)){const controls=migrateDefaultKeyboard(record.value.controls);const value=controls===record.value.controls?record.value:{...record.value,controls};restoreRef.current(value);if(controls!==record.value.controls)write(current,value);}else setIssue('Stored preferences are invalid. Current controls are preserved; export or delete the record in Local data.');}
  }catch(error){current.pending?.resolve(false);current.pending=undefined;if(context.current===current)setIssue(`Preferences could not be loaded. Your game can still run. ${error instanceof Error ? error.message : ''}`);}
  finally{current.loading=false;}
 };
 useEffect(()=>{
  setIssue('');if(!identity){context.current=undefined;return;}
  const current:Context={identity,stopped:false,loading:false};context.current=current;void read(current);
  return ()=>{current.pending?.resolve(false);if(context.current===current)context.current=undefined;};
 },[identity]);
 return {
  issue,
  remember:(value:Preferences)=>{
   const current=context.current;if(!current)return Promise.resolve(false);
   if(current.stopped){current.stopped=false;current.generation=undefined;}
   if(current.generation===undefined){return new Promise<boolean>(resolve=>{current.pending?.resolve(false);current.pending={value,resolve};if(!current.loading)void read(current);});}return write(current,value);
  },
  stop:()=>{if(context.current)context.current.stopped=true;},
  dismiss:()=>setIssue(''),
 };
}
