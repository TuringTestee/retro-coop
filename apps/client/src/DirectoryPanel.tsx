import {catalogEntry,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import type {ReactNode} from 'react';import React,{useEffect,useLayoutEffect,useRef,useState}from'react';
import{matchingRooms,publicCode}from'../../../packages/contracts/src/directory.ts';import type{RoomState}from'./room-client.ts';import{clampPage,pageRows}from'./directory-page.ts';

export function DirectoryPanel({state,onJoin,onRetry,connection,filterId,onClearFilter}:{filterId?:CatalogId;onClearFilter?:()=>void;state:RoomState;connection?:ReactNode;onJoin:(code:string)=>void;onRetry:()=>void}){
 const[query,setQuery]=useState(''),[page,setPage]=useState(0),[pageSize,setPageSize]=useState(()=>innerHeight<700?2:innerHeight<820?3:4);const search=useRef<HTMLInputElement>(null),focusedRoom=useRef<string|undefined>(undefined);
 useEffect(()=>{const resize=()=>setPageSize(innerHeight<700?2:innerHeight<820?3:4);visualViewport?.addEventListener('resize',resize);addEventListener('resize',resize);return()=>{visualViewport?.removeEventListener('resize',resize);removeEventListener('resize',resize);};},[]);
 const rooms=matchingRooms(state.directory??[],query).filter(room=>!filterId||room.catalogId===filterId),live=state.directoryStatus==='live',view=pageRows(rooms,page,pageSize);
 useLayoutEffect(()=>{const next=clampPage(page,rooms.length,pageSize);if(next!==page)setPage(next);if(focusedRoom.current&&!rooms.some(room=>room.id===focusedRoom.current)){search.current?.focus();focusedRoom.current=undefined;}},[rooms,page,pageSize]);
 const move=(next:number)=>{setPage(next);requestAnimationFrame(()=>document.querySelector<HTMLElement>('.room-list [data-room-id]')?.focus());};
 return <section className="directory-panel" aria-labelledby="directory-heading" data-testid="directory"><div className="directory-title"><div><p className="eyebrow">Live lobbies</p><h2 id="directory-heading">{filterId?`${catalogEntry(filterId).title} lobbies`:'All public lobbies'}</h2></div>{filterId&&<button onClick={()=>{setPage(0);onClearFilter?.();search.current?.focus();}}>Show all lobbies</button>}</div>
  {connection}<label>Search room, host, or code <input ref={search} type="search" value={query} maxLength={80} onChange={event=>{setQuery(event.target.value);setPage(0);}} onFocus={()=>{focusedRoom.current=undefined;}}/></label>
  {query&&<button onClick={()=>{setQuery('');setPage(0);search.current?.focus();}}>Clear search</button>}
  {state.directoryStatus==='loading'&&<p role="status">Loading lobbies…</p>}{state.directoryStatus==='stale'&&<p role="status">{state.directoryError} Previous results may be out of date. <button onClick={onRetry}>Retry directory</button></p>}
  {live&&!rooms.length&&<p role="status">{filterId?`No public ${catalogEntry(filterId).title} lobbies yet.`:query.trim()?'No matching public lobbies.':'No public lobbies yet. Start a game above.'}</p>}
  {publicCode(query)&&live&&!rooms.length&&<p>Unlisted lobbies require an invitation. Public codes are not private invitations.</p>}
  <ul className="room-list" aria-label="Public lobbies" onBlur={event=>{if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget as Node))focusedRoom.current=undefined;}}>
   {view.rows.map(room=>{const joinable=live&&!state.room&&!state.busy&&room.status==='waiting'&&room.occupancy===1;const known=room.catalogId?catalogEntry(room.catalogId):undefined;return <li key={room.id} data-room-id={room.id} tabIndex={-1} onFocus={()=>{focusedRoom.current=room.id;}}><strong>{known?.title??room.label}</strong><span>{known?'Included game':'Host-provided game'}</span><span>{room.host}</span><code>{room.code}</code><span>{room.occupancy}/2 · {room.status}</span><button aria-disabled={!joinable} onClick={()=>{if(joinable)onJoin(room.code!);}}>{room.status==='reconnecting'?'Host reconnecting':room.occupancy===2?'Full':'Join'}</button></li>;})}
  </ul>{view.pages>1&&<nav className="pagination" aria-label="Lobby pages"><button disabled={view.page===0} onClick={()=>move(view.page-1)}>Previous</button><span>Page {view.page+1} of {view.pages}</span><button disabled={view.page+1>=view.pages} onClick={()=>move(view.page+1)}>Next</button></nav>}
  {state.room&&<p>Leave or close your current lobby before joining another.</p>}
 </section>;
}
