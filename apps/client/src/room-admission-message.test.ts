import assert from 'node:assert/strict';
import {test} from 'node:test';
import {roomAdmissionMessage} from './room-admission-message.ts';

test('password step explains structured admission races without showing unrelated status',()=>{
 assert.equal(roomAdmissionMessage(undefined),'');
 assert.equal(roomAdmissionMessage({code:'room_changed',message:'That room has changed. Review the current room before trying again.'}),
  'That room has changed. Review the current room before trying again.');
 assert.equal(roomAdmissionMessage({code:'host_reconnecting',message:'The host is reconnecting. Try joining again later.'}),
  'The host is reconnecting. Try joining again later.');
 assert.equal(roomAdmissionMessage({code:'rate_limited',message:'Try later.'},2800),'Too many tries. Try again in 3 seconds.');
});
