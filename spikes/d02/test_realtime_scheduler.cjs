const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = {performance:{now:()=>1000}, Float32Array, setTimeout:fn=>{context.tick=fn;return 1;}};
context.window=context;
vm.runInNewContext(fs.readFileSync(__dirname+'/realtime.js','utf8'),context);
const probe=context.probe;
let steps=0;
Object.assign(probe,{ready:true,audio:{state:'running'},sink:{port:{postMessage(){}}},
  stats:{seconds:600,errors:[],audioBackpressurePolls:0,stalls:0},initial:0,
  local:new Map(),remote:new Map([[0,0]]),frame:0,limit:36060,audioQueued:8100,
  localMask:()=>0,send(){},worker:{postMessage(){steps++;}}});
(async()=>{
  await probe.start();
  assert.equal(probe.stats.errors.length,0);
  assert.equal(probe.stats.audioBackpressurePolls,1);
  assert.equal(steps,0);
  context.performance.now=()=>2000;
  context.tick();
  assert.equal(steps,0);
  probe.audioQueued=0;
  context.tick();
  assert.equal(steps,1);
  assert.equal(probe.stats.errors.length,0);
  // A 3 ms timer cadence exposed cumulative drift: the old elapsed-relative timer
  // recorded only 598 observations during a full 600 seconds.
  probe.busy=false;probe.audioQueued=8100;probe.frame=0;
  probe.stats.voiceLevels=[];probe.stats.voiceFrequencyHz=[];probe.stats.voiceMissedSlots=0;
  probe.analyser={getFloatTimeDomainData(samples){samples.fill(0.02);}};
  context.performance.now=()=>1000;
  await probe.start();
  for(let elapsed=3;elapsed<=600000;elapsed+=3){context.performance.now=()=>1000+elapsed;context.tick();}
  assert.equal(probe.stats.voiceLevels.length,600);
  assert.equal(probe.stats.voiceMissedSlots,0);
  context.performance.now=()=>605000;context.tick();
  assert.equal(probe.stats.voiceLevels.length,601);
  assert.equal(probe.stats.voiceMissedSlots,3);
  console.log('PASS: bounded scheduling resumes identical inputs; absolute voice slots avoid drift and expose missed samples');
})().catch(error=>{console.error(error);process.exitCode=1;});
