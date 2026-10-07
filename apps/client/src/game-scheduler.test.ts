import {test} from 'node:test';
import assert from 'node:assert/strict';
import {GameScheduler} from './game-scheduler.ts';
import {gameplayLimits,parseGamePacket,type GamePacket,type InputPacket,type LeasePacket} from '../../../packages/contracts/src/gameplay.ts';
const epoch='e'.repeat(32),host='h'.repeat(22),guest='g'.repeat(22),observer='o'.repeat(22),generation='c'.repeat(32),hash='a'.repeat(64);
function timeline(local=host,controllers:readonly[string|undefined,string|undefined]=[host,guest],start=0){let now=1000;const sent:GamePacket[]=[];const scheduler=new GameScheduler(epoch,{local,authority:host,controllers,revision:1},p=>sent.push(p),start,()=>now);return {scheduler,sent,time(value:number){now=value;}};}
function update(lease:LeasePacket,sequence:number,mask:number,release=false):InputPacket{return {kind:'input',epoch,revision:lease.revision,generation:lease.generation,lease:lease.lease,sequence,mask,release};}
const committed=(frame:number,p1=1,p2=0,revision=1)=>({kind:'frame' as const,epoch,stream:epoch,revision,frame,p1,p2});
function complete(q:GameScheduler,mask=0){q.sample(mask);const value=q.next()!;q.commit();return value;}

