import {ControllerMode,ControllerOwnership} from './ControllerMode.tsx';
import {catalogAvailability} from 'virtual:catalog';
import {catalog,catalogEntry,catalogId,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {downloadCatalogEntry} from './catalog-download.ts';
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
import type {Fingerprint,Visibility} from '../../../packages/contracts/src/rooms.ts';
export type RoomPanelHandle = {voice():VoiceSession|undefined;localPlayIntent():void;readyToResume():void;isGuest():boolean;beforeSelection():boolean;approveSelection(fingerprint:Fingerprint,isCurrent:()=>boolean):Promise<boolean>;cancelCreation():void};
export const RoomPanel = forwardRef<RoomPanelHandle,{showDiscovery:boolean;onChoose():void;onIncluded:(file:File,current:()=>boolean)=>void;selectionLoading:boolean;controls:Controls;onVoice:(state:VoiceState|undefined)=>void;fingerprint?:Fingerprint;player:()=>LocalPlayer|null;onNickname:(name:string)=>void;policy:ConnectionPolicy;changePolicy:(policy:ConnectionPolicy)=>void;onConnection:(status:string)=>void;onHost:()=>void}>(function RoomPanel({showDiscovery,onChoose,onIncluded,selectionLoading,controls,onVoice,fingerprint,player,onNickname,policy,changePolicy,onConnection,onHost},ref) {
 const [state,setState] = useState<RoomState>({status:'Choose a file to create a room. Your file stays here.',busy:false,connected:false});
 const [staying,setStaying] = useState<string>();
 const [visibility,setVisibility] = useState<Visibility>('public');
 const [invite] = useState(()=>new URLSearchParams(location.hash.slice(1)).get('invite'));
 const [label,setLabel] = useState(''), [nickname,setNickname] = useState(''), [copy,setCopy] = useState('');
 const client = useRef<RoomClient|null>(null), selectedVisibility = useRef<Visibility>('public');
 const seenFile = useRef<Fingerprint|undefined>(undefined), sentGuestFile = useRef('');
 const [catalogFilter,setCatalogFilter]=useState<CatalogId>(),[includedStatus,setIncludedStatus]=useState(''),[includedBusy,setIncludedBusy]=useState<CatalogId>();
 const included=useRef<{id:CatalogId;controller:AbortController;membership:string;candidate:boolean;sawLoading:boolean}|undefined>(undefined),attemptedGuest=useRef('');
 const membership=state.room ? `${state.room.id}:${state.room.role}:${state.room.chatMembership}` : '';
 const cancelIncluded=(message='Included loading canceled. Your previous game is preserved.')=>{
  const operation=included.current;included.current=undefined;operation?.controller.abort();
  if(operation?.candidate)player()?.cancel();
  setIncludedBusy(undefined);if(operation)setIncludedStatus(message);
 };
 const startIncluded=async(id:CatalogId)=>{const entry=catalogEntry(id);
  if(!catalogAvailability[id]){setIncludedStatus(`${entry.title} is unavailable in this deployment. Choose a local file or retry later.`);return;}
  if(state.room?.established){setIncludedStatus('Leave shared play before starting another game.');return;}
  cancelIncluded('');
  if(fingerprint && catalogId(fingerprint)===id){
   setIncludedStatus(`Using ${entry.title} already loaded in this tab without resetting progress.`);
   if(state.room?.role!=='guest') {if(!state.room)void client.current?.host(fingerprint,visibility);if(player()?.resume())client.current?.localPlayIntent();}
   return;
  }
  client.current?.beginSelection();selectedVisibility.current=visibility;
  const operation={id,controller:new AbortController(),membership,candidate:false,sawLoading:false};included.current=operation;
  setIncludedBusy(id);setIncludedStatus(`Downloading ${entry.title}…`);
  const current=()=>included.current===operation && !operation.controller.signal.aborted;
  const timeout=window.setTimeout(()=>operation.controller.abort(Error('The included download timed out. Retry the download.')),15000);
  try {
   const file=await downloadCatalogEntry(entry,operation.controller.signal,bytes=>{if(current())setIncludedStatus(`Downloading ${entry.title}: ${bytes} / ${entry.bytes} bytes`);});
   if(!current())return;
   operation.candidate=true;setIncludedStatus(`Download verified. Starting ${entry.title}…`);onIncluded(file,current);
  }catch(error){
   if(included.current===operation){included.current=undefined;setIncludedBusy(undefined);setIncludedStatus(error instanceof Error ? error.message : 'Download failed. Retry the included game.');}
  }finally{clearTimeout(timeout);}
 };
 useEffect(()=>{const operation=included.current;if(operation && operation.membership!==membership)cancelIncluded('The room changed. Included loading canceled; your previous game is preserved.');},[membership]);
 useEffect(()=>{
  const operation=included.current;if(!operation?.candidate)return;
  if(selectionLoading){operation.sawLoading=true;return;}
  if(operation.sawLoading){operation.candidate=false;setIncludedBusy(undefined);setIncludedStatus(fingerprint&&catalogId(fingerprint)===operation.id?`${catalogEntry(operation.id).title} is loaded. Use the game’s own menu to begin.`:'The game could not start. Check the player message, then retry.');}
 },[selectionLoading,fingerprint]);
 useEffect(()=>{
  if(state.room?.role!=='guest'){attemptedGuest.current='';return;}
  if(attemptedGuest.current===membership)return;attemptedGuest.current=membership;
  if(state.room.catalogId)void startIncluded(state.room.catalogId);
 },[membership,state.room?.catalogId]);
 useEffect(()=>()=>{const operation=included.current;included.current=undefined;operation?.controller.abort();if(operation?.candidate)player()?.cancel();},[]);

 useEffect(()=>{
  const rooms = new RoomClient(setState,()=>window.confirm('Choosing a different valid game closes this room and releases its guest. Continue?'),policy,player);client.current = rooms;
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
 useImperativeHandle(ref,()=>({voice:()=>client.current?.voice,localPlayIntent(){client.current?.localPlayIntent();},readyToResume(){client.current?.readyToResume();},isGuest(){return client.current?.isGuest()??false;},
  beforeSelection() {
   cancelIncluded();client.current?.beginSelection();selectedVisibility.current = visibility;return true;
  },approveSelection(fingerprint,isCurrent){return client.current?.approveSelection(fingerprint,isCurrent) ?? Promise.resolve(isCurrent());},cancelCreation(){cancelIncluded();client.current?.beginSelection();}
 }),[visibility,state.room]);
 useEffect(()=>{
  if(!fingerprint || seenFile.current === fingerprint) return;
  seenFile.current = fingerprint;client.current?.selectedGame(fingerprint);
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
 return <>{showDiscovery&&<><section className="launchers" aria-label="Start a game">{catalog.map(entry=><article className="catalog-launcher" key={entry.id}><div><h2>{entry.title}</h2><p>{entry.mode}</p></div><button disabled={!catalogAvailability[entry.id]||!!includedBusy||!!room?.established||room?.role==='guest'} onClick={()=>void startIncluded(entry.id)}>{catalogAvailability[entry.id]?`Play ${entry.title}`:'Unavailable'}</button><button onClick={()=>setCatalogFilter(entry.id)}>Show lobbies</button></article>)}<article className="file-launcher" onDragOver={event=>event.preventDefault()} onDrop={event=>{event.preventDefault();const input=document.querySelector<HTMLInputElement>('input[type=file]');if(input&&event.dataTransfer.files.length===1){const transfer=new DataTransfer();transfer.items.add(event.dataTransfer.files[0]);input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));}}}><strong>Host your NES file</strong><span>Drop any structurally valid .nes file or choose it locally.</span><button onClick={onChoose}>Choose NES file</button><label className="visibility"><input type="checkbox" checked={visibility==='unlisted'} onChange={event=>setVisibility(event.target.checked?'unlisted':'public')}/> Unlisted</label></article></section>
 {includedBusy&&<div className="catalog-status"><button onClick={()=>{cancelIncluded();client.current?.beginSelection();}}>Cancel loading</button></div>}{includedStatus&&<p className="catalog-status" role="status" data-testid="included-status">{includedStatus}</p>}
 <DirectoryPanel filterId={catalogFilter} onClearFilter={()=>setCatalogFilter(undefined)} connection={<ConnectionPolicyControl policy={policy} change={changePolicy}/>} state={state} onJoin={code=>void client.current?.joinCode(code)} onRetry={()=>void client.current?.watchDirectory()}/></>}
 <section id="room-session" className={`room-panel${invite&&!room?' invitation':''}${room&&!fingerprint?' pending-room':''}`} aria-labelledby="room-heading">
  {!room && !invite && <button onClick={onHost}>Host a game</button>}
  <h2 id="room-heading">{room ? room.label : invite ? 'Room invitation':'Play with a friend'}</h2>
  {!room && !invite && <><label className="visibility"><input type="checkbox" checked={visibility === 'unlisted'} onChange={event=>setVisibility(event.target.checked ? 'unlisted':'public')}/> Unlisted · invitation only</label><p>{visibility === 'public' ? 'Creates a public room; your file stays here.' : 'Creates an unlisted room; your file stays here.'} Players need their own matching file.</p></>}
  {invite && !room && state.preview && <p>{state.preview.label} · {state.preview.host} · {state.preview.occupancy}/2 places · {state.preview.status}. {state.preview.catalogId ? `${catalogEntry(state.preview.catalogId).title} is included; Join downloads its verified copy.` : 'Bring your own matching local game file.'}</p>}
  {room && <ControllerOwnership room={room}/>}
  <p role="status" data-testid="connection-status">{connectionStatus(state)}</p>
  {room&&!room.established&&<div className="room-invite"><strong>{room.visibility==='public'?`Public lobby · ${room.code}`:'Unlisted lobby · invite only'}</strong><label>Invitation <input aria-label="Room invitation" readOnly value={inviteUrl} onFocus={event=>event.currentTarget.select()}/></label><button onClick={()=>{void navigator.clipboard?.writeText(inviteUrl).then(()=>setCopy('Invitation copied.')).catch(()=>setCopy('Select the invitation text and copy it.'));if(!navigator.clipboard)setCopy('Select the invitation text and copy it.');}}>Copy invite</button><span className="hint">{copy}</span></div>}
  {(room||!invite)&&<details name="room-tools" className="session-settings"><summary>Connection and session settings</summary>
  <ConnectionPolicyControl policy={policy} change={changePolicy}/>
  <p className="hint">Player 2 remains reserved until both games acknowledge shared start. Fresh matching games start automatically. Progressed games stay paused until late-join support is available.</p>
  {room?.peer.epoch && <button onClick={()=>void client.current?.retryPeer()}>Retry connection</button>}
  {room?.peer.epoch && ['relay_unavailable','relay_capacity','failed'].includes(room.peer.status) && <><button onClick={()=>setStaying(room.peer.epoch)}>Stay in room</button>{staying===room.peer.epoch && <p role="status">You stayed in the room. Your current reservation deadline and local game are unchanged. Retry whenever you are ready.</p>}</>}
  <p role="status" aria-live="polite" data-testid="room-status">{state.status}</p>
  {state.retryAfterMs && <p>Wait at least {Math.ceil(state.retryAfterMs/1000)} seconds before retrying.</p>}
  {room && <div data-testid="room-view">
   <p><strong>{room.visibility === 'public' ? `Public · ${room.code}`:'Unlisted · invite only'}</strong> · {room.occupancy}/2 places · {room.status}</p>
   <p>You are {room.role === 'host' ? 'the host, Player 1':room.established?'Player 2':'Player 2 (reserved)'}. {room.guest ? `${room.guest} has the ${room.established?'established':'reserved'} guest place.`:'Waiting for a friend; local play can continue.'}</p>
   {room.reservationUntil && <p>Reservation expires at {new Date(room.reservationUntil).toLocaleTimeString()}. {room.matches ? 'Files match. Preparing the shared-play connection.' : 'The guest needs the exact matching file and emulator build; header differences also matter.'}</p>}
   {room.hostReconnectUntil && <p>Host disconnected. Return before {new Date(room.hostReconnectUntil).toLocaleTimeString()} to keep this room.</p>}
   {room.role === 'host' ? <details><summary>Session settings</summary>
    <label>Room name <input maxLength={80} value={label} onChange={event=>setLabel(event.target.value)}/></label><button disabled={!label.trim()} onClick={()=>void client.current?.act({type:'rename',roomId:room.id,label})}>Save room name</button>
    <label className="visibility"><input type="checkbox" checked={room.visibility === 'unlisted'} onChange={event=>{const visibility = event.target.checked ? 'unlisted':'public';if(visibility === 'public' && !window.confirm('Make this room public? Its room name and host nickname will be discoverable.')) return;void client.current?.act({type:'visibility',roomId:room.id,visibility});}}/> Unlisted · invitation only</label>
    {room.guest && <button onClick={()=>{if(window.confirm(`Remove ${room.guest}? Their reservation and reconnect permission will be revoked.`)) void client.current?.act({type:'kick',roomId:room.id,guestMembership:room.guestMembership!});}}>Remove guest</button>}
    <button onClick={()=>{if(window.confirm('Close this room for both players? Your local game stays available.')) void client.current?.act({type:'close',roomId:room.id});}}>Close room</button>
   </details> : <button onClick={()=>{if(!room.established||window.confirm('Leave shared play? The other player will pause; your local game is preserved.'))void client.current?.act({type:'leave',intent:room.reservationIntent!});}}>{room.established?'Leave shared game':'Cancel join'}</button>}
  </div>}
  </details>}
  {room&&<details name="room-tools" className="controller-disclosure"><summary>Session controllers</summary><ControllerMode room={room} act={command=>client.current!.act(command)}/></details>}
  {room && <section aria-label="Shared gameplay"><p role="status" data-testid="game-status">{room.game?.reason??state.gameplay?.status}</p><p data-testid="game-frame">{state.gameplay?.frame??0} shared frames · delay {state.gameplay?.delay??'negotiating'}</p>
   {room.established && ['paused','failed','resume_ready'].includes(room.game?.status??'') && <><button disabled={!!room.game?.controllerProposal} onClick={()=>client.current?.readyToResume()}>Ready to resume</button>{room.role==='host' && <button disabled={!!room.game?.controllerProposal||room.game?.status!=='resume_ready'} onClick={()=>client.current?.resumeTogether()}>Resume together</button>}<p role="status">{room.game?.status==='resume_ready' ? `Both players are ready. ${room.role==='host'?'Resume together when ready.':`Waiting for ${room.host} to resume.`}` : `Waiting for ${[!room.game?.ready?.includes('host') && room.host,!room.game?.ready?.includes('guest') && (room.guest??'Player 2')].filter(Boolean).join(' and ')} to resume.`}</p></>}
   {!room.established && ['failed','paused'].includes(room.game?.status??'') && <button onClick={()=>client.current?.retryGame()}>Retry shared play</button>}
  </section>}
  {room&&state.chat&&<details name="room-tools" className="chat-disclosure"><summary>Room chat</summary><ChatPanel state={state.chat} connected={state.connected} onDraft={text=>client.current?.chatDraft(text)} onSend={()=>void client.current?.sendChat()} onDiscard={()=>client.current?.discardChat()}/></details>}
  {room&&<details name="room-tools" className="voice-disclosure"><summary>Voice</summary><VoiceControls state={state.voice} voice={client.current?.voice}/></details>}
  <div className="controls">
   {state.busy && <button onClick={()=>client.current?.cancelPending()}>Cancel pending room action</button>}
   {!room && invite && <button disabled={state.busy} onClick={()=>void client.current?.join(invite)}>Retry join / Join</button>}
   {!room && !invite && fingerprint && <button disabled={state.busy} onClick={()=>void client.current?.host(fingerprint,visibility)}>Retry room creation</button>}
   {!state.connected && (state.room || state.admissionBlocked || /unavailable|lost|disconnected/.test(state.status)) && <button onClick={()=>void client.current?.reconnect()}>Reconnect rooms</button>}
  </div>
  {state.session && <details name="room-tools"><summary>Guest settings</summary><p className="hint">Temporary name for this browser tab. It is not an account.</p><label>Nickname <input maxLength={32} value={nickname} onChange={event=>setNickname(event.target.value)}/></label><button disabled={!nickname.trim()} onClick={()=>void client.current?.act({type:'nickname',nickname})}>Save nickname</button></details>}
  {state.needsNewGuest && <button onClick={()=>client.current?.newGuest()}>Start a new guest session</button>}
 </section></>;
});
