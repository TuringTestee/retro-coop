import {test} from 'node:test';
import assert from 'node:assert/strict';
import {GameScheduler} from './game-scheduler.ts';
import {parseGamePacket,type GamePacket} from '../../../packages/contracts/src/gameplay.ts';
const epoch='e'.repeat(32);
test('two independent delayed schedulers commit identical controller pairs through packet stalls',()=>{
 const toA:GamePacket[]=[],toB:GamePacket[]=[],a=new GameScheduler(epoch,6,p=>toB.push(p)),b=new GameScheduler(epoch,6,p=>toA.push(p));
 const left:number[][]=[],right:number[][]=[];
 for(let clock=0;clock<1000&&left.length<240;clock++) {
  a.sample((a.frame*13)&255);b.sample((b.frame*29)&255);
  if(clock%11!==0) {for(const p of toA.splice(0))a.receive(p);for(const p of toB.splice(0))b.receive(p);}
  const nextA=a.next(),nextB=b.next();
  if(nextA){left.push(nextA);a.commit();}if(nextB){right.push([nextB[1],nextB[0]]);b.commit();}
 }
 assert.equal(left.length,240);assert.deepEqual(left,right);assert.deepEqual(left.slice(0,6),Array.from({length:6},()=>[0,0]));assert.notDeepEqual(left[7],[0,0]);
});
test('epochs, bounded windows, duplicates and missing hashes cannot advance a wrong timeline',()=>{
 const q=new GameScheduler(epoch,3,()=>{});q.sample(1);assert.equal(q.next(),undefined);
 q.receive({kind:'input',epoch:'old'.repeat(12),frame:0,mask:255});assert.equal(q.next(),undefined);
 assert.throws(()=>q.receive({kind:'input',epoch,frame:121,mask:0}),/Invalid/);
 q.receive({kind:'input',epoch,frame:0,mask:2});assert.throws(()=>q.receive({kind:'input',epoch,frame:0,mask:2}),/duplicate/);q.commit();
 assert.throws(()=>q.receive({kind:'input',epoch,frame:0,mask:2}),/Invalid/);
 for(let frame=1;frame<120;frame++){q.sample(1);q.receive({kind:'input',epoch,frame,mask:2});q.commit();}
 q.receive({kind:'hash',epoch,frame:120,hash:'a'.repeat(64)});assert.throws(()=>q.hash('b'.repeat(64)),/mismatch/);
 assert.equal(parseGamePacket(JSON.stringify({kind:'input',epoch,frame:1,mask:256})),undefined);
 assert.equal(parseGamePacket(JSON.stringify({kind:'input',epoch,frame:1,mask:1,rom:'secret'})),undefined);
 assert.equal(parseGamePacket(JSON.stringify({kind:'hash',epoch,frame:119,hash:'a'.repeat(64)})),undefined);
});
test('ordered checkpoint admission rejects omitted checkpoints and repeats after comparison',()=>{
 const q=new GameScheduler(epoch,6,()=>{});
 for(let frame=0;frame<120;frame++){q.sample(1);q.receive({kind:'input',epoch,frame,mask:2});q.commit();}
 assert.throws(()=>q.receive({kind:'hash',epoch,frame:240,hash:'a'.repeat(64)}),/checkpoint|hash/);
 q.receive({kind:'hash',epoch,frame:120,hash:'a'.repeat(64)});q.hash('a'.repeat(64));
 assert.throws(()=>q.receive({kind:'hash',epoch,frame:120,hash:'a'.repeat(64)}),/checkpoint|hash/);
});

test('fixed input proposal uses observed round trip and actual region rate within approved bounds',async()=>{
 const {proposeInputDelay}=await import('./game-scheduler.ts');
 assert.equal(proposeInputDelay(5,60),6);
 assert.equal(proposeInputDelay(80,60),7);
 assert.equal(proposeInputDelay(80,50),6);
 assert.equal(proposeInputDelay(117,60),8);
 assert.equal(proposeInputDelay(5000,60),8);
 assert.equal(proposeInputDelay(Number.NaN,60),6);
});
