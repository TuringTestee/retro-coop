import {test}from'node:test';import assert from'node:assert/strict';import{pageRows}from'./directory-page.ts';
test('directory pages are deterministic and clamp after filtering or live removal',()=>{assert.deepEqual(pageRows([0,1,2,3,4,5],1),{page:1,pages:2,rows:[4,5]});assert.deepEqual(pageRows([0,1],9),{page:0,pages:1,rows:[0,1]});assert.deepEqual(pageRows([],1),{page:0,pages:1,rows:[]});});
