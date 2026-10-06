import React from 'react';
import {bindingLabel,type Controls} from './controls.ts';

/** Game actions share the binding inventory in Controls. */
export function GameShortcuts({controls,onSave,onLoad,busy,host,idle=false}:{controls:Controls;onSave?:()=>void;onLoad?:()=>void;busy?:boolean;host:boolean;idle?:boolean}){
 const hint=(action:'save'|'load')=>controls.keyboard[action].map(bindingLabel).join(' / ')||'Unbound';
 return <div className="rc-game-actions" aria-label="Game actions"><button aria-label={`Save (${hint('save')})`} disabled={busy} onClick={onSave}>Save{idle&&<small className="rc-input-hint">{hint('save')}</small>}</button><button aria-label={`Load (${hint('load')})`} disabled={busy||!host} onClick={onLoad}>Load{idle&&<small className="rc-input-hint">{host?hint('load'):'Host only'}</small>}</button>{!host&&<span>Only the host can load.</span>}</div>;
}
