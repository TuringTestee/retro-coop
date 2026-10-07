import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {Rooms} from './rooms.ts';
import {catalogEntry} from '../../../packages/contracts/src/catalog.ts';
import {parseRoomCommand,type RoomEvent,type RoomView,type Fingerprint} from '../../../packages/contracts/src/rooms.ts';
const fingerprint:Fingerprint={romSha256:'a'.repeat(64),coreSha256:'b'.repeat(64),localSchema:1,settings:'auto-region;zero-ram;48000hz;standard-p1-p2',cartridge:{format:'iNES',mapper:1,submapper:0,region:'NTSC',bytes:32784}};
function setup(file=fingerprint){
 const rooms=new Rooms(),events:RoomEvent[][]=Array.from({length:6},()=>[]),sessions=events.map(list=>rooms.attach(undefined,event=>list.push(event),()=>{}));
 let latest!:RoomView;
 function act(who:number,input:Record<string,unknown>){const command=parseRoomCommand({...input,requestId:randomUUID()});assert.ok(command&&command.type!=='hello');const result=rooms.handle(sessions[who].token,command);if(result.room)latest=result.room;return result;}
 const intent=randomUUID();act(0,{type:'create',intent,visibility:'public',fingerprint:file});act(0,{type:'confirmCreate',intent});
 const join=(who:number)=>act(who,{type:'join',invite:latest.invite,intent:randomUUID()}).room!;
 const edit=(who:number,type:string,extra:Record<string,unknown>)=>act(who,{type,roomId:latest.id,expectedRevision:latest.revision,...extra}).room!;
 return {act,join,edit,events,view:()=>latest};
}
test('five stable slots admit one final claimant and reject sixth member without overwriting identities',()=>{
 const t=setup();assert.deepEqual(t.view().slots.map(s=>s.id),['slot-1','slot-2','slot-3','slot-4','slot-5']);
 for(let i=1;i<5;i++)assert.equal(t.join(i).slot,`slot-${i+1}`);
 const before=t.view();assert.equal(before.occupancy,5);assert.equal(before.openSlots,0);assert.equal(new Set(before.slots.map(s=>s.member!.id)).size,5);
 assert.throws(()=>t.join(5),/room_full/);assert.deepEqual(t.view(),before);
 const row=t.act(5,{type:'directory'}).directory!.find(row=>row.id===before.id)!;assert.equal(row.occupancy,5);
});
test('host role swaps are atomic and stable; stale and unauthorized commands cannot alter ownership',()=>{
 const t=setup();t.join(1);t.join(2);const before=t.view(),ids=before.slots.map(s=>s.member?.id);
 assert.throws(()=>t.edit(1,'slotRole',{slotId:'slot-3',role:'player1'}),/host_only/);
 assert.throws(()=>t.edit(0,'slotRole',{slotId:'slot-4',role:'player1'}),/controller_occupied/);
 const swapped=t.edit(0,'slotRole',{slotId:'slot-3',role:'player1'});assert.deepEqual(swapped.slots.map(s=>s.member?.id),ids);assert.equal(swapped.slots[0].role,'observer');assert.equal(swapped.slots[2].role,'player1');assert.equal(swapped.hostMembership,ids[0]);assert.deepEqual(swapped.game.controllers.owners,[ids[2],ids[1]]);
 assert.equal(swapped.slots.filter(s=>s.role==='player1').length,1);
 assert.throws(()=>t.edit(0,'slotRole',{slotId:'slot-3',role:'player2',expectedRevision:before.revision}),/room_changed/);
 assert.equal(t.edit(0,'slotRole',{slotId:'slot-3',role:'player1'}).revision,swapped.revision,'same role is idempotent');
});
test('only empty slots close; removed membership cannot retain room or rejoin authority',()=>{
 const t=setup();const member=t.join(1);assert.throws(()=>t.edit(0,'slotAvailability',{slotId:'slot-2',open:false}),/slot_occupied/);
 const closed=t.edit(0,'slotAvailability',{slotId:'slot-3',open:false});assert.equal(closed.slots[2].open,false);const next=t.join(2);assert.equal(next.slot,'slot-4');
 assert.throws(()=>t.edit(1,'memberRemove',{membership:member.hostMembership}),/host_only/);
 assert.throws(()=>t.edit(0,'memberRemove',{membership:member.hostMembership}),/membership_changed/);
 const removed=t.edit(0,'memberRemove',{membership:member.chatMembership});assert.equal(removed.slots[1].member?.id,next.chatMembership,'remaining player moves up to the earliest open slot');assert.equal(removed.slots[3].member,undefined);assert.ok(t.events[1].some(e=>e.type==='ended'&&e.reason==='removed'));
 assert.throws(()=>t.act(1,{type:'gameReady',revision:removed.game.controllers.revision,roomRevision:removed.revision,frame:0,fresh:true,hash:'c'.repeat(64),protocol:2}),/not_in_room/);
 assert.throws(()=>t.join(1),/room_unavailable/);t.edit(0,'slotAvailability',{slotId:'slot-3',open:true});assert.equal(t.view().slots[2].open,true);
});
test('acquisition and removal use exact member identity without modifying other slots',()=>{
 const t=setup(),one=t.join(1),two=t.join(2);const before=two.slots[2];
 assert.throws(()=>t.act(1,{type:'memberAcquisition',roomId:one.id,membership:two.chatMembership,phase:'failed'}),/membership_changed/);
 const updated=t.act(1,{type:'memberAcquisition',roomId:one.id,membership:one.chatMembership,phase:'failed'}).room!;
 assert.equal(updated.slots[1].member?.acquisition,'failed');assert.deepEqual(updated.slots[2],before);
 const revision=updated.revision;t.edit(0,'slotAvailability',{slotId:'slot-5',open:false});assert.throws(()=>t.edit(0,'memberRemove',{membership:one.chatMembership,expectedRevision:revision}),/room_changed/);
});

test('slot controller choices honor catalog capability and reject superseded controller-consent commands',()=>{
 const entry=catalogEntry('from-below-1.0');const t=setup({...fingerprint,romSha256:entry.sha256,cartridge:{format:entry.format,mapper:entry.mapper,submapper:entry.submapper,region:entry.region,bytes:entry.bytes}});
 assert.deepEqual(t.view().controllerRoles,['player1']);assert.deepEqual(t.view().slots.map(slot=>slot.role),['player1','observer','observer','observer','observer']);
 assert.throws(()=>t.edit(0,'slotRole',{slotId:'slot-2',role:'player2'}),/unsupported_role/);
 assert.equal(parseRoomCommand({type:'gameControllerPropose',requestId:randomUUID(),peerEpoch:randomUUID(),revision:0,mode:'shared',p1:'guest'}),undefined);
});
