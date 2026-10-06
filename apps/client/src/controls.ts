import { keyMap, defaultPadBindings } from '../../../spikes/d02/demo/runtime/input.js';

export const actions = ['a','b','select','start','up','down','left','right','pushToTalk','rapidA','rapidB','save','load','pause','mute','restart'] as const;
export type Action = typeof actions[number];
export const labels: Record<Action,string> = {a:'A',b:'B',select:'Select',start:'Start',up:'Up',down:'Down',left:'Left',right:'Right',pushToTalk:'Push to talk',rapidA:'Rapid A',rapidB:'Rapid B',save:'Save',load:'Load',pause:'Pause / resume',mute:'Mute game',restart:'Restart'};
export type Bindings = Record<Action,string[]>;
export type Controls = {keyboard:Bindings; gamepad:Bindings; device:{index:number;id:string}|null};
/** Alt alone can be mapped; Alt combinations and browser command modifiers stay reserved. */
export function modifiedKey(event:Pick<KeyboardEvent,'code'|'altKey'|'ctrlKey'|'metaKey'>) {
 return event.ctrlKey||event.metaKey||event.altKey&&!['AltLeft','AltRight'].includes(event.code);
}
export function defaults():Controls {
 const extra:Partial<Bindings>={pushToTalk:['KeyV'],rapidA:['KeyA'],rapidB:['KeyD'],save:['KeyQ'],load:['KeyE'],pause:['KeyP'],mute:['KeyM'],restart:['KeyN']};
 const keyboard = Object.fromEntries(actions.map((action,index)=>[action,index<8 ? Object.keys(keyMap).filter(key=>keyMap[key as keyof typeof keyMap]===(1<<index)) : [...extra[action]!]])) as Bindings;
 const gamepad = Object.fromEntries(actions.map((action,index)=>[action,index<8 ? [...defaultPadBindings[index]] : action==='pushToTalk'?['button:10']:[]])) as Bindings;
 return {keyboard,gamepad,device:null};
}
export function conflict(bindings:Bindings, action:Action, binding:string):Action|undefined {
 return actions.find(other=>other!==action && bindings[other]?.includes(binding));
}
export function inputMask(bindings:Bindings, pressed:ReadonlySet<string>) {
 return actions.slice(0,8).reduce((mask,action,index)=>mask | (bindings[action].some(binding=>pressed.has(binding)) ? 1<<index : 0),0);
}
export function rapidMask(bindings:Bindings,pressed:ReadonlyMap<string,number>,now:number) {
 return (['rapidA','rapidB'] as const).reduce((mask,action,index)=>{
  const firing=bindings[action].some(key=>{const started=pressed.get(key);return started!==undefined&&!conflict(bindings,action,key)&&Math.floor((now-started)/50)%2===0;});
  return mask | (firing?1<<index:0);
 },0);
}
/** Replace the former default group only when the complete result preserves binding validity. */
export function migrateDefaultKeyboard(controls:Controls):Controls {
 const old:Partial<Bindings>={a:['KeyX'],b:['KeyZ'],select:['ShiftLeft','ShiftRight'],start:['Enter'],up:['ArrowUp'],down:['ArrowDown'],left:['ArrowLeft'],right:['ArrowRight'],pushToTalk:['KeyV']};
 if(!actions.slice(0,9).every(action=>JSON.stringify(controls.keyboard[action])===JSON.stringify(old[action])))return controls;
 const keyboard=defaults().keyboard;
 const candidate={...controls,keyboard:{...controls.keyboard,...Object.fromEntries(actions.slice(0,9).map(action=>[action,keyboard[action]]))}};
 return validControls(candidate)?candidate:controls;
}
/** Extend complete former mappings without taking a key already owned by a personal binding. */
export function normalizeControls(value:unknown):Controls|undefined {
 if(validControls(value))return migrateDefaultKeyboard(value);
 const supported=[actions.slice(0,15),actions.slice(0,9)].find(expected=>checkControls(value,expected));if(!supported)return;
 const old=value as Controls,next=defaults();
 for(const source of ['keyboard','gamepad'] as const){
  const assigned=new Set(Object.values(old[source]).flat());
  next[source]={...old[source],...Object.fromEntries(actions.slice(supported.length).map(action=>[action,next[source][action].filter(key=>!assigned.has(key))]))};
 }
 next.device=old.device;
 return migrateDefaultKeyboard(next);
}
export function padInputs(pad:Pick<Gamepad,'buttons'|'axes'>|null|undefined):Set<string> {
 const pressed = new Set<string>();
 pad?.buttons.forEach((button,index)=>{if(button.pressed) pressed.add(`button:${index}`);});
 pad?.axes.forEach((value,index)=>{if(Math.abs(value)>.5) pressed.add(`axis:${index}:${value<0 ? -1 : 1}`);});
 return pressed;
}
export function bindingLabel(binding:string) {
 const arrow:Record<string,string>={ArrowUp:'↑',ArrowDown:'↓',ArrowLeft:'←',ArrowRight:'→'};if(arrow[binding])return arrow[binding];
 if(binding.startsWith('button:')) return `Button ${Number(binding.split(':')[1])+1}`;
 if(binding.startsWith('axis:')) {const [,axis,direction]=binding.split(':');return `Axis ${Number(axis)+1} ${direction==='-1' ? '−' : '+'}`;}
 return binding.replace(/^Key/,'').replace(/^Digit/,'').replace(/([a-z])([A-Z])/g,'$1 $2');
}

