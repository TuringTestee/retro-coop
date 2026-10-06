import {test,type TestContext} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {LocalPlayer} from './player.ts';
import {RoomClient} from './room-client.ts';

test('late committed checkpoint response cannot publish or release inputs owned by a newer attempt',async()=>{
 const pending:Array<{operationId:string;resolve:(reply:unknown)=>void}>=[],published:unknown[]=[];let flushed=0,released=0;
 const player=Object.assign(Object.create(LocalPlayer.prototype),{
  shared:true,state:{running:false},busy:false,audio:{flush(){flushed++;}},release(){released++;},publish(value:unknown){published.push(value);},
  fileRequest(command:{type:string;operationId:string;epoch?:string;frame?:number;hash?:string}){
   if(command.type==='peer-checkpoint-prepare')return Promise.resolve({...command,type:'peer-checkpoint-prepared'});
   if(command.type==='peer-checkpoint-cancel')return Promise.resolve({...command,type:'peer-checkpoint-cancelled'});
   return new Promise(resolve=>pending.push({operationId:command.operationId,resolve}));
  }
 }) as LocalPlayer;
 let oldCurrent=true;const old=player.importPeerCheckpoint('old-epoch',10,new ArrayBuffer(72),'identity','hash',()=>oldCurrent);await setImmediate();assert.equal(pending.length,1);
 oldCurrent=false;player.cancelPeerCheckpoint();
 const current=player.importPeerCheckpoint('new-epoch',20,new ArrayBuffer(72),'identity','hash',()=>true);await setImmediate();assert.equal(pending.length,2);
 pending[0].resolve({type:'peer-checkpoint-imported',operationId:pending[0].operationId,epoch:'old-epoch',frame:10,hash:'hash'});await old;
 assert.equal(flushed,0);assert.equal(released,0);assert.deepEqual(published,[],'obsolete success overwrote current player UI');
 pending[1].resolve({type:'peer-checkpoint-imported',operationId:pending[1].operationId,epoch:'new-epoch',frame:20,hash:'hash'});await current;
 assert.equal(flushed,1);assert.equal(released,1);assert.equal((published[0] as {frames:number}).frames,20);
});

test('an invalid replacement keeps the previous game but reports a failed new selection',async()=>{
 const previous={romSha256:'old-rom',coreSha256:'old-core'};
 const states:Array<{loaded:boolean;loading:boolean;selectionPhase?:string;fingerprint?:unknown;status:string}>=[];
 const player=Object.assign(Object.create(LocalPlayer.prototype),{
  selectionListeners:new Set(),generation:0,disposed:false,active:{},state:{loaded:true,loading:false,running:false,frames:0,status:'Previous game loaded.',fingerprint:previous},
  rejectPending(){},activateAudio(){},read:async()=>new Uint8Array([1,2,3]).buffer,
  update(value:typeof states[number]){states.push(value);}
 }) as LocalPlayer;
 await player.load({name:'bad.nes'} as File,undefined,true);
 const result=states.at(-1)!;
 assert.equal(result.selectionPhase,'failed');
 assert.equal(result.loading,false);
 assert.equal(result.loaded,true);
 assert.equal(result.fingerprint,previous);
 assert.match(result.status,/not an NES game/);
});

