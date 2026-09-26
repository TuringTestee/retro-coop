import {actions,bindingLabel,labels,type Controls} from './controls.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';

/** The committed controller owner determines prompts; pending roles never grant input. */
export function PlayControls({controls,room,edit,roomSlots}:{controls:Controls;room?:RoomView;edit():void;roomSlots():void}) {
 const ownSlot=room?.slots.find(slot=>slot.member?.id===room.chatMembership);
 const ownerIndex=room?.game.controllers.owners.indexOf(room.chatMembership)??-1;
 const port=room?.started?(ownerIndex<0?null:ownerIndex+1):room?(ownSlot?.role==='player1'?1:ownSlot?.role==='player2'?2:null):1;
 const source=controls.device?'gamepad':'keyboard';
 return <section className="play-controls" aria-label="Your controls">
  <h2>Your controls <span>· {port===null?'Observer':`Player ${port}`}</span></h2>
  {port===null?<><p>Observer input is off. Room slots shows the assigned players.</p><button onClick={roomSlots}>Room slots</button></>:<>
   <p className="control-source">{controls.device?`Gamepad · ${controls.device.id}`:'Keyboard'}</p>
   <dl className="play-bindings">{actions.filter(action=>action!=='pushToTalk').map(action=><div key={action}><dt>{labels[action]}</dt><dd>{controls[source][action].map(bindingLabel).join(' / ')||'Unbound'}</dd></div>)}</dl>
   <button className="text-action" onClick={edit}>Edit controls</button>
  </>}
 </section>;
}
