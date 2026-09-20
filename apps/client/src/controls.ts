import { keyMap, defaultPadBindings } from '../../../spikes/d02/demo/runtime/input.js';

export const actions = ['a','b','select','start','up','down','left','right','pushToTalk'] as const;
export type Action = typeof actions[number];
export const labels: Record<Action,string> = {a:'A',b:'B',select:'Select',start:'Start',up:'Up',down:'Down',left:'Left',right:'Right',pushToTalk:'Push to talk (reserved)'};
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
