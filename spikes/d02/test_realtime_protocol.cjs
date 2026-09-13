// Exercise the actual receiver with browser hosts replaced; no network result is inferred.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const node=()=>({connections:[],connect(other){this.connections.push(other);return other;},frequency:{},gain:{value:1,setValueAtTime(value){this.value=value;}},start(){},fftSize:2048,getFloatTimeDomainData(a){a.fill(0);}});
async function setup(){
  const controls=new Map();
  const channel={readyState:'open',bufferedAmount:0,sent:[],send(value){this.sent.push(value);}};
  const context={performance:{now:()=>1000},Float32Array,setTimeout:()=>1,clearTimeout(){},
    setInterval:()=>1,document:{querySelector:selector=>{if(!controls.has(selector))controls.set(selector,{});return controls.get(selector);},createElement:()=>({play:async()=>{}}),body:{append(){}}},
    AudioContext:class{constructor(){this.sampleRate=48000;this.destination=node();this.currentTime=0;this.audioWorklet={addModule:async()=>{}};}
      createOscillator(){return node();} createGain(){return node();} createAnalyser(){return node();} createMediaStreamSource(){return node();}
      createMediaStreamDestination(){return {stream:{getAudioTracks:()=>[{}]}};}},
    AudioWorkletNode:class{constructor(){this.port={postMessage(){}};}connect(other){this.destination=other;}},
    RTCPeerConnection:class{addTrack(){}createDataChannel(){return channel;}close(){this.closed=true;}},
    Worker:class{postMessage(){queueMicrotask(()=>this.onmessage({data:{kind:'ready'}}));}},
  };
  context.window=context;
  vm.runInNewContext(fs.readFileSync(__dirname+'/realtime.js','utf8'),context);
  await context.probe.init({role:0,identity:'exact-build-and-ROM',rom64:'',wasm64:''});
  return {probe:context.probe,controls,channel,receive:data=>channel.onmessage({data:typeof data==='string'?data:JSON.stringify(data)})};
}
(async()=>{
  const match=await setup();
  assert.equal(match.probe.output.gain.value,0);
  const sound=match.controls.get('#sound');
  assert.equal(sound.checked,false);
  assert.equal(match.probe.sink.destination,match.probe.output);
  assert.equal(match.probe.output.connections[0],match.probe.outputMeter);
  assert.equal(match.probe.outputMeter.connections[0],match.probe.audio.destination);
  match.probe.pc.ontrack({streams:[{}]});
  assert.equal(match.probe.remoteElement.volume,0);
  assert.equal(match.probe.remoteVoice.connections[0],match.probe.analyser);
  assert.equal(match.probe.analyser.connections[0],match.probe.output);
  sound.checked=true;sound.onchange();assert.equal(match.probe.output.gain.value,1);
  sound.checked=false;sound.onchange();assert.equal(match.probe.output.gain.value,0);
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
  const selection=await setup();
  const report=new Map([
    ['transport',{type:'transport',selectedCandidatePairId:'selected'}],
    ['selected',{id:'selected',type:'candidate-pair',state:'in-progress',nominated:true,localCandidateId:'local',remoteCandidateId:'remote',bytesSent:10,bytesReceived:20}],
    ['unused',{id:'unused',type:'candidate-pair',state:'succeeded',nominated:false,localCandidateId:'local',remoteCandidateId:'remote'}],
    ['local',{protocol:'udp',candidateType:'host'}],['remote',{protocol:'udp',candidateType:'prflx'}]
  ]);
  let snapshots=0;selection.probe.pc.getStats=async()=>{snapshots++;return report;};
  selection.probe.sink.port.postMessage=()=>selection.probe.audioStatsResolve();
  selection.probe.stats.hashes=[];selection.probe.stats.rttMs=[];
  const measured=await selection.probe.result();
  assert.equal(snapshots,1);
  assert.equal(measured.rtc.filter(s=>s.type==='candidate-pair').length,1);
  assert.equal(measured.rtc[0].remote.candidateType,'prflx');
  assert.equal(measured.rtc[0].selected,true);
  assert.equal(measured.rtc[0].state,'in-progress');
  assert.equal(measured.outputMuted,true);assert.equal(measured.outputPeak,0);
  console.log('PASS: actual hello match/mismatch, bounded input/hash envelopes and duplicate rejection');
})().catch(error=>{console.error(error);process.exitCode=1;});
