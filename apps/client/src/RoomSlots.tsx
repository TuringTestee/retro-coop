import React,{useEffect,useRef,useState} from 'react';
import {SLOT_IDS,type RoomSlot,type SlotRole} from '../../../packages/contracts/src/slots.ts';
import type {RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {RoomClient} from './room-client.ts';

export const slotRoleLabel=(role:SlotRole)=>role==='observer'?'Watching':role==='player1'?'P1':'P2';

function slotStatus(room:RoomView,slot:RoomSlot){
 const member=slot.member;
 if(!member)return '';
 if(!member.connected)return 'Disconnected';
 const peer=room.peers.find(value=>value.member===member.id);
 if(peer&&['relay_unavailable','relay_capacity','failed'].includes(peer.status))return 'Connection failed';
 if(!room.fingerprint)return 'Waiting for game';
 if(!member.matches||member.acquisition!=='loaded')return ({checking:'Checking game',downloading:'Downloading game',loading:'Loading game',failed:'Game failed',loaded:'Game mismatch'})[member.acquisition];
 if(peer&&peer.status!=='connected')return 'Connecting';
 if(room.game.pending?.roles.some(value=>value.slotId===slot.id))return room.game.pending.status==='failed'?'Role change failed':'Changing role';
 if(room.started)return slot.role==='observer'?'Watching':!room.game.controllers.owners.includes(member.id)?'Waiting to play':room.game.status==='playing'?'Playing':'Paused';
 if(slot.role==='observer')return 'Can watch';
 return room.game.ready.includes(member.id)?'Ready':'Not ready';
}

export function RoomSlots({room,connected,act,onKickRequested,onFeedback,onInspect}:{room:RoomView;connected:boolean;act:RoomClient['act'];onKickRequested:(slot:RoomSlot)=>void;onFeedback:(message:string)=>void;onInspect:(name:string)=>void}){
 const [openSlot,setOpenSlot]=useState<string>(),[pending,setPending]=useState(false);
 const root=useRef<HTMLDivElement>(null),roomId=useRef(room.id);roomId.current=room.id;
 const returnFocus=(id:string)=>root.current?.querySelector<HTMLButtonElement>(`[data-slot-id="${id}"] .slot-row`)?.focus();
 const menuItems=(id:string)=>[...(root.current?.querySelectorAll<HTMLButtonElement>(`[data-slot-id="${id}"] .slot-menu button:not(:disabled)`)??[])];
 const focusMenu=(id:string,last=false)=>requestAnimationFrame(()=>{const items=menuItems(id);(last?items.at(-1):items[0])?.focus();});
 const moveMenu=(event:React.KeyboardEvent,id:string)=>{if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;const items=menuItems(id);if(!items.length)return;event.preventDefault();const current=items.indexOf(document.activeElement as HTMLButtonElement);const next=event.key==='Home'?0:event.key==='End'?items.length-1:event.key==='ArrowDown'?(current+1)%items.length:(current-1+items.length)%items.length;items[next]?.focus();};
 const inspect=(element:HTMLElement,title:string)=>{const label=element.querySelector('strong');onInspect(label&&label.scrollWidth>label.clientWidth+1?title:'');};
 useEffect(()=>{setOpenSlot(undefined);setPending(false);},[room.id]);
 useEffect(()=>{setOpenSlot(undefined);},[room.revision]);
 useEffect(()=>{const outside=(event:PointerEvent)=>{if(root.current&&!root.current.contains(event.target as Node))setOpenSlot(undefined);};const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'&&openSlot){event.preventDefault();setOpenSlot(undefined);returnFocus(openSlot);}};document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);};},[openSlot]);
 const send=async(command:Parameters<RoomClient['act']>[0])=>{const targetRoom=room.id;setOpenSlot(undefined);setPending(true);onFeedback('Updating players…');try{const ok=await act(command);if(root.current&&roomId.current===targetRoom)onFeedback(ok?'':'Slot change failed. Open the row to try again.');}catch{if(root.current&&roomId.current===targetRoom)onFeedback('Lobby unavailable. Reconnect and try again.');}finally{setPending(false);}};
 const action=(slot:RoomSlot,value:string)=>{setOpenSlot(undefined);if(value==='kick'){onKickRequested(slot);return;}returnFocus(slot.id);if(value==='retry'&&room.game.pending){void send({type:'gameRoleRetry',transactionId:room.game.pending.id});return;}if(value==='cancel'&&room.game.pending){void send({type:'gameRoleCancel',transactionId:room.game.pending.id});return;}if(value==='close'||value==='open'){void send({type:'slotAvailability',roomId:room.id,slotId:slot.id,open:value==='open',expectedRevision:room.revision});return;}if(value.startsWith('move:'))void send({type:'slotMove',roomId:room.id,fromSlotId:slot.id,toSlotId:value.slice(5) as RoomSlot['id'],expectedRevision:room.revision});};
 return <div ref={root} className="room-slots" aria-label="Players">
  {SLOT_IDS.map((id,index)=>{const slot=room.slots.find(value=>value.id===id);if(!slot)throw Error(`Missing lobby slot ${id}`);const member=slot.member;const title=member?`${slot.role==='observer'?'':`${slotRoleLabel(slot.role)} · `}${member.id===room.chatMembership?'You':member.nickname}`:`${slot.open?'Open':'Closed'} Slot ${index+1}`;const status=slotStatus(room,slot);const menuOpen=openSlot===id,host=room.role==='host';const transaction=room.game.pending;const ownsTransaction=transaction?.roles[0]?.slotId===id;
   return <div className="slot-wrap" data-testid="room-slot" data-slot-id={id} key={id}>
    {host?<button className={`slot-row${member?'':' slot-empty'}`} type="button" title={title} aria-label={`${slot.role==='observer'?'Watching. ':''}${title}${status?`. ${status}`:''}. Slot actions`} aria-haspopup="menu" aria-expanded={menuOpen} disabled={!connected||pending||!!transaction&&!ownsTransaction} onFocus={event=>inspect(event.currentTarget,title)} onBlur={()=>onInspect('')} onKeyDown={event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();if(!menuOpen)setOpenSlot(id);focusMenu(id,event.key==='ArrowUp');}}} onClick={()=>setOpenSlot(menuOpen?undefined:id)}><span className="slot-chevron" aria-hidden="true">{menuOpen?'⌃':'⌄'}</span><strong title={title}>{title}</strong><span className={`slot-state${status==='Ready'?' is-ready':''}`}>{status}</span></button>:<div className={`slot-row slot-readonly${member?'':' slot-empty'}`} tabIndex={0} title={title} aria-label={`${slot.role==='observer'?'Watching. ':''}${title}${status?`. ${status}`:''}`} onFocus={event=>inspect(event.currentTarget,title)} onBlur={()=>onInspect('')} onClick={event=>event.currentTarget.focus()}><strong title={title}>{title}</strong><span className={`slot-state${status==='Ready'?' is-ready':''}`}>{status}</span></div>}
    {host&&menuOpen&&<div className="slot-menu" role="menu" aria-label={`${title} actions`} onKeyDown={event=>moveMenu(event,id)}>{transaction?ownsTransaction&&<>{transaction.status==='failed'&&<button type="button" role="menuitem" onClick={()=>action(slot,'retry')}>Retry player change</button>}<button type="button" role="menuitem" onClick={()=>action(slot,'cancel')}>Cancel player change</button></>:!slot.open?<button type="button" role="menuitem" onClick={()=>action(slot,'open')}>Open slot</button>:!member?<button type="button" role="menuitem" onClick={()=>action(slot,'close')}>Close slot</button>:<>
     {room.slots.filter(target=>target.id!==id&&target.open).map(target=>{const place=target.role==='player1'?'Player 1':target.role==='player2'?'Player 2':`Spectator ${SLOT_IDS.indexOf(target.id)+1}`;return <button type="button" role="menuitem" key={target.id} aria-label={target.member?`Swap with ${target.member.nickname} · ${place}`:`Move as ${place}`} onClick={()=>action(slot,`move:${target.id}`)}>{target.member?`Swap with ${place}`:`Move as ${place}`}</button>;})}
     {member.id!==room.hostMembership&&<button type="button" role="menuitem" className="danger-text" title={`Kick ${member.nickname}`} aria-label={`Kick ${member.nickname}`} onClick={()=>action(slot,'kick')}>Kick</button>}
    </>}</div>}
   </div>;
  })}
 </div>;
}
