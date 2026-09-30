import {RoomSlots} from './RoomSlots.tsx';
import {ScrollRegion} from './ScrollRegion.tsx';
import {catalogAvailability} from 'virtual:catalog';
import {catalogEntry,catalogId,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {catalogFingerprint} from './catalog-fingerprint.ts';
import {downloadCatalogEntry} from './catalog-download.ts';
import {acquireMemberRom,MemberReservationExpiredError} from './member-rom.ts';
import type {LocalPlayer} from './player.ts';
import {VoiceControls} from './VoiceControls.tsx';
import type {VoiceSession,VoiceState} from './voice.ts';
import type {Controls} from './controls.ts';
import React, {forwardRef, useEffect, useImperativeHandle, useRef, useState} from 'react';
import {ChatPanel} from './ChatPanel.tsx';
import {DirectoryPanel} from './DirectoryPanel.tsx';
import {RoomClient, type RoomState} from './room-client.ts';
import {connectionStatus} from './connection-status.ts';
import {roomAdmissionMessage} from './room-admission-message.ts';
import {gameSize,roomDownloadLabel} from './room-download.ts';
import {matchesFile,validRoomPassword,type Fingerprint,type RoomView,type NewVisibility} from '../../../packages/contracts/src/rooms.ts';
type MemberOperation={roomId:string;membership:string;controller:AbortController;sawLoading:boolean};
type MemberAcquisition={phase:'checking'|'downloading'|'loading'|'loaded'|'failed'|'expired';message:string;notice?:string};
export type RoomPanelHandle = {voice():VoiceSession|undefined;setNickname(name:string):void;openPlayers():void;localPlayIntent():void;readyToResume():void;recoverRelease():void;isMember():boolean;exitToDirectory(onExited:()=>void,onStayed?:()=>void):void;syncInvitation(invite:string|null):void;beforeSelection():boolean;approveSelection(fingerprint:Fingerprint,isCurrent:()=>boolean):Promise<boolean>;cancelCreation():void;createCustom(file:File,fingerprint:Fingerprint,visibility:NewVisibility,password:string|undefined,current:()=>boolean):Promise<void>;createIncluded(code:string,fingerprint:Fingerprint,visibility:NewVisibility,password?:string):Promise<void>};
export const RoomPanel = forwardRef<RoomPanelHandle,{playCards?:React.ReactNode;showDiscovery:boolean;releaseInFullscreen:boolean;onChoose():void;onCreate():void;onBrowse():void;onExit():void;onInvitationDismiss():void;onAcquired:(file:File,current:()=>boolean)=>boolean;selectionLoading:boolean;controls:Controls;onVoice:(state:VoiceState|undefined)=>void;fingerprint?:Fingerprint;player:()=>LocalPlayer|null;onNickname:(name:string)=>void;onConnection:(status:string)=>void;onRoomChange:(room?:RoomView)=>void;onState:(state:RoomState)=>void}>(function RoomPanel({playCards,showDiscovery,releaseInFullscreen,onChoose,onCreate,onBrowse,onExit,onInvitationDismiss,onAcquired,selectionLoading,controls,onVoice,fingerprint,player,onNickname,onConnection,onRoomChange,onState},ref) {
 const [state,setState] = useState<RoomState>({status:'No room selected.',busy:false,connected:false});
 const [playersOpen,setPlayersOpen]=useState(false);
 const [invite,setInvite] = useState(()=>new URLSearchParams(location.hash.slice(1)).get('invite'));
 const [label,setLabel] = useState(''), [copy,setCopy] = useState('');
 const [joinPassword,setJoinPassword]=useState(''),[showJoinPassword,setShowJoinPassword]=useState(false),[invitePasswordOpen,setInvitePasswordOpen]=useState(false),[accessPassword,setAccessPassword]=useState(''),[showAccessPassword,setShowAccessPassword]=useState(false),[editingAccess,setEditingAccess]=useState(false);
 const [confirmLeave,setConfirmLeave]=useState(false),[confirmPublic,setConfirmPublic]=useState(false),[leaveError,setLeaveError]=useState('');
 const client = useRef<RoomClient|null>(null),invitePasswordDialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{if(invitePasswordOpen&&invitePasswordDialog.current&&!invitePasswordDialog.current.open)invitePasswordDialog.current.showModal();},[invitePasswordOpen]);
 useEffect(()=>{if(invitePasswordOpen&&!state.preview)setInvitePasswordOpen(false);},[invitePasswordOpen,state.preview]);
 const exitAction=useRef<(()=>void)|undefined>(undefined),stayAction=useRef<(()=>void)|undefined>(undefined),exiting=useRef(false);
 const leaveFocusPending=useRef(false);
 const publicFocusPending=useRef(false);
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
 const leaveRoom=async(room:RoomView)=>{if(exiting.current)return;exiting.current=true;const left=room.role==='host'?await client.current?.act({type:'close',roomId:room.id})??false:await client.current?.act({type:'leave',intent:room.reservationIntent!})??false;exiting.current=false;if(!left){setConfirmLeave(true);setLeaveError('Could not leave. Retry or stay.');return;}cancelIncluded('');cancelMember();setIncludedStatus('');setConfirmLeave(false);setLeaveError('');const action=exitAction.current;exitAction.current=undefined;action?.();};
 const requestExit=(onExited:()=>void,onStayed?:()=>void)=>{const room=memberRoom.current;if(!room){onExited();return;}exitAction.current=onExited;stayAction.current=onStayed;setLeaveError('');if(room.role==='host'||room.established){setConfirmLeave(true);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.room-confirm button')?.focus());}else void leaveRoom(room);};
 const cancelLeave=()=>{exitAction.current=undefined;const stayed=stayAction.current;stayAction.current=undefined;stayed?.();leaveFocusPending.current=true;setConfirmLeave(false);setLeaveError('');};
 useEffect(()=>{if(!confirmLeave&&leaveFocusPending.current){leaveFocusPending.current=false;document.querySelector<HTMLButtonElement>('[data-leave-room]')?.focus();}},[confirmLeave]);
 const cancelPublic=()=>{publicFocusPending.current=true;setConfirmPublic(false);};
 useEffect(()=>{if(!confirmPublic&&publicFocusPending.current){publicFocusPending.current=false;document.querySelector<HTMLButtonElement>('[data-make-public]')?.focus();}},[confirmPublic]);
 useEffect(()=>{setConfirmLeave(false);setConfirmPublic(false);setLeaveError('');},[state.room?.id,state.room?.started]);
 useEffect(()=>{if(state.room){setJoinPassword('');setShowJoinPassword(false);setAccessPassword('');setEditingAccess(false);}},[state.room?.id]);
 useEffect(()=>{setJoinPassword('');setShowJoinPassword(false);setInvitePasswordOpen(false);},[invite]);
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
  const rooms = new RoomClient(setState,player);client.current = rooms;
  void rooms.watchDirectory();
  if(invite) void rooms.preview(invite);
  return ()=>{rooms.dispose();client.current = null;};
 },[invite]);
 useEffect(()=>{client.current?.voice.configureControls(controls);},[controls]);
 useEffect(()=>{onVoice(state.voice);},[state.voice,onVoice]);
 useEffect(()=>{onConnection(connectionStatus(state));},[state.connection,state.room?.peers,onConnection]);
 useEffect(()=>{if(state.session) onNickname(state.session.nickname);},[state.session,onNickname]);
 useEffect(()=>{if(state.room) setLabel(state.room.label);},[state.room?.label]);
 useEffect(()=>{if(invite&&!state.room&&state.preview&&'openSlots' in state.preview&&state.preview.openSlots>0&&document.activeElement===document.body)requestAnimationFrame(()=>document.querySelector<HTMLElement>('.invite-action input, .invite-action button')?.focus());},[invite,state.room?.id,state.preview]);
 useEffect(()=>{onRoomChange(state.room);},[state.room,onRoomChange]);
 useEffect(()=>{onState(state);},[state,onState]);
 const recoverRelease=()=>{if(player()?.isLoaded()){player()?.allowLocalPlay();player()?.resume();}else onBrowse();client.current?.dismissRelease();};
 useImperativeHandle(ref,()=>({voice:()=>client.current?.voice,setNickname(name){void client.current?.act({type:'nickname',nickname:name});},openPlayers(){setPlayersOpen(value=>!value);},localPlayIntent(){client.current?.localPlayIntent();},readyToResume(){client.current?.readyToResume();},recoverRelease,isMember(){return client.current?.isMember()??false;},exitToDirectory(onExited,onStayed){requestExit(onExited,onStayed);},syncInvitation(value){setInvite(value);},
  beforeSelection() {
   if(state.startingRoom||state.room?.role==='member'&&!state.room.catalogId)return false;
   cancelIncluded();client.current?.beginSelection();return true;
 },approveSelection(fingerprint,isCurrent){if(state.room?.role==='member'&&!state.room.catalogId){const operation=memberOperation.current;return Promise.resolve(!!operation&&memberCurrent(operation)&&isCurrent()&&matchesFile(state.room.fingerprint,fingerprint));}return client.current?.approveSelection(fingerprint,isCurrent) ?? Promise.resolve(isCurrent());},cancelCreation(){cancelIncluded();client.current?.cancelPending();},
 createCustom(file,fingerprint,visibility,password,current){return client.current?.host(file,fingerprint,visibility,password,current)??Promise.resolve();},
 createIncluded(code,fingerprint,visibility,password){return client.current?.claimCode(code,fingerprint,visibility,password)??Promise.resolve();}
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
 const inviteDownload=state.preview?roomDownloadLabel(state.preview):'';
 const selfSlot=room?.slots.find(slot=>slot.member?.id===room.chatMembership);
 const selfReady=!!room?.game.ready.includes(room.chatMembership);
 const waitingMembers=room?.slots.filter(slot=>slot.member&&!room.game.ready.includes(slot.member.id)).map(slot=>slot.member!.nickname)??[];
 const gameplayPeers=room?.peers.filter(peer=>peer.gameplay&&(room.role!=='host'||room.slots.some(slot=>slot.role!=='observer'&&slot.member?.id===peer.member)))??[];
 const peersReady=gameplayPeers.every(peer=>peer.status==='connected');
 const allPeersReady=room?.peers.every(peer=>peer.status==='connected')??false;
 const hostPeerReady=room?.peers.some(peer=>peer.member===room.hostMembership&&peer.status==='connected')??false;
 const failedPeers=room?.peers.filter(peer=>peer.epoch&&['relay_unavailable','relay_capacity','failed'].includes(peer.status))??[];
 const connectionNode=room?.started==='shared'&&!state.connected?<p role="status" data-testid="connection-status">Room service disconnected. Reconnect to check membership.</p>:null;
 const connectionIssue=!state.connected||failedPeers.length>0;
 const memberAcquisitionVisible=!!memberAcquisition&&(memberAcquisition.phase!=='loaded'||!room?.started&&!!memberAcquisition.notice);
 const fileSelectionVisible=!!room&&!room.started&&selectionLoading&&!includedBusy&&!(room.role==='member'&&!room.catalogId);
 const roomStatusImportant=!!state.retryAfterMs||/failed|could not|cannot|lost|unavailable|expired|changed|closed|denied|leave this room/i.test(state.status);
 const gameplayRecovery=!!state.gameplay?.status&&/cancel|fail|could not|cannot|timed out|unavailable|denied/i.test(state.gameplay.status);
 const gameMessage=state.gameplay?.synchronizing||gameplayRecovery?state.gameplay?.status:room?.game.status==='resume_ready'?(room.role==='host'?'Players ready to resume.':'Waiting for host to resume.'):room?.game.status==='paused'&&room.established?'Waiting for the assigned players to prepare.':room?.game.reason??state.gameplay?.status;
 const leaveControl=room&&(confirmLeave||!(room.role==='member'&&!room.catalogId&&['checking','downloading','loading','expired'].includes(memberAcquisition?.phase??'')))&&(confirmLeave?<div className="room-confirm" role="group" aria-label="Confirm leave">{leaveError?<p role="alert" tabIndex={0}>{leaveError}</p>:<p>{room.role==='host'?'Close room for everyone?':'Leave this room?'}</p>}<button disabled={state.busy||exiting.current} onClick={()=>void leaveRoom(room)}>Confirm leave</button><button onClick={cancelLeave}>Stay in room</button></div>:<button data-leave-room onClick={()=>requestExit(onExit)}>Leave room</button>);
 return <>{state.releaseNotice&&!releaseInFullscreen&&<div className="release-notice" role="alert"><p>{state.releaseNotice}</p><button onClick={recoverRelease}>{player()?.isLoaded()?'Resume local game':'View rooms'}</button></div>}
 {showDiscovery&&<DirectoryPanel state={{...state,busy:state.busy||!!claiming}} notices={<>
  {claiming&&<p className="catalog-status" role="status">Checking this room… <button onClick={()=>{++claimGeneration.current;setClaiming('');setIncludedStatus('');client.current?.cancelPending();}}>Cancel</button></p>}
  {includedStatus&&!room&&<p className="catalog-status" role="status" data-testid="included-status">{includedStatus}</p>}
  {!room&&state.directoryStatus==='live'&&state.status!=='No room selected.'&&state.status!==state.directoryError&&!state.status.toLowerCase().includes('password')&&!state.retryAfterMs&&<p className="catalog-status" role="status" data-testid="room-notice">{state.status} {state.busy&&<button onClick={()=>client.current?.cancelPending()}>Cancel</button>}</p>}
 </>} onCreate={onCreate} onJoin={(code,password)=>void client.current?.joinCode(code,password)} onClaim={(code,id)=>void claim(code,id)} onRetry={()=>void client.current?.watchDirectory()} onDismissJoin={()=>client.current?.cancelJoin()}/>}
 {(room||invite)&& <section id="room-session" className={`room-panel${invite&&!room?' invitation':''}${room&&!fingerprint?' pending-room':''}${room?.role==='host'&&!room.started?' host-waiting':''}`} aria-labelledby="room-heading" data-testid={room?'room-view':undefined} data-invite={room?.invite}>
  <h2 id="room-heading">{room ? room.label : invite ? 'Room invitation':'Play with a friend'}</h2>
  {room?.started==='shared'&&<div data-layout-region="shared-leave-actions" className="room-leave-actions">{leaveControl}</div>}
  {playCards}
  {room&&!!room.started && <section className="shared-gameplay-actions" data-layout-region="game-actions" aria-label="Shared gameplay">
   <ScrollRegion className="game-state-message" aria-label="Game status">{connectionNode}{(room.game.status!=='playing'||state.gameplay?.synchronizing)&&<p role="status" data-testid="game-status">{gameMessage}</p>}</ScrollRegion>
   {state.gameplay?.synchronizing&&<button className="game-action-primary" onClick={()=>client.current?.cancelSynchronization()}>Cancel synchronization</button>}
   {room.established&&['paused','failed','resume_ready'].includes(room.game.status)&&!state.gameplay?.synchronizing&&(selfSlot?.role!=='observer'||room.role==='host')&&(room.role==='host'&&room.game.status==='resume_ready'?<button className="game-action-primary" disabled={!!room.game.pending} onClick={()=>client.current?.resumeTogether()}>Resume together</button>:<button className="game-action-primary" disabled={!!room.game.pending} onClick={()=>client.current?.readyToResume()}>Ready to resume</button>)}
   {room.started&&!room.established&&(room.role==='host'||selfSlot?.role!=='observer')&&['failed','paused'].includes(room.game.status)&&<button className="game-action-primary" onClick={()=>client.current?.retryGame()}>Retry shared play</button>}
  </section>}
  <ScrollRegion className="room-detail-scroll" aria-label="Room details">
  {invite&&!room&&state.preview&&<p>{state.preview.label} · {state.preview.host} · {'openSlots' in state.preview?`${state.preview.openSlots} open ${state.preview.openSlots===1?'place':'places'}`:'No open places'}{inviteDownload&&` · ${inviteDownload}`}</p>}
  {invite&&!room&&<div className="invite-action">{state.preview&&'openSlots' in state.preview&&state.preview.openSlots>0&&<button disabled={state.busy} onClick={()=>state.preview?.visibility==='protected'?setInvitePasswordOpen(true):void client.current?.join(invite)}>Join room</button>}{!state.busy&&!state.preview&&<button onClick={()=>void client.current?.preview(invite)}>Retry invitation</button>}<button onClick={clearInvitation}>View public rooms</button></div>}
  {invite&&!room&&invitePasswordOpen&&state.preview&&<dialog ref={invitePasswordDialog} className="room-password-dialog" aria-label={`Join ${state.preview.label}`} onClose={()=>{client.current?.cancelJoin();setInvitePasswordOpen(false);setJoinPassword('');setShowJoinPassword(false);requestAnimationFrame(()=>document.querySelector<HTMLElement>('.invite-action button')?.focus());}}><h3>{state.preview.label}</h3><p>Password required</p><form onSubmit={event=>{event.preventDefault();if(validRoomPassword(joinPassword))void client.current?.join(invite,joinPassword);}}><label>Room password <input type={showJoinPassword?'text':'password'} autoComplete="off" value={joinPassword} onChange={event=>setJoinPassword(event.target.value)}/></label><button type="button" onClick={()=>setShowJoinPassword(value=>!value)}>{showJoinPassword?'Hide':'Show'}</button><p className="hint">Use 8 to 128 characters.</p><p role="alert">{roomAdmissionMessage(state.admissionError,state.retryAfterMs)}</p><button data-layout-region="password-join" type="submit" disabled={!validRoomPassword(joinPassword)||state.busy}>Join room</button><button data-layout-region="password-back" type="button" onClick={()=>invitePasswordDialog.current?.close()}>Back</button></form></dialog>}
  {room?.role==='member'&&!room.catalogId&&(!room.started||memberAcquisitionVisible)&&<div data-layout-region="preparation-recovery" className={`member-acquisition${memberAcquisitionVisible?'':' quiet'}`} role="status" aria-live="polite">{memberAcquisition&&memberAcquisition.phase!=='loaded'&&<p>{memberAcquisition.message}</p>}{memberAcquisition?.notice&&<p>{memberAcquisition.notice}</p>}{memberAcquisition&&['checking','downloading','loading'].includes(memberAcquisition.phase)&&<button onClick={()=>void leaveMember()}>Cancel preparation</button>}{memberAcquisition?.phase==='failed'&&<button onClick={()=>void startMember(room)}>Retry download</button>}{memberAcquisition?.phase==='expired'&&<button onClick={()=>void leaveMember()}>Return to rooms</button>}</div>}
  {room?.started&&playersOpen&&<><RoomSlots room={room} connected={state.connected} act={command=>client.current!.act(command)}/><button onClick={()=>setPlayersOpen(false)}>Close players</button></>}
  {room&&!room.started&&<div data-layout-region="readiness-actions" className="room-start" role="group" aria-label="Your readiness">
   {fileSelectionVisible?<><button onClick={()=>{player()?.cancel();client.current?.beginSelection();}}>Cancel loading</button><span role="status">Checking game…</span></>:!state.connected?<p role="status">Room connection lost. Reconnect to get ready.</p>:selfReady?<button className="secondary-action" onClick={()=>client.current?.cancelSynchronization()}>Not ready</button>:<button disabled={!room.matches||selfSlot?.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||state.busy||selectionLoading||!allPeersReady||!!state.gameplay?.busy} onClick={()=>client.current?.prepareMember()}>Ready</button>}
   {state.gameplay?.busy&&<p role="status">{state.gameplay.status}</p>}
  </div>}
  {room?.started&&room.game.status==='playing'&&selfSlot?.role!=='observer'&&!room.game.controllers.owners.includes(room.chatMembership)&&<div className="room-start"><button disabled={!state.connected||!room.matches||selfSlot?.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading||!!state.gameplay?.busy} onClick={()=>client.current?.prepareMember()}>Prepare to play</button></div>}
  {room?.started&&room.role!=='host'&&room.game.status==='playing'&&selfSlot?.role==='observer'&&!state.gameplay?.observing&&!state.gameplay?.synchronizing&&<div className="room-start"><button disabled={!state.connected||!hostPeerReady||!room.matches||selfSlot.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading} onClick={()=>client.current?.prepareMember()}>Observe game</button></div>}
  {invite&&!room&&!invitePasswordOpen&&<p role="status" aria-live="polite" data-testid="room-status">{state.status}</p>}
  {room?.role==='host'&&<div data-layout-region="invite-actions" className="room-invite">{room.openSlots>0&&<><button onClick={()=>{void navigator.clipboard?.writeText(inviteUrl).then(()=>setCopy('Invitation copied.')).catch(()=>setCopy('Copy unavailable. Select the invitation below.'));if(!navigator.clipboard)setCopy('Copy unavailable. Select the invitation below.');}}>Copy invite</button>{copy&&<span className="hint" role="status">{copy}</span>}{copy.startsWith('Copy unavailable')&&<input aria-label="Room invitation" readOnly value={inviteUrl} onFocus={event=>event.currentTarget.select()}/>}</>}</div>}
  {room?.role==='host'&&!room.started&&<div data-layout-region="start-actions" className="room-start">{!confirmLeave&&<><button disabled={!room.matches||selfSlot?.member?.acquisition!=='loaded'||!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading||!!room.game.startRequested||!allPeersReady||waitingMembers.length>0} onClick={()=>{if(fingerprint)void client.current?.startRoom(fingerprint);}}>Start game</button><p role="status">{room.game.startRequested?'Starting…':waitingMembers.length?`Waiting for ${waitingMembers.join(', ')}.`:''}</p>{fingerprint&&!matchesFile(room.fingerprint,fingerprint)&&<p role="status">This file does not match the room. <button onClick={onChoose}>Choose matching NES file</button></p>}</>}</div>}
  {room&&includedStatus&&<p role="status" data-testid="included-status">{includedStatus} {includedBusy&&<button onClick={()=>cancelIncluded()}>Cancel loading</button>}{room.catalogId&&catalogAvailability[room.catalogId]&&!includedBusy&&(!fingerprint||!matchesFile(room.fingerprint,fingerprint)||!player()?.isLoaded(fingerprint))&&<button onClick={()=>void startIncluded(room.catalogId!)}>Retry download</button>}</p>}
  {room&&room.started!=='shared'&&<div data-layout-region="leave-actions" className="room-leave-actions">{leaveControl}</div>}
  {room&&!room.started&&<RoomSlots room={room} connected={state.connected} act={command=>client.current!.act(command)}/>}
  {room&&!room.started&&state.chat&&<details className="chat-disclosure"><summary>Chat</summary><ChatPanel state={state.chat} connected={state.connected} onDraft={text=>client.current?.chatDraft(text)} onSend={()=>void client.current?.sendChat()} onDiscard={()=>client.current?.discardChat()}/></details>}
  {room&&<p role="status" aria-live="polite" data-testid="room-status" className="room-status-line" style={{visibility:roomStatusImportant&&!connectionIssue?'visible':'hidden'}}>{state.status}</p>}
  {room&&<div data-layout-region="connection-recovery" className="connection-recovery" role="group" aria-label="Connection help">{room.hostReconnectUntil&&<p>Host disconnected. Return before {new Date(room.hostReconnectUntil).toLocaleTimeString()} to keep this room.</p>}{!state.connected&&<button onClick={()=>void client.current?.reconnect()}>Reconnect rooms</button>}{connectionIssue&&failedPeers.map(peer=><div key={peer.pairId}><p>Could not connect to {room.slots.find(slot=>slot.member?.id===peer.member)?.member?.nickname??'member'}.</p><button onClick={()=>void client.current?.retryPeer(peer.pairId)}>Retry connection</button></div>)}</div>}
  {room?.role==='host'&&(!room.started||playersOpen)&&<details name="room-tools" className="session-settings"><summary>Room settings</summary>
    <label>Room name <input maxLength={80} value={label} onChange={event=>setLabel(event.target.value)}/></label><button disabled={!label.trim()} onClick={()=>void client.current?.act({type:'rename',roomId:room.id,label})}>Save room name</button>
    <p>Room access: {room.visibility==='protected'?'Password protected':'Public'}</p>
    <button onClick={()=>{setEditingAccess(value=>!value);setAccessPassword('');}}>{editingAccess?'Cancel password change':room.visibility==='protected'?'Change password':'Protect room'}</button>
    {editingAccess&&<div className="room-password"><label>New room password <input type={showAccessPassword?'text':'password'} autoComplete="new-password" value={accessPassword} onChange={event=>setAccessPassword(event.target.value)}/></label><button type="button" onClick={()=>setShowAccessPassword(value=>!value)}>{showAccessPassword?'Hide':'Show'}</button><p className="hint">Use 8 to 128 characters. Share it separately from the invitation.</p><button disabled={state.busy||!validRoomPassword(accessPassword)} onClick={async()=>{if(await client.current?.act({type:'visibility',roomId:room.id,visibility:'protected',password:accessPassword,expectedAccessRevision:room.accessRevision})){setEditingAccess(false);setAccessPassword('');}}}>{room.visibility==='protected'?'Save new password':'Protect room'}</button></div>}
    {room.visibility==='protected'&&<button data-make-public onClick={()=>{setConfirmPublic(true);requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.visibility-confirm button')?.focus());}}>Make public</button>}
    {confirmPublic&&<div className="room-confirm visibility-confirm" role="group" aria-label="Confirm public room"><p>Anyone can join this room after you make it public.</p><button disabled={state.busy} onClick={async()=>{if(await client.current?.act({type:'visibility',roomId:room.id,visibility:'public',expectedAccessRevision:room.accessRevision}))setConfirmPublic(false);}}>Confirm public access</button><button onClick={cancelPublic}>Keep password</button></div>}
  </details>}
  {room&&room.started&&state.chat&&<details className="chat-disclosure"><summary>Room chat</summary><ChatPanel state={state.chat} connected={state.connected} onDraft={text=>client.current?.chatDraft(text)} onSend={()=>void client.current?.sendChat()} onDiscard={()=>client.current?.discardChat()}/></details>}
  {room&&!room.started&&<details name="room-tools" className="voice-disclosure"><summary>Voice</summary><VoiceControls state={state.voice} voice={client.current?.voice}/></details>}
  <div className="controls">
   {state.busy && !state.startingRoom && !state.uploading && <button onClick={()=>client.current?.cancelPending()}>Cancel pending room action</button>}
   {!room && !state.connected && (state.admissionBlocked || /unavailable|lost|disconnected/.test(state.status)) && <button onClick={()=>void client.current?.reconnect()}>Reconnect rooms</button>}
  </div>
  {state.needsNewGuest && <button onClick={()=>client.current?.newGuest()}>Start a new guest session</button>}
  </ScrollRegion>
 </section>}</>;
});
