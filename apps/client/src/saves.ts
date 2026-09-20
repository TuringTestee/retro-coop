/** Sole IndexedDB owner for local saves and preferences. ROMs are never accepted here. */
export type SaveSlot = {identity:string;slot:number;savedAt:number;bytes:ArrayBuffer};
export type BatteryRecord = {identity:string;savedAt:number;bytes:ArrayBuffer};
export type PreferencesRecord = {identity:string;savedAt:number;value:unknown};
const database='retro-coop-local',store='saves';
const stores=['saves','batteries','preferences','meta'];
function open():Promise<IDBDatabase> {
 return new Promise((resolve,reject)=>{
  const request=indexedDB.open(database,2);let abandoned=false;
  const timer=setTimeout(()=>{abandoned=true;reject(Error('Local storage did not respond. Retry later.'));},5000);
  request.onupgradeneeded=()=>{const db=request.result;if(!db.objectStoreNames.contains(store))db.createObjectStore(store,{keyPath:['identity','slot']}).createIndex('identity','identity');for(const name of ['batteries','preferences'])if(!db.objectStoreNames.contains(name))db.createObjectStore(name,{keyPath:'identity'});if(!db.objectStoreNames.contains('meta'))db.createObjectStore('meta');};
  request.onerror=()=>{clearTimeout(timer);reject(request.error ?? Error('Local storage unavailable'));};
  request.onblocked=()=>{clearTimeout(timer);abandoned=true;reject(Error('Close other Retro Coop tabs and retry.'));};
  request.onsuccess=()=>{clearTimeout(timer);if(abandoned){request.result.close();return;}request.result.onversionchange=()=>request.result.close();resolve(request.result);};
 });
}
async function transaction<T>(mode:IDBTransactionMode,operation:(store:IDBObjectStore,tx:IDBTransaction)=>IDBRequest<T>,names:string[]=[store]):Promise<T> {
 const db=await open();
 return new Promise((resolve,reject)=>{
  let result:T;const tx=db.transaction(names,mode);const timer=setTimeout(()=>tx.abort(),5000);
  tx.oncomplete=()=>{clearTimeout(timer);db.close();resolve(result);};
  tx.onabort=()=>{clearTimeout(timer);db.close();reject(tx.error ?? Error('Local storage transaction was cancelled.'));};
  tx.onerror=()=>{}; // Abort owns rejection; request success is not durable success.
  try {const request=operation(tx.objectStore(names[0]),tx);request.onsuccess=()=>{result=request.result;};}
  catch(error){clearTimeout(timer);tx.abort();db.close();reject(error);}
 });
}
export async function listSaves(identity:string):Promise<SaveSlot[]> {
 const rows=await transaction('readonly',store=>store.index('identity').getAll(identity));
 return rows.filter((row):row is SaveSlot=>row.identity===identity && Number.isSafeInteger(row.slot) && row.slot>0 && Number.isFinite(row.savedAt) && Math.abs(row.savedAt)<=8640000000000000 && row.bytes instanceof ArrayBuffer).sort((a,b)=>a.slot-b.slot);
}
async function changeRecord(name:string,key:IDBValidKey,expected:BatteryRecord|undefined,change:(store:IDBObjectStore)=>void) {
 let failure:unknown;
 try {await transaction('readwrite',store=>{
  const request=store.get(key);
  request.addEventListener('success',()=>{
   const current=request.result as SaveSlot|undefined;
   const same=sameRecord(current,expected);
   if(!same){failure=Error('This saved data changed in another tab. Reopen the panel before changing it.');store.transaction.abort();return;}
   try{change(store);}catch(error){failure=error;store.transaction.abort();}
  });return request;
 },[name]);}catch(error){throw failure ?? error;}
}
export async function putSave(save:SaveSlot,expected?:SaveSlot) {await changeRecord(store,[save.identity,save.slot],expected,store=>{store.put(save);});}
export async function deleteSave(expected:SaveSlot) {await changeRecord(store,[expected.identity,expected.slot],expected,store=>{store.delete([expected.identity,expected.slot]);});}
export function downloadSave(bytes:ArrayBuffer,slot?:number,kind:'state'|'battery'|'preferences'='state') {
 const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'}));
 try {const link=document.createElement('a');link.href=url;link.download=`retro-coop${slot ? '-slot-'+slot : '-backup'}.${kind==='state' ? 'rcstate' : kind==='battery' ? 'rcbat' : 'json'}`;link.click();}
 finally {setTimeout(()=>URL.revokeObjectURL(url),1000);}
}

