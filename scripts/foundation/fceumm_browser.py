#!/usr/bin/env python3
"""Exercise the real worker's OSS boundary; public lobby proof is a separate gate."""
import argparse
import json
import runpy
import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''async rom=>{
 let retained=false;const workers=[];const queues=new Map();let serial=0;
 const open=()=>{const worker=new Worker('/src/worker.ts',{type:'module'});workers.push(worker);const queue=new Map();queues.set(worker,queue);
  worker.onmessage=({data})=>{const key=data.requestId??queue.keys().next().value;const pending=queue.get(key);if(!pending)return;queue.delete(key);clearTimeout(pending.timer);pending.resolve(data);};worker.onerror=event=>{for(const p of queue.values()){clearTimeout(p.timer);p.reject(Error(event.message));}queue.clear();};return worker;};
 const request=(worker,data)=>new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('Worker boundary timed out')),12000);
  queues.get(worker).set(data.requestId,{resolve,reject,timer});worker.postMessage(data);
 });
 const expect=(result,type)=>{if(result.type!==type)throw Error(JSON.stringify(result));return result;};
 const rpc=(worker,type,extra={})=>request(worker,{type,requestId:++serial,...extra});
 const hex=bytes=>Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
 const digest=async bytes=>new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
 function fields(envelope){
  const bytes=new Uint8Array(envelope),view=new DataView(envelope),out=new Map();let p=88;
  while(p<bytes.length){const end=p+5+view.getUint32(p+1,true);p+=5;while(p<end){const tag=String.fromCharCode(...bytes.slice(p,p+4)).replace(/\0+$/,'');const n=view.getUint32(p+4,true);out.set(tag,{offset:p+8,length:n,header:p});p+=8+n;}}
  return out;
 }
 const repairDigest=async bytes=>{bytes.set(await digest(bytes.slice(72)),40);return bytes.buffer;};
 try{
  const a=open(),b=open();const readyA=expect(await rpc(a,'load',{rom:new Uint8Array(rom).buffer}),'ready'),readyB=expect(await rpc(b,'load',{rom:new Uint8Array(rom).buffer}),'ready');
  if(readyA.coreSha256!==readyB.coreSha256)throw Error('Backend fingerprints differ');
  const before=expect(await rpc(a,'state-hash'),'state-hash');expect(await rpc(a,'state-preview'),'state-preview');const after=expect(await rpc(a,'state-hash'),'state-hash');if(before.info.hash!==after.info.hash||!after.info.fresh)throw Error('Preview changed starting state');
  for(let frame=0;frame<240;frame++){expect(await rpc(a,'frame',{p1:1,p2:2}),'frame');expect(await rpc(b,'frame',{p1:1,p2:2}),'frame');}
  const saved=expect(await rpc(a,'state-capture'),'state-captured'),peer=expect(await rpc(b,'state-capture'),'state-captured');if(saved.hash!==peer.hash)throw Error('Paired hardware state differs');
  const f=fields(saved.bytes),ram=f.get('RAM'),raw=new Uint8Array(saved.bytes);
  if(raw[ram.offset]!==128||raw[ram.offset+1]!==64||raw[ram.offset+2]===0)throw Error('Original diagnostic did not execute native P1/P2 controls');
  let frameBytes=0,audioBytes=0;
  for(let frame=0;frame<180;frame++){const out=expect(await rpc(a,'frame',{p1:frame%2?129:0,p2:frame%3?66:0}),'frame');frameBytes=out.pixels.byteLength;audioBytes+=out.audio.byteLength;}
  const later=expect(await rpc(a,'state-capture'),'state-captured');expect(await rpc(a,'state-import',{bytes:saved.bytes}),'state-imported');
  for(let frame=0;frame<180;frame++)expect(await rpc(a,'frame',{p1:frame%2?129:0,p2:frame%3?66:0}),'frame');
  const replay=expect(await rpc(a,'state-capture'),'state-captured');if(later.hash!==replay.hash)throw Error('Restore replay diverged');
  const rewound=expect(await rpc(a,'state-rewind',{seconds:1}),'state-rewound');
  if(rewound.pixels.byteLength!==256*240*4||new Uint8Array(rewound.pixels)[3]!==255||rewound.info.maxSeconds!==10||rewound.info.peakBytes>rewound.info.budgetBytes)throw Error('Rewind failed its image or memory contract');
  expect(await rpc(a,'state-import',{bytes:replay.bytes}),'state-imported');
  const failures=[];
  const corrupt=async(name,mutate)=>{
   const bytes=new Uint8Array(replay.bytes.slice(0));mutate(bytes,fields(bytes.buffer));await repairDigest(bytes);
   const rejected=expect(await rpc(a,'state-import',{bytes:bytes.buffer}),'state-error');const retained=expect(await rpc(a,'state-hash'),'state-hash');if(retained.info.hash!==replay.hash)throw Error(name+' mutated live state');failures.push({name,error:rejected.message});
  };
  for(const [tag,value] of [['E0DV',255],['5BIT',255],['PROT',16],['TBTG',1],['IQFM',128]])await corrupt(tag,(bytes,f)=>{bytes[f.get(tag).offset]=value;});
  for(const [tag,value] of [['RCD1',2147483647],['TRIS',-1],['CBC5',2147483647],['SNTS',2147483647],['IQLB',16],['WAVE',2147483647]])await corrupt(tag,(bytes,f)=>{new DataView(bytes.buffer).setInt32(f.get(tag).offset,value,true);});
  await corrupt('filter-overflow',(bytes,f)=>new DataView(bytes.buffer).setBigInt64(f.get('FAC1').offset,(1n<<63n)-1n,true));
  await corrupt('unknown-tag',(bytes,f)=>bytes.set(new TextEncoder().encode('EVIL'),f.get('MODE').header));
  await corrupt('duplicate-tag',(bytes,f)=>bytes.set(new TextEncoder().encode('MODE'),f.get('MIRR').header));
  await corrupt('field-size',(bytes,f)=>new DataView(bytes.buffer).setUint32(f.get('MODE').header+4,0xffffffff,true));
  for(const [name,bytes] of [['truncated',replay.bytes.slice(0,-1)],['over-limit',new Uint8Array(2*1024*1024+1).buffer],['identity',(()=>{const b=new Uint8Array(replay.bytes.slice(0));b[8]^=1;return b.buffer;})()]]){
   expect(await rpc(a,'state-import',{bytes}),'state-error');if(expect(await rpc(a,'state-hash'),'state-hash').info.hash!==replay.hash)throw Error(name+' mutated live state');failures.push({name});
  }
  const unsupported=new Uint8Array(rom);unsupported[6]=0;unsupported[7]=0xe0;
  expect(await rpc(a,'load',{rom:unsupported.buffer}),'error');
  if(expect(await rpc(a,'state-hash'),'state-hash').info.hash!==replay.hash)throw Error('Failed cartridge replacement changed active progress');
  const op='o'.repeat(22),epoch='e'.repeat(22);
  expect(await rpc(a,'peer-checkpoint-prepare',{operationId:op,epoch,frame:saved.frame,bytes:saved.bytes,identity:saved.identity,hash:saved.hash,transactionId:op}),'peer-checkpoint-prepared');
  expect(await rpc(a,'peer-checkpoint-commit',{operationId:op}),'peer-checkpoint-imported');expect(await rpc(a,'peer-checkpoint-rollback',{operationId:op}),'peer-checkpoint-rolled-back');
  if(expect(await rpc(a,'state-hash'),'state-hash').info.hash!==replay.hash)throw Error('Shared rollback lost prior progress');
  const pending=rpc(a,'peer-checkpoint-prepare',{operationId:op,epoch,frame:saved.frame,bytes:saved.bytes,identity:saved.identity,hash:saved.hash,transactionId:op});
  const cancelled=rpc(a,'peer-checkpoint-cancel',{operationId:op});
  const messages=await Promise.all([pending,cancelled]);
  if(!messages.some(m=>m.type==='peer-checkpoint-cancelled')||!messages.some(m=>m.type==='peer-checkpoint-error'))throw Error('Cancellation accepted stale preparation');
  expect(await rpc(a,'peer-checkpoint-commit',{operationId:op}),'peer-checkpoint-error');
  if(expect(await rpc(a,'state-hash'),'state-hash').info.hash!==replay.hash)throw Error('Cancelled prepare changed active progress');
  expect(await rpc(a,'frame',{p1:1,p2:2}),'frame');
  expect(await rpc(a,'peer-checkpoint-prepare',{operationId:op,epoch,frame:saved.frame,bytes:saved.bytes,identity:saved.identity,hash:saved.hash,transactionId:op}),'peer-checkpoint-prepared');
  expect(await rpc(a,'peer-checkpoint-commit',{operationId:op}),'peer-checkpoint-imported');
  expect(await rpc(a,'peer-checkpoint-finish',{operationId:op}),'peer-checkpoint-finished');
  expect(await rpc(a,'state-import',{bytes:replay.bytes}),'state-imported');
  window.boundaryHold={worker:a,bytes:replay.bytes,hash:replay.hash,rpc,expect};retained=true;b.terminate();
  return {backend:readyA.coreSha256,pairedFrames:240,nativeRam:[raw[ram.offset],raw[ram.offset+1],raw[ram.offset+2]],stateBytes:saved.bytes.byteLength,replayFrames:180,frameBytes,audioBytes,failures,sharedRollback:true,cancelledPrepare:true,cancelledTransactionResumedAndRetried:true,failedReplacementPreserved:true,rewindPreserved:true};
 }finally{if(!retained)workers.forEach(worker=>worker.terminate());}
}'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='Reuse an owned Vite server; otherwise launch an isolated one')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Existing original diagnostic, with an ordinary mapper-225 header. This is
    # test cartridge data, not board/emulation code or a third-party ROM.
    rom = bytearray(runpy.run_path(str(ROOT / 'spikes/d02/original_fixture.py'))['build']())
    rom[6] = 0x10
    rom[7] = 0xe0
    server = None
    try:
        if not args.url:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                port = probe.getsockname()[1]
            args.url = f'http://127.0.0.1:{port}'
            server = subprocess.Popen(['npm', 'run', 'dev', '-w', '@retro-coop/client', '--', '--port', str(port)],
                                      cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            deadline = time.monotonic() + 15
            while True:
                try:
                    urllib.request.urlopen(args.url, timeout=1).close()
                    break
                except OSError:
                    if server.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('Isolated boundary server did not start')
                    time.sleep(0.1)
        with sync_playwright() as p:
            browser = p.chromium.launch(ignore_default_args=['--mute-audio'])
            page = browser.new_page()
            page.goto(args.url)
            result = page.evaluate(SCRIPT, list(rom))
            # Fault the *candidate* worker's module, never the active machine. A
            # genuine infinite loop must be killed by the application's watchdog.
            page.route('**/fceumm-instance.ts*', lambda route: route.fulfill(
                status=200, content_type='application/javascript', body='while(true){}'))
            result['boundedCandidateFailure'] = page.evaluate(r"""async()=>{
     const h=window.boundaryHold,started=performance.now();
     const rejected=h.expect(await h.rpc(h.worker,'state-import',{bytes:h.bytes}),'state-error');
     const retained=h.expect(await h.rpc(h.worker,'state-hash'),'state-hash');h.worker.terminate();
     if(retained.info.hash!==h.hash||!rejected.message.includes('execution limit'))throw Error('Candidate timeout changed active progress');
     return {error:rejected.message,seconds:(performance.now()-started)/1000,activeHashPreserved:true};
    }""")
            browser.close()
    finally:
        if server is not None:
            os.killpg(server.pid, signal.SIGTERM)
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGKILL)
                server.wait()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
