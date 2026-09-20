/** Sole IndexedDB owner for local save slots. ROMs are never accepted here. */
export type SaveSlot = {identity:string;slot:number;savedAt:number;bytes:ArrayBuffer};
const database='retro-coop-local',store='saves';
function open():Promise<IDBDatabase> {
 return new Promise((resolve,reject)=>{
  const request=indexedDB.open(database,1);let abandoned=false;
  request.onupgradeneeded=()=>{request.result.createObjectStore(store,{keyPath:['identity','slot']}).createIndex('identity','identity');};
  request.onerror=()=>reject(request.error ?? Error('Local storage unavailable'));
  request.onblocked=()=>{abandoned=true;reject(Error('Close other Retro Coop tabs and retry.'));};
  request.onsuccess=()=>{if(abandoned){request.result.close();return;}request.result.onversionchange=()=>request.result.close();resolve(request.result);};
 });
}
async function transaction<T>(mode:IDBTransactionMode,operation:(store:IDBObjectStore)=>IDBRequest<T>):Promise<T> {
 const db=await open();
 return new Promise((resolve,reject)=>{
  let result:T;const tx=db.transaction(store,mode);
  tx.oncomplete=()=>{db.close();resolve(result);};
  tx.onabort=()=>{db.close();reject(tx.error ?? Error('Local storage transaction was cancelled.'));};
  tx.onerror=()=>{}; // Abort owns rejection; request success is not durable success.
  try {const request=operation(tx.objectStore(store));request.onsuccess=()=>{result=request.result;};}
  catch(error){tx.abort();db.close();reject(error);}
 });
}
export async function listSaves(identity:string):Promise<SaveSlot[]> {
 const rows=await transaction('readonly',store=>store.index('identity').getAll(identity));
 return rows.filter((row):row is SaveSlot=>row.identity===identity && Number.isSafeInteger(row.slot) && row.slot>0 && Number.isFinite(row.savedAt) && Math.abs(row.savedAt)<=8640000000000000 && row.bytes instanceof ArrayBuffer).sort((a,b)=>a.slot-b.slot);
}
export async function putSave(save:SaveSlot) {await transaction('readwrite',store=>store.put(save));}
export async function deleteSave(identity:string,slot:number) {await transaction('readwrite',store=>store.delete([identity,slot]));}
export function downloadSave(bytes:ArrayBuffer,slot?:number) {
 const url=URL.createObjectURL(new Blob([bytes],{type:'application/octet-stream'}));
 try {const link=document.createElement('a');link.href=url;link.download=`retro-coop${slot ? '-slot-'+slot : '-backup'}.rcstate`;link.click();}
 finally {setTimeout(()=>URL.revokeObjectURL(url),1000);}
}
