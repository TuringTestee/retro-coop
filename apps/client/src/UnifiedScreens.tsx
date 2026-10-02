import React,{useEffect,useMemo,useState} from 'react';
import type {HumanRoomPreview,RoomPreview} from '../../../packages/contracts/src/rooms.ts';
import {validRoomPassword} from '../../../packages/contracts/src/rooms.ts';

const human=(room:RoomPreview):room is HumanRoomPreview=>'openSlots' in room;
const unavailable=(room:HumanRoomPreview)=>room.openSlots===0?'No open places':room.status==='reconnecting'?'Lobby reconnecting. Try soon.':!room.code?'Join unavailable. Try soon.':undefined;

export function LobbyDirectory({rooms,status,busy,error,onHost,onJoin,onDismissError,onCancelJoin,onInspect}:{rooms:RoomPreview[];status?:'loading'|'live'|'stale';busy:boolean;error?:string;onHost:()=>void;onJoin:(code:string,password?:string)=>void;onDismissError:()=>void;onCancelJoin:()=>void;onInspect:(label:string)=>void}){
 const [query,setQuery]=useState(''),[page,setPage]=useState(0),[target,setTarget]=useState<HumanRoomPreview>(),[password,setPassword]=useState('');
 const [pageSize,setPageSize]=useState(()=>typeof innerHeight==='number'&&innerHeight<700?2:4);
 useEffect(()=>{const resized=()=>setPageSize(innerHeight<700?2:4);addEventListener('resize',resized);return()=>removeEventListener('resize',resized);},[]);
 const discoverable=useMemo(()=>rooms.filter(human),[rooms]);
 const duplicates=useMemo(()=>{const counts=new Map<string,number>();for(const room of discoverable){const key=`${room.label}\u0000${room.host}`;counts.set(key,(counts.get(key)??0)+1);}return counts;},[discoverable]);
 const matching=useMemo(()=>discoverable.filter(room=>[room.label,room.host,room.gameTitle??'',room.code??''].join(' ').toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())),[discoverable,query]);
 const pages=Math.max(1,Math.ceil(matching.length/pageSize)),current=Math.min(page,pages-1),shown=matching.slice(current*pageSize,current*pageSize+pageSize);
 useEffect(()=>{onInspect('');},[rooms,query,current,onInspect]);
 useEffect(()=>{if(target&&!rooms.some(room=>room.id===target.id&&human(room)&&!unavailable(room)))setTarget(undefined);},[rooms,target]);
 const join=(room:HumanRoomPreview)=>{onDismissError();if(room.visibility==='protected'){setTarget(room);setPassword('');return;}if(room.code)onJoin(room.code);};
 return <section className="rc-listing" aria-label="All lobbies">
  <div className="rc-list-head"><span aria-live="polite">{status==='live'?`${matching.length} ${matching.length===1?'lobby':'lobbies'}`:status==='stale'?'Lobbies unavailable':'Finding lobbies…'}</span><input aria-label="Search lobbies" type="search" placeholder="Search lobbies" value={query} onChange={event=>{setQuery(event.target.value);setPage(0);}}/></div>
  <button className="rc-host-card" disabled={busy} onClick={onHost}><span className="rc-card-icon" aria-hidden="true">＋</span><strong>Host a new game</strong><span aria-hidden="true">→</span></button>
  <div className="rc-list-cards" style={{gridTemplateRows:`repeat(${pageSize},minmax(0,min(72px,${100/pageSize}%)))`}}>{status!=='live'?<div className="rc-list-empty"/>:shown.length?shown.map(room=>{
   const duplicate=(duplicates.get(`${room.label}\u0000${room.host}`)??0)>1;
   const code=room.code??room.id.slice(0,8),reason=unavailable(room);
   return <button className="rc-lobby-card" key={room.id} type="button" disabled={busy||!!reason} title={reason??`Join ${room.label}`} onFocus={()=>onInspect(`${room.label}${duplicate?` · Lobby code ${code}`:''}`)} onBlur={()=>onInspect('')} onClick={()=>{onInspect('');join(room);}}>
    <span className="rc-card-icon" aria-hidden="true">{room.gameTitle?'▣':'◇'}</span>
    <span className="rc-card-name"><strong title={room.label}>{room.label}</strong><small><span className="rc-card-mobile-access">{room.visibility==='protected'?'Password':'Public'} · {room.openSlots} open</span><span className="rc-card-game-title" title={reason??room.gameTitle??'No game yet'}>{reason??room.gameTitle??'No game yet'}</span><span className="rc-card-host"> · hosted by {room.host}</span></small>{duplicate&&<span className="rc-card-disambiguator" title={`Lobby code ${room.code??room.id}`}>Lobby code {code}</span>}</span>
    <span className="rc-card-access">{room.visibility==='protected'?'⌁ Password':'◌ Public'}</span>
    <span className="rc-card-count">{room.occupancy}/5</span>
   </button>;
  }):<div className="rc-list-empty"><strong>{query?'No lobbies match.':'No lobbies yet.'}</strong>{query&&<span>Try another search.</span>}</div>}</div>
  <div className="rc-join-detail">{target?<><span role={error?'alert':undefined} title={error??`Join ${target.label}`}>{error??`Join ${target.label}`}</span><input aria-label="Lobby password" type="password" autoComplete="off" placeholder="Lobby password" value={password} onChange={event=>{setPassword(event.target.value);onDismissError();}}/><button disabled={!validRoomPassword(password)||busy} onClick={()=>target.code&&onJoin(target.code,password)}>Join lobby</button><button className="rc-quiet" onClick={()=>{setTarget(undefined);onCancelJoin();}}>Cancel</button></>:error&&<span role="alert">{error}</span>}</div>
  {pages>1&&<nav className="rc-pagination" aria-label="Lobby pages"><button disabled={current===0} onClick={()=>setPage(current-1)}>← Previous</button><span>{current+1} / {pages}</span><button disabled={current>=pages-1} onClick={()=>setPage(current+1)}>Next →</button></nav>}
 </section>;
}
