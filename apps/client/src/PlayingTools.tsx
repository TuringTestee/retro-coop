import React from 'react';
import {bindingLabel,type Controls} from './controls.ts';

export function PlayingTools({controls,local}:{controls:Controls;local:boolean}){
 const keys=controls.keyboard;
 const assigned=new Set(Object.values(keys).flat());
 const short:Record<string,string>={ArrowUp:'↑',ArrowDown:'↓',ArrowLeft:'←',ArrowRight:'→',ShiftLeft:'Shift',ShiftRight:'Shift',Enter:'Enter'};
 const hint=(action:keyof typeof keys)=>[...new Set(keys[action].map(key=>short[key]??bindingLabel(key)))].join(' / ')||'Unbound';
 const mappings=[
  {name:'Move',keys:`${hint('up')} ${hint('left')} ${hint('down')} ${hint('right')}`,tone:'move'},
  {name:'B',keys:hint('b'),tone:'b'},
  {name:'A',keys:hint('a'),tone:'a'},
  {name:'Select',keys:hint('select'),tone:'system'},
  {name:'Start',keys:hint('start'),tone:'system'},
  {name:'Talk',keys:hint('pushToTalk'),tone:'voice'},
 ] as const;
 return <div className="rc-play-tools" aria-label="Game controls">
  <div className="rc-section-head"><span className="rc-eyebrow">CONTROLLER</span></div>
  <div className="rc-controller-art" role="img" aria-label="NES controller: direction pad on the left, Select and Start in the center, B and A on the right">
   <span className="rc-pad">↑<br/>← ✚ →<br/>↓</span>
   <span className="rc-system-buttons"><b>SEL</b><b>START</b></span>
   <span className="rc-action-buttons"><b>B</b><b>A</b></span>
  </div>
  <div className="rc-control-hints" aria-label="Keyboard controls">{mappings.map(item=><div className={`rc-control-line rc-control-${item.tone}`} key={item.name}><strong>{item.name}</strong><span aria-hidden="true"/><b><span className="rc-keyboard-word">Keyboard </span>{item.keys}</b></div>)}</div>
  <div className="rc-shortcuts" aria-label="Other shortcuts">{!assigned.has('KeyM')&&<span><strong>M</strong> Mute game</span>}{!assigned.has('F5')&&<span><strong>F5</strong> Save</span>}{local&&!assigned.has('F9')&&<span><strong>F9</strong> Load</span>}</div>
 </div>;
}
