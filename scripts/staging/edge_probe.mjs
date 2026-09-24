import WebSocket from 'ws';

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

console.log(JSON.stringify({https:true,staticRoute:true,versionedAsset:true,originDenied:true,forgedAddressCannotSplitQuota:true,distinctTransportAddressesAdmitted:21}));
