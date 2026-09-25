import test from 'node:test';
import assert from 'node:assert/strict';
import {connectionStatus} from './connection-status.ts';
import type {RoomState} from './room-client.ts';

test('route status distinguishes automatic relay, Relay only, direct, and recovery',()=>{
 const state=(policy:'standard'|'relay',route?:'direct'|'relay',status='connected')=>({room:{peer:{policy,status}},connection:{status:'Peer transport connected.',route}} as RoomState);
 assert.equal(connectionStatus(state('standard','relay')),'Direct connection unavailable. Relay keeps you playing together.');
 assert.equal(connectionStatus(state('relay','relay')),'Relay only is on. Connected through the relay.');
 assert.equal(connectionStatus(state('standard','direct')),'Peer transport connected. Route: direct.');
 assert.equal(connectionStatus(state('standard',undefined)),'Peer transport connected.');
 assert.match(connectionStatus(state('relay',undefined,'relay_unavailable')),/Relay service is unavailable/);
});
