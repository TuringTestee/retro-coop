import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isWorkerRequest } from './index.ts';
test('worker accepts transferable ROMs and controller bytes, rejects malformed inputs', () => {
 for (const data of [{type:'load',rom:new ArrayBuffer(16)}, {type:'frame',p1:255,p2:0}, {type:'pause'}]) assert.equal(isWorkerRequest(data),true);
 for (const data of [null,{}, {type:'load',rom:'url'}, {type:'load',rom:new ArrayBuffer(0)}, {type:'frame',p1:-1,p2:0}, {type:'frame',p1:1.2,p2:0}, {type:'frame',p1:0,p2:256}]) assert.equal(isWorkerRequest(data),false);
});
