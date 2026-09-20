async workerPath=>runWorkerProbe(workerPath,async({create,ask,ensure})=>{
   const hex=bytes=>[...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');
   const hash=async bytes=>hex(await crypto.subtle.digest('SHA-256',bytes));
   const worker=create(),rom=await(await fetch('/generated/diagnostic.nes')).arrayBuffer();
   const ready=await ask(worker,{type:'load',rom});ensure(ready.type==='ready','load');
   const phases=[],pixels=[],audio=[],states=[];let audioNonzero=false;
   for(let frame=0;frame<600;frame++){
    const r=await ask(worker,{type:'frame',epoch:'compiler-benchmark-00000000000000',frame,p1:frame%120<60?128:64,p2:frame%80<40?64:128});ensure(r.type==='frame','frame '+r.message);
    phases.push(r.diagnosticPhases);pixels.push(await hash(r.pixels));audio.push(await hash(r.audio));
    audioNonzero ||= new Float32Array(r.audio).some(x=>Number.isFinite(x)&&x!==0);
    if((frame+1)%120===0){const save=await ask(worker,{type:'state-export',requestId:frame+1});ensure(save.type==='state-exported','state export');states.push(await hash(save.bytes.slice(72)));}
   }
   const summarize=list=>Object.fromEntries(Object.keys(list[0]).map(key=>[key,list.reduce((n,row)=>n+row[key],0)/list.length]));
   return {frames:600,fps:ready.fps,core:ready.coreSha256,mean:summarize(phases),steady:summarize(phases.slice(120)),pixels:await hash(new TextEncoder().encode(pixels.join(''))),audio:await hash(new TextEncoder().encode(audio.join(''))),audioNonzero,canonicalPayloads:states};
  })
