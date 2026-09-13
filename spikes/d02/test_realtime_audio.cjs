// Execute the actual worklet with its browser host mocked, checking output separately.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let Processor;
const messages = [];
vm.runInNewContext(fs.readFileSync(__dirname + '/realtime-audio.js', 'utf8'), {
  Float32Array,
  AudioWorkletProcessor: class { constructor() { this.port = {postMessage: m => messages.push(m)}; } },
  registerProcessor: (name, cls) => { assert.equal(name, 'bounded-audio'); Processor = cls; },
});
const audio = new Processor();
const send = data => audio.port.onmessage({data});
const render = count => { const samples = new Float32Array(count); audio.process([], [[samples]]); return samples; };
send({kind:'begin'});
send({kind:'samples', epoch:0, samples:new Float32Array(12000).fill(0.5)});
assert.equal(audio.size, 12000);
send({kind:'samples', epoch:0, samples:new Float32Array([1])});
assert.equal(audio.stats.overflow, 1);
assert.equal(audio.size, 12000);
assert.equal(render(12000).every(x => x === 0.5), true);
assert.equal(render(128).every(x => x === 0), true);
assert.equal(audio.stats.underrun, 128);
send({kind:'samples', epoch:0, samples:new Float32Array(700).fill(-1)});
send({kind:'flush', epoch:1});
assert.equal(audio.size, 0);
assert.equal(audio.stats.flushed, 700);
send({kind:'samples', epoch:0, samples:new Float32Array(50).fill(-1)});
assert.equal(audio.stats.stale, 50);
assert.equal(audio.size, 0);
send({kind:'samples', epoch:1, samples:new Float32Array(800).fill(1)});
const fresh = render(800);
assert.equal(fresh[0], 0);
assert.ok(fresh[239] > 0.99 && fresh[239] < 1);
assert.equal(fresh[240], 1);
assert.equal(fresh.some(x => x < 0), false);
// Periodic drain acknowledgement continues even when producer is waiting for space.
messages.length = 0;
for (let i = 0; i < 16; i++) render(128);
assert.ok(messages.some(m => m.kind === 'queued' && m.queued === 0));
send({kind:'stop'});
const frozen = {...messages.at(-1)};
render(128);
send({kind:'stats'});
assert.deepEqual({...messages.at(-1)}, frozen);
assert.equal(frozen.received, frozen.played + frozen.flushed + frozen.queued + frozen.overflow);
console.log('PASS: worklet capacity, actual PCM, underrun, epoch flush/fade, stale rejection, drain notification and frozen accounting');
