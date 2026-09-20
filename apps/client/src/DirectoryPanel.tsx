import {featuredGame} from '../../../packages/contracts/src/catalog.ts';
import type {ReactNode} from 'react';
import React,{useLayoutEffect,useRef,useState} from 'react';
import {matchingRooms,publicCode} from '../../../packages/contracts/src/directory.ts';
import type {RoomState} from './room-client.ts';

export function DirectoryPanel({state,onJoin,onRetry,connection,featuredOnly=false,onClearFeatured}:{featuredOnly?:boolean;onClearFeatured?:()=>void;state:RoomState;connection?:ReactNode;onJoin:(code:string)=>void;onRetry:()=>void}) {
 const [query,setQuery]=useState('');
 const search=useRef<HTMLInputElement>(null), list=useRef<HTMLUListElement>(null), focusedRoom=useRef<string|undefined>(undefined);
 const rooms=matchingRooms(state.directory ?? [],query).filter(room=>!featuredOnly || room.catalogId===featuredGame.id), live=state.directoryStatus==='live';
 useLayoutEffect(()=>{
  if(focusedRoom.current && !rooms.some(room=>room.id===focusedRoom.current)) {search.current?.focus();focusedRoom.current=undefined;}
 },[rooms]);
 return <section className="directory-panel" aria-labelledby="directory-heading">
  <h2 id="directory-heading">Public rooms</h2>
  {connection}
  <p>Join reserves Player 2 for 120 seconds. Included rooms download the game; other rooms need your matching local file.</p>
  {featuredOnly && <p>Featured game <button onClick={onClearFeatured}>Show all sessions</button></p>}
  <label>Search rooms, hosts or public code <input ref={search} type="search" value={query} maxLength={80} onChange={event=>setQuery(event.target.value)} onFocus={()=>{focusedRoom.current=undefined;}}/></label>
  {query && <button onClick={()=>{setQuery('');search.current?.focus();}}>Clear search</button>}
  {state.directoryStatus==='loading' && <p role="status">Loading rooms…</p>}
  {state.directoryStatus==='stale' && <p role="status">{state.directoryError} Previous results may be out of date. <button onClick={onRetry}>Retry directory</button></p>}
  {live && !rooms.length && <p role="status">{featuredOnly ? 'No sessions yet for From Below. Start a session above.' : query.trim() ? 'No matching public rooms.' : 'No public rooms yet. Host a game to start one.'}</p>}
  {publicCode(query) && live && !rooms.length && <p>Unlisted rooms require an invitation. Public codes are not private invitations.</p>}
  <ul ref={list} className="room-list" aria-label="Public rooms" onBlur={event=>{if(event.relatedTarget && !event.currentTarget.contains(event.relatedTarget as Node)) focusedRoom.current=undefined;}}>
   {state.directoryStatus==='loading' && !state.directory?.length && [0,1,2].map(index=><li key={`loading-${index}`} className="room-placeholder" aria-hidden="true">Loading room…</li>)}
   {rooms.map(room=>{const joinable=live && !state.room && !state.busy && room.status==='waiting' && room.occupancy===1;return <li key={room.id} data-room-id={room.id} tabIndex={-1} onFocus={()=>{focusedRoom.current=room.id;}}>
    <strong><span>{room.label}</span> <small className="hint">Host-provided title</small></strong><span>{room.catalogId===featuredGame.id ? 'From Below · Game included' : 'Bring your own matching ROM'}</span> <span>Hosted by {room.host}</span> <code>{room.code}</code>
    <span>{room.occupancy}/2 places · {room.status}</span>
    <button aria-disabled={!joinable} onClick={()=>{if(joinable) onJoin(room.code!);}}>{room.status==='reconnecting' ? 'Host reconnecting' : room.occupancy===2 ? 'Player 2 reserved' : 'Join room'}</button>
   </li>;})}
  </ul>
  {state.room && <p>Leave or close your current room before joining another.</p>}
 </section>;
}
