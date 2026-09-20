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
 const player={holdForGame:async()=>({hash:'c'.repeat(64),frame:0,fresh:true}),stopGame(){},allowLocalPlay(){}} as unknown as import('./player.ts').LocalPlayer;
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
