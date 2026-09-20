import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isWorkerRequest } from './index.ts';
test('worker accepts transferable ROMs and controller bytes, rejects malformed inputs', () => {
 for (const data of [{type:'load',rom:new ArrayBuffer(16)}, {type:'frame',p1:255,p2:0}, {type:'pause'}]) assert.equal(isWorkerRequest(data),true);
 for (const data of [null,{}, {type:'load',rom:'url'}, {type:'load',rom:new ArrayBuffer(0)}, {type:'frame',p1:-1,p2:0}, {type:'frame',p1:1.2,p2:0}, {type:'frame',p1:0,p2:256}]) assert.equal(isWorkerRequest(data),false);
});

test('battery request shape is correlated; loaded core owns the file-size policy', () => {
 assert.equal(isWorkerRequest({type:'battery-export',requestId:0}),true);
 assert.equal(isWorkerRequest({type:'battery-import',requestId:3,bytes:new ArrayBuffer(8192)}),true);
 for (const requestId of [-1, 1.1, Infinity, Number.MAX_SAFE_INTEGER+1, '1', undefined]) assert.equal(isWorkerRequest({type:'battery-export',requestId}),false);
 for (const bytes of [new ArrayBuffer(0),'file']) assert.equal(isWorkerRequest({type:'battery-import',requestId:0,bytes}),false);
});

test('state operations reuse local-file shape and correlation validation', () => {
 for (const data of [{type:'state-info',requestId:1},{type:'state-validate',requestId:2,bytes:new ArrayBuffer(72)},{type:'state-export',requestId:1},{type:'state-import',requestId:2,bytes:new ArrayBuffer(72)}]) assert.equal(isWorkerRequest(data),true);
 for (const data of [{type:'state-info',requestId:-1},{type:'state-validate',requestId:2,bytes:new ArrayBuffer(0)},{type:'state-export',requestId:-1},{type:'state-import',requestId:2,bytes:'file'},{type:'state-import',requestId:2,bytes:new ArrayBuffer(0)}]) assert.equal(isWorkerRequest(data),false);
});

test('shared worker frames require a valid paired epoch and frame, and hash reuses the local RPC boundary',()=>{
 assert.equal(isWorkerRequest({type:'state-hash',requestId:12}),true);
 assert.equal(isWorkerRequest({type:'frame',p1:0,p2:255,epoch:'a'.repeat(24),frame:0}),true);
 for(const tag of [{epoch:'a'.repeat(24)},{frame:0},{epoch:' '.repeat(24),frame:0},{epoch:'a'.repeat(24),frame:-1}])assert.equal(isWorkerRequest({type:'frame',p1:0,p2:0,...tag}),false);
});
