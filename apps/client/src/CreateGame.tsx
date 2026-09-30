import React,{useEffect,useState} from 'react';
import {catalogAvailability} from 'virtual:catalog';
import {catalog} from '../../../packages/contracts/src/catalog.ts';
import type {NewVisibility,Fingerprint,RoomPreview} from '../../../packages/contracts/src/rooms.ts';
import {gameLibrary,type GameLibraryEntry} from './rom-library.ts';

export type CreateSelection={entry:GameLibraryEntry;file:File;fingerprint:Fingerprint;current:()=>boolean;fresh?:boolean};
export function CreateGame({selected,loading,busy,status,claimFailed,persistenceMessage,libraryRevision,visibility,setVisibility,password,setPassword,offers,onSelect,onAdd,onDrop,onCreate,onBack,onCancel,onLocal}: {
 selected?:CreateSelection;loading:boolean;busy:boolean;status:string;claimFailed:boolean;persistenceMessage:string;libraryRevision:number;visibility:NewVisibility;setVisibility:(value:NewVisibility)=>void;password:string;setPassword:(value:string)=>void;offers:RoomPreview[];onSelect:(entry:GameLibraryEntry)=>void;onAdd:()=>void;onDrop:(file:File|undefined)=>void;onCreate:()=>void;onBack:()=>void;onCancel:()=>void;onLocal:()=>void;
}) {
 const [entries,setEntries]=useState<GameLibraryEntry[]>([]),[libraryError,setLibraryError]=useState('');
 const [revision,setRevision]=useState(0);
 const [showPassword,setShowPassword]=useState(false);
 useEffect(()=>{let alive=true;void gameLibrary().then(rows=>{if(alive){setEntries(rows);setLibraryError('');}}).catch(()=>{if(alive){setEntries(catalog.map(item=>({kind:'included',catalogId:item.id,sha256:item.sha256,size:item.bytes,label:item.title,source:'download',lastUsedAt:0})));setLibraryError('Saved games are unavailable here. Included games and files added in this tab still work.');}});return()=>{alive=false;};},[revision,libraryRevision,selected?.entry.sha256,persistenceMessage]);
 useEffect(()=>{const refresh=()=>{if(!document.hidden)setRevision(value=>value+1);};addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);return()=>{removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);};},[]);
 const grouped=[...entries.filter(entry=>entry.kind==='saved').sort((a,b)=>b.lastUsedAt-a.lastUsedAt),...entries.filter(entry=>entry.kind==='included')];
 const includedId=selected?.entry.kind==='included'?selected.entry.catalogId:undefined;
 const includedOffer=includedId?offers.find(room=>room.catalogId===includedId&&room.occupancy===0&&room.status==='waiting'&&!!room.code):undefined;
 const includedReady=selected?.entry.kind!=='included'||!!includedOffer;
 return <section className="create-game" aria-labelledby="create-heading" data-testid="create-game">
  <div className="create-heading"><div><p className="eyebrow">Create game</p><h1 id="create-heading">Choose a game for your room</h1></div><button onClick={onBack}>Back to rooms</button></div>
  <div className="create-grid"><section className="create-library" aria-label="Your games" onDragOver={event=>event.preventDefault()} onDrop={event=>{event.preventDefault();onDrop(event.dataTransfer.files.length===1?event.dataTransfer.files[0]:undefined);}}><div className="create-library-title"><h2>Your games</h2><button onClick={onAdd}>Add NES file</button></div>
   {libraryError&&<p role="alert">{libraryError}</p>}
  <ul>{grouped.map(entry=><li key={entry.sha256}><button className={selected?.entry.sha256===entry.sha256?'selected':''} aria-pressed={selected?.entry.sha256===entry.sha256} onClick={()=>onSelect(entry)} disabled={loading||busy||entry.kind==='included'&&!catalogAvailability[entry.catalogId]}><strong>{entry.label}</strong>{entry.kind==='included'&&!catalogAvailability[entry.catalogId]&&<span>Unavailable here</span>}</button></li>)}</ul>
  </section><div className="create-details">
   <section className="create-options" aria-label="Room options"><h2>Room options</h2><p className="selected-game" style={{visibility:selected?'visible':'hidden'}}>Selected: <strong>{selected?.entry.label??'Game'}</strong></p><label>Access <select aria-label="Room access" value={visibility} onChange={event=>setVisibility(event.target.value as NewVisibility)}><option value="public">Public</option><option value="protected">Password protected</option></select></label>
    {visibility==='protected'&&<div className="room-password"><label>Room password <input type={showPassword?'text':'password'} autoComplete="new-password" value={password} maxLength={128} onChange={event=>setPassword(event.target.value)}/></label><button type="button" onClick={()=>setShowPassword(value=>!value)}>{showPassword?'Hide':'Show'}</button><p className="hint">Use 8 to 128 characters. Share it separately from the invitation.</p></div>}
    {selected?.entry.kind==='included'&&!includedOffer&&!claimFailed&&<p role="status">No place is available for this game. Try again or choose another game.</p>}
    <div className="create-actions"><button onClick={onCreate} disabled={!selected||loading||busy||!includedReady||visibility==='protected'&&(Array.from(password).length<8||Array.from(password).length>128)}>Create room</button>{(loading||busy)&&<button onClick={onCancel}>Cancel</button>}</div><button className="local-play" style={{visibility:selected?'visible':'hidden'}} onClick={onLocal} disabled={!selected||loading||busy}>Play locally</button>
    <p role="status" aria-live="polite">{status}</p>{selected?.fresh&&persistenceMessage&&<p role="status">{persistenceMessage}</p>}
   </section></div></div>
 </section>;
}
