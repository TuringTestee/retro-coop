import type {RoomView} from '../../../packages/contracts/src/rooms.ts';

/** The committed controller owner determines prompts; pending roles never grant input. */
export function PlayControls({room,edit,roomSlots}:{room?:RoomView;edit():void;roomSlots():void}) {
 const ownSlot=room?.slots.find(slot=>slot.member?.id===room.chatMembership);
 const ownerIndex=room?.game.controllers.owners.indexOf(room.chatMembership)??-1;
 const port=room?.started?(ownerIndex<0?null:ownerIndex+1):room?(ownSlot?.role==='player1'?1:ownSlot?.role==='player2'?2:null):1;
 return <section className="play-controls" aria-label="Your controls">
  <span className="play-role">{port===null?'Observer':`Player ${port}`}</span>
  {room?.started&&<button onClick={roomSlots}>Players</button>}
  {port!==null&&<button className="text-action" onClick={edit}>Controls</button>}
 </section>;
}
