import {admissionAddress,trustedProxyAddresses} from './admission-address.ts';
import {randomBytes} from 'node:crypto';
import {operatorHandler} from './operator.ts';
import {relayConfig} from './peer.ts';
import {peerLimits} from '../../../packages/contracts/src/peer.ts';
import { createServer } from 'node:http';
import { WebSocket, WebSocketServer } from 'ws';
import { health } from '../../../packages/contracts/src/index.ts';
import { parseRoomCommand, ROOM_METADATA_BYTES, type RoomEvent } from '../../../packages/contracts/src/rooms.ts';
import { Rooms, RoomError, limits, type Sender } from './rooms.ts';
import {catalog,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {RomStore,type RomLimits} from './rom-store.ts';
import {token as validToken} from '../../../packages/contracts/src/protocol-validation.ts';
export function config(env: NodeJS.ProcessEnv) {
 const stage = env.COORDINATOR_STAGE ?? 'local';
 if (!['local', 'staging'].includes(stage)) throw Error('COORDINATOR_STAGE must be local or staging');
 const port = Number(env.COORDINATOR_PORT ?? 8787);
 if (!Number.isInteger(port) || port < 0 || port > 65535) throw Error('Invalid COORDINATOR_PORT');
 const origins = (env.COORDINATOR_ORIGINS ?? (stage === 'local' ? 'http://127.0.0.1:5173,http://localhost:5173' : '')).split(',').filter(Boolean);
 if(!origins.length || origins.some(origin => {try { const url = new URL(origin);return !['http:','https:'].includes(url.protocol) || url.origin !== origin;}catch{return true;}})) throw Error('Set COORDINATOR_ORIGINS to exact allowed client origins');
 const trustedProxies=trustedProxyAddresses(env.COORDINATOR_TRUSTED_PROXIES ? env.COORDINATOR_TRUSTED_PROXIES.split(','):[]);
 const offerCatalogIds=env.COORDINATOR_EMPTY_OFFERS ? env.COORDINATOR_EMPTY_OFFERS.split(',') : [];
 if(new Set(offerCatalogIds).size!==offerCatalogIds.length || offerCatalogIds.some(id=>!catalog.some(entry=>entry.id===id)))throw Error('COORDINATOR_EMPTY_OFFERS must list unique included game IDs');
 return { stage, port, host: env.COORDINATOR_HOST ?? '127.0.0.1',origins,trustedProxies,offerCatalogIds:offerCatalogIds as CatalogId[] };
}
export function createCoordinator(options: {origins?:string[]; trustedProxies?:string[]; offerCatalogIds?:readonly CatalogId[]; now?:()=>number; romDirectory?:string; romLimits?:RomLimits; requireCustomUpload?:boolean} = {}) {
 const store=new RomStore(options.romDirectory,options.romLimits);
 const rooms = new Rooms(options.now??Date.now,undefined,relayConfig(process.env),options.offerCatalogIds,{requireCustomUpload:options.requireCustomUpload??false,discard:id=>store.discard(id)});
 const origins = new Set(options.origins ?? config({}).origins);
 const trustedProxies=new Set(trustedProxyAddresses(options.trustedProxies ?? []));
 const now=options.now??Date.now;
 const transferAttempts=new Map<string,number[]>();
 const server = createServer((request, response) => {
  response.setHeader('Cache-Control', 'no-store');response.setHeader('Content-Type', 'application/json');response.setHeader('Referrer-Policy','no-referrer');
  const origin=request.headers.origin;
  const upload=/^\/rooms\/([A-Za-z0-9_-]{43})\/rom$/.exec(request.url ?? '');
  if(upload && (request.method==='PUT'||request.method==='OPTIONS')) {
   if(!origin || !origins.has(origin)){response.writeHead(403).end(JSON.stringify({error:'origin_denied'}));return;}
   response.setHeader('Access-Control-Allow-Origin',origin);response.setHeader('Vary','Origin');
   response.setHeader('Access-Control-Allow-Methods','PUT, OPTIONS');response.setHeader('Access-Control-Allow-Headers','Authorization, Content-Type, X-Room-Intent');
   if(request.method==='OPTIONS'){response.writeHead(204).end();return;}
   const address=admissionAddress(request.socket.remoteAddress,request.headers['x-forwarded-for'],trustedProxies);
   if(!address){response.writeHead(403).end(JSON.stringify({error:'admission_denied'}));return;}
   const recent=(transferAttempts.get(address)??[]).filter(time=>time>now()-60_000);
   if(recent.length>=30 || (!transferAttempts.has(address)&&transferAttempts.size>=1000)){response.writeHead(429).end(JSON.stringify({error:'rate_limited'}));return;}
   recent.push(now());transferAttempts.set(address,recent);
   const authorization=/^Bearer ([A-Za-z0-9_-]{43})$/.exec(request.headers.authorization ?? '');
   const intent=request.headers['x-room-intent'];
   const length=request.headers['content-length'];
   if(!authorization || typeof intent!=='string' || !validToken(intent) || !length || !/^[0-9]+$/.test(length) || request.headers['content-type']!=='application/octet-stream' || request.headers['transfer-encoding']) {
    response.writeHead(400).end(JSON.stringify({error:'invalid_upload_request'}));return;
   }
   void store.upload(rooms,authorization[1],upload[1],intent,Number(length),request).then(result=>{
    if(!response.destroyed)response.writeHead(201).end(JSON.stringify(result));
   },error=>{
    if(response.destroyed)return;
    const code=error instanceof RoomError?error.code:'server_error';
    const status=code==='session_expired'||code==='host_only'||code==='host_disconnected'?403:code==='upload_capacity'||code==='rate_limited'?429:code==='upload_size_limit'?413:code==='server_error'?500:400;
    response.writeHead(status).end(JSON.stringify({error:code}));
   });
   return;
  }
  if (request.url === '/health' && request.method === 'GET') response.writeHead(200).end(JSON.stringify(health));
  else response.writeHead(404).end(JSON.stringify({ error: 'not_found' }));
 });
 const sockets = new WebSocketServer({noServer:true,maxPayload:peerLimits.frame,perMessageDeflate:false});
 // The transport peer owns address identity unless an explicit trusted proxy boundary applies.
 const admission = new Map<string,{id:string;times:number[];clients:Set<WebSocket>;revision:number;blockedUntil:number}>();
 const revokers=new Map<WebSocket,()=>void>();
 const sweepAdmission=()=>{for(const [key,item] of admission)if(!item.clients.size && item.blockedUntil<=now() && item.times.every(time=>time<=now()-60_000))admission.delete(key);};
 const operator=operatorHandler({
  rooms:()=>rooms.operatorRooms(),remove:id=>rooms.removeRoom(id),
  subjects:()=>{sweepAdmission();return [...admission].filter(([,item])=>item.clients.size || item.blockedUntil>now()).map(([address,item])=>({id:item.id,address,connections:item.clients.size,revision:item.revision,...(item.blockedUntil>now()?{blockedUntil:item.blockedUntil}:{})}));},
  block:(id,revision,seconds)=>{
   const item=[...admission.values()].find(item=>item.id===id);
   if(!item?.clients.size || item.revision!==revision)throw Error('Admission subject changed; review it again');
   item.blockedUntil=now()+seconds*1000;
   for(const ws of item.clients){revokers.get(ws)?.();ws.close(4003,'Admission temporarily blocked');}
  },
 },now);
 server.on('upgrade',(request,socket,head) => {
  const address=admissionAddress(request.socket.remoteAddress,request.headers['x-forwarded-for'],trustedProxies),timestamp=now();
  if(!address) {socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');return;}
  sweepAdmission();
  const record = admission.get(address) ?? {id:randomBytes(24).toString('base64url'),times:[],clients:new Set<WebSocket>(),revision:0,blockedUntil:0};record.times=record.times.filter(time=>time>timestamp-60_000);
  if(!origins.has(request.headers.origin ?? '') || !['/ws','/coordinator/ws'].includes(request.url ?? '') || sockets.clients.size >= limits.connections || record.clients.size >= 20 || record.times.length >= 30 || (!admission.has(address) && admission.size >= 1000)) {socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');return;}
  record.times.push(timestamp);admission.set(address,record);
  sockets.handleUpgrade(request,socket,head,ws => {
   // A completed upgrade carries an explicit browser-readable denial, without authenticating or admitting a session.
   if(record.blockedUntil>timestamp){ws.on('error',()=>{});ws.close(4003,'Admission temporarily blocked');return;}
   record.clients.add(ws);record.revision++;ws.once('close',()=>{record.clients.delete(ws);record.revision++;revokers.delete(ws);});sockets.emit('connection',ws);
  });
 });
 sockets.on('connection',ws => {
  let token:string|undefined;
  let windowStarted = Date.now(), received = 0;
  const send:Sender = (event:RoomEvent) => {if(ws.readyState !== WebSocket.OPEN) return;if(ws.bufferedAmount > 64*1024) {ws.terminate();return;}ws.send(JSON.stringify(event));};
  revokers.set(ws,()=>{if(token)rooms.revoke(token,send);});
  const authDeadline = setTimeout(()=>ws.close(1008,'Authenticate first'),5000);authDeadline.unref();
  ws.on('error',()=>{}); // Protocol errors close the socket; content is never logged.
  ws.on('message',(raw,binary) => {
   if(ws.readyState!==WebSocket.OPEN)return;
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
 const timer = setInterval(()=>{rooms.sweep();for(const [address,times] of transferAttempts)if(times.every(time=>time<=now()-60_000))transferAttempts.delete(address);},1000);timer.unref();
 const stop = () => {clearInterval(timer);rooms.stop();store.stop();for(const client of sockets.clients) client.terminate();sockets.close();};
 server.once('close',stop);
 return Object.assign(server,{stopRooms:stop,operator,romStore:store,rooms});
}
export async function shutdown(server: ReturnType<typeof createCoordinator>) {
 server.stopRooms();
 const deadline = setTimeout(() => server.closeAllConnections(), 2000);deadline.unref();
 try { await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())); }
 finally { clearTimeout(deadline); }
}
