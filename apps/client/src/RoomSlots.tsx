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
 const peer=room.peers.find(peer=>peer.member===member.id);
 if(peer&&peer.status!=='connected')return ['relay_unavailable','relay_capacity','failed'].includes(peer.status)?'Connection needs retry':'Connecting…';
 const proposed=room.game.pending?.roles.find(change=>change.slotId===slot.id);
 if(proposed)return room.game.pending!.status==='failed'?'Role change failed · choose Retry or Cancel':`Changing to ${slotRoleLabel(proposed.role)}…`;
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
 const [removing,setRemoving]=useState<{slotId:string;membership:string;nickname:string}>();
 const panel=useRef<HTMLDivElement>(null),dialog=useRef<HTMLDialogElement>(null),generation=useRef(0);
 const focusSlot=(id:string)=>requestAnimationFrame(()=>panel.current?.querySelector<HTMLElement>(`[data-slot-id="${id}"] [data-slot-action]`)?.focus());
 const dismiss=()=>{const id=removing?.slotId;dialog.current?.close();setRemoving(undefined);if(id)focusSlot(id);};
 useEffect(()=>{generation.current++;setPending(false);setError('');setRemoving(undefined);},[room.id]);
 useEffect(()=>{if(removing&&!room.slots.some(slot=>slot.id===removing.slotId&&slot.member?.id===removing.membership)){dialog.current?.close();setRemoving(undefined);focusSlot(removing.slotId);}},[room.slots,removing]);
 useEffect(()=>{if(removing&&dialog.current&&!dialog.current.open){dialog.current.showModal();dialog.current.querySelector<HTMLElement>('[data-confirm-kick]')?.focus();}},[removing]);
 const send=async(command:Parameters<RoomClient['act']>[0])=>{
  const attempt=generation.current;setPending(true);setError('');
  try{const ok=await act(command);if(attempt!==generation.current)return false;if(!ok)setError('The change was not confirmed. Check the current slots and try again.');return ok;}
  catch{if(attempt===generation.current)setError('The room could not be reached. Reconnect and try again.');return false;}
  finally{if(attempt===generation.current)setPending(false);}
 };
 const locked=pending||!connected;
 const choose=(slot:RoomSlot,value:string)=>{
  if(!value)return;
  if(value==='kick'&&slot.member){setError('');setRemoving({slotId:slot.id,membership:slot.member.id,nickname:slot.member.nickname});return;}
  if(value==='retry'&&room.game.pending){void send({type:'gameRoleRetry',transactionId:room.game.pending.id});return;}
  if(value==='cancel'&&room.game.pending){void send({type:'gameRoleCancel',transactionId:room.game.pending.id});return;}
  if(value==='close'||value==='open'){void send({type:'slotAvailability',roomId:room.id,slotId:slot.id,open:value==='open',expectedRevision:room.revision});return;}
  if(value.startsWith('role:'))void send({type:'slotRole',roomId:room.id,slotId:slot.id,role:value.slice(5) as SlotRole,expectedRevision:room.revision});
 };
 return <div ref={panel} className={`room-slots ${room.role==='host'?'host-slots':'member-slots'}`} aria-label="Room slots">
  {SLOT_IDS.map((id,index)=>{const slot=room.slots.find(value=>value.id===id);if(!slot)throw Error(`Missing room slot ${id}`);const member=slot.member;
   const transaction=room.game.pending,ownsTransaction=transaction?.roles[0]?.slotId===id;
   const roles:SlotRole[]=[...room.controllerRoles,'observer'];
   return <section key={id} data-testid="room-slot" data-slot-id={id} aria-label={`Slot ${index+1}`}>
    <div data-slot-region="identity" tabIndex={0} aria-label={`Slot ${index+1} identity`}><strong>Slot {index+1} · {slotRoleLabel(slot.role)}</strong><span>{member?`${member.id===room.chatMembership?'You':member.nickname}${member.id===room.hostMembership?' · Host':''}`:''}</span></div>
    <div data-slot-region="status" role="status" tabIndex={0} aria-label={`Slot ${index+1} status`}>{status(room,slot)}</div>
    <div data-slot-region="actions">{room.role==='host'&&<select data-slot-action aria-label={`Slot ${index+1} actions`} value="" disabled={locked||!!transaction&&!ownsTransaction} onChange={event=>{const value=event.currentTarget.value;event.currentTarget.value='';choose(slot,value);}}>
     <option value="">Choose action</option>
     {slot.open&&<optgroup label="Set role">{roles.map(role=>{
      const occupiedElsewhere=!member&&role!=='observer'&&room.slots.some(other=>other.id!==id&&other.role===role&&!!other.member);
      return <option key={role} value={`role:${role}`} disabled={!!transaction||occupiedElsewhere}>{slotRoleLabel(role)}{role===slot.role?' · current':''}</option>;
     })}</optgroup>}
     {member&&member.id!==room.hostMembership&&<option value="kick" disabled={!!transaction}>Kick member</option>}
     {!member&&<option value={slot.open?'close':'open'} disabled={!!transaction}>{slot.open?'Close slot':'Open slot'}</option>}
     {ownsTransaction&&<optgroup label="Role change">{transaction.status==='failed'&&<option value="retry">Retry role change</option>}<option value="cancel">Cancel role change</option></optgroup>}
    </select>}</div>
   </section>;})}
  {removing&&room.role==='host'&&<dialog ref={dialog} className="slot-kick-dialog" aria-label={`Kick ${removing.nickname}`} onClose={()=>{const id=removing.slotId;setRemoving(undefined);focusSlot(id);}}>
   <h3>Kick {removing.nickname}?</h3>
   <p>They will leave the room and must join again to return.</p>
   {error&&<p role="alert">{error}</p>}
   <div className="slot-kick-actions"><button data-confirm-kick disabled={locked} onClick={async()=>{if(await send({type:'memberRemove',roomId:room.id,membership:removing.membership,expectedRevision:room.revision}))dismiss();}}>Kick member</button><button disabled={pending} onClick={dismiss}>Cancel</button></div>
  </dialog>}
  <div className="slot-feedback" role="status">{error|| (pending?'Updating room…':room.game.pending?.status==='failed'?room.game.pending.reason??'Previous roles and progress are preserved.':room.game.pending?.status==='freezing'?'Pausing at a shared frame before changing roles…':room.game.pending?'Synchronizing the new players before changing roles…':'')}</div>
 </div>;
}
