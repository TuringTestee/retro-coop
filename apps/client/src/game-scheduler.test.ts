import {test} from 'node:test';
import assert from 'node:assert/strict';
import {GameScheduler,proposeInputDelay} from './game-scheduler.ts';
import {gameplayLimits,parseGamePacket,type GamePacket} from '../../../packages/contracts/src/gameplay.ts';
const epoch='e'.repeat(32),host='host-member',guest='guest-member',observer='observer-member',hash='a'.repeat(64);
const input=(frame:number,mask=2):GamePacket=>({kind:'input',epoch,frame,mask});
const committed=(frame:number,p1=1,p2=2):GamePacket=>({kind:'frame',epoch,frame,p1,p2});
const state=(frame:number,value=hash):GamePacket=>({kind:'hash',epoch,frame,hash:value});
function timeline(local=host,controllers:readonly[string|undefined,string|undefined]=[host,guest],start=0){const sent:GamePacket[]=[];const scheduler=new GameScheduler(epoch,6,{local,authority:host,controllers},p=>sent.push(p),start);return {scheduler,sent};}

test('authority broadcasts only completed frames; replicas cannot advance on raw input or local sampling',()=>{
 const a=timeline(),b=timeline(guest);a.scheduler.sample(255);b.scheduler.sample(31);
 assert.equal(a.scheduler.next(),undefined);assert.equal(b.scheduler.next(),undefined);assert.deepEqual(a.sent,[]);
 for(const packet of b.sent.splice(0))a.scheduler.receive(packet,guest);
 assert.deepEqual(a.scheduler.next(),[0,0]);assert.deepEqual(a.sent,[]);
 assert.throws(()=>b.scheduler.receive(input(0),host),/authority/);assert.throws(()=>b.scheduler.commit(),/missing/);
 a.scheduler.commit();assert.deepEqual(a.sent,[committed(0,0,0)]);assert.equal(b.scheduler.next(),undefined);
 b.scheduler.receive(a.sent[0],host);assert.deepEqual(b.scheduler.next(),[0,0]);b.scheduler.commit();assert.equal(b.scheduler.frame,1);
});

test('delayed host and replica produce identical committed vectors despite transport stalls',()=>{
 const a=timeline(),b=timeline(guest),left:number[][]=[],right:number[][]=[];
 for(let clock=0;clock<2000&&right.length<240;clock++){
  a.scheduler.sample((a.scheduler.frame*13)&255);b.scheduler.sample((b.scheduler.frame*29)&255);
  if(clock%11!==0){for(const p of b.sent.splice(0))a.scheduler.receive(p,guest);for(const p of a.sent.splice(0))b.scheduler.receive(p,host);}
  if(left.length<240&&a.scheduler.next()){left.push(a.scheduler.next()!);a.scheduler.commit();}
  if(b.scheduler.next()){right.push(b.scheduler.next()!);b.scheduler.commit();}
 }
 assert.equal(left.length,240);assert.deepEqual(left,right);assert.deepEqual(left.slice(0,6),Array.from({length:6},()=>[0,0]));assert.notDeepEqual(left[8],[0,0]);
});

test('member mapping supports host observer, remote controllers, swapped ports and one-owner shared mode',()=>{
 const remote='third-member',a=timeline(host,[guest,remote]);a.scheduler.sample(255);assert.deepEqual(a.sent,[]);assert.equal(a.scheduler.next(),undefined);
 a.scheduler.receive(input(0,3),guest);assert.equal(a.scheduler.next(),undefined);a.scheduler.receive(input(0,9),remote);assert.deepEqual(a.scheduler.next(),[3,9]);a.scheduler.commit();
 const swapped=timeline(host,[guest,host]);swapped.scheduler.sample(255);swapped.scheduler.receive(input(0,19),guest);assert.deepEqual(swapped.scheduler.next(),[19,0]);
 const shared=timeline(host,[guest,undefined]);shared.scheduler.receive(input(0,77),guest);assert.deepEqual(shared.scheduler.next(),[77,0]);
 const passive=timeline(observer);passive.scheduler.sample(255);assert.deepEqual(passive.sent,[]);assert.equal(passive.scheduler.next(),undefined);passive.scheduler.receive(committed(0,3,9),host);assert.deepEqual(passive.scheduler.next(),[3,9]);
 assert.throws(()=>a.scheduler.receive(input(1),observer),/authority/);
});

