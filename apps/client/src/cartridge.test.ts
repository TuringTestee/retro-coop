import test from 'node:test';
import assert from 'node:assert/strict';
import {inspectCartridge, neutralDefaults} from './cartridge.ts';
function fixture() { const bytes = new Uint8Array(16+16384); bytes.set([78,69,83,26,1]); return bytes; }
test('admission is structural, accepts unknown mapper metadata and large valid files',() => {
 const bytes = fixture(); bytes[6] = 0x20;
 assert.equal(inspectCartridge(bytes).mapper,2);
 const large = new Uint8Array(9*1024*1024); large.set(bytes); large[7] = 8;
 assert.equal(inspectCartridge(large).format,'NES 2.0');
 assert.equal(inspectCartridge(large).bytes,large.length);
 const changed = bytes.slice(); changed[7] = 0xf0;
 assert.equal(inspectCartridge(changed).mapper,242); // Core, not a title or mapper allowlist, determines support.
});
test('malformed header, truncation and impossible NES2 exponent sizes fail locally',() => {
 assert.throws(() => inspectCartridge(new Uint8Array()),/not an NES/);
 const bytes = fixture();
 assert.throws(() => inspectCartridge(bytes.slice(0,20)),/incomplete/);
 bytes[7] = 8; bytes[9] = 15; bytes[4] = 252;
 assert.throws(() => inspectCartridge(bytes),/incomplete/);
});
test('neutral defaults depend only on random values, never cartridge data',() => {
 assert.deepEqual(neutralDefaults(new Uint32Array([1,2])),{guest:'Guest Azure 1',room:'Amber Harbor'});
});
