import React,{useEffect,useState} from 'react';
import {validRoomPassword,type RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {RoomClient} from './room-client.ts';

export function LobbyOptions({room,onAct}:{room:RoomView;onAct:RoomClient['act']}){
 const [password,setPassword]=useState(''),[passwordMode,setPasswordMode]=useState(false),[busy,setBusy]=useState(false),[feedback,setFeedback]=useState('');
 useEffect(()=>{setPassword('');setPasswordMode(false);},[room.id,room.visibility]);
 const changeAccess=async()=>{setBusy(true);const protect=room.visibility==='public';const ok=await onAct({type:'visibility',roomId:room.id,visibility:protect?'protected':'public',expectedAccessRevision:room.accessRevision,...protect?{password}:{}});setBusy(false);if(ok){setPassword('');setPasswordMode(false);setFeedback(protect?'New visitors need the password.':'Anyone can join this lobby.');}else setFeedback('Could not change who can join. Try again.');};
 return passwordMode?<><strong>Require a password</strong><label>New password<input aria-label="New lobby password" type="password" autoComplete="new-password" value={password} onChange={event=>setPassword(event.target.value)}/><small>Use 8 to 128 characters.</small></label><button disabled={busy||!validRoomPassword(password)} onClick={()=>void changeAccess()}>Save password</button><button className="rc-quiet" onClick={()=>{setPasswordMode(false);setPassword('');}}>Back</button>{feedback&&<span role="status">{feedback}</span>}</>:<><div className="rc-lobby-access"><strong>Who can join?</strong><span>{room.visibility==='public'?'Public':'Password protected'}</span><button disabled={busy} onClick={()=>room.visibility==='public'?setPasswordMode(true):void changeAccess()}>{room.visibility==='public'?'Require password':'Make public'}</button></div>{feedback&&<span role="status">{feedback}</span>}</>;
}
