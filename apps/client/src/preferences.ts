import {useEffect,useRef,useState} from 'react';
import {validControls,type Controls} from './controls.ts';
import {readStored,putPreferences,type PreferencesRecord} from './saves.ts';
export type Preferences={controls:Controls;filter:'nearest'|'scanlines';volume:number};
export function validPreferences(value:unknown):value is Preferences {
 if(!value || typeof value!=='object')return false;
 const candidate=value as Preferences;
 return Object.keys(candidate).length===3 && validControls(candidate.controls) && ['nearest','scanlines'].includes(candidate.filter) && Number.isFinite(candidate.volume) && candidate.volume>=0 && candidate.volume<=1;
}
type Context={identity:string;generation?:number;pending?:Preferences;stopped:boolean;loading:boolean};
/** Restore never writes defaults; only an explicit user edit schedules persistence. */
export function usePreferences(identity:string|undefined,restore:(value:Preferences)=>void) {
 const [issue,setIssue]=useState('');
 const restoreRef=useRef(restore);restoreRef.current=restore;
 const context=useRef<Context|undefined>(undefined),writes=useRef(Promise.resolve());
 const write=(current:Context,value:Preferences)=>{
  const generation=current.generation;
  writes.current=writes.current.catch(()=>{}).then(async()=>{
   if(context.current!==current || current.stopped || generation===undefined || generation!==current.generation)return;
   try{await putPreferences({identity:current.identity,savedAt:Date.now(),value},generation);if(context.current===current)setIssue('');}
   catch(error){if(context.current===current){current.generation=undefined;setIssue(`Preferences could not be saved. Export or manage Local data. ${error instanceof Error ? error.message : ''}`);}}
  });
 };
 const read=async(current:Context)=>{
  current.loading=true;
  try {
   const {generation,record}=await readStored<PreferencesRecord>('preferences',current.identity);
   if(context.current!==current || current.stopped)return;current.generation=generation;
   if(current.pending){write(current,current.pending);current.pending=undefined;return;}
   if(record){if(validPreferences(record.value))restoreRef.current(record.value);else setIssue('Stored preferences are invalid. Current controls are preserved; export or delete the record in Local data.');}
  }catch(error){if(context.current===current)setIssue(`Preferences could not be loaded. Your game can still run. ${error instanceof Error ? error.message : ''}`);}
  finally{current.loading=false;}
 };
 useEffect(()=>{
  setIssue('');if(!identity){context.current=undefined;return;}
  const current:Context={identity,stopped:false,loading:false};context.current=current;void read(current);
  return ()=>{if(context.current===current)context.current=undefined;};
 },[identity]);
 return {
  issue,
  remember:(value:Preferences)=>{
   const current=context.current;if(!current)return;
   if(current.stopped){current.stopped=false;current.generation=undefined;}
   if(current.generation===undefined){current.pending=value;if(!current.loading)void read(current);}else write(current,value);
  },
  stop:()=>{if(context.current)context.current.stopped=true;},
  dismiss:()=>setIssue(''),
 };
}
