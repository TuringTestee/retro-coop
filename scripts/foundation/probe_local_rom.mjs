#!/usr/bin/env node
/** Probe a user-supplied ROM against the pinned native core without bundling it. */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {inspectCartridge} from '../../packages/contracts/src/fingerprint.ts';

const path = process.argv[2];
if (!path || process.argv.length !== 3) {
  console.error('Usage: node scripts/foundation/probe_local_rom.mjs <local.nes>');
  process.exit(1);
}

const rom = readFileSync(path);
const report = {
  romSha256: createHash('sha256').update(rom).digest('hex'),
  bytes: rom.length,
};
try {
  report.cartridge = inspectCartridge(rom);
} catch (error) {
  console.log(JSON.stringify({...report, result: 'invalid', reason: String(error.message)}));
  process.exit(2);
}

const wasm = readFileSync(fileURLToPath(new URL('../../apps/client/src/generated/retro_coop_d02.wasm', import.meta.url)));
const module = await WebAssembly.compile(wasm);
const imports = {};
for (const item of WebAssembly.Module.imports(module)) {
  if (item.kind !== 'function') throw Error(`Unexpected core import: ${item.kind}`);
  (imports[item.module] ??= {})[item.name] = () => { throw Error(`Unexpected host call: ${item.name}`); };
}
const core = (await WebAssembly.instantiate(module, imports)).exports;
const output = kind => new Uint8Array(core.memory.buffer, core.local_output(kind), core.local_output_len()).slice();
const checked = value => {
  if (value !== 1) throw Error(new TextDecoder().decode(output(0)));
};

let loaded = false;
try {
  const ptr = core.local_alloc(rom.length);
  new Uint8Array(core.memory.buffer, ptr, rom.length).set(rom);
  checked(core.local_initialize(ptr, rom.length));
  loaded = true;
  const digest = createHash('sha256').update(wasm).digest();
  const identity = core.local_battery_alloc(digest.length);
  new Uint8Array(core.memory.buffer, identity, digest.length).set(digest);
  checked(core.local_bind_core(identity, digest.length));
  checked(core.local_state_hash());
  const initialHash = Buffer.from(output(0)).toString('hex');
  checked(core.local_state_export());
  const snapshot = output(0);
  for (let frame = 0; frame < 120; frame++) checked(core.local_frame(0, 0));
  checked(core.local_state_hash());
  const playedHash = Buffer.from(output(0)).toString('hex');
  const pixels = output(5);
  if (pixels.length !== 256 * 240 * 4 || !pixels.some(value => value !== 0)) {
    throw Error('The preview is empty or has the wrong dimensions');
  }
  const restore = core.local_state_alloc(snapshot.length);
  new Uint8Array(core.memory.buffer, restore, snapshot.length).set(snapshot);
  checked(core.local_state_import(restore, snapshot.length));
  checked(core.local_state_hash());
  const restoredHash = Buffer.from(output(0)).toString('hex');
  if (playedHash === initialHash || restoredHash !== initialHash) {
    throw Error('Frame advance or state restoration failed');
  }
  console.log(JSON.stringify({...report, result: 'playable', frames: 120, previewPixels: pixels.length, stateRestored: true}));
} catch (error) {
  console.log(JSON.stringify({...report, result: loaded ? 'failed' : 'unsupported', reason: String(error.message)}));
  process.exitCode = 2;
}
