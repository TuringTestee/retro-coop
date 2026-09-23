import { test } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { spawn } from 'node:child_process';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import { config, createCoordinator, shutdown } from './server.ts';
test('health is content-free, other routes reject, shutdown closes listener', async () => {
 const server = createCoordinator(); server.listen(0, '127.0.0.1'); await once(server, 'listening');
 const url = `http://127.0.0.1:${(server.address() as {port: number}).port}`;
 try {
  const response = await fetch(url + '/health'); assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {status:'ok', service:'retro-coop-coordinator', protocol:1});
  assert.equal((await fetch(url + '/rooms')).status, 404);
  assert.equal((await fetch(url + '/health', {method:'POST'})).status, 404);
 } finally { await shutdown(server); }
 await assert.rejects(fetch(url + '/health'));
});
test('configuration is explicit and rejects bad ports/stages', () => {
 assert.deepEqual(config({}), {stage:'local', port:8787, host:'127.0.0.1',trustedProxies:[],offerCatalogIds:[],origins:['http://127.0.0.1:5173','http://localhost:5173']});
 assert.equal(config({COORDINATOR_STAGE:'staging',COORDINATOR_ORIGINS:'https://example.test'}).stage, 'staging');
 assert.deepEqual(config({COORDINATOR_EMPTY_OFFERS:'super-tilt-bro-pal,from-below-1.0'}).offerCatalogIds,['super-tilt-bro-pal','from-below-1.0']);
 for(const value of ['unknown','from-below-1.0,from-below-1.0',',from-below-1.0'])assert.throws(()=>config({COORDINATOR_EMPTY_OFFERS:value}));
 for (const port of ['abc','-1','65536','1.5']) assert.throws(() => config({COORDINATOR_PORT:port}));
 assert.throws(() => config({COORDINATOR_STAGE:'production'}));
});
test('SIGTERM exits a running coordinator cleanly', {timeout:5000}, async () => {
 const romDirectory=mkdtempSync(join(tmpdir(),'retro-server-test-roms-'));
 const child = spawn(process.execPath, ['apps/coordinator/src/main.ts'], {env:{...process.env,COORDINATOR_PORT:'0',COORDINATOR_ROM_DIR:romDirectory}, stdio:['ignore','pipe','pipe']});
 try {
  await once(child.stdout, 'data');
  const ended = once(child, 'exit'); child.kill('SIGTERM');
  assert.deepEqual(await ended, [0, null]);
 } finally { if (child.exitCode === null) child.kill('SIGKILL');rmSync(romDirectory,{recursive:true,force:true}); }
});
