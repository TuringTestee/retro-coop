import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validFingerprint,matchesFile,type Fingerprint} from './fingerprint.ts';
const exact:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'NES 2.0',mapper:4095,submapper:15,region:'Dendy',bytes:9*1024*1024}};
test('shared fingerprint preserves exact file, emulator, schema and settings identity',()=>{
 assert.ok(validFingerprint(exact));assert.ok(matchesFile(exact,{...exact}));
 for(const changed of [{romSha256:'c'.repeat(64)},{coreSha256:'c'.repeat(64)},{localSchema:2},{settings:'different'}]) {
  assert.equal(matchesFile(exact,{...exact,...changed} as Fingerprint),false);
 }
 for(const changed of [{coreSha256:'bad'},{localSchema:2},{settings:'different'},{filename:'private.nes'},{cartridge:{...exact.cartridge,mapper:4096}}]) assert.equal(validFingerprint({...exact,...changed}),false);
});
