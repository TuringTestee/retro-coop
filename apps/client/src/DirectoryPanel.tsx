import React,{useLayoutEffect,useRef,useState} from 'react';
import {matchingRooms,publicCode} from '../../../packages/contracts/src/directory.ts';
import type {RoomState} from './room-client.ts';

export function DirectoryPanel({state,onJoin,onRetry}:{state:RoomState;onJoin:(code:string)=>void;onRetry:()=>void}) {
 const [query,setQuery]=useState('');
 const search=useRef<HTMLInputElement>(null), list=useRef<HTMLUListElement>(null), focusedRoom=useRef<string|undefined>(undefined);
 const rooms=matchingRooms(state.directory ?? [],query), live=state.directoryStatus==='live';
 useLayoutEffect(()=>{
  if(document.activeElement instanceof HTMLButtonElement && document.activeElement.disabled) (document.activeElement.closest('li') as HTMLElement|null)?.focus();
  if(focusedRoom.current && !rooms.some(room=>room.id===focusedRoom.current)) {search.current?.focus();focusedRoom.current=undefined;}
 },[rooms]);
 return <section className="directory-panel" aria-labelledby="directory-heading">
  <h2 id="directory-heading">Public rooms</h2>
  <p>Join reserves Player 2 for 120 seconds. Bring your own matching game file.</p>
  <label>Search rooms, hosts or public code <input ref={search} type="search" value={query} maxLength={80} onChange={event=>setQuery(event.target.value)} onFocus={()=>{focusedRoom.current=undefined;}}/></label>
  {state.directoryStatus==='loading' && <p role="status">Loading rooms…</p>}
  {state.directoryStatus==='stale' && <p role="status">{state.directoryError} Previous results may be out of date. <button onClick={onRetry}>Retry directory</button></p>}
  {live && !rooms.length && <p role="status">{query.trim() ? 'No matching public rooms.' : 'No public rooms yet. Host a game to start one.'}</p>}
  {publicCode(query) && live && !rooms.length && <p>Unlisted rooms require an invitation. Public codes are not private invitations.</p>}
  <ul ref={list} className="room-list" aria-label="Public rooms" onBlur={event=>{if(event.relatedTarget && !event.currentTarget.contains(event.relatedTarget as Node)) focusedRoom.current=undefined;}}>
   {state.directoryStatus==='loading' && !state.directory?.length && [0,1,2].map(index=><li key={`loading-${index}`} className="room-placeholder" aria-hidden="true">Loading room…</li>)}
   {rooms.map(room=><li key={room.id} data-room-id={room.id} tabIndex={-1} onFocus={()=>{focusedRoom.current=room.id;}}>
    <strong>{room.label}</strong> <span>Hosted by {room.host}</span> <code>{room.code}</code>
    <span>{room.occupancy}/2 places · {room.status}</span>
    <button disabled={!live || !!state.room || state.busy || room.status!=='waiting' || room.occupancy!==1} onClick={()=>onJoin(room.code!)}>{room.status==='reconnecting' ? 'Host reconnecting' : room.occupancy===2 ? 'Player 2 reserved' : 'Join room'}</button>
   </li>)}
  </ul>
  {state.room && <p>Leave or close your current room before joining another.</p>}
 </section>;
}
