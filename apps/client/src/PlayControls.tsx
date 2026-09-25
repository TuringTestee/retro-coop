import {actions,bindingLabel,labels,type Controls} from './controls.ts';
import {defaultControllers} from '../../../packages/contracts/src/gameplay.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';

/** Read the accepted assignment; pending proposals never change the prompts. */
export function PlayControls({controls,room,edit,sessionControllers}:{controls:Controls;room?:RoomView;edit():void;sessionControllers():void}) {
 const assignment=room?.game?.controllers??defaultControllers;
 const port=room?.started==='shared'?(assignment.p1===room.role?1:assignment.mode==='shared'?null:2):1;
 const source=controls.device?'gamepad':'keyboard';
 return <section className="play-controls" aria-label="Your controls">
  <h2>Your controls <span>· {assignment.mode==='shared'&&room?.started==='shared'?'Shared P1':`Player ${port}`}</span></h2>
  {port===null?<><p>Your input is idle.</p><p>{assignment.p1==='host'?room?.host:room?.guest} controls P1 now.</p><button onClick={sessionControllers}>Session controllers</button></>:<>
   <p className="control-source">{controls.device?`Gamepad · ${controls.device.id}`:'Keyboard'}</p>
   <dl className="play-bindings">{actions.filter(action=>action!=='pushToTalk').map(action=><div key={action}><dt>{labels[action]}</dt><dd>{controls[source][action].map(bindingLabel).join(' / ')||'Unbound'}</dd></div>)}</dl>
   <button className="text-action" onClick={edit}>Edit controls</button>
  </>}
 </section>;
}
