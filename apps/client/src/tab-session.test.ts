import test from 'node:test';
import assert from 'node:assert/strict';
import {TabSession} from './tab-session.ts';

function navigatorWith(context:{after:(fn:()=>void)=>void},locks?:unknown){
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'navigator');
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{locks}});
 context.after(()=>{if(descriptor)Object.defineProperty(globalThis,'navigator',descriptor);else Reflect.deleteProperty(globalThis,'navigator');});
}
for(const locks of [undefined,{request(){throw new DOMException('Unavailable','SecurityError');}},{request:()=>Promise.reject(Error('Unavailable'))}]){
 test(`unavailable locks isolate only fresh server-issued identities (${locks?'restricted':'absent'})`,async context=>{
  navigatorWith(context,locks);const session=new TabSession();
  assert.equal(await session.claim('copied-token'),false);
  assert.equal(await session.claim('new-server-token',true),true);
  assert.equal(session.mayPersist(),false);
  assert.equal(await session.claim('new-server-token'),true,'owned in-memory reconnect must work');
  session.close();assert.equal(await session.claim('new-server-token'),false,'closed identities must not be reused without exclusion');
 });
}
test('actual lock contention rejects copied identities and preserves the owning tab',async context=>{
 const owned=new Set<string>();navigatorWith(context,{async request(name:string,_options:unknown,callback:(lock:unknown)=>Promise<void>){
  if(owned.has(name))return callback(null);owned.add(name);try{return await callback({name});}finally{owned.delete(name);}
 }});
 const one=new TabSession(),two=new TabSession();
 assert.equal(await one.claim('token'),true);assert.equal(one.mayPersist(),true);
 assert.equal(await two.claim('token'),false);assert.equal(await two.claim('token',true),false,'a contention result cannot bypass exclusion');
 assert.equal(await one.claim('token'),true);one.close();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(await two.claim('token'),true);two.close();
});
test('a closed pending lock request cannot install an isolated session',async context=>{
 let reject!:(error:Error)=>void;navigatorWith(context,{request:()=>new Promise((_done,fail)=>reject=fail)});
 const session=new TabSession(),claim=session.claim('new-token',true);
 while(!reject)await new Promise(resolve=>setImmediate(resolve));session.close();reject(Error('Failed later'));
 assert.equal(await claim,false);
});
