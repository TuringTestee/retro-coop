import { keyMap, defaultPadBindings } from '../../../spikes/d02/demo/runtime/input.js';

export const actions = ['a','b','select','start','up','down','left','right','pushToTalk'] as const;
export type Action = typeof actions[number];
export const labels: Record<Action,string> = {a:'A',b:'B',select:'Select',start:'Start',up:'Up',down:'Down',left:'Left',right:'Right',pushToTalk:'Push to talk'};
export type Bindings = Record<Action,string[]>;
export type Controls = {keyboard:Bindings; gamepad:Bindings; device:{index:number;id:string}|null};
export function defaults():Controls {
 const keyboard = Object.fromEntries(actions.map((action,index)=>[action,index<8 ? Object.keys(keyMap).filter(key=>keyMap[key as keyof typeof keyMap]===(1<<index)) : ['KeyV']])) as Bindings;
 const gamepad = Object.fromEntries(actions.map((action,index)=>[action,index<8 ? [...defaultPadBindings[index]] : ['button:10']])) as Bindings;
 return {keyboard,gamepad,device:null};
}
export function conflict(bindings:Bindings, action:Action, binding:string):Action|undefined {
 return actions.find(other=>other!==action && bindings[other].includes(binding));
}
export function inputMask(bindings:Bindings, pressed:ReadonlySet<string>) {
 return actions.slice(0,8).reduce((mask,action,index)=>mask | (bindings[action].some(binding=>pressed.has(binding)) ? 1<<index : 0),0);
}
export const rapidKeys = {KeyA:1,KeyD:2} as const;
export function rapidMask(bindings:Bindings,pressed:ReadonlyMap<string,number>,now:number) {
 return Object.entries(rapidKeys).reduce((mask,[key,bit])=>{
  const started=pressed.get(key);
  return mask | (started!==undefined && !actions.some(action=>bindings[action].includes(key)) && Math.floor((now-started)/50)%2===0 ? bit : 0);
 },0);
}
/** Replace only the former exact defaults, leaving all personal mappings alone. */
export function migrateDefaultKeyboard(controls:Controls):Controls {
 const old:Partial<Bindings>={a:['KeyX'],b:['KeyZ'],select:['ShiftLeft','ShiftRight'],start:['Enter'],up:['ArrowUp'],down:['ArrowDown'],left:['ArrowLeft'],right:['ArrowRight'],pushToTalk:['KeyV']};
 if(!actions.every(action=>JSON.stringify(controls.keyboard[action])===JSON.stringify(old[action])))return controls;
 return {...controls,keyboard:defaults().keyboard};
}
export function padInputs(pad:Pick<Gamepad,'buttons'|'axes'>|null|undefined):Set<string> {
 const pressed = new Set<string>();
 pad?.buttons.forEach((button,index)=>{if(button.pressed) pressed.add(`button:${index}`);});
 pad?.axes.forEach((value,index)=>{if(Math.abs(value)>.5) pressed.add(`axis:${index}:${value<0 ? -1 : 1}`);});
 return pressed;
}
export function bindingLabel(binding:string) {
 if(binding.startsWith('button:')) return `Button ${Number(binding.split(':')[1])+1}`;
 if(binding.startsWith('axis:')) {const [,axis,direction]=binding.split(':');return `Axis ${Number(axis)+1} ${direction==='-1' ? '−' : '+'}`;}
 return binding.replace(/^Key/,'').replace(/^Digit/,'').replace(/([a-z])([A-Z])/g,'$1 $2');
}

/** Stored controls use the same action/conflict rules as interactive remapping. */
export function validControls(value:unknown):value is Controls {
 if(!value || typeof value!=='object')return false;
 const controls=value as Controls;
 if(Object.keys(controls).length!==3)return false;
 for(const source of ['keyboard','gamepad'] as const) {
  const bindings=controls[source];if(!bindings || Object.keys(bindings).length!==actions.length)return false;
  for(const action of actions)if(!Array.isArray(bindings[action]) || bindings[action].length>16 || bindings[action].some(binding=>typeof binding!=='string' || !binding.length || binding.length>64))return false;
  for(const action of actions)if(bindings[action].some(binding=>!!conflict(bindings,action,binding)))return false;
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
