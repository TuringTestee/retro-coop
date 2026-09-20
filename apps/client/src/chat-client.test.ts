import {test} from 'node:test';
import assert from 'node:assert/strict';
import {ChatClient,type ChatState} from './chat-client.ts';
import type {RoomView,RoomData} from '../../../packages/contracts/src/rooms.ts';
const room:RoomView={id:'room',chatMembership:'member',connectionPolicy:'standard',peer:{policy:'standard',status:'waiting'},invite:'invite',role:'guest',slot:2,label:'Room',host:'Host',visibility:'public',status:'reserved',occupancy:2,fingerprint:{romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:0,submapper:0,region:'NTSC',bytes:24592}}};
test('explicit retry preserves message identity and draft, and membership changes reject late responses',async()=>{
 let state:ChatState={messages:[],draft:'',sending:false},calls=0;
 const sent:string[]=[];let resolve:((data:RoomData)=>void)|undefined;
 const client=new ChatClient(value=>state=value,command=>{sent.push(command.clientId);if(++calls===1) return Promise.reject(Error('disconnected'));return new Promise(done=>resolve=done);});
 client.enter(room);client.draft('keep this');await client.send('Me');assert.equal(state.draft,'keep this');assert.equal(state.outbox?.error,'disconnected');
 const retry=client.send('Me');assert.equal(sent[0],sent[1]);resolve!({chatAck:{clientId:sent[1],messageId:'accepted'}});await retry;assert.equal(state.messages.length,1);assert.equal(state.draft,'');
 client.draft('old membership');const pending=client.send('Me');state=client.enter({...room,chatMembership:'new-member'});resolve!({chatAck:{clientId:sent[2],messageId:'late'}});await pending;assert.deepEqual(state.messages,[]);assert.equal(state.draft,'');
});
test('received own message confirms delivery once; stale membership events cannot leak into a rejoin',async()=>{
 let state:ChatState={messages:[],draft:'',sending:false};let reject:((error:Error)=>void)|undefined;
 const client=new ChatClient(value=>state=value,()=>new Promise((_,fail)=>reject=fail));client.enter(room);client.draft('hello');const pending=client.send('Me');
 const message={id:'server-id',clientId:state.outbox!.command.clientId,sender:'guest' as const,nickname:'Me',text:'hello',at:1};
 client.receive({type:'chat',roomId:room.id,membership:'member',message});assert.equal(state.messages.length,1);assert.equal(state.outbox,undefined);
 reject!(Error('ack lost'));await pending;assert.equal(state.outbox,undefined);
 client.receive({type:'chat',roomId:room.id,membership:'member',message});assert.equal(state.messages.length,1);
 state=client.enter({...room,chatMembership:'new'});client.receive({type:'chat',roomId:room.id,membership:'member',message});assert.equal(state.messages.length,0);
});

test('current-member chat retains at most 100 messages and clears on room closure',()=>{
 let state:ChatState={messages:[],draft:'',sending:false};const client=new ChatClient(value=>state=value,async()=>({}));client.enter(room);
 for(let i=0;i<150;i++) client.receive({type:'chat',roomId:room.id,membership:room.chatMembership,message:{id:String(i),clientId:String(i),sender:'host',nickname:'Host',text:`message ${i}`,at:i}});
 assert.equal(state.messages.length,100);assert.equal(state.messages[0].text,'message 50');assert.equal(state.messages.at(-1)!.text,'message 149');
 state=client.enter(undefined);assert.deepEqual(state.messages,[]);
});
