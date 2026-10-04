import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {setImmediate} from 'node:timers/promises';
import {RoomClient} from './room-client.ts';
import {Rooms} from '../../coordinator/src/rooms.ts';
import type {Fingerprint,RoomCommand,RoomData} from '../../../packages/contracts/src/rooms.ts';

type Selection={roomId:string;intent:string;expectedRevision:number};
type Command=RoomCommand extends infer T?T extends RoomCommand?Omit<T,'requestId'>:never:never;
type TestClient=Pick<RoomClient,'reconcileGameSelection'|'cancelGameSelection'|'act'> & {confirmSelection:(selection:Selection)=>Promise<RoomData>};
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:4,submapper:0,region:'NTSC',bytes:40976}};
function prepared(){
 let now=1000;const rooms=new Rooms(()=>now),host=rooms.attach(undefined,()=>{},()=>{});
 const act=(command:Command)=>rooms.handle(host.token,{...command,requestId:randomUUID()} as Exclude<RoomCommand,{type:'hello'}>);
 const lobby=act({type:'createLobby',intent:randomUUID(),label:'Game Night',visibility:'public'}).room!,intent=randomUUID();
 act({type:'beginGameSelection',roomId:lobby.id,intent,expectedRevision:lobby.revision,fingerprint,title:'New NES'});
 const lease=rooms.beginUpload(host.token,lobby.id,intent,fingerprint.cartridge.bytes);rooms.commitUpload(lobby.id,lease.id,'/private/verified-nes');
 const selection={roomId:lobby.id,intent,expectedRevision:lobby.revision},commands:unknown[]=[],states:Array<Record<string,unknown>>=[];
 const fixture={disposed:false,confirmingSelection:selection,gameSelection:intent,state:{room:lobby},
  publish(patch:Record<string,unknown>){states.push(patch);},failure(error:Error){states.push({status:error.message});},apply(data:RoomData){this.state.room=data.room!;},
  async connectOnce(){rooms.attach(host.token,()=>{},()=>{});},async connect(){},
  async request(command:Command){commands.push(command);return act(command);},setRoom(room:typeof lobby){this.state.room=room;}
 };
 const client=Object.assign(Object.create(RoomClient.prototype),fixture) as TestClient;
 return {client,selection,rooms,host,act,commands,states,advance(ms:number){now+=ms;rooms.sweep();}};
}

test('lost successful confirmation retries the original intent and revision against room authority',async()=>{
 const t=prepared();let lost=true;
 Object.assign(t.client,{async request(command:Command){t.commands.push(command);const result=t.act(command);if(lost){lost=false;throw Error('Reply lost after commit');}return result;}});
 const result=await t.client.confirmSelection(t.selection);
 assert.equal(result.room?.fingerprint?.romSha256,fingerprint.romSha256);assert.equal(result.room?.revision,t.selection.expectedRevision+1);
 assert.deepEqual(t.commands,[{type:'confirmGameSelection',...t.selection},{type:'confirmGameSelection',...t.selection}]);
});

test('authoritative rejection and expired intent exit without retry or fingerprint inference',async()=>{
 for(const expired of [false,true]){
  const t=prepared();if(expired)t.advance(300_001);else t.act({type:'cancelGameSelection',roomId:t.selection.roomId,intent:t.selection.intent});
  const result=await t.client.reconcileGameSelection();assert.equal(result.ok,false);assert.equal(result.uncertain,false);assert.equal(t.commands.length,1);
  assert.equal((t.client as unknown as {confirmingSelection?:Selection}).confirmingSelection,undefined);
 }
});

test('exhausted transport retries retain exact intent and report unknown outcome without cancellation',async()=>{
 const t=prepared();Object.assign(t.client,{async request(command:unknown){t.commands.push(command);throw Error('Disconnected');}});
 const result=await t.client.reconcileGameSelection();assert.equal(result.ok,false);assert.equal(result.uncertain,true);assert.equal(t.commands.length,3);
 assert.equal((t.client as unknown as {confirmingSelection:Selection}).confirmingSelection,t.selection);
 t.client.cancelGameSelection();assert.equal(t.commands.length,3);assert.match(String(t.states.at(-1)?.status),/Reconnect/);
});

test('a retained unknown selection is reconciled by exact intent on the next retry',async()=>{
 const t=prepared();let repliesLost=true;
 Object.assign(t.client,{async request(command:Command){t.commands.push(command);const result=t.act(command);if(repliesLost)throw Error('Reply lost after commit');return result;}});
 assert.equal((await t.client.reconcileGameSelection()).uncertain,true);
 repliesLost=false;assert.equal((await t.client.reconcileGameSelection()).ok,true);
 assert.equal((t.client as unknown as {state:{room:{revision:number}}}).state.room.revision,t.selection.expectedRevision+1);
 assert.equal((t.client as unknown as {confirmingSelection?:Selection}).confirmingSelection,undefined);
 assert.equal(t.commands.length,4);for(const command of t.commands)assert.deepEqual(command,{type:'confirmGameSelection',...t.selection});
});

test('reconnection is bounded by three existing request deadlines even if connect stalls',async context=>{
 context.mock.timers.enable({apis:['setTimeout']});
 const t=prepared();let calls=0;Object.assign(t.client,{async request(){calls++;throw Error('Lost reply');},connectOnce(){return new Promise(()=>{});}});
 const pending=t.client.reconcileGameSelection();await setImmediate();context.mock.timers.tick(24_000);
 const result=await pending;assert.equal(result.uncertain,true);assert.equal(calls,1);assert.match(result.message!,/unknown/);
});

test('room exit remains available during unknown confirmation and a late reply cannot reinstall it',async()=>{
 const t=prepared();let release!:(data:RoomData)=>void;
 Object.assign(t.client,{request(command:Command){t.commands.push(command);if(command.type==='confirmGameSelection')return new Promise<RoomData>(resolve=>{release=resolve;});return Promise.resolve(t.act(command));}});
 const pending=t.client.confirmSelection(t.selection);await setImmediate();
 assert.equal(await t.client.act({type:'close',roomId:t.selection.roomId}),true);
 release({room:t.rooms.attach(t.host.token,()=>{},()=>{}).data.room});
 await assert.rejects(pending,error=>(error as Error & {code:string}).code==='game_selection_ended');
 assert.equal((t.client as unknown as {state:{room?:unknown}}).state.room,undefined);
 assert.equal((t.client as unknown as {confirmingSelection?:Selection}).confirmingSelection,undefined);
});
