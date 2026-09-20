import { test } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { spawn } from 'node:child_process';
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
 assert.deepEqual(config({}), {stage:'local', port:8787, host:'127.0.0.1'});
 assert.equal(config({COORDINATOR_STAGE:'staging'}).stage, 'staging');
 for (const port of ['abc','-1','65536','1.5']) assert.throws(() => config({COORDINATOR_PORT:port}));
 assert.throws(() => config({COORDINATOR_STAGE:'production'}));
});
test('SIGTERM exits a running coordinator cleanly', {timeout:5000}, async () => {
 const child = spawn(process.execPath, ['apps/coordinator/src/main.ts'], {env:{...process.env,COORDINATOR_PORT:'0'}, stdio:['ignore','pipe','pipe']});
 try {
  await once(child.stdout, 'data');
  const ended = once(child, 'exit'); child.kill('SIGTERM');
  assert.deepEqual(await ended, [0, null]);
 } finally { if (child.exitCode === null) child.kill('SIGKILL'); }
});