test('stalled authority exposes only completed history at its current absolute boundary',()=>{
 const {scheduler:q,sent}=timeline(host,[host,guest],917);q.sample(1);
 assert.equal(q.next(),undefined);assert.equal(q.frame,917);assert.deepEqual(q.historySince(917),[]);assert.equal(q.historySince(916),undefined);
 q.receive(input(917,9),guest);assert.deepEqual(q.historySince(917),[]);q.commit();assert.equal(q.frame,918);
 assert.deepEqual(q.historySince(917),[committed(917,0,9)]);assert.deepEqual(q.historySince(918),[]);assert.equal(q.next(),undefined);assert.equal(q.historySince(919),undefined);assert.deepEqual(sent,[committed(917,0,9)]);
});

test('history keeps exactly its bounded rolling window with canonical masks',()=>{
 const {scheduler:q}=timeline(host,[guest,undefined],31),count=gameplayLimits.historyFrames+17;
 for(let i=0;i<count;i++){q.receive(input(q.frame,i&255),guest);q.commit();}
 const oldest=q.frame-gameplayLimits.historyFrames,history=q.historySince(oldest)!;
 assert.equal(history.length,gameplayLimits.historyFrames);assert.equal(q.historySince(oldest-1),undefined);
 assert.deepEqual(history[0],committed(oldest,17,0));assert.deepEqual(history.at(-1),committed(q.frame-1,(count-1)&255,0));assert.equal(timeline(guest).scheduler.historySince(0),undefined);
});

test('epoch, ownership, duplicate and bounded-window checks reject invalid timeline feeds',()=>{
 const {scheduler:a}=timeline(),{scheduler:b}=timeline(guest);a.sample(1);
 assert.equal(a.receive({...input(0),epoch:'old'},guest),false);assert.equal(a.next(),undefined);
 assert.throws(()=>a.receive(input(0),host),/authority/);assert.throws(()=>a.receive(input(gameplayLimits.inputWindow+1),guest),/Invalid/);
 a.receive(input(0),guest);assert.throws(()=>a.receive(input(0),guest),/duplicate/);a.commit();assert.throws(()=>a.receive(input(0),guest),/Invalid/);
 assert.throws(()=>a.receive(committed(1),host),/host/);assert.throws(()=>b.receive(committed(0),observer),/host/);assert.throws(()=>b.receive(committed(1),host),/Invalid/);
 b.receive(committed(0),host);assert.throws(()=>b.receive(committed(0),host),/duplicate/);
 for(let frame=1;frame<gameplayLimits.inputWindow;frame++)b.receive(committed(frame),host);
 assert.throws(()=>b.receive(committed(gameplayLimits.inputWindow),host),/Invalid/);
 assert.equal(parseGamePacket(JSON.stringify({...input(1),mask:256})),undefined);assert.equal(parseGamePacket(JSON.stringify({...committed(1),rom:'secret'})),undefined);
});

function advance(q:GameScheduler,to:number){while(q.frame<to){q.sample(1);q.receive(input(q.frame),guest);q.commit();}}
test('active owner hashes enforce ordered comparison and mismatch while observer reports do not gate authority',()=>{
 const {scheduler:q}=timeline();advance(q,120);assert.equal(q.receive(state(120),observer),false);
 assert.throws(()=>q.receive(state(240),guest),/hash/);q.receive(state(120),guest);q.hash(hash);assert.throws(()=>q.receive(state(120),guest),/hash/);
 advance(q,240);q.receive(state(240),guest);assert.throws(()=>q.hash('b'.repeat(64)),/mismatch/);
 const resumed=timeline(host,[host,guest],917);advance(resumed.scheduler,960);resumed.scheduler.receive(state(960),guest);resumed.scheduler.hash(hash);assert.throws(()=>resumed.scheduler.receive(state(960),guest),/hash/);
 const {scheduler:stalled}=timeline();advance(stalled,120);stalled.hash(hash);advance(stalled,240);stalled.hash(hash);advance(stalled,360);assert.throws(()=>stalled.hash(hash),/stopped arriving/);
});

test('passive observers compare host hashes locally without sending reports or blocking host',()=>{
 const {scheduler:q,sent}=timeline(observer);
 for(let frame=0;frame<120;frame++){q.receive(committed(frame),host);q.commit();}
 assert.equal(q.receive(state(120),guest),false);q.receive(state(120),host);q.hash(hash);assert.deepEqual(sent,[]);
 const authority=timeline(host,[undefined,undefined]);for(let i=0;i<120;i++)authority.scheduler.commit();authority.scheduler.hash(hash);assert.equal(authority.scheduler.frame,120);
});

test('input delay uses observed round trip and worker pacing within approved bounds',()=>{
 assert.equal(proposeInputDelay(5,60),6);assert.equal(proposeInputDelay(80,60),7);assert.equal(proposeInputDelay(80,50),6);assert.equal(proposeInputDelay(117,60),8);assert.equal(proposeInputDelay(5000,60),8);assert.equal(proposeInputDelay(Number.NaN,60),6);
});