test('host press and release use the next native dispatch with remote input absent',()=>{
 const {scheduler:q,sent}=timeline();q.sample(1);assert.deepEqual(q.next(),[1,0]);assert.deepEqual(sent,[]);
 q.commit();q.sample(0);assert.deepEqual(q.next(),[0,0]);q.commit();assert.deepEqual(sent,[committed(0),committed(1,0)]);
});
test('published command is immutable when input or assignment changes during worker execution',()=>{
 const {scheduler:q,sent}=timeline();const lease=q.grant(guest,generation,'l'.repeat(32))!;q.receive(update(lease,1,2),guest);q.sample(1);assert.deepEqual(q.next(),[1,2]);
 q.sample(4);q.receive(update(lease,2,8),guest);q.configure([guest,host],2);q.commit();assert.deepEqual(sent,[committed(0,1,2)]);
 assert.deepEqual(q.next(),[0,0]);q.commit();assert.equal((sent[1] as {revision:number}).revision,2);
});
test('whole-mask pending presses preserve taps, held controls and real chords without invented combinations',()=>{
 const {scheduler:q}=timeline();q.sample(1);q.sample(0);assert.deepEqual(q.next(),[1,0]);q.commit();assert.deepEqual(complete(q),[0,0]);
 q.sample(1);q.sample(0);q.sample(2);q.sample(0);assert.deepEqual(q.next(),[2,0]);q.commit();
 q.sample(64);q.sample(0);q.sample(128);assert.deepEqual(q.next(),[128,0]);q.commit();
 q.sample(128);q.sample(129);q.sample(128);assert.deepEqual(q.next(),[129,0]);q.commit();assert.deepEqual(complete(q,128),[128,0]);
 q.sample(3);assert.deepEqual(q.next(),[3,0]);q.commit();q.sample(0);q.sample(1);q.releaseLocal();assert.deepEqual(q.next(),[0,0]);
});
test('remote leases expire on the host clock even while increasing old heartbeats arrive',()=>{
 const t=timeline(),q=t.scheduler,lease=q.grant(guest,generation,'l'.repeat(32))!;
 q.receive(update(lease,1,2),guest);assert.deepEqual(complete(q),[0,2]);t.time(lease.expiresAt+1);
 assert.equal(q.receive(update(lease,2,2),guest),false);assert.deepEqual(complete(q),[0,0]);
 const next=q.grant(guest,generation,'n'.repeat(32))!;q.receive(update(next,3,2),guest);t.time(lease.expiresAt+20);assert.deepEqual(complete(q),[0,2]);
 assert.equal(q.receive(update(lease,4,255),guest),false);assert.deepEqual(complete(q),[0,2]);q.revoke(guest);assert.deepEqual(complete(q),[0,0]);
});
test('renewed neutral samples cannot extend a queued tap from the prior lease',()=>{
 const t=timeline(),q=t.scheduler,old=q.grant(guest,generation,'l'.repeat(32))!;
 q.receive(update(old,1,1),guest);q.receive(update(old,2,0),guest);
 t.time(2000);const renewed=q.grant(guest,generation,'n'.repeat(32))!;q.receive(update(renewed,3,0),guest);
 t.time(old.expiresAt+1);assert.deepEqual(complete(q),[0,0]);
});
test('input authority rejects stale generations, assignments, sequences and senders; release cancels pending taps',()=>{
 const {scheduler:q}=timeline(),lease=q.grant(guest,generation,'l'.repeat(32))!;
 assert.throws(()=>q.receive(update(lease,1,2),observer),/authority/);
 for(const packet of [{...update(lease,1,2),generation:'x'.repeat(32)},{...update(lease,1,2),revision:0},{...update(lease,1,2),epoch:'old'}])assert.equal(q.receive(packet,guest),false);
 assert.equal(q.receive(update(lease,1,2),guest),true);assert.equal(q.receive(update(lease,1,255),guest),false);
 q.receive(update(lease,2,0,true),guest);assert.deepEqual(complete(q),[0,0]);
});
test('guest executes every contiguous completed frame once, including older assignment history',()=>{
 const h=timeline(),g=timeline(guest);h.scheduler.sample(1);assert.equal(g.scheduler.next(),undefined);
 for(let frame=0;frame<300;frame++){if(frame===20)h.scheduler.configure([host,undefined],2);complete(h.scheduler,frame&255);}
 g.scheduler.configure([host,undefined],2);
 for(const packet of h.sent)g.scheduler.receive(packet,host);
 for(let frame=0;frame<300;frame++){const expected=h.scheduler.historyFrame(frame)!;assert.deepEqual(g.scheduler.next(),[expected.p1,expected.p2]);g.scheduler.commit();}
 assert.equal(g.scheduler.frame,300);assert.equal(g.scheduler.next(),undefined);assert.throws(()=>g.scheduler.commit(),/undispatched/);
 assert.throws(()=>g.scheduler.receive(committed(301),host),/Invalid/);assert.throws(()=>g.scheduler.receive(committed(300),observer),/host/);
});
test('missing peer hashes never block host advancement; mismatches identify only that guest',()=>{
 const {scheduler:q}=timeline();for(let frame=0;frame<gameplayLimits.historyFrames*2;frame++){complete(q);if(q.frame%120===0)q.hash(hash);}
 assert.equal(q.frame,gameplayLimits.historyFrames*2);assert.equal(q.historySince(q.frame-gameplayLimits.historyFrames)!.length,gameplayLimits.historyFrames);assert.equal(q.historySince(q.frame-gameplayLimits.historyFrames-1),undefined);
 const frame=Math.floor(q.frame/120)*120;q.receive({kind:'hash',epoch,stream:epoch,frame,hash:'b'.repeat(64)},guest);assert.deepEqual(q.takeFaults(),[guest]);assert.deepEqual(complete(q),[0,0]);
 assert.equal(q.receive({kind:'hash',epoch,stream:epoch,frame:120,hash},guest),false);
});
test('host authority is independent of controller position',()=>{
 const swapped=timeline(host,[guest,host]);swapped.scheduler.sample(3);assert.deepEqual(swapped.scheduler.next(),[0,3]);
 const watching=timeline(host,[guest,observer]);watching.scheduler.sample(255);assert.deepEqual(watching.scheduler.next(),[0,0]);
});
test('packet parser admits bounded new protocol fields and rejects released future-input packets',()=>{
 const lease:LeasePacket={kind:'lease',epoch,revision:1,generation,lease:'l'.repeat(32),expiresAt:3000};
 for(const packet of [lease,update(lease,1,3),committed(0)])assert.deepEqual(parseGamePacket(JSON.stringify(packet)),packet);
 for(const packet of [{kind:'input',epoch,frame:6,mask:1},{...update(lease,1,2),release:true},{...update(lease,0,2)},{...committed(0),p1:256},{...committed(0),rom:'secret'}])assert.equal(parseGamePacket(JSON.stringify(packet)),undefined);
});