// Exercise the real candidate handler across the asynchronous lobby commit gate.
async function preparedReplacement(context:TestContext){
 let candidate: {onmessage?:(event:unknown)=>Promise<void>;terminate:()=>void},candidateStopped=0,oldStopped=0,remembered=0,current=true;
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'Worker');
 Object.defineProperty(globalThis,'Worker',{configurable:true,writable:true,value:class {constructor(){candidate=this;}terminate(){candidateStopped++;}}});
 context.after(()=>{if(descriptor)Object.defineProperty(globalThis,'Worker',descriptor);else Reflect.deleteProperty(globalThis,'Worker');});
 const old={terminate(){oldStopped++;}},fingerprint={romSha256:'old-rom',coreSha256:'old-core'};
 const rom=new Uint8Array(16+16384);rom.set([0x4e,0x45,0x53,0x1a,1,0]);
 const player=Object.assign(Object.create(LocalPlayer.prototype),{
  selectionListeners:new Set(),generation:0,disposed:false,active:old,
  state:{loaded:true,loading:false,running:false,frames:0,status:'Previous game loaded.',fingerprint,previewImage:'old-preview'},
  rejectPending(){},activateAudio(){},read:async()=>rom.buffer,send(){},persistBattery:async()=>{},
  fileRequest:async(command:{type:string})=>{if(command.type==='state-preview')throw Error('Optional preview unavailable');return {type:'state-hash',info:{hash:'prepared',frame:0,fresh:true}};},
  inputDevice:()=>({available:true}),audio:{flush(){}},release(){},update(){}
 }) as LocalPlayer;
 let resolve!:(result:{ok:boolean;uncertain?:boolean;message?:string})=>void,reached!:()=>void;
 const reachedGate=new Promise<void>(done=>reached=done),gate=new Promise<{ok:boolean;uncertain?:boolean;message?:string}>(done=>resolve=done);
 await player.load(new File([rom],'replacement.nes'),undefined,true,()=>current,async()=>{reached();return gate;},()=>remembered++);
 const handled=candidate!.onmessage!({data:{type:'ready',coreSha256:'a'.repeat(64),fps:60,battery:false}});await reachedGate;
 async function next(){
  let resolveNext!:(result:{ok:boolean;uncertain?:boolean;message?:string})=>void,reachedNext!:()=>void;
  const nextGate=new Promise<{ok:boolean;uncertain?:boolean;message?:string}>(done=>resolveNext=done);
  const nextReached=new Promise<void>(done=>reachedNext=done);
  await player.load(new File([rom],'next.nes'),undefined,true,()=>true,async()=>{reachedNext();return nextGate;},()=>remembered++);
  const handledNext=candidate!.onmessage!({data:{type:'ready',coreSha256:'b'.repeat(64),fps:60,battery:false}});await nextReached;
  return {resolve:resolveNext,handled:handledNext,worker:candidate!};
 }
 return {player,old,fingerprint,resolve,handled,next,get state(){return (player as unknown as {state:{fingerprint:unknown;previewImage?:string;loaded:boolean;loading:boolean;selectionPhase:string}}).state;},get active(){return (player as unknown as {active:unknown}).active;},get oldStopped(){return oldStopped;},get candidateStopped(){return candidateStopped;},get remembered(){return remembered;},replaceContext(){current=false;}};
}

test('failed lobby upload retains the previous worker, fingerprint and preview without remembering the candidate',async context=>{
 const t=await preparedReplacement(context);assert.equal(t.active,t.old);assert.equal(t.oldStopped,0);assert.equal(t.remembered,0);
 t.resolve({ok:false,message:'Upload failed. Retry.'});await t.handled;
 assert.equal(t.active,t.old);assert.equal(t.oldStopped,0);assert.equal(t.candidateStopped,1);assert.equal(t.state.fingerprint,t.fingerprint);assert.equal(t.state.previewImage,'old-preview');assert.equal(t.state.selectionPhase,'failed');assert.equal(t.remembered,0);
});

test('cancelled or replaced contexts cannot install a late confirmed candidate',async context=>{
 const t=await preparedReplacement(context);t.replaceContext();t.player.cancel();t.resolve({ok:true});await t.handled;
 assert.equal(t.active,t.old);assert.equal(t.oldStopped,0);assert.equal(t.candidateStopped,1);assert.equal(t.remembered,0);
});

test('uncertain confirmation preserves both workers, blocks Cancel and installs only after exact reconciliation',async context=>{
 const t=await preparedReplacement(context);t.player.setSelectionFinishing();t.player.cancel();assert.equal(t.candidateStopped,0);
 t.resolve({ok:false,uncertain:true,message:'Unknown confirmation.'});await t.handled;
 assert.equal(t.state.selectionPhase,'uncertain');assert.equal(t.active,t.old);assert.equal(t.oldStopped,0);assert.equal(t.remembered,0);
 t.player.cancel();assert.equal(t.candidateStopped,0);
 t.player.selectionCompletion()({ok:true});assert.notEqual(t.active,t.old);assert.equal(t.oldStopped,1);assert.equal(t.state.loaded,true);assert.equal(t.state.loading,false);assert.equal(t.remembered,1);assert.equal(t.player.selectionLocked(),false);
 // Recovery selects an already initialized worker, so its confirmation cannot lock a later fallback load.
 t.player.setSelectionFinishing();assert.equal(t.player.selectionLocked(),false);
});


