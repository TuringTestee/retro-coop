import { config, createCoordinator, shutdown } from './server.ts';
import {listenOperator} from './operator.ts';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
const settings = config(process.env);
if(process.env.COORDINATOR_REQUIRE_CUSTOM_UPLOAD && !['0','1'].includes(process.env.COORDINATOR_REQUIRE_CUSTOM_UPLOAD))throw Error('COORDINATOR_REQUIRE_CUSTOM_UPLOAD must be 0 or 1');
const server = createCoordinator({origins:settings.origins,trustedProxies:settings.trustedProxies,offerCatalogIds:settings.offerCatalogIds,romDirectory:process.env.COORDINATOR_ROM_DIR ?? join(tmpdir(),'retro-coop-rom-store'),requireCustomUpload:process.env.COORDINATOR_REQUIRE_CUSTOM_UPLOAD==='1'});
const operator=process.env.COORDINATOR_OPERATOR_DIR ? await listenOperator(process.env.COORDINATOR_OPERATOR_DIR,server.operator):undefined;
server.on('error', error => { console.error(error.message); process.exitCode = 1;operator?.close();operator?.closeAllConnections();server.stopRooms(); });
server.listen(settings.port, settings.host, () => console.log(JSON.stringify({ event: 'listening', ...settings, port: (server.address() as {port: number}).port })));
let stopping = false;
for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => {
  if (stopping) return;
  stopping = true;
  operator?.close();operator?.closeAllConnections();
  void shutdown(server).catch(error => { console.error(error.message); process.exitCode = 1; });
});