function sameBytes(a:ArrayBuffer,b:ArrayBuffer){const left=new Uint8Array(a),right=new Uint8Array(b);return left.every((byte,index)=>byte===right[index]);}


/** One epoch prevents automatic work from recreating data after a clear in any tab. */
export async function readStored<T>(name:'batteries'|'preferences',identity:string):Promise<{generation:number;record:T|undefined}> {
 let generation=0;
 const record=await transaction('readonly',(store,tx)=>{const epoch=tx.objectStore('meta').get('generation');epoch.onsuccess=()=>{generation=epoch.result ?? 0;};return store.get(identity);},[name,'meta']);
 return {generation,record:record as T|undefined};
}
async function automaticWrite(name:'batteries'|'preferences',generation:number,write:(store:IDBObjectStore,fail:(error:Error)=>void)=>void) {
 let failure:unknown;
 try {await transaction('readwrite',(store,tx)=>{
  const fail=(error:Error)=>{failure=error;tx.abort();};
  const epoch=tx.objectStore('meta').get('generation');epoch.addEventListener('success',()=>{
   if((epoch.result ?? 0)!==generation){fail(Error('Local data was cleared in another view. Retry explicitly to save new progress.'));return;}
   try{write(store,fail);}catch(error){fail(error instanceof Error ? error : Error('Local storage failed'));}
  });return epoch;
 },[name,'meta']);}catch(error){throw failure ?? error;}
}
export async function putBattery(record:BatteryRecord,expected:BatteryRecord|undefined,generation:number) {
 await automaticWrite('batteries',generation,(store,fail)=>{
  const request=store.get(record.identity);request.addEventListener('success',()=>{
   const current=request.result as BatteryRecord|undefined;
   if(!sameRecord(current,expected)){fail(Error('Battery progress changed in another tab. Export a backup before reloading this game.'));return;}
   try{store.put(record);}catch(error){fail(error instanceof Error ? error : Error('Battery storage failed'));}
  });
 });
}
export async function putPreferences(record:PreferencesRecord,generation:number) {await automaticWrite('preferences',generation,store=>{store.put(record);});}
export type LocalData = {generation:number;saves:SaveSlot[];batteries:BatteryRecord[];preferences:PreferencesRecord[]};
export async function listLocalData():Promise<LocalData> {
 const result:LocalData={generation:0,saves:[],batteries:[],preferences:[]};
 await transaction('readonly',(_,tx)=>{
  for(const name of ['saves','batteries','preferences'] as const){const request=tx.objectStore(name).getAll();request.onsuccess=()=>{result[name]=request.result;};}
  const epoch=tx.objectStore('meta').get('generation');epoch.addEventListener('success',()=>{result.generation=epoch.result ?? 0;});return epoch;
 },stores);return result;
}
export async function deleteBattery(expected:BatteryRecord) {await changeRecord('batteries',expected.identity,expected,store=>{store.delete(expected.identity);});}
export async function deletePreferences(expected:PreferencesRecord) {
 let failure:unknown;
 try{await transaction('readwrite',store=>{const request=store.get(expected.identity);request.addEventListener('success',()=>{if(JSON.stringify(request.result)!==JSON.stringify(expected)){failure=Error('Preferences changed in another tab. Reopen Local data before deleting them.');store.transaction.abort();return;}store.delete(expected.identity);});return request;},['preferences']);}catch(error){throw failure ?? error;}
}
export async function clearLocalData(generation:number) {
 let failure:unknown;
 try{await transaction('readwrite',(_,tx)=>{const meta=tx.objectStore('meta'),request=meta.get('generation');request.addEventListener('success',()=>{
  if((request.result ?? 0)!==generation){failure=Error('Local data changed. Reopen this panel before clearing it.');tx.abort();return;}
  for(const name of ['saves','batteries','preferences'])tx.objectStore(name).clear();meta.put(generation+1,'generation');
 });return request;},stores);}catch(error){throw failure ?? error;}
}
function sameRecord(current:BatteryRecord|undefined,expected:BatteryRecord|undefined) {return !current && !expected || !!current && !!expected && current.savedAt===expected.savedAt && current.bytes instanceof ArrayBuffer && current.bytes.byteLength===expected.bytes.byteLength && sameBytes(current.bytes,expected.bytes);}
