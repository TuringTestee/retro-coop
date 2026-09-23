/** Test-only same-origin static gateway; production proxy provisioning belongs to D24. */
import {createServer,request as httpRequest} from 'node:http';
import {connect} from 'node:net';
import {readFile} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
import {once} from 'node:events';
import {config,createCoordinator,shutdown} from '../../apps/coordinator/src/server.ts';
import {listenOperator} from '../../apps/coordinator/src/operator.ts';
const root = resolve(process.env.RETRO_COOP_STATIC_ROOT ?? 'apps/client/dist');
const gateway = createServer(async(request,response)=>{
 const upload=/^\/coordinator(\/rooms\/[A-Za-z0-9_-]{43}\/rom)$/.exec(request.url??'');
 if(upload && (request.method==='PUT'||request.method==='GET'||request.method==='OPTIONS')){
  const upstream=httpRequest({hostname:'127.0.0.1',port:coordinatorPort,path:upload[1],method:request.method,headers:request.headers},incoming=>{
   response.writeHead(incoming.statusCode??502,incoming.headers);incoming.pipe(response);
  });
  upstream.on('error',()=>{if(!response.headersSent)response.writeHead(502);response.end();});
  request.pipe(upstream);return;
 }
 const file = resolve(root,'.'+new URL(request.url!,'http://localhost').pathname.replace(/\/$/,'/index.html'));
 if(!file.startsWith(root+'/')) {response.writeHead(404).end();return;}
 try {const bytes = await readFile(file);response.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css','.wasm':'application/wasm'} as Record<string,string>)[extname(file)] ?? 'application/octet-stream');response.end(bytes);}catch{response.writeHead(404).end();}
});
gateway.listen(0,'127.0.0.1');await once(gateway,'listening');
const url = `http://127.0.0.1:${(gateway.address() as {port:number}).port}`;
const offerCatalogIds=config({...process.env,COORDINATOR_ORIGINS:url}).offerCatalogIds;
const coordinator = createCoordinator({origins:[url],offerCatalogIds});coordinator.listen(0,'127.0.0.1');await once(coordinator,'listening');
const operator=process.env.COORDINATOR_OPERATOR_DIR ? await listenOperator(process.env.COORDINATOR_OPERATOR_DIR,coordinator.operator):undefined;
const coordinatorPort = (coordinator.address() as {port:number}).port;
const connections = new Set<ReturnType<typeof connect>>();
gateway.on('upgrade',(request,socket,head)=>{
 const upstream = connect(coordinatorPort,'127.0.0.1',()=>{
  upstream.write(`${request.method} ${request.url} HTTP/1.1\r\n${Object.entries(request.headers).map(([key,value])=>`${key}: ${value}`).join('\r\n')}\r\n\r\n`);
  if(head.length) upstream.write(head);socket.pipe(upstream);upstream.pipe(socket);
 });
 connections.add(upstream);upstream.on('close',()=>{connections.delete(upstream);socket.destroy();});upstream.on('error',()=>socket.destroy());socket.on('error',()=>upstream.destroy());socket.on('close',()=>upstream.destroy());
});
console.log(JSON.stringify({url}));
process.on('SIGTERM',()=>{operator?.closeAllConnections();operator?.close();for(const connection of connections) connection.destroy();gateway.closeAllConnections();gateway.close();void shutdown(coordinator);});
