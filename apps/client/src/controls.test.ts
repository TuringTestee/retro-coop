import test from 'node:test';
import assert from 'node:assert/strict';
import {actions,defaults,conflict,inputMask,migrateDefaultKeyboard,padInputs,rapidMask,validControls,normalizeControls,bindingSummary,modifiedKey} from './controls.ts';
import {gamepadMask} from '../../../spikes/d02/demo/runtime/input.js';
test('all eight NES inputs and reserved talk binding share conflict detection',()=>{
 const settings=defaults();
 actions.slice(0,8).forEach((action,index)=>assert.equal(inputMask(settings.keyboard,new Set(settings.keyboard[action])),1<<index));
 assert.equal(inputMask(settings.keyboard,new Set(['KeyV'])),0);
 assert.equal(conflict(settings.keyboard,'a','KeyV'),'pushToTalk');
 assert.equal(conflict(settings.gamepad,'a','button:10'),'pushToTalk');
 assert.equal(conflict(settings.keyboard,'a','KeyC'),'b');
 assert.equal(conflict(settings.keyboard,'a','KeyQ'),'save');
});
test('public Play keys send the documented NES buttons',()=>{
 const keyboard=defaults().keyboard;
 assert.equal(inputMask(keyboard,new Set(['KeyZ'])),1);
 assert.equal(inputMask(keyboard,new Set(['KeyC'])),2);
 assert.equal(inputMask(keyboard,new Set(['AltLeft'])),4);
 assert.equal(inputMask(keyboard,new Set(['Space'])),8);
});
test('compact binding names retain direction and individually mapped modifier sides',()=>{
 assert.equal(bindingSummary(['ArrowUp','ArrowRight']),'↑ / →');
 assert.equal(bindingSummary(['AltLeft','AltRight']),'Alt');
 assert.equal(bindingSummary(['AltRight']),'Alt Right');
 assert.equal(bindingSummary(['ShiftLeft','ShiftRight','KeyK']),'Shift / K');
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


test('missing or restricted Gamepad API leaves keyboard and touch available',async context=>{
 const {GamepadInput,availableGamepads}=await import('./controls.ts');
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'navigator');
 context.after(()=>{if(descriptor)Object.defineProperty(globalThis,'navigator',descriptor);else Reflect.deleteProperty(globalThis,'navigator');});
 for(const value of [{},{getGamepads(){throw new DOMException('Restricted','SecurityError');}},{getGamepads:()=>[null]}]){
  Object.defineProperty(globalThis,'navigator',{configurable:true,value});
  assert.deepEqual(availableGamepads(),[]);
  assert.equal(new GamepadInput().sample({index:0,id:'Saved pad'}).available,false);
  assert.equal(inputMask(defaults().keyboard,new Set(['KeyZ'])),1);
 }
});
test('a remembered pad releases held return inputs, ignores a different device and preserves preferences',async context=>{
 const {GamepadInput}=await import('./controls.ts'),device={index:0,id:'Saved pad'},held={pressed:true};
 let pad:unknown={index:0,id:device.id,connected:true,buttons:[held],axes:[1]};
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'navigator');
 Object.defineProperty(globalThis,'navigator',{configurable:true,value:{getGamepads:()=>[pad]}});
 context.after(()=>{if(descriptor)Object.defineProperty(globalThis,'navigator',descriptor);else Reflect.deleteProperty(globalThis,'navigator');});
 const input=new GamepadInput();assert.deepEqual([...input.sample(device).pressed],[]);
 held.pressed=false;(pad as {axes:number[]}).axes=[0];input.sample(device);
 held.pressed=true;assert.deepEqual([...input.sample(device).pressed],['button:0']);
 pad=null;assert.equal(input.sample(device).available,false);
 pad={index:0,id:'Other pad',connected:true,buttons:[held],axes:[0]};assert.equal(input.sample(device).available,false);
 pad={index:0,id:device.id,connected:true,buttons:[held],axes:[1]};assert.deepEqual([...input.sample(device).pressed],[]);
 held.pressed=false;(pad as {axes:number[]}).axes=[0];input.sample(device);
 held.pressed=true;assert.deepEqual([...input.sample(device).pressed],['button:0']);
 input.release(device);assert.deepEqual([...input.sample(device).pressed],[]);
 assert.deepEqual(device,{index:0,id:'Saved pad'});
});
test('legacy personal bindings keep their keys and suppress conflicting newly editable shortcuts',()=>{
 const current=defaults(),legacy={...current,keyboard:Object.fromEntries(actions.slice(0,9).map(action=>[action,current.keyboard[action]])),gamepad:Object.fromEntries(actions.slice(0,9).map(action=>[action,current.gamepad[action]]))};
 legacy.keyboard.a=['KeyQ'];legacy.keyboard.b=[];
 const upgraded=normalizeControls(legacy)!;
 assert.deepEqual(upgraded.keyboard.a,['KeyQ']);assert.deepEqual(upgraded.keyboard.b,[]);assert.deepEqual(upgraded.keyboard.save,[]);assert.deepEqual(upgraded.keyboard.load,['KeyE']);assert.equal(validControls(upgraded),true);
 delete legacy.keyboard.up;assert.equal(normalizeControls(legacy),undefined);
});
test('rapid fire follows an edited key and game actions never enter the NES mask',()=>{
 const keyboard=defaults().keyboard;keyboard.rapidA=['KeyF'];
 assert.equal(rapidMask(keyboard,new Map([['KeyA',0]]),0),0);assert.equal(rapidMask(keyboard,new Map([['KeyF',0]]),0),1);assert.equal(rapidMask(keyboard,new Map([['KeyF',0]]),50),0);
 assert.equal(inputMask(keyboard,new Set(['KeyQ','KeyE','KeyN','KeyM','KeyP','KeyV'])),0);
});

test('mapped Alt alone is eligible while browser modifier combinations stay reserved',()=>{
 const plain={altKey:false,ctrlKey:false,metaKey:false};
 assert.equal(modifiedKey({...plain,code:'AltLeft',altKey:true}),false);
 assert.equal(modifiedKey({...plain,code:'AltRight',altKey:true}),false);
 assert.equal(modifiedKey({...plain,code:'KeyQ',altKey:true}),true);
 assert.equal(modifiedKey({...plain,code:'KeyQ',ctrlKey:true}),true);
 assert.equal(modifiedKey({...plain,code:'MetaLeft',metaKey:true}),true);
});

test('15-binding records gain real Restart without changing personal or unbound mappings',()=>{
 const former=defaults();delete (former.keyboard as Partial<typeof former.keyboard>).restart;delete (former.gamepad as Partial<typeof former.gamepad>).restart;
 former.keyboard.a=['KeyN'];former.keyboard.save=[];
 const migrated=normalizeControls(former)!;assert.ok(migrated);assert.deepEqual(migrated.keyboard.a,['KeyN']);assert.deepEqual(migrated.keyboard.save,[]);assert.deepEqual(migrated.keyboard.restart,[]);
 const plain=defaults();delete (plain.keyboard as Partial<typeof plain.keyboard>).restart;delete (plain.gamepad as Partial<typeof plain.gamepad>).restart;
 assert.deepEqual(normalizeControls(plain)!.keyboard.restart,['KeyN']);
});
