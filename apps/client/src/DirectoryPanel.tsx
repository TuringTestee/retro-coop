import {catalogEntry,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {matchingRooms} from '../../../packages/contracts/src/directory.ts';
import {validRoomPassword,type RoomPreview} from '../../../packages/contracts/src/rooms.ts';
import type {RoomState} from './room-client.ts';
import {clampPage,pageRows} from './directory-page.ts';
import {roomAdmissionMessage} from './room-admission-message.ts';
import {roomDownloadLabel} from './room-download.ts';
import {useOverflowFocus} from './ScrollRegion.tsx';
function roomState(room:RoomPreview) {
 if(room.status==='unavailable')return 'Unavailable';
 const open='openSlots' in room?room.openSlots:5-room.occupancy;
 return open===0?'Full':`${open} ${open===1?'place':'places'} open`;
}

export function DirectoryPanel({state,notices,onCreate,onJoin,onClaim,onRetry,onDismissJoin}:{state:RoomState;notices?:React.ReactNode;onCreate:()=>void;onJoin:(code:string,password?:string)=>void;onClaim:(code:string,id:CatalogId)=>void;onRetry:()=>void;onDismissJoin:()=>void}) {
 const[query,setQuery]=useState(''),[page,setPage]=useState(0),[pageSize,setPageSize]=useState(()=>innerHeight<700?2:innerHeight<820?3:4);
 const [protectedRoom,setProtectedRoom]=useState<RoomPreview>(),[password,setPassword]=useState(''),[showPassword,setShowPassword]=useState(false);
 const passwordDialog=useRef<HTMLDialogElement>(null);
 const list=useRef<HTMLUListElement>(null),listTabIndex=useOverflowFocus(list);
 useEffect(()=>{if(protectedRoom&&passwordDialog.current&&!passwordDialog.current.open)passwordDialog.current.showModal();},[protectedRoom]);
 const search=useRef<HTMLInputElement>(null),focusedRoom=useRef<string|undefined>(undefined);
 useEffect(()=>{const resize=()=>setPageSize(innerHeight<700?2:innerHeight<820?3:4);visualViewport?.addEventListener('resize',resize);addEventListener('resize',resize);return()=>{visualViewport?.removeEventListener('resize',resize);removeEventListener('resize',resize);};},[]);
 const rooms=matchingRooms(state.directory??[],query),live=state.directoryStatus==='live',view=pageRows(rooms,page,pageSize);
 useLayoutEffect(()=>{const next=clampPage(page,rooms.length,pageSize);if(next!==page)setPage(next);if(focusedRoom.current&&!rooms.some(room=>room.id===focusedRoom.current)){search.current?.focus();focusedRoom.current=undefined;}else if(focusedRoom.current&&document.activeElement===document.body)document.querySelector<HTMLElement>(`[data-room-id="${CSS.escape(focusedRoom.current)}"]`)?.focus();},[rooms,page,pageSize]);
 const move=(next:number)=>{setPage(next);requestAnimationFrame(()=>document.querySelector<HTMLElement>('.room-list [data-room-id]')?.focus());};
 return <section className="directory-panel" aria-labelledby="directory-heading" data-testid="directory" data-directory-status={state.directoryStatus}>
  <div className="directory-title" data-layout-region="directory-heading"><h2 id="directory-heading">Public rooms</h2><span role="status">{state.directoryStatus==='loading'?'Loading…':''}</span><button onClick={onCreate} disabled={!!state.room}>Create game</button></div>
  <div className="directory-search" data-layout-region="directory-search"><label>Search room, game, host, or code <input ref={search} type="search" value={query} maxLength={80} onChange={event=>{setQuery(event.target.value);setPage(0);}} onFocus={()=>{focusedRoom.current=undefined;}}/></label></div>
  <div className="directory-feedback" data-layout-region="directory-feedback" role="status" aria-live="polite">{notices}{state.directoryStatus==='stale'&&<p>{state.directoryError} <button onClick={onRetry}>Retry</button></p>}{live&&!rooms.length&&<p>{query.trim()?'No matching public rooms.':'No public rooms right now.'}</p>}</div>
  <ul className="room-list" data-layout-region="directory-list" ref={list} tabIndex={listTabIndex} aria-label="Public rooms" onBlur={event=>{if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget as Node))focusedRoom.current=undefined;}}>
   {view.rows.map(room=>{const known=room.catalogId?catalogEntry(room.catalogId):undefined,available=live&&!state.room&&room.status!=='unavailable'&&('openSlots' in room?room.openSlots>0:true)&&!state.busy;
    const claim=available&&room.occupancy===0,join=available&&room.occupancy>0;
    return <li key={room.id} data-room-id={room.id} tabIndex={-1} onFocus={()=>{focusedRoom.current=room.id;}}>
     <strong>{room.label}{room.visibility==='protected'&&<span className="room-lock"> · 🔒 Password required</span>}</strong>
     <span>{known?known.title!==room.label?known.title:'':roomDownloadLabel(room)}</span>
     <span>{room.host}</span><span>{roomState(room)}</span>
     {claim&&room.catalogId&&<button onClick={()=>onClaim(room.code!,room.catalogId!)}>Join as host</button>}
     {join&&<button onClick={()=>room.visibility==='protected'?setProtectedRoom(room):onJoin(room.code!)}>Join</button>}
    </li>;
   })}
  </ul>
  {protectedRoom&&<dialog ref={passwordDialog} className="room-password-dialog" aria-label={`Join ${protectedRoom.label}`} onClose={()=>{onDismissJoin();setProtectedRoom(undefined);setPassword('');setShowPassword(false);requestAnimationFrame(()=>document.querySelector<HTMLElement>(`[data-room-id="${CSS.escape(protectedRoom.id)}"] button`)?.focus());}}><h3>{protectedRoom.label}</h3><p>{protectedRoom.catalogId?catalogEntry(protectedRoom.catalogId)?.title:roomDownloadLabel(protectedRoom)} · Password required</p><form onSubmit={event=>{event.preventDefault();if(validRoomPassword(password))onJoin(protectedRoom.code!,password);}}><label>Room password <input type={showPassword?'text':'password'} autoComplete="off" value={password} onChange={event=>setPassword(event.target.value)}/></label><button type="button" onClick={()=>setShowPassword(value=>!value)}>{showPassword?'Hide':'Show'}</button><p className="hint">Use 8 to 128 characters.</p><p role="alert">{roomAdmissionMessage(state.admissionError,state.retryAfterMs)}</p><button data-layout-region="password-join" type="submit" disabled={!validRoomPassword(password)||state.busy}>Join room</button><button data-layout-region="password-back" type="button" onClick={()=>passwordDialog.current?.close()}>Back</button></form></dialog>}
  <div className="pagination-region" data-layout-region="directory-actions">{view.pages>1&&<nav className="pagination" aria-label="Room pages"><button disabled={view.page===0} onClick={()=>move(view.page-1)}>Previous</button><span>Page {view.page+1} of {view.pages}</span><button disabled={view.page+1>=view.pages} onClick={()=>move(view.page+1)}>Next</button></nav>}</div>
 </section>;
}
