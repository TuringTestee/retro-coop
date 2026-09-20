import test from 'node:test';
import assert from 'node:assert/strict';
import {actions,defaults,conflict,inputMask,padInputs} from './controls.ts';
import {gamepadMask} from '../../../spikes/d02/demo/runtime/input.js';
test('all eight NES inputs and reserved talk binding share conflict detection',()=>{
 const settings=defaults();
 actions.slice(0,8).forEach((action,index)=>assert.equal(inputMask(settings.keyboard,new Set(settings.keyboard[action])),1<<index));
 assert.equal(inputMask(settings.keyboard,new Set(['KeyV'])),0);
 assert.equal(conflict(settings.keyboard,'a','KeyV'),'pushToTalk');
 assert.equal(conflict(settings.gamepad,'a','button:10'),'pushToTalk');
 assert.equal(conflict(settings.keyboard,'a','KeyZ'),'b');
 assert.equal(conflict(settings.keyboard,'a','KeyQ'),undefined);
});
test('gamepad axes/buttons use the demo-owned defaults and custom assignments',()=>{
 const settings=defaults();
 const pad={buttons:Array.from({length:16},(_,index)=>({pressed:index===0 || index===9,touched:false,value:0})),axes:[-1,1]};
 assert.equal(inputMask(settings.gamepad,padInputs(pad)),1|8|64|32);
 assert.equal(inputMask(settings.gamepad,padInputs(pad)),gamepadMask(pad));
 settings.gamepad.a=['axis:0:-1'];
 assert.equal(inputMask(settings.gamepad,padInputs(pad))&1,1);
 assert.equal(inputMask(settings.gamepad,padInputs(null)),0);
});
test('default restoration returns independent mapping arrays',()=>{
 const one=defaults(),two=defaults();one.keyboard.a[0]='KeyQ';one.gamepad.up.push('button:3');
 assert.deepEqual(two.keyboard.a,['KeyX']);assert.equal(two.gamepad.up.includes('button:3'),false);
});
