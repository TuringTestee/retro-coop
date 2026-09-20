import { config, createCoordinator, shutdown } from './server.ts';
const settings = config(process.env);
const server = createCoordinator();
server.on('error', error => { console.error(error.message); process.exitCode = 1; });
server.listen(settings.port, settings.host, () => console.log(JSON.stringify({ event: 'listening', ...settings, port: (server.address() as {port: number}).port })));
let stopping = false;
for (const signal of ['SIGINT', 'SIGTERM'] as const) process.on(signal, () => {
  if (stopping) return;
  stopping = true;
  void shutdown(server).catch(error => { console.error(error.message); process.exitCode = 1; });
});
