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
