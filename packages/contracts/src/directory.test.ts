import {test} from 'node:test';
import assert from 'node:assert/strict';
import {matchingRooms,publicCode} from './directory.ts';
import {parseRoomCommand,type RoomPreview} from './rooms.ts';

test('directory search preserves distinct same-name rooms and supports names or exact normalized codes',()=>{
 const rooms:RoomPreview[]=[{id:'one',label:'Arcade',host:'Jade',visibility:'public',code:'ABCDEFGH',status:'waiting',occupancy:1},{id:'two',label:'Arcade',host:'Coral',visibility:'public',code:'BCDEFGHJ',status:'reserved',occupancy:2}];
 assert.deepEqual(matchingRooms(rooms,'ARca'),rooms);assert.deepEqual(matchingRooms(rooms,'JADE'),[rooms[0]]);
 assert.deepEqual(matchingRooms(rooms,' abcdefgh '),[rooms[0]]);assert.deepEqual(matchingRooms(rooms,'ABCDE'),[]);
 assert.equal(publicCode('O1234567'),undefined);
 for(const type of ['lookupCode','joinCode']) {
  const command={type,requestId:'r'.repeat(32),code:' abcdefgh ',...(type==='joinCode' ? {intent:'i'.repeat(32)}:{})};
  assert.equal((parseRoomCommand(command) as {code:string})?.code,'ABCDEFGH');
  assert.equal(parseRoomCommand({...command,filename:'private.nes'}),undefined);
 }
});
