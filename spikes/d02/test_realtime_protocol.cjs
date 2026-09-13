// Exercise the actual receiver with browser hosts replaced; no network result is inferred.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const node=()=>({connect(other){return other;},frequency:{},gain:{},start(){}});
async function setup(){
  const channel={readyState:'open',bufferedAmount:0,sent:[],send(value){this.sent.push(value);}};
  const context={performance:{now:()=>1000},Float32Array,setTimeout:()=>1,clearTimeout(){},
    document:{querySelector:()=>({})},
    AudioContext:class{constructor(){this.sampleRate=48000;this.audioWorklet={addModule:async()=>{}};}
      createOscillator(){return node();} createGain(){return node();}
      createMediaStreamDestination(){return {stream:{getAudioTracks:()=>[{}]}};}},
    AudioWorkletNode:class{constructor(){this.port={postMessage(){}};}connect(){}},
    RTCPeerConnection:class{addTrack(){}createDataChannel(){return channel;}close(){this.closed=true;}},
    Worker:class{postMessage(){queueMicrotask(()=>this.onmessage({data:{kind:'ready'}}));}},
  };
  context.window=context;
  vm.runInNewContext(fs.readFileSync(__dirname+'/realtime.js','utf8'),context);
  await context.probe.init({role:0,identity:'exact-build-and-ROM',rom64:'',wasm64:''});
  return {probe:context.probe,channel,receive:data=>channel.onmessage({data:typeof data==='string'?data:JSON.stringify(data)})};
}
(async()=>{
  const match=await setup();
  match.channel.onopen();
  assert.deepEqual(JSON.parse(match.channel.sent[0]),{kind:'hello',identity:'exact-build-and-ROM'});
  match.receive({kind:'hello',identity:'exact-build-and-ROM'});
  assert.equal(match.probe.ready,true);
  match.receive({kind:'input',frame:0,mask:255});
  assert.equal(match.probe.remote.get(0),255);
  match.receive({kind:'input',frame:0,mask:255});
  assert.ok(match.probe.stats.errors.includes('Duplicate input'));
  for(const message of [{kind:'input',frame:121,mask:1},{kind:'input',frame:1,mask:256},{kind:'hash',frame:1,hash:'0'.repeat(64)}])match.receive(message);
  assert.equal(match.probe.remote.size,1);
  assert.ok(match.probe.stats.errors.includes('Invalid input range'));
  assert.ok(match.probe.stats.errors.includes('Invalid hash envelope'));
  match.receive('x'.repeat(513));
  assert.ok(match.probe.stats.errors.includes('Input envelope too large'));
  const mismatch=await setup();
  mismatch.receive({kind:'hello',identity:'different-build-or-ROM'});
  assert.equal(mismatch.probe.ready,false);
  assert.equal(mismatch.probe.pc.closed,true);
  assert.ok(mismatch.probe.stats.errors.includes('Fingerprint mismatch'));
  await assert.rejects(()=>mismatch.probe.start(),/Peer\/audio not ready/);
  console.log('PASS: actual hello match/mismatch, bounded input/hash envelopes and duplicate rejection');
})().catch(error=>{console.error(error);process.exitCode=1;});
