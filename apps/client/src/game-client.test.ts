import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {GameClient,type GameplayState} from './game-client.ts';
import type {LocalPlayer} from './player.ts';
import type {Fingerprint,RoomView} from '../../../packages/contracts/src/rooms.ts';
const host='h'.repeat(22),member='m'.repeat(22),peerEpoch='p'.repeat(22),epoch='e'.repeat(22),hash='c'.repeat(64);
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:1,submapper:0,region:'NTSC',bytes:32784}};
const room=(self=member):RoomView=>({id:'r'.repeat(22),label:'Room',visibility:'public',status:'waiting',host:'Host',occupancy:2,openSlots:3,hostReady:true,established:false,chatMembership:self,hostMembership:host,invite:'i'.repeat(22),role:self===host?'host':'member',slot:self===host?'slot-1':'slot-2',revision:1,controllerRoles:['player1','player2'],connectionPolicy:'standard',peers:[],reservationIntent:'j'.repeat(22),fingerprint,matches:true,game:{status:'waiting',controllers:{owners:[host,member],revision:1},ready:[],startRequested:false},slots:[{id:'slot-1',role:'player1',open:true,revision:0,member:{id:host,nickname:'Host',connected:true,matches:true,acquisition:'loaded'}},{id:'slot-2',role:'player2',open:true,revision:0,member:{id:member,nickname:'Member',connected:true,matches:true,acquisition:'loaded'}},...(['slot-3','slot-4','slot-5'] as const).map(id=>({id,role:'observer' as const,open:true,revision:0}))]});
function setup(self=member){
 const commands:{type:string;[key:string]:unknown}[]=[],updates:GameplayState[]=[],holds:Array<(value:{frame:number;hash:string;fresh:boolean})=>void>=[];let deferHold=false,sendHook:((command:{type:string})=>Promise<void>)|undefined;
 const player={isLoaded:()=>true,frameRate:()=>60,holdForGame:()=>deferHold?new Promise(resolve=>holds.push(resolve)):Promise.resolve({frame:0,hash,fresh:true}),cancelPeerCheckpoint(){},sampleGameInput:()=>0,stopGame(){},allowLocalPlay(){},releaseControllers(){}} as unknown as LocalPlayer;
 const game=new GameClient(()=>player,async command=>{commands.push(command);await sendHook?.(command);},state=>updates.push(state));
 const channel={readyState:'open',bufferedAmount:0,send(){},onmessage:undefined} as unknown as RTCDataChannel;
 game.enter(room(self));game.selected(fingerprint);game.ready(self===host?member:host,channel,peerEpoch);
 return {game,player,commands,updates,channel,holds,defer:()=>{deferHold=true;},send:(hook:typeof sendHook)=>{sendHook=hook;}};
}
const tick=()=>setImmediate();
test('replaced peer channel cannot mutate current game through delayed malformed message',()=>{
 const t=setup(),current={readyState:'open',bufferedAmount:0,send(){}} as unknown as RTCDataChannel;try{
  t.game.ready(host,current,'n'.repeat(22));const count=t.updates.length;t.channel.onmessage!.call(t.channel,new MessageEvent('message',{data:'bad'}));assert.equal(t.updates.length,count);
  current.onmessage!.call(current,new MessageEvent('message',{data:'bad'}));assert.ok(t.updates.length>count);
 }finally{t.game.dispose();}
});
test('completed old readiness cannot overwrite a later membership change',async()=>{
 const t=setup();let finish!:()=>void;t.send(()=>new Promise(resolve=>{finish=resolve;}));try{
  t.game.playIntent();await tick();assert.equal(typeof finish,'function');t.game.enter(undefined);const latest=t.updates.at(-1);finish();await tick();assert.deepEqual(t.updates.at(-1),latest);
 }finally{t.game.dispose();}
});
test('cancelling an in-flight offer releases only that operation and newer readiness remains exclusive',async()=>{
 for(const oldFirst of [true,false]){const t=setup();t.defer();try{
  t.game.playIntent();assert.equal(t.holds.length,1);t.game.cancelIntent();if(oldFirst){t.holds[0]({frame:0,hash,fresh:true});await tick();}
  t.game.playIntent();assert.equal(t.holds.length,2);if(!oldFirst){t.holds[0]({frame:0,hash,fresh:true});await tick();}t.game.retry();assert.equal(t.holds.length,2);
  t.holds[1]({frame:0,hash,fresh:true});await tick();assert.deepEqual(t.commands.map(c=>c.type),['gameUnready','gameReady']);
 }finally{t.game.dispose();}}
});
test('host explicit retry works regardless of previous stop and does not duplicate readiness',async()=>{
 const t=setup(host);try{t.game.handle({type:'gameStop',reason:'Timed out'});t.game.retry();await tick();t.game.enter(room(host));await tick();assert.equal(t.commands.filter(c=>c.type==='gameReady').length,1);}finally{t.game.dispose();}
});
test('wrong selected file cannot prepare until matching file and explicit intent are supplied',async()=>{
 const t=setup();try{t.game.selected({...fingerprint,romSha256:'f'.repeat(64)});t.game.playIntent();await tick();assert.equal(t.commands.length,0);t.game.cancelIntent();t.game.selected(fingerprint);await tick();assert.deepEqual(t.commands.map(c=>c.type),['gameUnready']);t.game.playIntent();await tick();assert.equal(t.commands.at(-1)?.type,'gameReady');assert.equal(t.commands.at(-1)?.roomRevision,1);}finally{t.game.dispose();}
});
test('changing an already prepared member file explicitly revokes its readiness',async()=>{
 const t=setup();try{t.game.playIntent();await tick();assert.equal(t.commands.at(-1)?.type,'gameReady');t.game.selected({...fingerprint,romSha256:'f'.repeat(64)});await tick();assert.deepEqual(t.commands.map(c=>c.type),['gameReady','gameUnready']);}finally{t.game.dispose();}
});
test('file replacement during worker hold invalidates stale readiness before it reaches coordinator',async()=>{
 const t=setup();t.defer();try{t.game.playIntent();t.game.selected({...fingerprint,romSha256:'f'.repeat(64)});t.holds[0]({frame:0,hash,fresh:true});await tick();assert.equal(t.commands.some(c=>c.type==='gameReady'),false);}finally{t.game.dispose();}
});
test('room revision invalidates an unfinished Ready click until the member chooses Ready again',async()=>{
 const t=setup();t.defer();try{
  t.game.playIntent();assert.equal(t.holds.length,1);
  const changed=room();changed.revision=2;changed.slots[1].revision=1;t.game.enter(changed);
  t.holds[0]({frame:0,hash,fresh:true});await tick();
  assert.equal(t.commands.some(c=>c.type==='gameReady'),false);
  assert.equal(t.updates.at(-1)?.intent,false);
  t.game.playIntent();assert.equal(t.holds.length,2);
  t.holds[1]({frame:0,hash,fresh:true});await tick();
  assert.equal(t.commands.at(-1)?.type,'gameReady');assert.equal(t.commands.at(-1)?.roomRevision,2);
 }finally{t.game.dispose();}
});
test('late configured controller offers readiness for activation rather than requesting observer sync',async()=>{
 const t=setup();try{const late=room();late.started='shared';late.established=true;late.game={...late.game,status:'playing',epoch,controllers:{owners:[host,null],revision:2}};t.game.enter(late);t.commands.length=0;t.game.playIntent();await tick();assert.equal(t.commands.some(c=>c.type==='gameObserve'),false);assert.ok(t.commands.some(c=>c.type==='gameReady'&&c.revision===2));}finally{t.game.dispose();}
});

test('prepared timeline retains ordered peer packets arriving before the local Start event',async()=>{
 for(const self of [host,member]){
  const t=setup(self);let clock:Parameters<LocalPlayer['startGame']>[0]|undefined;
  t.player.bindGameEpoch=async()=>{};t.player.startGame=value=>{clock=value;};t.player.wakeGame=()=>{};
  try{
   const controllers=room(self).game.controllers,context={epoch,authority:host,frame:0,hash,delay:6,controllers};
   t.game.handle({type:'gamePrepare',...context});await tick();assert.equal(t.commands.at(-1)?.type,'gameAck');
   const packet=self===host?{kind:'input',epoch,frame:0,mask:0}:{kind:'frame',epoch,frame:0,p1:0,p2:0};
   t.channel.onmessage!.call(t.channel,new MessageEvent('message',{data:JSON.stringify(packet)}));
   assert.equal(clock,undefined,'early transport cannot execute a frame before Start');
   t.game.handle({type:'gameStart',...context});assert.ok(clock);assert.deepEqual((clock as Parameters<LocalPlayer['startGame']>[0]).next(0),{frame:0,p1:0,p2:0});
  }finally{t.game.dispose();}
 }
});
