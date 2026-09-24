import WebSocket from 'ws';
import {createHash, randomUUID} from 'node:crypto';

const base = process.argv[2];
if (!base || !base.startsWith('https://')) throw Error('Pass the local HTTPS edge URL.');
const origin = new URL(base).origin;
const websocket = new URL('/coordinator/ws', base);
websocket.protocol = 'wss:';

async function connect(localAddress, forgedAddress, requestOrigin=origin) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(websocket, {
      origin: requestOrigin,
      localAddress,
      headers: {'X-Forwarded-For': forgedAddress},
      handshakeTimeout: 3000,
    });
    socket.once('open', () => resolve(socket));
    socket.once('error', reject);
  });
}

async function denied(localAddress, forgedAddress, requestOrigin=origin) {
  try {
    const socket = await connect(localAddress, forgedAddress, requestOrigin);
    socket.close();
    throw Error('Unexpected WebSocket admission');
  } catch (error) {
    if (!String(error).includes('Unexpected server response: 403')) throw error;
  }
}

const health = await fetch(new URL('/healthz', base));
if (health.status !== 200 || await health.text() !== 'ok') throw Error('HTTPS edge health failed');
const page = await fetch(new URL('/create', base));
const html = await page.text();
if (page.status !== 200 || !html.includes('<title>Retro Coop</title>')) throw Error('Static page routing failed');
const assetPath = /src="(\/assets\/[^\"]+\.js)"/.exec(html)?.[1];
if (!assetPath) throw Error('Versioned client asset missing');
const asset = await fetch(new URL(assetPath, base));
if (asset.status !== 200 || !asset.headers.get('cache-control')?.includes('immutable')) throw Error('Immutable client asset failed');
await denied('127.0.0.1', '192.0.2.1', 'https://untrusted.example');

const sameAddress = [];
try {
  for (let index=0; index<20; index++) sameAddress.push(await connect('127.0.0.1', `192.0.2.${index+1}`));
  await denied('127.0.0.1', '192.0.2.21');
} finally {
  for (const socket of sameAddress) socket.close();
}

const distinctAddresses = [];
try {
  for (let index=0; index<21; index++) distinctAddresses.push(await connect(`127.0.1.${index+1}`, '203.0.113.200'));
} finally {
  for (const socket of distinctAddresses) socket.close();
}

async function command(socket, value) {
  const requestId = randomUUID();
  const result = new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      socket.off('message', receive);
      reject(Error(`Room command ${value.type} timed out`));
    }, 3000);
    const receive = raw => {
      const event = JSON.parse(raw.toString());
      if (event.type !== 'result' || event.requestId !== requestId) return;
      clearTimeout(timeout);
      socket.off('message', receive);
      if (!event.ok) reject(Error(`Room command ${value.type} failed: ${event.error}`));
      else resolve(event.data);
    };
    socket.on('message', receive);
  });
  socket.send(JSON.stringify({...value, requestId}));
  return result;
}

const rom = Buffer.alloc(16+16384);
rom.set([0x4e,0x45,0x53,0x1a,1,0]);
const fingerprint = {
  romSha256:createHash('sha256').update(rom).digest('hex'),
  coreSha256:'b'.repeat(64),
  localSchema:1,
  settings:'auto-region;zero-ram;48000hz;standard-p1-p2',
  cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:rom.length},
};
const host = await connect('127.0.2.1', '203.0.113.1');
const guest = await connect('127.0.2.2', '203.0.113.2');
try {
  const hostToken = (await command(host, {type:'hello'})).session.token;
  const guestToken = (await command(guest, {type:'hello'})).session.token;
  const intent = randomUUID();
  const room = (await command(host, {type:'create',intent,visibility:'public',fingerprint})).room;
  const romUrl = new URL(`/coordinator/rooms/${room.id}/rom`, base);
  const upload = (bearer, uploadIntent) => fetch(romUrl, {
    method:'PUT',
    headers:{Origin:origin,Authorization:`Bearer ${bearer}`,'X-Room-Intent':uploadIntent,'Content-Type':'application/octet-stream'},
    body:rom,
  });
  const rejectedUpload = await upload('x'.repeat(43), intent);
  if (rejectedUpload.status !== 403) throw Error(`Unauthorized host upload returned ${rejectedUpload.status}; expected 403`);
  const acceptedUpload = await upload(hostToken, intent);
  if (acceptedUpload.status !== 201) throw Error(`Host ROM upload through HTTPS edge returned ${acceptedUpload.status}; expected 201`);
  const published = (await command(host, {type:'confirmCreate',intent})).room;
  const joined = (await command(guest, {type:'join',invite:published.invite,intent:randomUUID()})).room;
  const download = (bearer, membership) => fetch(romUrl, {
    headers:{Origin:origin,Authorization:`Bearer ${bearer}`,'X-Room-Membership':membership},
  });
  const rejectedDownload = await download(hostToken, joined.chatMembership);
  if (rejectedDownload.status !== 403) throw Error(`Unauthorized guest download returned ${rejectedDownload.status}; expected 403`);
  const acceptedDownload = await download(guestToken, joined.chatMembership);
  if (acceptedDownload.status !== 200 || !Buffer.from(await acceptedDownload.arrayBuffer()).equals(rom)) throw Error('Guest ROM download through HTTPS edge differed from upload');
} finally {
  host.close();
  guest.close();
}

console.log(JSON.stringify({https:true,staticRoute:true,versionedAsset:true,originDenied:true,forgedAddressCannotSplitQuota:true,distinctTransportAddressesAdmitted:21,hostUpload:true,guestDownload:true,transferAuthorization:true}));
