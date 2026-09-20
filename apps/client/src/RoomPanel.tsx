import React, {forwardRef, useEffect, useImperativeHandle, useRef, useState} from 'react';
import {RoomClient, type RoomState} from './room-client.ts';
import type {Fingerprint,Visibility} from '../../../packages/contracts/src/rooms.ts';
export type RoomPanelHandle = {beforeSelection():boolean;cancelCreation():void};
export const RoomPanel = forwardRef<RoomPanelHandle,{fingerprint?:Fingerprint;onNickname:(name:string)=>void}>(function RoomPanel({fingerprint,onNickname},ref) {
 const [state,setState] = useState<RoomState>({status:'Choose a file to create a room. Your file stays here.',busy:false,connected:false});
 const [visibility,setVisibility] = useState<Visibility>('public');
 const [invite] = useState(()=>new URLSearchParams(location.hash.slice(1)).get('invite'));
 const [label,setLabel] = useState(''), [nickname,setNickname] = useState(''), [copy,setCopy] = useState('');
 const client = useRef<RoomClient|null>(null), selectedVisibility = useRef<Visibility>('public');
 const seenFile = useRef<Fingerprint|undefined>(undefined), sentGuestFile = useRef('');
 useEffect(()=>{
  const rooms = new RoomClient(setState);client.current = rooms;
  if(invite) void rooms.preview(invite);
  return ()=>{rooms.dispose();client.current = null;};
 },[invite]);
 useEffect(()=>{if(state.session) {onNickname(state.session.nickname);setNickname(state.session.nickname);}},[state.session,onNickname]);
 useEffect(()=>{if(state.room) setLabel(state.room.label);},[state.room?.label]);
 useImperativeHandle(ref,()=>({
  beforeSelection() {
   if(state.room?.role === 'host' && !window.confirm('Choosing a different valid game closes this room and releases its guest. Continue?')) return false;
   client.current?.cancelCreation();selectedVisibility.current = visibility;return true;
  },cancelCreation(){client.current?.cancelCreation();}
 }),[visibility,state.room]);
 useEffect(()=>{
  if(!fingerprint || seenFile.current === fingerprint) return;
  seenFile.current = fingerprint;
  if(state.room?.role === 'guest' || invite) return;
  void client.current?.host(fingerprint,selectedVisibility.current);
 },[fingerprint,invite,state.room?.role]);
 useEffect(()=>{
  if(!fingerprint || state.room?.role !== 'guest') {sentGuestFile.current = '';return;}
  const key = state.room.id+fingerprint.romSha256+fingerprint.coreSha256;
  if(sentGuestFile.current !== key) {sentGuestFile.current = key;void client.current?.act({type:'file',fingerprint});}
 },[fingerprint,state.room?.id,state.room?.role]);
 const room = state.room;
 const inviteUrl = room ? `${location.origin}${location.pathname}#invite=${room.invite}`:'';
 return <section className="room-panel" aria-labelledby="room-heading">
  <h2 id="room-heading">{room ? room.label : invite ? 'Room invitation':'Play with a friend'}</h2>
  {!room && !invite && <><label className="visibility"><input type="checkbox" checked={visibility === 'unlisted'} onChange={event=>setVisibility(event.target.checked ? 'unlisted':'public')}/> Unlisted · invitation only</label><p>{visibility === 'public' ? 'Creates a public room; your file stays here.' : 'Creates an unlisted room; your file stays here.'} Players need their own matching file.</p></>}
  {invite && !room && state.preview && <p>{state.preview.label} · {state.preview.host} · {state.preview.occupancy}/2 places · {state.preview.status}</p>}
  <p className="hint">This build supports rooms and reservations. Shared gameplay, peer connections and the public directory are coming next.</p>
  <p role="status" aria-live="polite" data-testid="room-status">{state.status}</p>
  {state.retryAfterMs && <p>Wait at least {Math.ceil(state.retryAfterMs/1000)} seconds before retrying.</p>}
  {room && <div data-testid="room-view">
   <p><strong>{room.visibility === 'public' ? `Public · ${room.code}`:'Unlisted · invite only'}</strong> · {room.occupancy}/2 places · {room.status}</p>
   <p>You are {room.role === 'host' ? 'the host, Player 1':'Player 2 (reserved)'}. {room.guest ? `${room.guest} has the reserved guest place.`:'Waiting for a friend; local play can continue.'}</p>
   {room.reservationUntil && <p>Reservation expires at {new Date(room.reservationUntil).toLocaleTimeString()}. {room.matches ? 'Files match. Waiting for the future shared-play connection.' : 'The guest needs the exact matching file and emulator build; header differences also matter.'}</p>}
   {room.hostReconnectUntil && <p>Host disconnected. Return before {new Date(room.hostReconnectUntil).toLocaleTimeString()} to keep this room.</p>}
   <label>Invitation <input aria-label="Room invitation" readOnly value={inviteUrl} onFocus={event=>event.currentTarget.select()}/></label>
   <button onClick={()=>{void navigator.clipboard?.writeText(inviteUrl).then(()=>setCopy('Invitation copied.')).catch(()=>setCopy('Select the invitation text and copy it.'));if(!navigator.clipboard) setCopy('Select the invitation text and copy it.');}}>Copy invite</button><span className="hint"> {copy}</span>
   {room.role === 'host' ? <details><summary>Session settings</summary>
    <label>Room name <input maxLength={80} value={label} onChange={event=>setLabel(event.target.value)}/></label><button disabled={!label.trim()} onClick={()=>void client.current?.act({type:'rename',label})}>Save room name</button>
    <label className="visibility"><input type="checkbox" checked={room.visibility === 'unlisted'} onChange={event=>{const visibility = event.target.checked ? 'unlisted':'public';if(visibility === 'public' && !window.confirm('Make this room public? Its room name and host nickname will be discoverable.')) return;void client.current?.act({type:'visibility',visibility});}}/> Unlisted · invitation only</label>
    {room.guest && <button onClick={()=>{if(window.confirm(`Remove ${room.guest}? Their reservation and reconnect permission will be revoked.`)) void client.current?.act({type:'kick'});}}>Remove guest</button>}
    <button onClick={()=>{if(window.confirm('Close this room for both players? Your local game stays available.')) void client.current?.act({type:'close'});}}>Close room</button>
   </details> : <button onClick={()=>void client.current?.act({type:'leave'})}>Cancel join</button>}
  </div>}
  <div className="controls">
   {state.busy && <button onClick={()=>client.current?.cancelPending()}>Cancel pending room action</button>}
   {!room && invite && <button disabled={state.busy} onClick={()=>void client.current?.join(invite)}>Retry join / Join</button>}
   {!room && !invite && fingerprint && <button disabled={state.busy} onClick={()=>void client.current?.host(fingerprint,visibility)}>Retry room creation</button>}
   {!state.connected && (state.room || /unavailable|lost|disconnected/.test(state.status)) && <button onClick={()=>void client.current?.reconnect()}>Reconnect rooms</button>}
  </div>
  {state.session && <details><summary>Guest settings</summary><p className="hint">Temporary name for this browser tab. It is not an account.</p><label>Nickname <input maxLength={32} value={nickname} onChange={event=>setNickname(event.target.value)}/></label><button disabled={!nickname.trim()} onClick={()=>void client.current?.act({type:'nickname',nickname})}>Save nickname</button></details>}
  {state.needsNewGuest && <button onClick={()=>client.current?.newGuest()}>Start a new guest session</button>}
 </section>;
});