test('an acknowledged candidate after actual context departure releases its lock and worker',async context=>{
 const t=await preparedReplacement(context);t.player.setSelectionFinishing();t.replaceContext();
 t.resolve({ok:true});await t.handled;
 assert.equal(t.player.selectionLocked(),false);assert.equal(t.candidateStopped,1);assert.equal(t.state.loading,false);assert.equal(t.active,t.old);assert.equal(t.remembered,0);
});

test('successful departure abandons a confirming candidate before battery persistence completes',async context=>{
 const t=await preparedReplacement(context);t.player.setSelectionFinishing();let persisted!:()=>void;
 Object.assign(t.player,{canvas:{getContext(){return null;}},pause(){},persistBattery:()=>new Promise<void>(resolve=>persisted=resolve)});
 const quitting=t.player.quit();assert.equal(t.player.selectionLocked(),false);assert.equal(t.candidateStopped,1);
 t.resolve({ok:true});await t.handled;assert.equal(t.remembered,0);
 persisted();await quitting;assert.equal(t.oldStopped,1);
});

for(const result of [{ok:true},{ok:false,message:'Old upload failed.'},{ok:false,uncertain:true,message:'Old upload uncertain.'}]){
 test(`cancelled selection cannot finish its replacement with ${JSON.stringify(result)}`,async context=>{
  const t=await preparedReplacement(context),lateReconciliation=t.player.selectionCompletion();t.player.cancel();const next=await t.next();t.player.setSelectionFinishing();
  lateReconciliation(result);
  t.resolve(result);await t.handled;
  assert.equal(t.candidateStopped,1,'old completion terminated the newer worker');
  assert.equal(t.player.selectionLocked(),true,'old completion changed the current confirmation lock');
  assert.equal(t.state.selectionPhase,'loading');assert.equal(t.active,t.old);
  next.resolve({ok:true});await next.handled;
  assert.equal(t.active,next.worker);assert.equal(t.oldStopped,1);assert.equal(t.remembered,1);
  assert.equal((t.state.fingerprint as {coreSha256:string}).coreSha256,'b'.repeat(64));
  assert.equal(t.state.selectionPhase,'loaded');assert.equal(t.player.selectionLocked(),false);
 });
}

for(const outcome of ['success','failure'] as const){
 test(`old selection reconciliation ${outcome} cannot publish into a replacement context`,async()=>{
  let resolve!:(value:unknown)=>void,reject!:(error:Error)=>void;
  const old={roomId:'old-room',intent:'old-intent',expectedRevision:1},next={roomId:'new-room',intent:'new-intent',expectedRevision:2};
  const published:unknown[]=[],applied:unknown[]=[],failed:unknown[]=[];
  const client=Object.assign(Object.create(RoomClient.prototype),{confirmingSelection:old,gameSelection:old.intent,
   confirmSelection:()=>new Promise((done,fail)=>{resolve=done;reject=fail;}),publish:(value:unknown)=>published.push(value),apply:(value:unknown)=>applied.push(value),failure:(value:unknown)=>failed.push(value)}) as RoomClient;
  const pending=client.reconcileGameSelection();Object.assign(client,{confirmingSelection:next,gameSelection:next.intent});
  if(outcome==='success')resolve({room:{id:old.roomId}});else reject(Error('Old confirmation failed.'));
  await pending;assert.deepEqual(applied,[]);assert.deepEqual(failed,[]);assert.deepEqual(published,[{selectionFinishing:true,status:'Finishing game selection…'}]);
  assert.equal((client as unknown as {confirmingSelection:unknown}).confirmingSelection,next);
 });
}

