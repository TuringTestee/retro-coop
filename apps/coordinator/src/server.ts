import { createServer } from 'node:http';
import { health } from '../../../packages/contracts/src/index.ts';
export function config(env: NodeJS.ProcessEnv) {
  const stage = env.COORDINATOR_STAGE ?? 'local';
  if (!['local', 'staging'].includes(stage)) throw Error('COORDINATOR_STAGE must be local or staging');
  const port = Number(env.COORDINATOR_PORT ?? 8787);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw Error('Invalid COORDINATOR_PORT');
  return { stage, port, host: env.COORDINATOR_HOST ?? '127.0.0.1' };
}
export function createCoordinator() {
  return createServer((request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('Content-Type', 'application/json');
    if (request.url === '/health' && request.method === 'GET') {
      response.writeHead(200).end(JSON.stringify(health));
    } else response.writeHead(404).end(JSON.stringify({ error: 'not_found' }));
  });
}
export async function shutdown(server: ReturnType<typeof createCoordinator>) {
  const deadline = setTimeout(() => server.closeAllConnections(), 2000);
  deadline.unref();
  try { await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
  finally { clearTimeout(deadline); }
}
