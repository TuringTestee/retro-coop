// Load the documented 20-room ceiling through the running loopback edge before public DNS.
import WebSocket from 'ws';
import {createHash, randomUUID} from 'node:crypto';
import {readFileSync} from 'node:fs';
import http from 'node:http';

const origin = 'https://retro-coop.1001.page';
const rom = Buffer.alloc(16 + 16384);
rom.set([0x4e, 0x45, 0x53, 0x1a, 1, 0]);
const fingerprint = {
  romSha256: createHash('sha256').update(rom).digest('hex'),
  coreSha256: 'b'.repeat(64), localSchema: 1,
  settings: 'auto-region;zero-ram;48000hz;standard-p1-p2',
  cartridge: {format: 'iNES', mapper: 0, submapper: 0, region: 'NTSC', bytes: rom.length},
};
const sockets = [];
const command = (socket, value) => new Promise((resolve, reject) => {
  const requestId = randomUUID();
  const timer = setTimeout(() => reject(Error(`Room ${value.type} timed out`)), 5000);
  const receive = raw => {
    const event = JSON.parse(raw.toString());
    if (event.type !== 'result' || event.requestId !== requestId) return;
    clearTimeout(timer);
    socket.off('message', receive);
    if (!event.ok) reject(Error(`Room ${value.type} failed: ${event.error}`));
    else resolve(event.data);
  };
  socket.on('message', receive);
  socket.send(JSON.stringify({...value, requestId}));
});
function connect(ip) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket('ws://127.0.0.1:8080/coordinator/ws', {
      origin, localAddress: ip, headers: {'X-Forwarded-For': ip}, handshakeTimeout: 5000,
    });
    socket.once('open', () => resolve(socket));
    socket.once('error', reject);
  });
}
function upload(roomId, intent, token, ip) {
  return new Promise((resolve, reject) => {
    const request = http.request(`http://127.0.0.1:8080/coordinator/rooms/${roomId}/rom`, {
      method: 'PUT', localAddress: ip, headers: {Origin: origin, Authorization: `Bearer ${token}`,
        'X-Room-Intent': intent, 'Content-Type': 'application/octet-stream',
        'Content-Length': String(rom.length), 'X-Forwarded-For': ip},
    }, response => {
      response.resume();
      response.once('end', () => response.statusCode === 201 ? resolve() : reject(Error(`ROM upload returned ${response.statusCode}`)));
    });
    request.once('error', reject);
    request.end(rom);
  });
}
try {
  for (let index = 1; index <= 20; index++) {
    const ip = `127.0.10.${index}`;
    const socket = await connect(ip);
    sockets.push(socket);
    const token = (await command(socket, {type: 'hello'})).session.token;
    const intent = randomUUID();
    const room = (await command(socket, {type: 'create', intent, visibility: 'public', fingerprint})).room;
    await upload(room.id, intent, token, ip);
    await command(socket, {type: 'confirmCreate', intent});
  }
  const available = /MemAvailable:\s+(\d+) kB/.exec(readFileSync('/proc/meminfo', 'utf8'));
  if (!available) throw Error('Host available memory is not observable');
  console.log('MEMORY_PROOF:' + JSON.stringify({rooms: 20, romBytes: 20 * rom.length,
    availableKiB: Number(available[1]), coordinatorProbeRss: process.memoryUsage().rss}));
} finally {
  sockets.forEach(socket => socket.close());
}
