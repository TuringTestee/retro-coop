function instrumentWorker() {
 const instantiate=WebAssembly.instantiate.bind(WebAssembly),send=postMessage.bind(globalThis);
 let requestAt=0,phases={},previousPostMs=0;
 addEventListener('message',event=>{if(event.data.type==='frame'){requestAt=performance.now();phases={};}});
 WebAssembly.instantiate=async(...args)=>{
  const instance=await instantiate(...args),exports={...instance.exports};
  for(const name of ['local_frame','local_output'])exports[name]=(...values)=>{
   const at=performance.now(),result=instance.exports[name](...values);
   const key=name==='local_frame'?'emulateMs':values[0]===5?'pixelsMs':values[0]===2?'audioMs':'otherMs';
   phases[key]=(phases[key]||0)+performance.now()-at;return result;
  };
  return {exports};
 };
 globalThis.postMessage=(message,options)=>{
  if(message.type==='frame')message.diagnosticPhases={...phases,workerTotalMs:performance.now()-requestAt,previousPostMs};
  const at=performance.now();send(message,options);previousPostMs=performance.now()-at;
 };
}

instrumentWorker();
