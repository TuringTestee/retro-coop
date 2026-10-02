import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {LocalPlayer} from './player.ts';

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
  generation:0,disposed:false,active:{},state:{loaded:true,loading:false,running:false,frames:0,status:'Previous game loaded.',fingerprint:previous},
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
