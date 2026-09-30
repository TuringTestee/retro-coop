import React,{useEffect,useRef,useState} from 'react';
import {SLOT_IDS,type RoomSlot,type SlotRole} from '../../../packages/contracts/src/slots.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {RoomClient} from './room-client.ts';
export const slotRoleLabel=(role:SlotRole)=>role==='observer'?'Observer':role==='player1'?'Player 1':'Player 2';

function status(room:RoomView,slot:RoomSlot) {
 const member=slot.member;
 if(!member)return slot.open?'Open':'Closed';
 if(!member.connected)return 'Disconnected · waiting to reconnect';
 if(!member.matches||member.acquisition!=='loaded')return ({checking:'Checking game…',downloading:'Downloading game…',loading:'Loading game…',failed:'Game preparation failed',loaded:'Waiting for matching game'})[member.acquisition];
 const proposed=room.game.pending?.roles.find(change=>change.slotId===slot.id);
 if(proposed)return room.game.pending!.status==='failed'?`Change to ${slotRoleLabel(proposed.role)} failed`:`Changing to ${slotRoleLabel(proposed.role)}…`;
 if(room.game.ready.includes(member.id))return 'Ready';
 if(room.started){
  if(['paused','failed','resume_ready'].includes(room.game.status))return slot.role==='observer'?'Observer · game paused':'Paused';
  if(room.game.status==='pausing')return 'Pausing…';
  if(room.game.status==='starting')return 'Starting…';
  return slot.role==='observer'?'Observer':'Playing';
 }
 return 'Not ready';
}

/** Physical positions stay mounted when membership, readiness or controller ownership changes. */
export function RoomSlots({room,connected,act}:{room:RoomView;connected:boolean;act:RoomClient['act']}) {
 const [pending,setPending]=useState(false),[error,setError]=useState('');
 const [removing,setRemoving]=useState<{slotId:string;membership:string}>();
 const [managing,setManaging]=useState<string>();
 const panel=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null),generation=useRef(0);
 useEffect(()=>{generation.current++;setPending(false);setError('');setRemoving(undefined);setManaging(undefined);},[room.id]);
 useEffect(()=>{if(removing&&!room.slots.some(slot=>slot.id===removing.slotId&&slot.member?.id===removing.membership))setRemoving(undefined);},[room.slots,removing]);
 const focusSlot=(id:string)=>requestAnimationFrame(()=>panel.current?.querySelector<HTMLElement>(`[data-slot-id="${id}"] [data-manage-slot]`)?.focus());
 const cancel=()=>{setRemoving(undefined);requestAnimationFrame(()=>dialog.current?.querySelector<HTMLElement>('[data-remove-member]')?.focus());};
 useEffect(()=>{if(managing){dialog.current?.showModal();dialog.current?.querySelector<HTMLElement>('select, button')?.focus();}},[managing]);
 const send=async(command:Parameters<RoomClient['act']>[0])=>{
  const attempt=generation.current;setPending(true);setError('');
  try{const ok=await act(command);if(attempt!==generation.current)return false;if(!ok)setError('The change was not confirmed. Check the current slots and try again.');return ok;}
  catch{if(attempt===generation.current)setError('The room could not be reached. Reconnect and try again.');return false;}
  finally{if(attempt===generation.current)setPending(false);}
 };
 const locked=pending||!connected||!!room.game.pending;
 const selected=room.slots.find(slot=>slot.id===managing),selectedMember=selected?.member,selectedIndex=selected?SLOT_IDS.indexOf(selected.id)+1:0;
 return <div ref={panel} className="room-slots" aria-label="Room slots">
  {SLOT_IDS.map((id,index)=>{const slot=room.slots.find(value=>value.id===id);if(!slot)throw Error(`Missing room slot ${id}`);const member=slot.member;return <section key={id} data-testid="room-slot" data-slot-id={id} aria-label={`Slot ${index+1}`}>
   <div data-slot-region="identity" tabIndex={0} aria-label={`Slot ${index+1} identity`}><strong>Slot {index+1} · {slotRoleLabel(slot.role)}</strong><span>{member?`${member.id===room.chatMembership?'You':member.nickname}${member.id===room.hostMembership?' · Host':''}`:''}</span></div>
   <div data-slot-region="status" role="status" tabIndex={0} aria-label={`Slot ${index+1} status`}>{status(room,slot)}</div>
   <div data-slot-region="actions">{room.role==='host'&&<button data-manage-slot aria-haspopup="dialog" disabled={locked} onClick={()=>setManaging(id)}>Manage</button>}</div>
  </section>;})}
  {selected&&room.role==='host'&&<dialog ref={dialog} className="slot-management-dialog" aria-label={`Manage slot ${selectedIndex}`} onClose={()=>{const id=managing;setManaging(undefined);setRemoving(undefined);if(id)focusSlot(id);}}>
   <h3>Slot {selectedIndex} · {slotRoleLabel(selected.role)}</h3>
   <label>Role <select aria-label={`Slot ${selectedIndex} role`} value={selected.role} disabled={locked} onChange={event=>void send({type:'slotRole',roomId:room.id,slotId:selected.id,role:event.target.value as SlotRole,expectedRevision:room.revision})}>{room.controllerRoles.map(role=><option key={role} value={role}>{slotRoleLabel(role)}</option>)}<option value="observer">Observer</option></select></label>
   {room.controllerRoles.length===1&&<p className="hint">This game has one controller. Other members can observe.</p>}
   {!selectedMember&&<button disabled={locked} onClick={()=>void send({type:'slotAvailability',roomId:room.id,slotId:selected.id,open:!selected.open,expectedRevision:room.revision})}>{selected.open?'Close slot':'Open slot'}</button>}
   {selectedMember&&selectedMember.id!==room.hostMembership&&(removing?.slotId===selected.id&&removing.membership===selectedMember.id?<div className="slot-confirm" role="group" aria-label={`Remove ${selectedMember.nickname}`}><p>Remove {selectedMember.nickname}? They must join again to return.</p><button data-confirm-remove disabled={pending} onClick={async()=>{if(await send({type:'memberRemove',roomId:room.id,membership:selectedMember.id,expectedRevision:room.revision})){dialog.current?.close();}}}>Confirm removal</button><button disabled={pending} onClick={cancel}>Cancel removal</button></div>:<button data-remove-member disabled={locked} onClick={()=>{setRemoving({slotId:selected.id,membership:selectedMember.id});requestAnimationFrame(()=>dialog.current?.querySelector<HTMLElement>('[data-confirm-remove]')?.focus());}}>Remove member</button>)}
   <button onClick={()=>dialog.current?.close()}>Done</button>
  </dialog>}
  <div className="slot-feedback" role="status">{error|| (pending?'Updating room…':'')}</div>
  {room.game.pending&&<div className="slot-transaction" role="group" aria-label="Role change"><p role="status">{room.game.pending.status==='failed'?room.game.pending.reason??'Role change failed. Previous roles and progress are preserved.':room.game.pending.status==='freezing'?'Pausing at a shared frame before changing roles…':'Synchronizing the new players before changing roles…'}</p>{room.role==='host'&&<>{room.game.pending.status==='failed'&&<button disabled={pending||!connected} onClick={()=>void send({type:'gameRoleRetry',transactionId:room.game.pending!.id})}>Retry role change</button>}<button disabled={pending||!connected} onClick={()=>void send({type:'gameRoleCancel',transactionId:room.game.pending!.id})}>Cancel role change</button></>}</div>}
 </div>;
}
