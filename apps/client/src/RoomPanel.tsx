import {ControllerMode,ControllerOwnership} from './ControllerMode.tsx';
import {catalogAvailability} from 'virtual:catalog';
import {catalogEntry,catalogId,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {catalogFingerprint} from './catalog-fingerprint.ts';
import {downloadCatalogEntry} from './catalog-download.ts';
import {acquireGuestRom,GuestPlaceExpiredError} from './guest-rom.ts';
import type {LocalPlayer} from './player.ts';
import {VoiceControls} from './VoiceControls.tsx';
import type {VoiceSession,VoiceState} from './voice.ts';
import type {Controls} from './controls.ts';
import {ConnectionPolicyControl} from './ConnectionPolicy.tsx';
import type {ConnectionPolicy} from '../../../packages/contracts/src/peer.ts';
import React, {forwardRef, useEffect, useImperativeHandle, useRef, useState} from 'react';
import {ChatPanel} from './ChatPanel.tsx';
import {DirectoryPanel} from './DirectoryPanel.tsx';
import {RoomClient, connectionStatus, type RoomState} from './room-client.ts';
import {matchesFile,type Fingerprint,type RoomView,type Visibility} from '../../../packages/contracts/src/rooms.ts';
type GuestOperation={roomId:string;membership:string;controller:AbortController;sawLoading:boolean};
type GuestAcquisition={phase:'checking'|'downloading'|'loading'|'loaded'|'failed'|'expired';message:string;notice?:string};
const gameSize=(bytes:number)=>bytes<1_000_000?`${Math.max(1,Math.ceil(bytes/1000))} KB`:`${(bytes/1_000_000).toFixed(1)} MB`;
export type RoomPanelHandle = {voice():VoiceSession|undefined;localPlayIntent():void;readyToResume():void;isGuest():boolean;beforeSelection():boolean;approveSelection(fingerprint:Fingerprint,isCurrent:()=>boolean):Promise<boolean>;cancelCreation():void;createCustom(file:File,fingerprint:Fingerprint,visibility:Visibility,current:()=>boolean):Promise<void>;createIncluded(code:string,fingerprint:Fingerprint,visibility:Visibility):Promise<void>};
export const RoomPanel = forwardRef<RoomPanelHandle,{showDiscovery:boolean;onChoose():void;onCreate():void;onBrowse():void;onInvitationDismiss():void;onAcquired:(file:File,current:()=>boolean)=>boolean;selectionLoading:boolean;controls:Controls;onVoice:(state:VoiceState|undefined)=>void;fingerprint?:Fingerprint;player:()=>LocalPlayer|null;onNickname:(name:string)=>void;policy:ConnectionPolicy;changePolicy:(policy:ConnectionPolicy)=>void;onConnection:(status:string)=>void;onRoomChange:(room?:RoomView)=>void;onState:(state:RoomState)=>void}>(function RoomPanel({showDiscovery,onChoose,onCreate,onBrowse,onInvitationDismiss,onAcquired,selectionLoading,controls,onVoice,fingerprint,player,onNickname,policy,changePolicy,onConnection,onRoomChange,onState},ref) {
 const [state,setState] = useState<RoomState>({status:'No room selected.',busy:false,connected:false});
 const [staying,setStaying] = useState<string>();
 const [invite,setInvite] = useState(()=>new URLSearchParams(location.hash.slice(1)).get('invite'));
 const [label,setLabel] = useState(''), [nickname,setNickname] = useState(''), [copy,setCopy] = useState('');
 const [slotPending,setSlotPending]=useState(false),[slotError,setSlotError]=useState(false),[removeGuest,setRemoveGuest]=useState<string>();
 const client = useRef<RoomClient|null>(null);
 const removeButtonRef=useRef<HTMLButtonElement|null>(null),confirmRemoveRef=useRef<HTMLButtonElement|null>(null);
 const seenFile = useRef<Fingerprint|undefined>(undefined), sentGuestFile = useRef('');
 const [includedStatus,setIncludedStatus]=useState(''),[includedBusy,setIncludedBusy]=useState<CatalogId>(),[claiming,setClaiming]=useState('');
 const [guestAcquisition,setGuestAcquisition]=useState<GuestAcquisition>();
 const guestOperation=useRef<GuestOperation|undefined>(undefined),guestRoom=useRef<RoomView|undefined>(undefined),guestConnected=useRef(state.connected);guestRoom.current=state.room;guestConnected.current=state.connected;
 const claimGeneration=useRef(0);
 const included=useRef<{id:CatalogId;controller:AbortController;membership:string;candidate:boolean;sawLoading:boolean}|undefined>(undefined),attemptedGuest=useRef('');
 const membership=state.room ? `${state.room.id}:${state.room.role}:${state.room.chatMembership}` : '';
 const guestCurrent=(operation:GuestOperation)=>guestOperation.current===operation&&!operation.controller.signal.aborted&&guestConnected.current&&guestRoom.current?.id===operation.roomId&&guestRoom.current?.role==='guest'&&guestRoom.current.chatMembership===operation.membership&&!!guestRoom.current.reservationIntent&&!guestRoom.current.started;
 const cancelGuest=()=>{const operation=guestOperation.current;guestOperation.current=undefined;operation?.controller.abort();if(operation?.sawLoading)player()?.cancel();setGuestAcquisition(undefined);};
 const startGuest=async(room:RoomView)=>{
  if(room.role!=='guest'||room.catalogId)return;
  cancelGuest();const token=client.current?.guestToken();if(!token){setGuestAcquisition({phase:'failed',message:'Your room session is unavailable. Return to rooms.'});return;}
  const operation:GuestOperation={roomId:room.id,membership:room.chatMembership,controller:new AbortController(),sawLoading:false};guestOperation.current=operation;
  setGuestAcquisition({phase:'checking',message:'Checking saved game…'});
  const current=()=>guestCurrent(operation);
  void client.current?.guestAcquisition(room.id,room.chatMembership,'checking');
  try{
   const result=await acquireGuestRom(room,token,operation.controller.signal,bytes=>{if(current()){setGuestAcquisition({phase:'downloading',message:`Downloading game… ${gameSize(bytes)} / ${gameSize(room.fingerprint.cartridge.bytes)}`});void client.current?.guestAcquisition(room.id,room.chatMembership,'downloading');}},current);
   if(!current())return;
   setGuestAcquisition({phase:'loading',message:'Loading game…',notice:result.notice});
   void client.current?.guestAcquisition(room.id,room.chatMembership,'loading');
   if(!onAcquired(result.file,current))throw Error('The game could not start loading. Retry download.');
   operation.sawLoading=true;
  }catch(error){if(current()){setGuestAcquisition({phase:error instanceof GuestPlaceExpiredError?'expired':'failed',message:error instanceof Error?error.message:'Download failed. Retry download.'});void client.current?.guestAcquisition(room.id,room.chatMembership,'failed');}}
 };
 const leaveGuest=async()=>{const room=guestRoom.current;cancelGuest();if(room?.reservationIntent)await client.current?.act({type:'leave',intent:room.reservationIntent});if(invite)clearInvitation();else onBrowse();requestAnimationFrame(()=>document.querySelector<HTMLInputElement>('.directory-panel input')?.focus());};
 const clearInvitation=()=>{history.replaceState(null,'',location.pathname+location.search);setInvite(null);onInvitationDismiss();onBrowse();requestAnimationFrame(()=>document.querySelector<HTMLInputElement>('.directory-panel input')?.focus());};
 const cancelIncluded=(message='Included loading canceled. Your previous game is preserved.')=>{
  const operation=included.current;included.current=undefined;operation?.controller.abort();
  if(operation?.candidate)player()?.cancel();
  setIncludedBusy(undefined);if(operation)setIncludedStatus(message);
 };
 const startIncluded=async(id:CatalogId)=>{if(state.startingRoom)return;const entry=catalogEntry(id);
  if(!catalogAvailability[id]){setIncludedStatus(`${entry.title} is unavailable here. Leave room and try another game.`);return;}
  if(state.room?.established){setIncludedStatus('Leave shared play before starting another game.');return;}
  cancelIncluded('');
  if(fingerprint && player()?.isLoaded(fingerprint) && catalogId(fingerprint)===id){
   setIncludedStatus(`Using ${entry.title} already loaded in this tab without resetting progress.`);
   return;
  }
  client.current?.beginSelection();
  const operation={id,controller:new AbortController(),membership,candidate:false,sawLoading:false};included.current=operation;
  setIncludedBusy(id);setIncludedStatus(`Downloading ${entry.title}…`);
  const current=()=>included.current===operation && !operation.controller.signal.aborted;
  const timeout=window.setTimeout(()=>operation.controller.abort(Error('The included download timed out. Retry the download.')),15000);
  try {
   const file=await downloadCatalogEntry(entry,operation.controller.signal,bytes=>{if(current())setIncludedStatus(`Downloading ${entry.title}: ${bytes} / ${entry.bytes} bytes`);});
   if(!current())return;
   operation.candidate=true;setIncludedStatus(`Download verified. Preparing ${entry.title}…`);if(!onAcquired(file,current))throw Error(`Could not start ${entry.title}. Retry download.`);
  }catch(error){
   if(included.current===operation){included.current=undefined;setIncludedBusy(undefined);setIncludedStatus(error instanceof Error ? error.message : 'Download failed. Retry the included game.');}
  }finally{clearTimeout(timeout);}
 };
 useEffect(()=>{const operation=included.current;if(operation && operation.membership!==membership)cancelIncluded('The room changed. Included loading canceled; your previous game is preserved.');},[membership]);
 useEffect(()=>{const room=guestRoom.current;if(room?.role==='guest'&&!room.catalogId)void startGuest(room);else{cancelGuest();setGuestAcquisition(undefined);}return()=>{cancelGuest();};},[membership]);
 useEffect(()=>{if(!state.connected&&guestOperation.current){cancelGuest();setGuestAcquisition({phase:'failed',message:'Room connection lost. Reconnect rooms, then retry download.'});}},[state.connected]);
 useEffect(()=>{const operation=guestOperation.current;if(!operation||!guestCurrent(operation)||guestAcquisition?.phase!=='loading')return;if(selectionLoading){operation.sawLoading=true;return;}if(operation.sawLoading){if(fingerprint&&matchesFile(guestRoom.current!.fingerprint,fingerprint)&&player()?.isLoaded(fingerprint)){setGuestAcquisition({...guestAcquisition,phase:'loaded',message:'Game ready in this browser.'});void client.current?.guestAcquisition(operation.roomId,operation.membership,'loaded');}else{setGuestAcquisition({...guestAcquisition,phase:'failed',message:'The game could not load. Retry download.'});void client.current?.guestAcquisition(operation.roomId,operation.membership,'failed');}}},[selectionLoading,fingerprint,guestAcquisition?.phase]);
 useEffect(()=>{
  const operation=included.current;if(!operation?.candidate)return;
  if(selectionLoading){operation.sawLoading=true;return;}
  if(operation.sawLoading){operation.candidate=false;setIncludedBusy(undefined);setIncludedStatus(fingerprint&&catalogId(fingerprint)===operation.id?'':'The game could not load. Check the player message, then retry.');}
 },[selectionLoading,fingerprint]);
 useEffect(()=>{
  if(!state.room?.catalogId){attemptedGuest.current='';return;}
  if(attemptedGuest.current===membership)return;attemptedGuest.current=membership;
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
 useEffect(()=>{onConnection(connectionStatus(state));},[state.connection,state.room?.peer.status,onConnection]);
 useEffect(()=>{if(state.session) {onNickname(state.session.nickname);setNickname(state.session.nickname);}},[state.session,onNickname]);
 useEffect(()=>{if(state.room) setLabel(state.room.label);},[state.room?.label]);
 useEffect(()=>{setRemoveGuest(undefined);setSlotError(false);},[state.room?.id,state.room?.guestMembership]);
 useEffect(()=>{if(invite&&!state.room)requestAnimationFrame(()=>document.querySelector<HTMLSelectElement>('.room-panel.invitation .connection-policy select')?.focus());},[invite]);
 useEffect(()=>{onRoomChange(state.room);},[state.room,onRoomChange]);
 useEffect(()=>{onState(state);},[state,onState]);
 useImperativeHandle(ref,()=>({voice:()=>client.current?.voice,localPlayIntent(){client.current?.localPlayIntent();},readyToResume(){client.current?.readyToResume();},isGuest(){return client.current?.isGuest()??false;},
  beforeSelection() {
   if(state.startingRoom||state.room?.role==='guest'&&!state.room.started&&!state.room.catalogId)return false;
   cancelIncluded();client.current?.beginSelection();return true;
 },approveSelection(fingerprint,isCurrent){if(state.room?.role==='guest'&&!state.room.catalogId){const operation=guestOperation.current;return Promise.resolve(!!operation&&guestCurrent(operation)&&isCurrent()&&matchesFile(state.room.fingerprint,fingerprint));}return client.current?.approveSelection(fingerprint,isCurrent) ?? Promise.resolve(isCurrent());},cancelCreation(){cancelIncluded();client.current?.cancelPending();},
 createCustom(file,fingerprint,visibility,current){return client.current?.host(file,fingerprint,visibility,current)??Promise.resolve();},
 createIncluded(code,fingerprint,visibility){return client.current?.claimCode(code,fingerprint,visibility)??Promise.resolve();}
 }),[state.room]);
 useEffect(()=>{
  if(!fingerprint || seenFile.current === fingerprint) return;
  seenFile.current = fingerprint;client.current?.selectedGame(fingerprint);
  // Loading a game is local. Only the Create room action publishes a room.
 },[fingerprint,invite,state.room?.role]);
 useEffect(()=>{
  if(!fingerprint || state.room?.role !== 'guest') {sentGuestFile.current = '';return;}
  const key = state.room.id+fingerprint.romSha256+fingerprint.coreSha256;
  if(sentGuestFile.current !== key) {sentGuestFile.current = key;void client.current?.act({type:'file',fingerprint});}
 },[fingerprint,state.room?.id,state.room?.role]);
 const room = state.room;
 const changeGuestPlace=async(place:'open'|'closed')=>{const current=state.room;if(!current||current.role!=='host'||current.started)return;setSlotPending(true);setSlotError(false);const ok=await client.current?.act({type:'guestPlace',roomId:current.id,place,expectedVersion:current.guestPlaceVersion});setSlotPending(false);setSlotError(!ok);};
 const dismissRemove=()=>{setRemoveGuest(undefined);requestAnimationFrame(()=>removeButtonRef.current?.focus());};
 const confirmRemove=async()=>{const current=state.room;if(!current?.guestMembership||current.guestMembership!==removeGuest)return;setSlotPending(true);setSlotError(false);const ok=await client.current?.act({type:'kick',roomId:current.id,guestMembership:removeGuest});setSlotPending(false);setSlotError(!ok);if(ok)setRemoveGuest(undefined);};
 const inviteUrl = room ? `${location.origin}${location.pathname}#invite=${room.invite}`:'';
 return <>{state.releaseNotice&&<div className="release-notice" role="alert"><p>{state.releaseNotice}</p><button onClick={()=>{if(player()?.isLoaded()){player()?.allowLocalPlay();player()?.resume();}else onBrowse();client.current?.dismissRelease();}}>{player()?.isLoaded()?'Resume local game':'View rooms'}</button></div>}
 {showDiscovery&&<>
 {claiming&&<p className="catalog-status" role="status">Checking this room… <button onClick={()=>{++claimGeneration.current;setClaiming('');setIncludedStatus('');client.current?.cancelPending();}}>Cancel</button></p>}
 {includedStatus&&!room&&<p className="catalog-status" role="status" data-testid="included-status">{includedStatus}</p>}
 {!room&&state.status!=='No room selected.'&&<p className="catalog-status" role="status" data-testid="room-notice">{state.status} {state.busy&&<button onClick={()=>client.current?.cancelPending()}>Cancel</button>}</p>}
 <DirectoryPanel connection={<ConnectionPolicyControl compact policy={policy} change={changePolicy}/>} state={{...state,busy:state.busy||!!claiming}} onCreate={onCreate} onJoin={code=>void client.current?.joinCode(code)} onClaim={(code,id)=>void claim(code,id)} onRetry={()=>void client.current?.watchDirectory()}/></>}
 {(room||invite)&& <section id="room-session" className={`room-panel${invite&&!room?' invitation':''}${room&&!fingerprint?' pending-room':''}`} aria-labelledby="room-heading">
  <h2 id="room-heading">{room ? room.label : invite ? 'Room invitation':'Play with a friend'}{room&&!room.started&&<small> · {room.visibility==='public'?`Public · ${room.code}`:'Unlisted'}</small>}</h2>
  {invite && !room && state.preview && <p>{state.preview.label} · {state.preview.host} · {state.preview.occupancy}/2 places · {'guestPlace' in state.preview && state.preview.guestPlace==='closed'?'Guest place closed':state.preview.status}. {state.preview.status==='waiting'&&state.preview.occupancy===1&&('guestPlace' in state.preview?state.preview.guestPlace==='open':true)?state.preview.catalogId ? `${catalogEntry(state.preview.catalogId).title} is included; Join downloads its verified copy.${state.preview.catalogId==='from-below-1.0'?' One controller; share turns with the other player.':''}` : `Host-shared NES · ${state.preview.romBytes?`${gameSize(state.preview.romBytes)} download`:'download size unavailable'}`:''}</p>}
  {invite&&!room&&<div className="invite-action">{state.preview?.status==='waiting'&&state.preview.occupancy===1&&('guestPlace' in state.preview?state.preview.guestPlace==='open':true)&&<><ConnectionPolicyControl compact policy={policy} change={changePolicy}/><button disabled={state.busy} onClick={()=>void client.current?.join(invite)}>Join room</button></>}{!state.busy&&!state.preview&&<button onClick={()=>void client.current?.preview(invite)}>Retry invitation</button>}<button onClick={clearInvitation}>View public rooms</button></div>}
  {room?.role==='guest'&&!room.catalogId&&guestAcquisition&&<div className="guest-acquisition" role="status" aria-live="polite"><p>{guestAcquisition.message}</p>{guestAcquisition.notice&&<p>{guestAcquisition.notice}</p>}{['checking','downloading','loading'].includes(guestAcquisition.phase)&&<button onClick={()=>void leaveGuest()}>Cancel preparation</button>}{guestAcquisition.phase==='failed'&&<button onClick={()=>void startGuest(room)}>Retry download</button>}{guestAcquisition.phase==='expired'&&<button onClick={()=>void leaveGuest()}>Return to rooms</button>}</div>}
  {room?.catalogId==='from-below-1.0'&&!room.started&&<p>One controller; share turns. The host controls first. Both players must agree to a handoff in Session controllers.</p>}
  {room&&selectionLoading&&!includedBusy&&!(room.role==='guest'&&!room.catalogId)&&<p role="status">Checking the selected file… <button onClick={()=>{player()?.cancel();client.current?.beginSelection();}}>Cancel loading</button></p>}
  {room&&!room.started?<div className="room-slots"><div><strong>Player 1 · Host</strong><span>{room.role==='host'?'You':room.host}</span></div><div><strong>Player 2 · Guest</strong><span>{room.role==='guest'?'You':room.guest??`Guest place: ${room.guestPlace==='closed'?'Closed':'Open'}`}</span>{room.role==='host'&&room.guest&&!removeGuest&&<button ref={removeButtonRef} disabled={slotPending} onClick={()=>{setRemoveGuest(room.guestMembership);requestAnimationFrame(()=>confirmRemoveRef.current?.focus());}}>Remove guest</button>}{room.role==='host'&&room.guest&&removeGuest===room.guestMembership&&<div className="slot-confirm" onKeyDown={event=>{if(event.key==='Escape'){dismissRemove();event.stopPropagation();}}}><p>Remove {room.guest}? They cannot reconnect.</p><button ref={confirmRemoveRef} disabled={slotPending} onClick={()=>void confirmRemove()}>Confirm removal</button><button disabled={slotPending} onClick={dismissRemove}>Cancel</button></div>}{room.role==='host'&&!room.guest&&<button disabled={slotPending||!state.connected} onClick={()=>void changeGuestPlace(room.guestPlace==='open'?'closed':'open')}>{room.guestPlace==='open'?'Close place':'Open place'}</button>}{room.role==='host'&&slotError&&<p role="alert">{state.status} {!room.guest&&<button disabled={slotPending} onClick={()=>void changeGuestPlace(room.guestPlace==='open'?'closed':'open')}>Retry</button>}</p>}</div></div>:room&&<ControllerOwnership room={room}/>}
  {room?.role==='guest'&&!room.started&&<div className="room-start" role="group" aria-label="Guest preparation">
   {!state.connected?<p role="status">Room connection lost. Reconnect to check readiness.</p>:room.peer.status==='connected'&&!selectionLoading&&!!fingerprint&&player()?.isLoaded(fingerprint)&&matchesFile(room.fingerprint,fingerprint)&&room.game?.ready?.includes('guest')?<p role="status">Ready to play. Waiting for the host to start.</p>:room.catalogId||guestAcquisition?.phase==='loaded'?<>{room.peer.status==='connected'&&<button disabled={!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading||!!state.gameplay?.intent} onClick={()=>client.current?.prepareGuest()}>Prepare to play</button>}{room.peer.status!=='connected'&&<p role="status">Game ready in this browser. Waiting for peer connection…</p>}{state.gameplay?.intent&&<p role="status">{state.gameplay.status}</p>}</>:null}
  </div>}
  {(room?.peer.epoch||!state.connected)&&<p role="status" data-testid="connection-status">{connectionStatus(state)}</p>}
  {invite&&!room&&<p role="status" aria-live="polite" data-testid="room-status">{state.status}</p>}
  {room?.role==='host'&&!room.started&&room.guestPlace==='open'&&<div className="room-invite"><button onClick={()=>{void navigator.clipboard?.writeText(inviteUrl).then(()=>setCopy('Invitation copied.')).catch(()=>setCopy('Select the invitation text and copy it.'));if(!navigator.clipboard)setCopy('Select the invitation text and copy it.');}}>Copy invite</button><span className="hint" role="status">{copy}</span><label className={copy.startsWith('Select')?'':'invite-fallback'}>Invitation <input aria-label="Room invitation" readOnly value={inviteUrl} onFocus={event=>event.currentTarget.select()}/></label></div>}
  {room?.role==='host'&&!room.started&&<div className="room-start"><p>{!state.connected?'Room connection lost. Reconnect to check whether the guest is ready.':room.game?.startRequested?'Checking both games before shared Start…':room.game?.ready?.includes('guest')?'Guest is prepared. Start together when you are ready.':room.guest&&!room.guestConnected?'Guest disconnected. Start now to play alone and release their place.':room.guestAcquisition==='checking'?'Guest checking a saved game. Start now to play alone and release their place.':room.guestAcquisition==='downloading'?'Guest downloading. Start now to play alone and release their place.':room.guestAcquisition==='loading'?'Guest loading. Start now to play alone and release their place.':room.guestAcquisition==='failed'?'Guest download failed. Start now to play alone and release their place.':room.guestAcquisition==='loaded'&&room.peer.status!=='connected'?'Guest game loaded; waiting for peer connection. Start now to play alone and release their place.':room.guest?'Guest is preparing. Start now to play alone and release their place.':room.guestPlace==='closed'?'Start alone, or open Guest place before inviting someone.':'Start now to play alone, or wait for a guest.'}</p><button disabled={!fingerprint||!player()?.isLoaded(fingerprint)||!matchesFile(room.fingerprint,fingerprint)||state.busy||selectionLoading||!!room.game?.startRequested} onClick={()=>{if(fingerprint)void client.current?.startRoom(fingerprint);}}>Start game</button>{fingerprint&&!matchesFile(room.fingerprint,fingerprint)&&<p role="status">This file does not match the room. <button onClick={onChoose}>Choose matching NES file</button></p>}</div>}
  {room&&!room.started&&includedStatus&&<p role="status" data-testid="included-status">{includedStatus} {includedBusy&&<button onClick={()=>cancelIncluded()}>Cancel loading</button>}{room.catalogId&&catalogAvailability[room.catalogId]&&!includedBusy&&(!fingerprint||!player()?.isLoaded(fingerprint))&&<button onClick={()=>void startIncluded(room.catalogId!)}>Retry download</button>}</p>}
  {room&&!(room.role==='guest'&&!room.catalogId&&['checking','downloading','loading','expired'].includes(guestAcquisition?.phase??''))&&<button onClick={async()=>{let left=false;if(room.role==='host'){if(window.confirm('Leave and close this room for both players? Your local game stays available.'))left=await client.current?.act({type:'close',roomId:room.id})??false;}else if(!room.established||window.confirm('Leave shared play? Your local game stays available.')){cancelGuest();left=await client.current?.act({type:'leave',intent:room.reservationIntent!})??false;}if(left){const nextInvite=new URLSearchParams(location.hash.slice(1)).get('invite');if(nextInvite&&nextInvite!==invite){setInvite(nextInvite);onBrowse();}else if(invite)clearInvitation();else onBrowse();requestAnimationFrame(()=>document.querySelector<HTMLInputElement>('.directory-panel input')?.focus());}}}>Leave room</button>}
  {room&&!room.started&&state.chat&&<ChatPanel state={state.chat} connected={state.connected} onDraft={text=>client.current?.chatDraft(text)} onSend={()=>void client.current?.sendChat()} onDiscard={()=>client.current?.discardChat()}/>}
  {(room||!invite)&&<details name="room-tools" className="session-settings"><summary>Connection and session settings</summary>
  <ConnectionPolicyControl policy={policy} change={changePolicy}/>
  <p className="hint">The host chooses Start after both games are ready.</p>
  {room?.peer.epoch && <button onClick={()=>void client.current?.retryPeer()}>Retry connection</button>}
  {room?.peer.epoch && ['relay_unavailable','relay_capacity','failed'].includes(room.peer.status) && <><button onClick={()=>setStaying(room.peer.epoch)}>Stay in room</button>{staying===room.peer.epoch && <p role="status">You stayed in the room. Your current reservation deadline and local game are unchanged. Retry whenever you are ready.</p>}</>}
  <p role="status" aria-live="polite" data-testid="room-status">{state.status}</p>
  {state.retryAfterMs && <p>Wait at least {Math.ceil(state.retryAfterMs/1000)} seconds before retrying.</p>}
  {room && <div data-testid="room-view">
   <p><strong>{room.visibility === 'public' ? `Public · ${room.code}`:'Unlisted · invite only'}</strong> · {room.occupancy}/2 places · {room.status}</p>
   <p>You are {room.role === 'host' ? 'the host, Player 1':room.established?'Player 2':'Player 2 (reserved)'}. {room.guest ? `${room.guest} has the ${room.established?'established':'reserved'} guest place.`:room.started==='solo'?'Playing alone; new guests cannot join.':'Waiting for a friend.'}</p>
   {room.reservationUntil && <p>Reservation expires at {new Date(room.reservationUntil).toLocaleTimeString()}. {room.matches ? 'Game verified. Preparing the shared-play connection.' : 'The guest game is still being acquired or loaded.'}</p>}
   {room.hostReconnectUntil && <p>Host disconnected. Return before {new Date(room.hostReconnectUntil).toLocaleTimeString()} to keep this room.</p>}
   {room.role === 'host' ? <details><summary>Session settings</summary>
    <label>Room name <input maxLength={80} value={label} onChange={event=>setLabel(event.target.value)}/></label><button disabled={!label.trim()} onClick={()=>void client.current?.act({type:'rename',roomId:room.id,label})}>Save room name</button>
    <label className="visibility"><input type="checkbox" checked={room.visibility === 'unlisted'} onChange={event=>{const visibility = event.target.checked ? 'unlisted':'public';if(visibility === 'public' && !window.confirm('Make this room public? Its room name and host nickname will be discoverable.')) return;void client.current?.act({type:'visibility',roomId:room.id,visibility});}}/> Unlisted · invitation only</label>
   </details> : null}
  </div>}
  </details>}
  {room&&<details name="room-tools" className="controller-disclosure"><summary>Session controllers</summary><ControllerMode room={room} act={command=>client.current!.act(command)}/></details>}
  {room&&!!room.started&&room.started!=='solo' && <section aria-label="Shared gameplay"><p role="status" data-testid="game-status">{room.game?.reason??state.gameplay?.status}</p><p data-testid="game-frame">{state.gameplay?.frame??0} shared frames · delay {state.gameplay?.delay??'negotiating'}</p>
   {room.established && ['paused','failed','resume_ready'].includes(room.game?.status??'') && <><button disabled={!!room.game?.controllerProposal} onClick={()=>client.current?.readyToResume()}>Ready to resume</button>{room.role==='host' && <button disabled={!!room.game?.controllerProposal||room.game?.status!=='resume_ready'} onClick={()=>client.current?.resumeTogether()}>Resume together</button>}<p role="status">{room.game?.status==='resume_ready' ? `Both players are ready. ${room.role==='host'?'Resume together when ready.':`Waiting for ${room.host} to resume.`}` : `Waiting for ${[!room.game?.ready?.includes('host') && room.host,!room.game?.ready?.includes('guest') && (room.guest??'Player 2')].filter(Boolean).join(' and ')} to resume.`}</p></>}
   {room.started==='shared'&&!room.established && ['failed','paused'].includes(room.game?.status??'') && <button onClick={()=>client.current?.retryGame()}>Retry shared play</button>}
  </section>}
  {room&&room.started&&state.chat&&<details className="chat-disclosure"><summary>Room chat</summary><ChatPanel state={state.chat} connected={state.connected} onDraft={text=>client.current?.chatDraft(text)} onSend={()=>void client.current?.sendChat()} onDiscard={()=>client.current?.discardChat()}/></details>}
  {room&&<details name="room-tools" className="voice-disclosure"><summary>Voice</summary><VoiceControls state={state.voice} voice={client.current?.voice}/></details>}
  <div className="controls">
   {state.busy && !state.startingRoom && !state.uploading && <button onClick={()=>client.current?.cancelPending()}>Cancel pending room action</button>}
   {!state.connected && (state.room || state.admissionBlocked || /unavailable|lost|disconnected/.test(state.status)) && <button onClick={()=>void client.current?.reconnect()}>Reconnect rooms</button>}
  </div>
  {state.session && <details name="room-tools"><summary>Guest settings</summary><p className="hint">Temporary name for this browser tab. It is not an account.</p><label>Nickname <input maxLength={32} value={nickname} onChange={event=>setNickname(event.target.value)}/></label><button disabled={!nickname.trim()} onClick={()=>void client.current?.act({type:'nickname',nickname})}>Save nickname</button></details>}
  {state.needsNewGuest && <button onClick={()=>client.current?.newGuest()}>Start a new guest session</button>}
 </section>}</>;
});
