import {catalogEntry,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import type {ReactNode} from 'react';
import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {matchingRooms,publicCode} from '../../../packages/contracts/src/directory.ts';
import type {RoomPreview} from '../../../packages/contracts/src/rooms.ts';
import type {RoomState} from './room-client.ts';
import {clampPage,pageRows} from './directory-page.ts';
const gameSize=(bytes:number)=>bytes<1_000_000?`${Math.max(1,Math.ceil(bytes/1000))} KB`:`${(bytes/1_000_000).toFixed(1)} MB`;

function roomState(room:RoomPreview) {
 if(room.occupancy===0)return room.status==='unavailable'?'0/2 · Room capacity full':'0/2 · Waiting for host';
 if(room.guestPlace==='closed' && room.status==='waiting')return '1/2 · Guest place closed';
 if(room.status==='reserved')return '2/2 · Guest preparing';
 if(room.status==='reconnecting')return `${room.occupancy}/2 · Reconnecting; Join unavailable`;
 if(room.status==='playing')return `${room.occupancy}/2 · Playing; Join unavailable`;
 if(room.status==='paused')return `${room.occupancy}/2 · Paused; Join unavailable`;
 if(room.occupancy===2)return '2/2 · Full';
 return '1/2 · Waiting for guest';
}

export function DirectoryPanel({state,onCreate,onJoin,onClaim,onRetry,connection}:{state:RoomState;connection?:ReactNode;onCreate:()=>void;onJoin:(code:string)=>void;onClaim:(code:string,id:CatalogId)=>void;onRetry:()=>void}) {
 const[query,setQuery]=useState(''),[page,setPage]=useState(0),[pageSize,setPageSize]=useState(()=>innerHeight<700?2:innerHeight<820?3:4);
 const search=useRef<HTMLInputElement>(null),focusedRoom=useRef<string|undefined>(undefined);
 useEffect(()=>{const resize=()=>setPageSize(innerHeight<700?2:innerHeight<820?3:4);visualViewport?.addEventListener('resize',resize);addEventListener('resize',resize);return()=>{visualViewport?.removeEventListener('resize',resize);removeEventListener('resize',resize);};},[]);
 const rooms=matchingRooms(state.directory??[],query),live=state.directoryStatus==='live',view=pageRows(rooms,page,pageSize);
 useLayoutEffect(()=>{const next=clampPage(page,rooms.length,pageSize);if(next!==page)setPage(next);if(focusedRoom.current&&!rooms.some(room=>room.id===focusedRoom.current)){search.current?.focus();focusedRoom.current=undefined;}else if(focusedRoom.current&&document.activeElement===document.body)document.querySelector<HTMLElement>(`[data-room-id="${CSS.escape(focusedRoom.current)}"]`)?.focus();},[rooms,page,pageSize]);
 const move=(next:number)=>{setPage(next);requestAnimationFrame(()=>document.querySelector<HTMLElement>('.room-list [data-room-id]')?.focus());};
 return <section className="directory-panel" aria-labelledby="directory-heading" data-testid="directory">
  <div className="directory-title"><h2 id="directory-heading">Public rooms</h2><span role="status">{live?'Live':state.directoryStatus==='stale'?'Connection lost':'Loading…'}</span><button onClick={onCreate} disabled={!!state.room}>Create game</button></div>
  {connection}
  <label>Search room, game, host, or code <input ref={search} type="search" value={query} maxLength={80} onChange={event=>{setQuery(event.target.value);setPage(0);}} onFocus={()=>{focusedRoom.current=undefined;}}/></label>
  {query&&<button onClick={()=>{setQuery('');setPage(0);search.current?.focus();}}>Clear search</button>}
  {state.directoryStatus==='loading'&&<p role="status">Looking for rooms…</p>}
  {state.directoryStatus==='stale'&&<p role="status">{state.directoryError} <button onClick={onRetry}>Retry</button></p>}
  {live&&!rooms.length&&<p role="status">{query.trim()?'No matching public rooms.':'No public rooms right now.'}</p>}
  {publicCode(query)&&live&&!rooms.length&&<p>Unlisted rooms open through invitations.</p>}
  {state.room&&<p>Leave your current room before joining another.</p>}
  <ul className="room-list" aria-label="Public rooms" onBlur={event=>{if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget as Node))focusedRoom.current=undefined;}}>
   {view.rows.map(room=>{const known=room.catalogId?catalogEntry(room.catalogId):undefined,available=live&&!state.room&&room.status==='waiting'&&('guestPlace' in room?room.guestPlace==='open':true)&&!state.busy;
    const claim=available&&room.occupancy===0,join=available&&room.occupancy===1;
    return <li key={room.id} data-room-id={room.id} tabIndex={-1} onFocus={()=>{focusedRoom.current=room.id;}}>
     <strong>{room.label}</strong>
     <span>{known?`${known.title!==room.label?`${known.title} · `:''}${room.catalogId==='from-below-1.0'?'One controller; share turns':'P1/P2 controllers'} · included`:`Host-shared NES · ${'romBytes' in room&&room.romBytes?`${gameSize(room.romBytes)} download`:'download size unavailable'}`}</span>
     <span>{room.host}</span><code>{room.code}</code><span>{roomState(room)}</span>
     {claim&&room.catalogId&&<button onClick={()=>onClaim(room.code!,room.catalogId!)}>Join as host</button>}
     {join&&<button onClick={()=>onJoin(room.code!)}>Join</button>}
    </li>;
   })}
  </ul>
  {view.pages>1&&<nav className="pagination" aria-label="Room pages"><button disabled={view.page===0} onClick={()=>move(view.page-1)}>Previous</button><span>Page {view.page+1} of {view.pages}</span><button disabled={view.page+1>=view.pages} onClick={()=>move(view.page+1)}>Next</button></nav>}
 </section>;
}
