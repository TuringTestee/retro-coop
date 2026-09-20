import {admissionAddress,trustedProxyAddresses} from './admission-address.ts';
import {relayConfig} from './peer.ts';
import {peerLimits} from '../../../packages/contracts/src/peer.ts';
import { createServer } from 'node:http';
import { WebSocket, WebSocketServer } from 'ws';
import { health } from '../../../packages/contracts/src/index.ts';
import { parseRoomCommand, ROOM_METADATA_BYTES, type RoomEvent } from '../../../packages/contracts/src/rooms.ts';
import { Rooms, RoomError, limits, type Sender } from './rooms.ts';
export function config(env: NodeJS.ProcessEnv) {
 const stage = env.COORDINATOR_STAGE ?? 'local';
 if (!['local', 'staging'].includes(stage)) throw Error('COORDINATOR_STAGE must be local or staging');
 const port = Number(env.COORDINATOR_PORT ?? 8787);
 if (!Number.isInteger(port) || port < 0 || port > 65535) throw Error('Invalid COORDINATOR_PORT');
 const origins = (env.COORDINATOR_ORIGINS ?? (stage === 'local' ? 'http://127.0.0.1:5173,http://localhost:5173' : '')).split(',').filter(Boolean);
 if(!origins.length || origins.some(origin => {try { const url = new URL(origin);return !['http:','https:'].includes(url.protocol) || url.origin !== origin;}catch{return true;}})) throw Error('Set COORDINATOR_ORIGINS to exact allowed client origins');
 const trustedProxies=trustedProxyAddresses(env.COORDINATOR_TRUSTED_PROXIES ? env.COORDINATOR_TRUSTED_PROXIES.split(','):[]);
 return { stage, port, host: env.COORDINATOR_HOST ?? '127.0.0.1',origins,trustedProxies };
}
export function createCoordinator(options: {origins?:string[]; rooms?:Rooms; trustedProxies?:string[]} = {}) {
 const rooms = options.rooms ?? new Rooms(Date.now,undefined,relayConfig(process.env));
 const origins = new Set(options.origins ?? config({}).origins);
 const trustedProxies=new Set(trustedProxyAddresses(options.trustedProxies ?? []));
 const server = createServer((request, response) => {
  response.setHeader('Cache-Control', 'no-store');response.setHeader('Content-Type', 'application/json');response.setHeader('Referrer-Policy','no-referrer');
  if (request.url === '/health' && request.method === 'GET') response.writeHead(200).end(JSON.stringify(health));
  else response.writeHead(404).end(JSON.stringify({ error: 'not_found' }));
 });
 const sockets = new WebSocketServer({noServer:true,maxPayload:peerLimits.frame,perMessageDeflate:false});
 // The transport peer owns address identity unless an explicit trusted proxy boundary applies.
 const admission = new Map<string,{times:number[];active:number}>();
 server.on('upgrade',(request,socket,head) => {
  const address=admissionAddress(request.socket.remoteAddress,request.headers['x-forwarded-for'],trustedProxies),now=Date.now();
  if(!address) {socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');return;}
  for(const [key,item] of admission) if(!item.active && item.times.every(time => time <= now-60_000)) admission.delete(key);
  const record = admission.get(address) ?? {times:[],active:0};record.times = record.times.filter(time => time > now-60_000);
  if(!origins.has(request.headers.origin ?? '') || !['/ws','/coordinator/ws'].includes(request.url ?? '') || sockets.clients.size >= limits.connections || record.active >= 20 || record.times.length >= 30 || (!admission.has(address) && admission.size >= 1000)) {socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');return;}
  record.times.push(now);admission.set(address,record);
  sockets.handleUpgrade(request,socket,head,ws => {record.active++;ws.once('close',()=>record.active--);sockets.emit('connection',ws);});
 });
 sockets.on('connection',ws => {
  let token:string|undefined;
  let windowStarted = Date.now(), received = 0;
  const send:Sender = (event:RoomEvent) => {if(ws.readyState !== WebSocket.OPEN) return;if(ws.bufferedAmount > 64*1024) {ws.terminate();return;}ws.send(JSON.stringify(event));};
  const authDeadline = setTimeout(()=>ws.close(1008,'Authenticate first'),5000);authDeadline.unref();
  ws.on('error',()=>{}); // Protocol errors close the socket; content is never logged.
  ws.on('message',(raw,binary) => {
   if(Date.now()-windowStarted >= 10_000) {windowStarted = Date.now();received = 0;}
   if(++received > 120) {ws.close(1008,'Message rate exceeded');return;}
   let command;
   try {if(!binary) command = parseRoomCommand(JSON.parse(raw.toString()));}catch{}
   if(Buffer.byteLength(raw.toString())>ROOM_METADATA_BYTES && command?.type!=='peerSignal') {ws.close(1009,'Message too large');return;}
   if(!command) {ws.close(1008,'Invalid room message');return;}
   try {
    let data;
    if(command.type === 'hello') {
     if(token) throw new RoomError('already_authenticated');
     const attached = rooms.attach(command.token,send,()=>ws.close(1000,'Session replaced or expired'),command.policy);
     token = attached.token;data = attached.data;clearTimeout(authDeadline);
    } else {if(!token) throw new RoomError('authenticate_first');data = rooms.handle(token,command,send);}
    send({type:'result',requestId:command.requestId,ok:true,data});
   } catch(error) { const failure = error instanceof RoomError ? error:new RoomError('server_error');send({type:'result',requestId:command.requestId,ok:false,error:failure.code,...(failure.retryAfterMs ? {retryAfterMs:failure.retryAfterMs}:{})}); }
  });
  ws.once('close',()=>{clearTimeout(authDeadline);if(token) rooms.detach(token,send);});
 });
 const timer = setInterval(()=>rooms.sweep(),1000);timer.unref();
 const stop = () => {clearInterval(timer);rooms.stop();for(const client of sockets.clients) client.terminate();sockets.close();};
 server.once('close',stop);
 return Object.assign(server,{stopRooms:stop});
}
export async function shutdown(server: ReturnType<typeof createCoordinator>) {
 server.stopRooms();
 const deadline = setTimeout(() => server.closeAllConnections(), 2000);deadline.unref();
 try { await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
 finally { clearTimeout(deadline); }
}