/** A paired modifier uses one familiar key name; individual-side mappings remain explicit. */
export function bindingSummary(bindings:readonly string[]) {
 const paired=['Alt','Shift','Control','Meta'].filter(key=>bindings.includes(`${key}Left`)&&bindings.includes(`${key}Right`));
 return [...new Set(bindings.map(binding=>paired.find(key=>binding===`${key}Left`||binding===`${key}Right`)??bindingLabel(binding)))].join(' / ');
}

/** Stored controls use the same action/conflict rules as interactive remapping. */
export function validControls(value:unknown):value is Controls {
 return checkControls(value,actions);
}
function checkControls(value:unknown,expected:readonly Action[]):boolean {
 if(!value || typeof value!=='object')return false;
 const controls=value as Controls;
 if(Object.keys(controls).length!==3)return false;
 for(const source of ['keyboard','gamepad'] as const) {
  const bindings=controls[source];if(!bindings || Object.keys(bindings).length!==expected.length)return false;
  for(const action of expected)if(!Array.isArray(bindings[action]) || bindings[action].length>16 || bindings[action].some(binding=>typeof binding!=='string' || !binding.length || binding.length>64))return false;
  if(source==='gamepad'&&expected.slice(9).some(action=>bindings[action].length))return false;
  for(const action of expected)if(bindings[action].some(binding=>!!conflict(bindings,action,binding)))return false;
 }
 return controls.device===null || !!controls.device && Number.isSafeInteger(controls.device.index) && controls.device.index>=0 && controls.device.index<256 && typeof controls.device.id==='string' && controls.device.id.length>0 && controls.device.id.length<=1024;
}

/** Suppress every held physical pad input until that input is observed released. */
export class ReleasedInputs {
 private blocked=new Set<string>();
 release(pressed:ReadonlySet<string>){for(const input of pressed)this.blocked.add(input);}
 sample(pressed:ReadonlySet<string>){for(const input of this.blocked)if(!pressed.has(input))this.blocked.delete(input);return new Set([...pressed].filter(input=>!this.blocked.has(input)));}
}

/** Device APIs are optional; keyboard and on-screen input remain available. */
export function availableGamepads():Gamepad[] {
 try{return [...(navigator.getGamepads?.()??[])].filter((pad):pad is Gamepad=>!!pad&&pad.connected);}catch{return [];}
}
/** Returning peripherals must release held buttons before generating new input. */
export class GamepadInput {
 private identity?:string;
 private released=new ReleasedInputs();
 sample(device:Controls['device']) {
  const pad=device?availableGamepads().find(pad=>pad.index===device.index&&pad.id===device.id):undefined;
  const identity=pad?`${pad.index}:${pad.id}`:undefined,pressed=padInputs(pad);
  if(identity!==this.identity){this.released.release(pressed);this.identity=identity;}
  return {pad,available:!device||!!pad,pressed:this.released.sample(pressed)};
 }
 release(device:Controls['device']) {this.released.release(padInputs(this.sample(device).pad));}
}
