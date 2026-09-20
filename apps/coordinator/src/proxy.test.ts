import {test} from 'node:test';
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {WebSocket} from 'ws';
import {config,createCoordinator,shutdown} from './server.ts';
import {admissionAddress,trustedProxyAddresses} from './admission-address.ts';
async function fixture(trustedProxies:string[],run:(open:(forwarded?:string)=>Promise<number>)=>Promise<void>) {
 const origin='https://client.example',server=createCoordinator({origins:[origin],trustedProxies});
 server.listen(0,'127.0.0.1');await once(server,'listening');
 const url=`ws://127.0.0.1:${(server.address() as {port:number}).port}/ws`,clients:WebSocket[]=[];
 const open=(forwarded?:string)=>new Promise<number>((resolve,reject)=>{
  const socket=new WebSocket(url,{origin,headers:forwarded===undefined?{}:{'X-Forwarded-For':forwarded}});clients.push(socket);
  socket.once('open',()=>resolve(101));socket.on('error',reject);
  socket.once('unexpected-response',(_request,response)=>{resolve(response.statusCode!);response.destroy();socket.terminate();});
 });
 try {await run(open);}finally{for(const socket of clients)socket.terminate();await shutdown(server);}
}
test('trusted proxy preserves per-client admission rather than capping the entire deployment at twenty sockets',async()=>{
 await fixture(['127.0.0.1'],async open=>{for(let i=1;i<=21;i++)assert.equal(await open(`192.0.2.${i}`),101,`distinct client ${i}`);});
});
test('one trusted client still hits its address limit and direct clients cannot spoof forwarding identity',async()=>{
 await fixture(['127.0.0.1'],async open=>{for(let i=0;i<20;i++)assert.equal(await open('192.0.2.1'),101);assert.equal(await open('192.0.2.1'),403);});
 await fixture(['127.0.0.2'],async open=>{for(let i=1;i<=20;i++)assert.equal(await open(`192.0.2.${i}`),101);assert.equal(await open('192.0.2.21'),403);});
});
test('trusted path rejects absent, invalid and ambiguous identity instead of guessing a client',async()=>{
 await fixture(['127.0.0.1'],async open=>{
  for(const value of [undefined,'unknown','192.0.2.1, 192.0.2.2','192.0.2.1:1234','192.0.2.1;secret'])assert.equal(await open(value),403);
  assert.equal(await open('2001:db8::1'),101);
 });
});
test('proxy trust must be explicit literal addresses, never arbitrary forwarded-header trust',()=>{
 for(const value of ['*','true','localhost','0.0.0.0/0','127.0.0.1,','https://proxy.example'])assert.throws(()=>config({COORDINATOR_TRUSTED_PROXIES:value}),/proxy/i);
 assert.deepEqual(config({COORDINATOR_TRUSTED_PROXIES:'127.0.0.1,::1'}).trustedProxies,['127.0.0.1','::1']);
});
test('equivalent IPv6 and IPv4-mapped addresses share quota and proxy identities',()=>{
 const trusted=new Set(trustedProxyAddresses(['0:0:0:0:0:0:0:1','::ffff:127.0.0.1']));
 assert.equal(admissionAddress('::1','2001:0db8:0:0:0:0:0:1',trusted),'2001:db8::1');
 assert.equal(admissionAddress('127.0.0.1','::ffff:c000:201',trusted),'192.0.2.1');
 assert.equal(admissionAddress('::ffff:127.0.0.1','192.0.2.1',trusted),'192.0.2.1');
 assert.equal(admissionAddress('192.0.2.1','forged',trusted),'192.0.2.1');
 assert.equal(admissionAddress(undefined,'192.0.2.1',trusted),undefined);
 assert.equal(admissionAddress('::1',['192.0.2.1','192.0.2.2'],trusted),undefined);
 assert.equal(admissionAddress('::1','fe80::1%eth0',trusted),undefined);
});
