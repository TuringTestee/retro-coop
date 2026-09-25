import WebSocket from 'ws';

const base = process.argv[2];
if (!base?.startsWith('http://')) throw Error('Pass local Caddy HTTP URL.');
const health = await fetch(new URL('/healthz', base));
if (health.status !== 200 || !(await health.text()).includes('retro-coop')) throw Error('Caddy did not reach the loopback edge');
const websocket = new URL('/coordinator/ws', base);
websocket.protocol = 'ws:';
function connect(localAddress, forgedAddress, expected=101) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(websocket, {
      origin:'https://retro-coop.1001.page', localAddress,
      headers:{'X-Forwarded-For': forgedAddress}, handshakeTimeout:3000,
    });
    if (expected === 101) {
      socket.once('open', () => resolve(socket));
      socket.once('error', reject);
    } else {
      socket.once('open', () => reject(Error('Caller-supplied forwarding header split a Caddy quota')));
      socket.once('error', error => {
        if (String(error).includes(`Unexpected server response: ${expected}`)) resolve(null);
        else reject(error);
      });
    }
  });
}
const same = [];
try {
  for (let i=0; i<6; i++) same.push(await connect('127.0.5.1', `198.51.100.${i+1}`));
  await connect('127.0.5.1', '198.51.100.7', 429);
  const another = await connect('127.0.5.2', '198.51.100.1');
  another.close();
} finally {
  same.forEach(socket => socket.close());
}
console.log(JSON.stringify({caddyToLoopbackEdge:true,forgedForwardingRejected:true,distinctPeerAdmitted:true}));
