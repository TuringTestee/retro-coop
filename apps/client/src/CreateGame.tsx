import React,{useEffect,useState} from 'react';
import {catalogAvailability} from 'virtual:catalog';
import {catalog,catalogEntry} from '../../../packages/contracts/src/catalog.ts';
import type {ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
import type {Visibility,Fingerprint,RoomPreview} from '../../../packages/contracts/src/rooms.ts';
import {gameLibrary,previewDisplay,type GameLibraryEntry} from './rom-library.ts';
import {ConnectionPolicyControl} from './ConnectionPolicy.tsx';

export type CreateSelection={entry:GameLibraryEntry;file:File;fingerprint:Fingerprint;current:()=>boolean;fresh?:boolean};
export function CreateGame({selected,loading,busy,status,claimFailed,persistenceMessage,visibility,setVisibility,policy,setPolicy,offers,onSelect,onAdd,onDrop,onCreate,onBack,onCancel,onLocal}: {
 selected?:CreateSelection;loading:boolean;busy:boolean;status:string;claimFailed:boolean;persistenceMessage:string;visibility:Visibility;setVisibility:(value:Visibility)=>void;policy:ConnectionPolicy;setPolicy:(value:ConnectionPolicy)=>void;offers:RoomPreview[];onSelect:(entry:GameLibraryEntry)=>void;onAdd:()=>void;onDrop:(file:File|undefined)=>void;onCreate:()=>void;onBack:()=>void;onCancel:()=>void;onLocal:()=>void;
}) {
 const [entries,setEntries]=useState<GameLibraryEntry[]>([]),[libraryError,setLibraryError]=useState('');
 const [preview,setPreview]=useState<{image:string;alt:string}|{text:'No preview yet.'}>({text:'No preview yet.'});
 const [revision,setRevision]=useState(0);
 useEffect(()=>{let alive=true;void gameLibrary().then(rows=>{if(alive){setEntries(rows);setLibraryError('');}}).catch(()=>{if(alive){setEntries(catalog.map(item=>({kind:'included',catalogId:item.id,sha256:item.sha256,size:item.bytes,label:item.title,source:'download',lastUsedAt:0})));setLibraryError('Saved games are unavailable here. Included games and files added in this tab still work.');}});return()=>{alive=false;};},[revision,selected?.entry.sha256,persistenceMessage]);
 useEffect(()=>{let alive=true;const recent=[...entries].filter(row=>!!row.preview).sort((a,b)=>b.lastUsedAt-a.lastUsedAt);void (async()=>{for(const row of recent){const value=await previewDisplay(row);if(!alive)return;if('image' in value){setPreview(value);return;}}if(alive)setPreview({text:'No preview yet.'});})();return()=>{alive=false;};},[entries]);
 useEffect(()=>{const refresh=()=>{if(!document.hidden)setRevision(value=>value+1);};addEventListener('focus',refresh);document.addEventListener('visibilitychange',refresh);return()=>{removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh);};},[]);
 const grouped=[...entries.filter(entry=>entry.kind==='saved').sort((a,b)=>b.lastUsedAt-a.lastUsedAt),...entries.filter(entry=>entry.kind==='included')];
 const includedId=selected?.entry.kind==='included'?selected.entry.catalogId:undefined;
 const includedOffer=includedId?offers.find(room=>room.catalogId===includedId&&room.occupancy===0&&room.status==='waiting'&&!!room.code):undefined;
 const includedReady=selected?.entry.kind!=='included'||!!includedOffer;
 return <section className="create-game" aria-labelledby="create-heading" data-testid="create-game">
  <div className="create-heading"><div><p className="eyebrow">Create game</p><h1 id="create-heading">Choose a game for your room</h1></div><button onClick={onBack}>Back to rooms</button></div>
  <div className="create-grid"><section className="create-library" aria-label="Your games" onDragOver={event=>event.preventDefault()} onDrop={event=>{event.preventDefault();onDrop(event.dataTransfer.files.length===1?event.dataTransfer.files[0]:undefined);}}><div className="create-library-title"><h2>Your games</h2><button onClick={onAdd}>Add NES file</button></div>
   <p className="hint">Saved here or included · drop one NES file here</p>
   {libraryError&&<p role="alert">{libraryError}</p>}
  <ul>{grouped.map(entry=><li key={entry.sha256}><button className={selected?.entry.sha256===entry.sha256?'selected':''} aria-pressed={selected?.entry.sha256===entry.sha256} onClick={()=>onSelect(entry)} disabled={loading||busy||entry.kind==='included'&&!catalogAvailability[entry.catalogId]}><strong>{entry.label}</strong><span>{entry.kind==='included'?'Included':entry.source==='download'?'Downloaded':'Saved'} · {Math.ceil(entry.size/1024)} KiB</span>{entry.kind==='included'&&!catalogAvailability[entry.catalogId]&&<span>Unavailable here</span>}</button></li>)}</ul>
  </section><div className="create-details"><section className="create-preview" aria-label="Recent game preview"><h2>Recent game preview</h2>{'image' in preview?<><img src={preview.image} alt={preview.alt}/><p>{entries.find(row=>row.preview===preview.image)?.label}</p></>:<p>{preview.text}</p>}</section>
   <section className="create-options" aria-label="Room options"><h2>Room options</h2><p>Selected: <strong>{selected?.entry.label??'No game selected'}</strong></p><label>Access <select aria-label="Room access" value={visibility} onChange={event=>setVisibility(event.target.value as Visibility)}><option value="public">Public</option><option value="unlisted">Unlisted</option></select></label><p className="hint">Public appears in rooms; Unlisted uses an invitation.</p><ConnectionPolicyControl compact policy={policy} change={setPolicy}/>
    {selected?.entry.kind==='included'&&!claimFailed&&<p role="status">{includedOffer?`Included offer ready: ${catalogEntry(selected.entry.catalogId).title}. Creating claims its Host place.`:'No Host place is available for this included game. Retry when an offer is available or choose another game.'}</p>}
    {selected?.entry.kind==='saved'&&<p className="hint">Guests download this file while the room is open.</p>}<div className="create-actions"><button onClick={onCreate} disabled={!selected||loading||busy||!includedReady}>Create room</button><button className="local-play" onClick={onLocal} disabled={!selected||loading||busy}>Play locally</button>{(loading||busy)&&<button onClick={onCancel}>Cancel</button>}</div>
    <p role="status" aria-live="polite">{status}</p>{selected?.fresh&&persistenceMessage&&<p role="status">{persistenceMessage}</p>}
   </section></div></div>
 </section>;
}