for(const outcome of ['success','failure'])for(const replacement of [undefined,{id:'next',chatMembership:'next-member',role:'host',peers:[]}]){
 test(`lobby selection ownership ends on ${replacement?'replacement':'departure'} with late ${outcome}, preserving newer work`,async()=>{
  const old={id:'old',chatMembership:'old-member',role:'host',peers:[]},selection={roomId:'old',intent:'old-intent',expectedRevision:1};
  let resolve!:(value:unknown)=>void,reject!:(error:Error)=>void;const abort=new AbortController(),applied:unknown[]=[];
  const client=Object.assign(Object.create(RoomClient.prototype),{state:{room:old,busy:true,uploading:true,selectionFinishing:true},confirmingSelection:selection,gameSelection:selection.intent,uploadAbort:abort,
   peers:new Map(),peerStates:new Map(),game:{enter(){}},chat:{enter(){}},player:()=>null,reportLoadedGame(){},closePeers(){},
   update(){},confirmSelection:()=>new Promise((done,fail)=>{resolve=done;reject=fail;}),apply:(value:unknown)=>applied.push(value)}) as RoomClient;
  const owned=client as unknown as {setRoom(room?:unknown):void;state:{busy:boolean;uploading:boolean;selectionFinishing:boolean};confirmingSelection:unknown;gameSelection:unknown;uploadAbort:unknown};
  const pending=client.reconcileGameSelection();owned.setRoom(replacement);
  assert.equal(abort.signal.aborted,true);assert.equal(owned.confirmingSelection,undefined);assert.equal(owned.gameSelection,undefined);assert.equal(owned.uploadAbort,undefined);
  assert.equal(owned.state.selectionFinishing,false);assert.equal(owned.state.busy,false);assert.equal(owned.state.uploading,false);
  Object.assign(client,{confirmingSelection:{roomId:'next',intent:'next-intent'},gameSelection:'next-intent'});owned.state.selectionFinishing=true;
  if(outcome==='success')resolve({room:old});else reject(Error('Old reply failed.'));await pending;assert.deepEqual(applied,[]);assert.equal(owned.state.selectionFinishing,true);
 });
}
test('same lobby updates preserve selection ownership and unrelated admission work',()=>{
 const room={id:'same',chatMembership:'member',role:'host',peers:[]},selection={roomId:'same',intent:'intent',expectedRevision:1},abort=new AbortController();
 const client=Object.assign(Object.create(RoomClient.prototype),{state:{room,busy:true,uploading:true,selectionFinishing:true},confirmingSelection:selection,gameSelection:selection.intent,uploadAbort:abort,
 peers:new Map(),peerStates:new Map(),game:{enter(){}},chat:{enter(){}},player:()=>null,reportLoadedGame(){},closePeers(){},update(){}}) as unknown as {setRoom(room?:unknown):void;state:{busy:boolean};confirmingSelection:unknown};
 client.setRoom({...room});assert.equal(abort.signal.aborted,false);assert.equal(client.confirmingSelection,selection);assert.equal(client.state.busy,true);
 Object.assign(client,{state:{busy:true},confirmingSelection:undefined,gameSelection:undefined,uploadAbort:undefined});client.setRoom(undefined);assert.equal(client.state.busy,true);
});

test('authorization loss force-abandons a locked candidate without disturbing its replacement',async context=>{
 const t=await preparedReplacement(context);t.player.setSelectionFinishing();const late=t.player.selectionCompletion();
 t.player.rejectSelection('The lobby changed. Choose a game again.');assert.equal(t.player.selectionLocked(),false);assert.equal(t.candidateStopped,1);
 const next=await t.next();t.player.setSelectionFinishing();late({ok:true});t.resolve({ok:true});await t.handled;
 assert.equal(t.player.selectionLocked(),true);assert.equal(t.active,t.old);
 next.resolve({ok:true});await next.handled;assert.equal(t.active,next.worker);assert.equal(t.player.selectionLocked(),false);
});
test('asynchronous checkpoint authorization is checked again after preparation before native commit',async()=>{
 let checks=0,commits=0;const player=Object.assign(Object.create(LocalPlayer.prototype),{shared:true,state:{running:false},busy:false,audio:{flush(){}},release(){},publish(){},fileRequest:async(command:{type:string})=>{if(command.type==='peer-checkpoint-commit')commits++;return {...command,type:command.type==='peer-checkpoint-prepare'?'peer-checkpoint-prepared':command.type==='peer-checkpoint-commit'?'peer-checkpoint-imported':'peer-checkpoint-cancelled'};}}) as LocalPlayer;
 const authorized=async()=>++checks===1;
 await assert.rejects(player.importPeerCheckpoint('epoch',10,new ArrayBuffer(72),'identity','hash',authorized),/authorization changed/);
 assert.equal(commits,0);
});
