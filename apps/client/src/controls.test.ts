import test from 'node:test';
import assert from 'node:assert/strict';
import {actions,defaults,conflict,inputMask,migrateDefaultKeyboard,padInputs,rapidMask,validControls} from './controls.ts';
import {gamepadMask} from '../../../spikes/d02/demo/runtime/input.js';
test('all eight NES inputs and reserved talk binding share conflict detection',()=>{
 const settings=defaults();
 actions.slice(0,8).forEach((action,index)=>assert.equal(inputMask(settings.keyboard,new Set(settings.keyboard[action])),1<<index));
 assert.equal(inputMask(settings.keyboard,new Set(['KeyV'])),0);
 assert.equal(conflict(settings.keyboard,'a','KeyV'),'pushToTalk');
 assert.equal(conflict(settings.gamepad,'a','button:10'),'pushToTalk');
 assert.equal(conflict(settings.keyboard,'a','KeyC'),'b');
 assert.equal(conflict(settings.keyboard,'a','KeyQ'),undefined);
});
test('public Play keys send the documented NES buttons',()=>{
 const keyboard=defaults().keyboard;
 assert.equal(inputMask(keyboard,new Set(['KeyZ'])),1);
 assert.equal(inputMask(keyboard,new Set(['KeyC'])),2);
 assert.equal(inputMask(keyboard,new Set(['AltLeft'])),4);
 assert.equal(inputMask(keyboard,new Set(['Space'])),8);
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
 assert.deepEqual(two.keyboard.a,['KeyZ']);assert.equal(two.gamepad.up.includes('button:3'),false);
});
test('rapid fire pulses on held A and D without overriding personal mappings',()=>{
 const settings=defaults(),held=new Map([['KeyA',100],['KeyD',100]]);
 assert.equal(rapidMask(settings.keyboard,held,100),3);
 assert.equal(rapidMask(settings.keyboard,held,149),3);
 assert.equal(rapidMask(settings.keyboard,held,150),0);
 assert.equal(rapidMask(settings.keyboard,held,200),3);
 settings.keyboard.b=['KeyD'];
 assert.equal(rapidMask(settings.keyboard,held,200),1);
});
test('only exact former keyboard defaults migrate; gamepad and custom mappings remain',()=>{
 const prior=defaults();prior.keyboard={...prior.keyboard,a:['KeyX'],b:['KeyZ'],select:['ShiftLeft','ShiftRight'],start:['Enter']};
 const upgraded=migrateDefaultKeyboard(prior);
 assert.deepEqual(upgraded.keyboard,defaults().keyboard);
 assert.equal(upgraded.gamepad,prior.gamepad);
 prior.keyboard.b=['KeyB'];assert.equal(migrateDefaultKeyboard(prior),prior);
});

test('stored controls reject malformed shapes and cross-action conflicts without throwing',()=>{
 assert.equal(validControls(defaults()),true);
 for(const value of [null,{}, {keyboard:{a:['KeyX']},gamepad:{},device:null}])assert.equal(validControls(value),false);
 const duplicate=defaults();duplicate.keyboard.a=['KeyV'];assert.equal(validControls(duplicate),false);
 const missing=defaults();delete (missing.keyboard as Partial<typeof missing.keyboard>).b;assert.equal(validControls(missing),false);
 const disconnected=defaults();disconnected.device={id:'Saved controller',index:1};assert.equal(validControls(disconnected),true);
});

test('released pad buttons and axes stay neutral until each physical input releases',async()=>{
 const {ReleasedInputs}=await import('./controls.ts');const latch=new ReleasedInputs();
 latch.release(new Set(['button:0','axis:0:1']));assert.deepEqual([...latch.sample(new Set(['button:0','axis:0:1']))],[]);
 assert.deepEqual([...latch.sample(new Set(['button:0','axis:0:1','button:1']))],['button:1']);
 latch.sample(new Set(['button:0']));assert.deepEqual([...latch.sample(new Set(['button:0','axis:0:1']))],['axis:0:1']);
 latch.sample(new Set());assert.deepEqual([...latch.sample(new Set(['button:0']))],['button:0']);
});

test('virtual contacts preserve overlapping holds and reject stale generations',async()=>{
 const {VirtualContacts}=await import('./virtual-controls.ts');const contacts=new VirtualContacts();
 const one=contacts.begin(1,1),two=contacts.begin(2,1),pad=contacts.begin(3,16|128);
 assert.equal(contacts.mask(),1|16|128);contacts.end(1,one);assert.equal(contacts.mask(),1|16|128);
 contacts.end(2,two);assert.equal(contacts.mask(),16|128);contacts.update(3,pad,32|64);assert.equal(contacts.mask(),32|64);
 contacts.clear();const fresh=contacts.begin(3,2);contacts.end(3,pad);contacts.update(3,pad,255);assert.equal(contacts.mask(),2);
 contacts.end(3,fresh);assert.equal(contacts.mask(),0);
});
test('virtual pad covers eight directions, deadzone and bounded touchdown origin',async()=>{
 const {directionMask,boundedOrigin}=await import('./virtual-controls.ts');
 assert.equal(directionMask(0,0),0);assert.equal(directionMask(8,0),0);
 [[30,0,128],[30,30,128|32],[0,30,32],[-30,30,32|64],[-30,0,64],[-30,-30,64|16],[0,-30,16],[30,-30,16|128]].forEach(([x,y,mask])=>assert.equal(directionMask(x,y),mask));
 assert.equal(boundedOrigin(90,48),64);assert.equal(directionMask(90-boundedOrigin(90,48),0),128);
});
