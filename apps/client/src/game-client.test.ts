import {test} from 'node:test';
import assert from 'node:assert/strict';
import {GameClient} from './game-client.ts';

test('a replaced peer channel cannot change the current game through a delayed message',()=>{
 const updates:unknown[]=[];
 const game=new GameClient(()=>null,async()=>{},state=>updates.push(state));
 const oldChannel={readyState:'open',onmessage:undefined} as unknown as RTCDataChannel;
 const currentChannel={readyState:'open',onmessage:undefined} as unknown as RTCDataChannel;
 game.ready(oldChannel,'old-peer-epoch');
 game.ready(currentChannel,'current-peer-epoch');
 oldChannel.onmessage!.call(oldChannel,new MessageEvent('message',{data:'malformed stale packet'}));
 assert.equal(updates.length,0,'stale callback cleared the current game');
 currentChannel.onmessage!.call(currentChannel,new MessageEvent('message',{data:'malformed current packet'}));
 assert.equal(updates.length,1,'current channel validation must remain active');
});

test('a completed old readiness request cannot overwrite a later membership change',async()=>{
 const {setImmediate}=await import('node:timers/promises');
 const updates:{status:string}[]=[];
 let finish!:()=>void;
 const player={frameRate:()=>60,holdForGame:async()=>({hash:'c'.repeat(64),frame:0,fresh:true}),stopGame(){},allowLocalPlay(){}} as unknown as import('./player.ts').LocalPlayer;
 const game=new GameClient(()=>player,()=>new Promise<void>(resolve=>{finish=resolve;}),state=>updates.push(state));
 const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}} as const;
 game.enter({id:'room',role:'guest',matches:true,fingerprint,peer:{epoch:'peer'},reservationIntent:'intent'} as import('../../../packages/contracts/src/rooms.ts').RoomView);
 game.selected(fingerprint);
 game.ready({readyState:'open'} as RTCDataChannel,'peer');
 await setImmediate();assert.equal(typeof finish,'function');
 game.enter(undefined);const latest=updates.at(-1)!.status;
 finish();await setImmediate();
 assert.equal(updates.at(-1)!.status,latest,'old readiness completion changed the current membership status');
});

test('explicit host retry submits readiness regardless of guest inspection order',async()=>{
 const {setImmediate}=await import('node:timers/promises');
 for(const guestFirst of [true,false]){
  const sent:unknown[]=[];let holds=0;
  const player={frameRate:()=>60,holdForGame:async()=>{holds++;return {hash:'c'.repeat(64),frame:0,fresh:true};},stopGame(){},allowLocalPlay(){}} as unknown as import('./player.ts').LocalPlayer;
  const game=new GameClient(()=>player,async command=>{sent.push(command);},()=>{});
  const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}} as const;
  game.enter({id:'room',role:'host',matches:true,fingerprint,peer:{epoch:'peer'},game:{status:'failed'},established:false} as import('../../../packages/contracts/src/rooms.ts').RoomView);
  game.selected(fingerprint);game.ready({readyState:'open'} as RTCDataChannel,'peer');
  game.handle({type:'gameStop',reason:'Shared start timed out.'});
  if(guestFirst){game.handle({type:'gameInspect',peerEpoch:'peer'});await setImmediate();assert.equal(holds,0,'background inspection renewed canceled intent');}
  game.retry();await setImmediate();
  if(!guestFirst){game.handle({type:'gameInspect',peerEpoch:'peer'});await setImmediate();}
  assert.equal(holds,1,guestFirst?'guest-first retry did not prepare host':'host-first retry duplicated host readiness');
  assert.equal(sent.length,1);
 }
});

test('canceling an in-flight readiness offer releases only that operation ownership',async()=>{
 const {setImmediate}=await import('node:timers/promises');
 for(const completeOldFirst of [true,false]){
  const sent:unknown[]=[];const finish:Array<()=>void>=[];
  const player={frameRate:()=>60,holdForGame:()=>new Promise(resolve=>finish.push(()=>resolve({hash:'c'.repeat(64),frame:0,fresh:true}))),stopGame(){},allowLocalPlay(){}} as unknown as import('./player.ts').LocalPlayer;
  const game=new GameClient(()=>player,async command=>{sent.push(command);},()=>{});
  const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}} as const;
  game.enter({id:'room',role:'guest',matches:true,fingerprint,peer:{epoch:'peer'},established:false} as import('../../../packages/contracts/src/rooms.ts').RoomView);
  game.selected(fingerprint);game.ready({readyState:'open'} as RTCDataChannel,'peer');await setImmediate();
  assert.equal(finish.length,1);game.cancelIntent();
  if(completeOldFirst){finish[0]();await setImmediate();}
  game.selected(fingerprint);await setImmediate();assert.equal(finish.length,2,'canceled readiness retained its in-flight lock');
  if(!completeOldFirst){finish[0]();await setImmediate();}
  game.retry();await setImmediate();assert.equal(finish.length,2,'old completion released the newer offer');
  finish[1]();await setImmediate();assert.equal(sent.length,1,'only current readiness may publish');
  game.enter({id:'room',role:'guest',matches:true,fingerprint,peer:{epoch:'peer'},established:false} as import('../../../packages/contracts/src/rooms.ts').RoomView);
  await setImmediate();assert.equal(finish.length,2,'retry during preparation invalidated completed readiness');
 }
});

test('current input and completed state hash wake the existing frame owner without polling',async()=>{
 const {setImmediate}=await import('node:timers/promises');
 const fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}} as const;
 const epoch='e'.repeat(32),peerEpoch='p'.repeat(32),hash='c'.repeat(64),wakes:string[]=[];
 let driver!:import('./player.ts').GameDriver,finishHash!:(value:{hash:string})=>void;
 const player={frameRate:()=>60,holdForGame:async()=>({hash,frame:0,fresh:true}),startGame(value:typeof driver){driver=value;},wakeGame(value:string){wakes.push(value);},stateHash:()=>new Promise<{hash:string}>(resolve=>{finishHash=resolve;}),stopGame(){},allowLocalPlay(){}} as unknown as import('./player.ts').LocalPlayer;
 const game=new GameClient(()=>player,async()=>{},()=>{});
 const channel={readyState:'open',send(){},onmessage:undefined} as unknown as RTCDataChannel;
 game.enter({id:'room',role:'guest',matches:true,fingerprint,peer:{epoch:peerEpoch},reservationIntent:'intent'} as import('../../../packages/contracts/src/rooms.ts').RoomView);
 game.selected(fingerprint);game.ready(channel,peerEpoch);await setImmediate();
 game.handle({type:'gamePrepare',peerEpoch,epoch,hash,delay:6});await setImmediate();
 game.handle({type:'gameStart',peerEpoch,epoch,delay:6});
 const receive=(frame:number,packetEpoch=epoch)=>channel.onmessage!.call(channel,new MessageEvent('message',{data:JSON.stringify({kind:'input',epoch:packetEpoch,frame,mask:0})}));
 receive(0,'z'.repeat(32));assert.deepEqual(wakes,[],'obsolete epoch woke the current frame owner');
 for(let frame=0;frame<120;frame++){receive(frame);assert.equal(wakes.length,frame+1,'admitted input waited for polling');assert.equal(driver.next(0)?.frame,frame);driver.committed(frame);}
 assert.equal(driver.next(0),undefined,'frame advanced while its hash was pending');
 finishHash({hash});await setImmediate();assert.equal(wakes.length,121,'completed hash waited for polling');assert.ok(wakes.every(value=>value===epoch));
});
