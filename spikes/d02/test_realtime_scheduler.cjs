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
  console.log('PASS: full-queue scheduling waits without exceptions, then resumes the same input frame');
})().catch(error=>{console.error(error);process.exitCode=1;});
