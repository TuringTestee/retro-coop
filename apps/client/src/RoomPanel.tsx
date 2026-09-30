import {RoomSlots} from './RoomSlots.tsx';
import {catalogAvailability} from 'virtual:catalog';
import {catalogEntry,catalogId,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {catalogFingerprint} from './catalog-fingerprint.ts';
import {downloadCatalogEntry} from './catalog-download.ts';
import {acquireMemberRom,MemberReservationExpiredError} from './member-rom.ts';
import type {LocalPlayer} from './player.ts';
import {VoiceControls} from './VoiceControls.tsx';
import type {VoiceSession,VoiceState} from './voice.ts';
import type {Controls} from './controls.ts';
import {ConnectionPolicyControl} from './ConnectionPolicy.tsx';
import type {ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
import React, {forwardRef, useEffect, useImperativeHandle, useRef, useState} from 'react';
import {ChatPanel} from './ChatPanel.tsx';
import {DirectoryPanel} from './DirectoryPanel.tsx';
import {RoomClient, type RoomState} from './room-client.ts';
import {connectionStatus} from './connection-status.ts';
import {matchesFile,type Fingerprint,type RoomView,type Visibility} from '../../../packages/contracts/src/rooms.ts';
type MemberOperation={roomId:string;membership:string;controller:AbortController;sawLoading:boolean};
type MemberAcquisition={phase:'checking'|'downloading'|'loading'|'loaded'|'failed'|'expired';message:string;notice?:string};
const gameSize=(bytes:number)=>bytes<1_000_000?`${Math.max(1,Math.ceil(bytes/1000))} KB`:`${(bytes/1_000_000).toFixed(1)} MB`;
export type RoomPanelHandle = {voice():VoiceSession|undefined;openPlayers():void;localPlayIntent():void;readyToResume():void;recoverRelease():void;isMember():boolean;exitToDirectory(onExited:()=>void,onStayed?:()=>void):void;syncInvitation(invite:string|null):void;beforeSelection():boolean;approveSelection(fingerprint:Fingerprint,isCurrent:()=>boolean):Promise<boolean>;cancelCreation():void;createCustom(file:File,fingerprint:Fingerprint,visibility:Visibility,current:()=>boolean):Promise<void>;createIncluded(code:string,fingerprint:Fingerprint,visibility:Visibility):Promise<void>};
export const RoomPanel = forwardRef<RoomPanelHandle,{playCards?:React.ReactNode;renderFps?:number;showDiscovery:boolean;releaseInFullscreen:boolean;onChoose():void;onCreate():void;onBrowse():void;onExit():void;onInvitationDismiss():void;onAcquired:(file:File,current:()=>boolean)=>boolean;selectionLoading:boolean;controls:Controls;onVoice:(state:VoiceState|undefined)=>void;fingerprint?:Fingerprint;player:()=>LocalPlayer|null;onNickname:(name:string)=>void;policy:ConnectionPolicy;changePolicy:(policy:ConnectionPolicy)=>void;onConnection:(status:string)=>void;onRoomChange:(room?:RoomView)=>void;onState:(state:RoomState)=>void}>(function RoomPanel({playCards,renderFps,showDiscovery,releaseInFullscreen,onChoose,onCreate,onBrowse,onExit,onInvitationDismiss,onAcquired,selectionLoading,controls,onVoice,fingerprint,player,onNickname,policy,changePolicy,onConnection,onRoomChange,onState},ref) {
 const [state,setState] = useState<RoomState>({status:'No room selected.',busy:false,connected:false});
 const [playersOpen,setPlayersOpen]=useState(false);
 const [staying,setStaying] = useState<string>();
 const [invite,setInvite] = useState(()=>new URLSearchParams(location.hash.slice(1)).get('invite'));
 const [label,setLabel] = useState(''), [nickname,setNickname] = useState(''), [copy,setCopy] = useState('');
 const [confirmLeave,setConfirmLeave]=useState(false),[confirmPublic,setConfirmPublic]=useState(false),[leaveError,setLeaveError]=useState('');
 const client = useRef<RoomClient|null>(null);
 const exitAction=useRef<(()=>void)|undefined>(undefined),stayAction=useRef<(()=>void)|undefined>(undefined),exiting=useRef(false);
 const leaveFocusPending=useRef(false);
 const seenFile = useRef<Fingerprint|undefined>(undefined), sentMemberFile = useRef('');
 const [includedStatus,setIncludedStatus]=useState(''),[includedBusy,setIncludedBusy]=useState<CatalogId>(),[claiming,setClaiming]=useState('');
 const [memberAcquisition,setMemberAcquisition]=useState<MemberAcquisition>();
 const memberOperation=useRef<MemberOperation|undefined>(undefined),memberRoom=useRef<RoomView|undefined>(undefined),memberConnected=useRef(state.connected);memberRoom.current=state.room;memberConnected.current=state.connected;
 const claimGeneration=useRef(0);
 const included=useRef<{id:CatalogId;controller:AbortController;membership:string;candidate:boolean;sawLoading:boolean}|undefined>(undefined),attemptedMember=useRef('');
 const membership=state.room ? `${state.room.id}:${state.room.role}:${state.room.chatMembership}` : '';
 const memberCurrent=(operation:MemberOperation)=>memberOperation.current===operation&&!operation.controller.signal.aborted&&memberConnected.current&&memberRoom.current?.id===operation.roomId&&memberRoom.current?.role==='member'&&memberRoom.current.chatMembership===operation.membership&&!!memberRoom.current.reservationIntent;
 const cancelMember=()=>{const operation=memberOperation.current;memberOperation.current=undefined;operation?.controller.abort();if(operation?.sawLoading)player()?.cancel();setMemberAcquisition(undefined);};
 const startMember=async(room:RoomView)=>{
  if(room.role!=='member'||room.catalogId)return;
  cancelMember();const token=client.current?.memberToken();if(!token){setMemberAcquisition({phase:'failed',message:'Your room session is unavailable. Return to rooms.'});return;}
  const operation:MemberOperation={roomId:room.id,membership:room.chatMembership,controller:new AbortController(),sawLoading:false};memberOperation.current=operation;
  setMemberAcquisition({phase:'checking',message:'Checking saved game…'});
  const current=()=>memberCurrent(operation);
  void client.current?.memberAcquisition(room.id,room.chatMembership,'checking');
  try{
   const result=await acquireMemberRom(room,token,operation.controller.signal,bytes=>{if(current()){setMemberAcquisition({phase:'downloading',message:`Downloading game… ${gameSize(bytes)} / ${gameSize(room.fingerprint.cartridge.bytes)}`});void client.current?.memberAcquisition(room.id,room.chatMembership,'downloading');}},current);
   if(!current())return;
   setMemberAcquisition({phase:'loading',message:'Loading game…',notice:result.notice});
   void client.current?.memberAcquisition(room.id,room.chatMembership,'loading');
   if(!onAcquired(result.file,current))throw Error('The game could not start loading. Retry download.');
   operation.sawLoading=true;
  }catch(error){if(current()){setMemberAcquisition({phase:error instanceof MemberReservationExpiredError?'expired':'failed',message:error instanceof Error?error.message:'Download failed. Retry download.'});void client.current?.memberAcquisition(room.id,room.chatMembership,'failed');}}
 };
 const leaveMember=async()=>{requestExit(onExit);};
 const clearInvitation=()=>{client.current?.clearPreview();history.replaceState(null,'',location.pathname+location.search);setInvite(null);onInvitationDismiss();onBrowse();requestAnimationFrame(()=>document.querySelector<HTMLInputElement>('.directory-panel input')?.focus());};
 const leaveRoom=async(room:RoomView)=>{if(exiting.current)return;exiting.current=true;const left=room.role==='host'?await client.current?.act({type:'close',roomId:room.id})??false:await client.current?.act({type:'leave',intent:room.reservationIntent!})??false;exiting.current=false;if(!left){setConfirmLeave(true);setLeaveError('Could not leave the room. Retry or stay here.');return;}cancelIncluded('');cancelMember();setIncludedStatus('');setConfirmLeave(false);setLeaveError('');const action=exitAction.current;exitAction.current=undefined;stayAction.current=undefined;action?.();};
 const requestExit=(onExited:()=>void,onStayed?:()=>void)=>{const room=memberRoom.current;if(!room){onExited();return;}exitAction.current=onExited;stayAction.current=onStayed;setLeaveError('');if(room.role==='host'||room.established){setConfirmLeave(true);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.room-confirm button')?.focus());}else void leaveRoom(room);};
 const cancelLeave=()=>{exitAction.current=undefined;const stayed=stayAction.current;stayAction.current=undefined;stayed?.();leaveFocusPending.current=true;setConfirmLeave(false);setLeaveError('');};
 useEffect(()=>{if(!confirmLeave&&leaveFocusPending.current){leaveFocusPending.current=false;document.querySelector<HTMLButtonElement>('[data-leave-room]')?.focus();}},[confirmLeave]);
 const cancelPublic=()=>{setConfirmPublic(false);requestAnimationFrame(()=>document.querySelector<HTMLInputElement>('.visibility input')?.focus());};
 useEffect(()=>{setConfirmLeave(false);setConfirmPublic(false);setLeaveError('');},[state.room?.id,state.room?.started]);
 useEffect(()=>{if(!confirmLeave&&!confirmPublic)return;const escape=(event:KeyboardEvent)=>{if(event.key!=='Escape'||event.defaultPrevented||document.querySelector('.tool-page'))return;event.preventDefault();if(confirmLeave)cancelLeave();else cancelPublic();};addEventListener('keydown',escape);return()=>removeEventListener('keydown',escape);},[confirmLeave,confirmPublic]);
 const cancelIncluded=(message='Included loading canceled. Your previous game is preserved.')=>{
  const operation=included.current;included.current=undefined;operation?.controller.abort();
  if(operation?.candidate)player()?.cancel();
  setIncludedBusy(undefined);if(operation)setIncludedStatus(message);
 };
 const startIncluded=async(id:CatalogId)=>{if(state.startingRoom)return;const entry=catalogEntry(id);
  if(!catalogAvailability[id]){setIncludedStatus(`${entry.title} is unavailable here. Leave room and try another game.`);return;}
  if(state.room?.established&&state.room.role==='host'){setIncludedStatus('Leave shared play before starting another game.');return;}
  cancelIncluded('');
  if(fingerprint && player()?.isLoaded(fingerprint) && catalogId(fingerprint)===id){
   setIncludedStatus(`Using ${entry.title} already loaded in this tab without resetting progress.`);
   return;
  }
  client.current?.beginSelection();
  const operation={id,controller:new AbortController(),membership,candidate:false,sawLoading:false};included.current=operation;
  setIncludedBusy(id);setIncludedStatus(`Downloading ${entry.title}…`);if(state.room)void client.current?.memberAcquisition(state.room.id,state.room.chatMembership,'downloading');
  const current=()=>included.current===operation && !operation.controller.signal.aborted;
  const timeout=window.setTimeout(()=>operation.controller.abort(Error('The included download timed out. Retry the download.')),15000);
  try {
   const file=await downloadCatalogEntry(entry,operation.controller.signal,bytes=>{if(current())setIncludedStatus(`Downloading ${entry.title}: ${bytes} / ${entry.bytes} bytes`);});
   if(!current())return;
   operation.candidate=true;setIncludedStatus(`Download verified. Preparing ${entry.title}…`);if(state.room)void client.current?.memberAcquisition(state.room.id,state.room.chatMembership,'loading');if(!onAcquired(file,current))throw Error(`Could not start ${entry.title}. Retry download.`);
  }catch(error){
   if(included.current===operation){if(state.room)void client.current?.memberAcquisition(state.room.id,state.room.chatMembership,'failed');included.current=undefined;setIncludedBusy(undefined);setIncludedStatus(error instanceof Error ? error.message : 'Download failed. Retry the included game.');}
  }finally{clearTimeout(timeout);}
 };
 useEffect(()=>{const operation=included.current;if(operation && operation.membership!==membership)cancelIncluded(state.releaseNotice?'':'The room changed. Included loading canceled; your previous game is preserved.');},[membership]);
 useEffect(()=>{if(state.releaseNotice){cancelIncluded('');setIncludedStatus('');}},[state.releaseNotice]);
 useEffect(()=>{const room=memberRoom.current;if(room?.role==='member'&&!room.catalogId)void startMember(room);else{cancelMember();setMemberAcquisition(undefined);}return()=>{cancelMember();};},[membership]);
 useEffect(()=>{if(!state.connected&&memberOperation.current){cancelMember();setMemberAcquisition({phase:'failed',message:'Room connection lost. Reconnect rooms, then retry download.'});}},[state.connected]);
 useEffect(()=>{const operation=memberOperation.current;if(!operation||!memberCurrent(operation)||memberAcquisition?.phase!=='loading')return;if(selectionLoading){operation.sawLoading=true;return;}if(operation.sawLoading){if(fingerprint&&matchesFile(memberRoom.current!.fingerprint,fingerprint)&&player()?.isLoaded(fingerprint)){setMemberAcquisition({...memberAcquisition,phase:'loaded',message:'Game ready in this browser.'});void client.current?.memberAcquisition(operation.roomId,operation.membership,'loaded');}else{setMemberAcquisition({...memberAcquisition,phase:'failed',message:'The game could not load. Retry download.'});void client.current?.memberAcquisition(operation.roomId,operation.membership,'failed');}}},[selectionLoading,fingerprint,memberAcquisition?.phase]);
 useEffect(()=>{
  const operation=included.current;if(!operation?.candidate)return;
  if(selectionLoading){operation.sawLoading=true;return;}
  if(operation.sawLoading){operation.candidate=false;setIncludedBusy(undefined);setIncludedStatus(fingerprint&&catalogId(fingerprint)===operation.id?'':'The game could not load. Check the player message, then retry.');}
 },[selectionLoading,fingerprint]);
 useEffect(()=>{
  if(!state.room?.catalogId){attemptedMember.current='';return;}
  if(attemptedMember.current===membership)return;attemptedMember.current=membership;
  if(!fingerprint||!player()?.isLoaded(fingerprint)||catalogId(fingerprint)!==state.room.catalogId)void startIncluded(state.room.catalogId);
 },[membership,state.room?.catalogId]);
 const claim=async(code:string,id:CatalogId)=>{
  if(!catalogAvailability[id]){setIncludedStatus(`${catalogEntry(id).title} is unavailable here. Try another room.`);return;}
  const generation=++claimGeneration.current;setClaiming(code);setIncludedStatus('Checking the emulator before claiming Host…');
  try {const identity=await catalogFingerprint(id);if(generation===claimGeneration.current){await client.current?.claimCode(code,identity);setIncludedStatus('');}}
  catch(error){if(generation===claimGeneration.current)setIncludedStatus(error instanceof Error?error.message:'Could not prepare this game. Retry Join as host.');}
  finally {if(generation===claimGeneration.current)setClaiming('');}
 };
 useEffect(()=>()=>{const operation=included.current;included.current=undefined;operation?.controller.abort();if(operation?.candidate)player()?.cancel();},[]);
 useEffect(()=>{const sync=()=>{if(!state.room)setInvite(new URLSearchParams(location.hash.slice(1)).get('invite'));};addEventListener('hashchange',sync);addEventListener('popstate',sync);return()=>{removeEventListener('hashchange',sync);removeEventListener('popstate',sync);};},[state.room?.id]);

 useEffect(()=>{
  const rooms = new RoomClient(setState,policy,player);client.current = rooms;
  void rooms.watchDirectory();
  if(invite) void rooms.preview(invite);
  return ()=>{rooms.dispose();client.current = null;};
 },[invite]);
 useEffect(()=>{void client.current?.setPolicy(policy);},[policy]);
 useEffect(()=>{client.current?.voice.configureControls(controls);},[controls]);
 useEffect(()=>{onVoice(state.voice);},[state.voice,onVoice]);
 useEffect(()=>{onConnection(connectionStatus(state));},[state.connection,state.room?.peers,onConnection]);
 useEffect(()=>{if(state.session) {onNickname(state.session.nickname);setNickname(state.session.nickname);}},[state.session,onNickname]);
 useEffect(()=>{if(state.room) setLabel(state.room.label);},[state.room?.label]);
 useEffect(()=>{if(invite&&!state.room&&state.preview&&'openSlots' in state.preview&&state.preview.openSlots>0&&document.activeElement===document.body)requestAnimationFrame(()=>document.querySelector<HTMLSelectElement>('.room-panel.invitation .connection-policy select')?.focus());},[invite,state.room?.id,state.preview]);
 useEffect(()=>{onRoomChange(state.room);},[state.room,onRoomChange]);
 useEffect(()=>{onState(state);},[state,onState]);
 const recoverRelease=()=>{if(player()?.isLoaded()){player()?.allowLocalPlay();player()?.resume();}else onBrowse();client.current?.dismissRelease();};
 useImperativeHandle(ref,()=>({voice:()=>client.current?.voice,openPlayers(){setPlayersOpen(value=>!value);},localPlayIntent(){client.current?.localPlayIntent();},readyToResume(){client.current?.readyToResume();},recoverRelease,isMember(){return client.current?.isMember()??false;},exitToDirectory(onExited,onStayed){requestExit(onExited,onStayed);},syncInvitation(value){setInvite(value);},
  beforeSelection() {
   if(state.startingRoom||state.room?.role==='member'&&!state.room.catalogId)return false;
   cancelIncluded();client.current?.beginSelection();return true;
 },approveSelection(fingerprint,isCurrent){if(state.room?.role==='member'&&!state.room.catalogId){const operation=memberOperation.current;return Promise.resolve(!!operation&&memberCurrent(operation)&&isCurrent()&&matchesFile(state.room.fingerprint,fingerprint));}return client.current?.approveSelection(fingerprint,isCurrent) ?? Promise.resolve(isCurrent());},cancelCreation(){cancelIncluded();client.current?.cancelPending();},
 createCustom(file,fingerprint,visibility,current){return client.current?.host(file,fingerprint,visibility,current)??Promise.resolve();},
 createIncluded(code,fingerprint,visibility){return client.current?.claimCode(code,fingerprint,visibility)??Promise.resolve();}
 }),[state.room]);
 useEffect(()=>{
  if(!fingerprint || seenFile.current === fingerprint) return;
  seenFile.current = fingerprint;client.current?.selectedGame(fingerprint);
  // Loading a game is local. Only the Create room action publishes a room.
 },[fingerprint,invite,state.room?.role]);
 useEffect(()=>{
  if(!fingerprint || state.room?.role !== 'member') {sentMemberFile.current = '';return;}
  const key = state.room.id+fingerprint.romSha256+fingerprint.coreSha256;
  if(sentMemberFile.current !== key) {sentMemberFile.current = key;void client.current?.act({type:'file',fingerprint});}
 },[fingerprint,state.room?.id,state.room?.role]);
 const room = state.room;
 useEffect(()=>{setPlayersOpen(false);},[room?.id]);
 const inviteUrl = room ? `${location.origin}/#invite=${room.invite}`:'';
 const selfSlot=room?.slots.find(slot=>slot.member?.id===room.chatMembership);
 const selfReady=!!room?.game.ready.includes(room.chatMembership);
 const waitingMembers=room?.slots.filter(slot=>slot.member&&!room.game.ready.includes(slot.member.id)).map(slot=>slot.member!.nickname)??[];
 const gameplayPeers=room?.peers.filter(peer=>peer.gameplay&&(room.role!=='host'||room.slots.some(slot=>slot.role!=='observer'&&slot.member?.id===peer.member)))??[];
 const peersReady=gameplayPeers.every(peer=>peer.status==='connected');
 const allPeersReady=room?.peers.every(peer=>peer.status==='connected')??false;
 const directShared=room?.peers.every(peer=>peer.status==='connected')&&room?.started==='shared'&&state.connected&&peersReady&&state.connection?.route==='direct';
 const connectionNode=!directShared&&(room?.peers.some(peer=>peer.epoch)||!state.connected)?<p role="status" className={room?.started==='shared'&&state.connection?.route==='relay'&&peersReady?'relay-notice':undefined} data-testid="connection-status">{connectionStatus(state)}</p>:null;
 const leaveControl=room&&(confirmLeave||!(room.role==='member'&&!room.catalogId&&['checking','downloading','loading','expired'].includes(memberAcquisition?.phase??'')))&&(confirmLeave?<div className="room-confirm" role="group" aria-label="Confirm leave"><p>{room.role==='host'?'Close this room for everyone?':'Leave this room?'}</p><button disabled={state.busy||exiting.current} onClick={()=>void leaveRoom(room)}>Confirm leave</button><button onClick={cancelLeave}>Stay in room</button>{leaveError&&<p role="alert">{leaveError}</p>}</div>:<button data-leave-room onClick={()=>requestExit(onExit)}>Leave room</button>);
 return <>{state.releaseNotice&&!releaseInFullscreen&&<div className="release-notice" role="alert"><p>{state.releaseNotice}</p><button onClick={recoverRelease}>{player()?.isLoaded()?'Resume local game':'View rooms'}</button></div>}
 {showDiscovery&&<><div className="discovery-notices">
 {claiming&&<p className="catalog-status" role="status">Checking this room… <button onClick={()=>{++claimGeneration.current;setClaiming('');setIncludedStatus('');client.current?.cancelPending();}}>Cancel</button></p>}
 {includedStatus&&!room&&<p className="catalog-status" role="status" data-testid="included-status">{includedStatus}</p>}
 {!room&&state.status!=='No room selected.'&&state.status!==state.directoryError&&<p className="catalog-status" role="status" data-testid="room-notice">{state.status} {state.busy&&<button onClick={()=>client.current?.cancelPending()}>Cancel</button>}</p>}
 </div>
 <DirectoryPanel connection={<ConnectionPolicyControl compact policy={policy} change={changePolicy}/>} state={{...state,busy:state.busy||!!claiming}} onCreate={onCreate} onJoin={code=>void client.current?.joinCode(code)} onClaim={(code,id)=>void claim(code,id)} onRetry={()=>void client.current?.watchDirectory()}/></>}
 {(room||invite)&& <section id="room-session" className={`room-panel${invite&&!room?' invitation':''}${room&&!fingerprint?' pending-room':''}`} aria-labelledby="room-heading">
  {room?.started==='shared'&&connectionNode}
  <h2 id="room-heading">{room ? room.label : invite ? 'Room invitation':'Play with a friend'}</h2>
  {room?.started==='shared'&&leaveControl}
  {playCards}
  {invite&&!room&&state.preview&&<p>{state.preview.label} · {state.preview.host} · {'openSlots' in state.preview?`${state.preview.openSlots} open places`:'No open places'}. Join prepares the game for you.</p>}
  {invite&&!room&&<div className="invite-action">{state.preview&&'openSlots' in state.preview&&state.preview.openSlots>0&&<><ConnectionPolicyControl compact policy={policy} change={changePolicy}/><button disabled={state.busy} onClick={()=>void client.current?.join(invite)}>Join room</button></>}{!state.busy&&!state.preview&&<button onClick={()=>void client.current?.preview(invite)}>Retry invitation</button>}<button onClick={clearInvitation}>View public rooms</button></div>}
  {room?.role==='member'&&!room.catalogId&&memberAcquisition&&(!room.started||memberAcquisition.phase!=='loaded')&&<div className="member-acquisition" role="status" aria-live="polite"><p>{memberAcquisition.message}</p>{memberAcquisition.notice&&<p>{memberAcquisition.notice}</p>}{['checking','downloading','loading'].includes(memberAcquisition.phase)&&<button onClick={()=>void leaveMember()}>Cancel preparation</button>}{memberAcquisition.phase==='failed'&&<button onClick={()=>void startMember(room)}>Retry download</button>}{memberAcquisition.phase==='expired'&&<button onClick={()=>void leaveMember()}>Return to rooms</button>}</div>}
  {room&&selectionLoading&&!includedBusy&&!(room.role==='member'&&!room.catalogId)&&<p role="status">Checking the selected file… <button onClick={()=>{player()?.cancel();client.current?.beginSelection();}}>Cancel loading</button></p>}
  {room&&(!room.started||playersOpen)&&<><RoomSlots room={room} connected={state.connected} act={command=>client.current!.act(command)}/>{room.started&&<button onClick={()=>setPlayersOpen(false)}>Close players</button>}</>}
  {room&&!room.started&&<div className="room-start" role="group" aria-label="Your readiness">
   {!state.connected?<p role="status">Room connection lost. Reconnect to get ready.</p>:selfReady?<button onClick={()=>client.current?.cancelSynchronization()}>Not ready</button>:<button disabled={!room.matches||selfSlot?.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading||!allPeersReady||!!state.gameplay?.busy} onClick={()=>client.current?.prepareMember()}>Ready</button>}
   {state.gameplay?.busy&&<p role="status">{state.gameplay.status}</p>}
  </div>}
  {room?.started&&room.game.status==='playing'&&selfSlot?.role!=='observer'&&!room.game.controllers.owners.includes(room.chatMembership)&&<div className="room-start"><button disabled={!state.connected||!room.matches||selfSlot?.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading||!!state.gameplay?.busy} onClick={()=>client.current?.prepareMember()}>Prepare to play</button></div>}
  {room?.started&&room.game.status==='playing'&&selfSlot?.role==='observer'&&!state.gameplay?.observing&&!state.gameplay?.synchronizing&&<div className="room-start"><button disabled={!state.connected||!room.matches||selfSlot.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading} onClick={()=>client.current?.prepareMember()}>Observe game</button></div>}
  {room?.started!=='shared'&&connectionNode}
  {invite&&!room&&<p role="status" aria-live="polite" data-testid="room-status">{state.status}</p>}
  {room?.role==='host'&&room.openSlots>0&&<div className="room-invite"><button onClick={()=>{void navigator.clipboard?.writeText(inviteUrl).then(()=>setCopy('Invitation copied.')).catch(()=>setCopy('Copy unavailable. Select the invitation below.'));if(!navigator.clipboard)setCopy('Copy unavailable. Select the invitation below.');}}>Copy invite</button>{copy&&<span className="hint" role="status">{copy}</span>}{copy.startsWith('Copy unavailable')&&<input aria-label="Room invitation" readOnly value={inviteUrl} onFocus={event=>event.currentTarget.select()}/>}</div>}
  {room?.role==='host'&&!room.started&&!confirmLeave&&<div className="room-start"><button disabled={!room.matches||selfSlot?.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading||!!room.game.startRequested||!allPeersReady||waitingMembers.length>0} onClick={()=>{if(fingerprint)void client.current?.startRoom(fingerprint);}}>Start game</button><p role="status">{room.game.startRequested?'Starting…':waitingMembers.length?`Waiting for ${waitingMembers.join(', ')}.`:''}</p>{fingerprint&&!matchesFile(room.fingerprint,fingerprint)&&<p role="status">This file does not match the room. <button onClick={onChoose}>Choose matching NES file</button></p>}</div>}
  {room&&includedStatus&&<p role="status" data-testid="included-status">{includedStatus} {includedBusy&&<button onClick={()=>cancelIncluded()}>Cancel loading</button>}{room.catalogId&&catalogAvailability[room.catalogId]&&!includedBusy&&(!fingerprint||!matchesFile(room.fingerprint,fingerprint)||!player()?.isLoaded(fingerprint))&&<button onClick={()=>void startIncluded(room.catalogId!)}>Retry download</button>}</p>}
  {room?.started!=='shared'&&leaveControl}
  {room&&!room.started&&state.chat&&<details className="chat-disclosure"><summary>Chat</summary><ChatPanel state={state.chat} connected={state.connected} onDraft={text=>client.current?.chatDraft(text)} onSend={()=>void client.current?.sendChat()} onDiscard={()=>client.current?.discardChat()}/></details>}
  {(room||!invite)&&<details name="room-tools" className="session-settings"><summary>Connection and session settings</summary>
  <ConnectionPolicyControl policy={policy} change={changePolicy}/>
  <p className="hint">Connection options for this room.</p>
  {room?.peers.map(peer=><div key={peer.pairId}><p>{room.slots.find(slot=>slot.member?.id===peer.member)?.member?.nickname??'Member'} · {peer.status}</p>{peer.epoch&&<button onClick={()=>void client.current?.retryPeer(peer.pairId)}>Retry connection</button>}{peer.epoch&&['relay_unavailable','relay_capacity','failed'].includes(peer.status)&&<><button onClick={()=>setStaying(peer.pairId)}>Stay in room</button>{staying===peer.pairId&&<p role="status">You stayed in the room. Retry the connection when ready.</p>}</>}</div>)}
  <p role="status" aria-live="polite" data-testid="room-status">{state.status}</p>
  {state.retryAfterMs && <p>Wait at least {Math.ceil(state.retryAfterMs/1000)} seconds before retrying.</p>}
  {room && <div data-testid="room-view" data-invite={room.invite}>
   {room.reservationUntil && <p>Reservation expires at {new Date(room.reservationUntil).toLocaleTimeString()}. {room.matches ? 'Game verified. Preparing the shared-play connection.' : 'Your game is still being acquired or loaded.'}</p>}
   {room.hostReconnectUntil && <p>Host disconnected. Return before {new Date(room.hostReconnectUntil).toLocaleTimeString()} to keep this room.</p>}
   {room.role === 'host' ? <details><summary>Session settings</summary>
    <label>Room name <input maxLength={80} value={label} onChange={event=>setLabel(event.target.value)}/></label><button disabled={!label.trim()} onClick={()=>void client.current?.act({type:'rename',roomId:room.id,label})}>Save room name</button>
    <label className="visibility"><input type="checkbox" checked={room.visibility === 'unlisted'} onChange={event=>{if(event.target.checked)void client.current?.act({type:'visibility',roomId:room.id,visibility:'unlisted'});else{setConfirmPublic(true);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.visibility-confirm button')?.focus());}}}/> Unlisted · invitation only</label>
    {confirmPublic&&<div className="room-confirm visibility-confirm" role="group" aria-label="Confirm public room"><p>Make this room public? Its room name and host nickname will appear in Public rooms.</p><button disabled={state.busy} onClick={async()=>{if(await client.current?.act({type:'visibility',roomId:room.id,visibility:'public'}))setConfirmPublic(false);}}>Make public</button><button onClick={cancelPublic}>Keep unlisted</button></div>}
   </details> : null}
  </div>}
  </details>}
  {room&&!!room.started && <section aria-label="Shared gameplay">{(room.game.status!=='playing'||state.gameplay?.synchronizing)&&<p role="status" data-testid="game-status">{state.gameplay?.synchronizing?state.gameplay.status:room.game?.reason??state.gameplay?.status}</p>}
   {state.gameplay?.synchronizing&&<button onClick={()=>client.current?.cancelSynchronization()}>Cancel synchronization</button>}
   {room.established&&['paused','failed','resume_ready'].includes(room.game.status)&&<>{(selfSlot?.role!=='observer'||room.role==='host')&&<button disabled={!!room.game.pending||!!state.gameplay?.synchronizing} onClick={()=>client.current?.readyToResume()}>Ready to resume</button>}{room.role==='host'&&<button disabled={!!room.game.pending||room.game.status!=='resume_ready'} onClick={()=>client.current?.resumeTogether()}>Resume together</button>}<p role="status">{room.game.status==='resume_ready'?`Assigned players are ready. Waiting for ${room.host} to resume.`:'Waiting for the assigned players to prepare.'}</p></>}
   {room.started&&!room.established&&(room.role==='host'||selfSlot?.role!=='observer')&&['failed','paused'].includes(room.game.status)&&<button onClick={()=>client.current?.retryGame()}>Retry shared play</button>}
  </section>}
  {room&&room.started&&state.chat&&<details className="chat-disclosure"><summary>Room chat</summary><ChatPanel state={state.chat} connected={state.connected} onDraft={text=>client.current?.chatDraft(text)} onSend={()=>void client.current?.sendChat()} onDiscard={()=>client.current?.discardChat()}/></details>}
  {room&&!room.started&&<details name="room-tools" className="voice-disclosure"><summary>Voice</summary><VoiceControls state={state.voice} voice={client.current?.voice}/></details>}
  <div className="controls">
   {state.busy && !state.startingRoom && !state.uploading && <button onClick={()=>client.current?.cancelPending()}>Cancel pending room action</button>}
   {!state.connected && (state.room || state.admissionBlocked || /unavailable|lost|disconnected/.test(state.status)) && <button onClick={()=>void client.current?.reconnect()}>Reconnect rooms</button>}
  </div>
  {state.session && <details name="room-tools"><summary>Nickname settings</summary><p className="hint">Temporary name for this browser tab. It is not an account.</p><label>Nickname <input maxLength={32} value={nickname} onChange={event=>setNickname(event.target.value)}/></label><button disabled={!nickname.trim()} onClick={()=>void client.current?.act({type:'nickname',nickname})}>Save nickname</button></details>}
  {state.needsNewGuest && <button onClick={()=>client.current?.newGuest()}>Start a new guest session</button>}
 </section>}</>;
});
