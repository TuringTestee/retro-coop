import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {catalogEntry,catalogId,type CatalogId} from '../../../packages/contracts/src/catalog.ts';
import {matchesFile,type Fingerprint,type NewVisibility,type RoomView} from '../../../packages/contracts/src/rooms.ts';
import {RoomClient,type RoomState} from './room-client.ts';
import {downloadCatalogEntry} from './catalog-download.ts';
import {acquireMemberRom,MemberReservationExpiredError} from './member-rom.ts';
import {connectionStatus} from './connection-status.ts';
import type {GameSelectionResult,LocalPlayer} from './player.ts';
import type {SaveSlot} from './saves.ts';
import type {Controls} from './controls.ts';
import type {VoiceSession,VoiceState} from './voice.ts';

type Operation={roomId:string;membership:string;target:RoomView;controller:AbortController;loading:boolean};
type IncludedOperation={id:CatalogId;membership:string;target?:RoomView;controller:AbortController;loading:boolean;candidate:boolean};
export type RoomControllerHandle={
 loadSaved(record:SaveSlot,current:()=>Promise<boolean>):Promise<void>;decideLoad(accept:boolean):Promise<void>;cancelLoad():Promise<void>;
 currentMembership(roomId:string,membership:string,unusedHost?:boolean):boolean;restoreGame(frame:number,hash:string,current:()=>boolean):Promise<void>;voice():VoiceSession|undefined;setNickname(name:string):Promise<boolean>;localPlayIntent():void;observeGame():void;cancelPreparation():void;readyToResume():void;resumeTogether():void;pauseTogether():void;
 prepareFile(file:File,signal:AbortSignal):Promise<File>;reconcileSelection():Promise<void>;cancelSelection():void;cancelCreation():void;
 leaveNow():Promise<boolean>;joinCode(code:string,password?:string):Promise<void>;joinInvite(invite:string,password?:string):Promise<void>;retryDirectory():Promise<void>;reconnect():Promise<void>;retryPeer(pairId:string):Promise<void>;clearAdmissionError():void;cancelJoin():void;
 act:RoomClient['act'];chatDraft(text:string):void;sendChat():Promise<void>;discardChat():void;ready():void;unready():void;start(fingerprint:Fingerprint):Promise<void>;
 loadIncluded(id:CatalogId):Promise<void>;retryMemberGame():Promise<void>;syncInvitation(invite:string|null):void;beforeSelection():boolean;approveSelection(fingerprint:Fingerprint,isCurrent:()=>boolean):Promise<boolean>;
 createLobby(label:string,visibility:NewVisibility,password?:string):Promise<{ok:boolean;message?:string;room?:RoomView}>;selectLobbyGame(file:File,fingerprint:Fingerprint,title:string,current:()=>boolean):Promise<GameSelectionResult>;
};

export const RoomController=forwardRef<RoomControllerHandle,{
 state:RoomState;onAcquired:(file:File,current:()=>boolean)=>boolean;selectionLoading:boolean;controls:Controls;fingerprint?:Fingerprint;player:()=>LocalPlayer|null;
 onVoice:(state:VoiceState|undefined)=>void;onNickname:(name:string)=>void;onConnection:(status:string)=>void;onRoomChange:(room?:RoomView)=>void;onState:(state:RoomState)=>void;onNotice:(message:string)=>void;onGameProgress:(message:string)=>void;
}>(function RoomController({state,onAcquired,selectionLoading,controls,fingerprint,player,onVoice,onNickname,onConnection,onRoomChange,onState,onNotice,onGameProgress},ref){
 const [invite,setInvite]=useState(()=>new URLSearchParams(location.hash.slice(1)).get('invite'));
 const client=useRef<RoomClient|null>(null),member=useRef<Operation|undefined>(undefined),included=useRef<IncludedOperation|undefined>(undefined);
 const room=useRef<RoomView|undefined>(undefined),connected=useRef(false),seenFile=useRef<Fingerprint|undefined>(undefined),sentFile=useRef(''),attemptedIncluded=useRef('');
 const voiceStartedRoom=useRef('');
 room.current=state.room;connected.current=state.connected;
 const membership=state.room?`${state.room.id}:${state.room.role}:${state.room.chatMembership}`:'';

 const acquisitionCurrent=(target:RoomView)=>{const active=room.current;return connected.current&&active?.id===target.id&&active.chatMembership===target.chatMembership&&active.role===target.role&&active.slot===target.slot&&active.game.controllers.revision===target.game.controllers.revision&&active.game.epoch===target.game.epoch&&!!active.fingerprint&&!!target.fingerprint&&matchesFile(active.fingerprint,target.fingerprint);};
 const memberCurrent=(operation:Operation)=>member.current===operation&&!operation.controller.signal.aborted&&acquisitionCurrent(operation.target);
 const cancelMember=()=>{const operation=member.current;member.current=undefined;operation?.controller.abort();if(operation?.loading)player()?.cancel();if(operation)onGameProgress('');};
 const cancelIncluded=()=>{const operation=included.current;included.current=undefined;operation?.controller.abort();if(operation?.candidate)player()?.cancel();if(operation)onGameProgress('');};
 const acquireMember=async(target:RoomView)=>{
  if(target.catalogId||!target.fingerprint)return;
  cancelMember();const token=client.current?.memberToken();if(!token){onNotice('Reconnect to download the lobby game.');return;}
  const operation:Operation={roomId:target.id,membership:target.chatMembership,target,controller:new AbortController(),loading:false};member.current=operation;
  const current=()=>memberCurrent(operation),expected=target.fingerprint;
  onNotice('Checking the lobby game…');onGameProgress('Checking the lobby game…');void client.current?.memberAcquisition(target.id,target.chatMembership,'checking');
  try{
   const result=await acquireMemberRom(target,token,operation.controller.signal,()=>{if(current()){onNotice('Downloading the lobby game…');onGameProgress('Downloading the lobby game…');void client.current?.memberAcquisition(target.id,target.chatMembership,'downloading');}},current);
   if(!current())return;
   onNotice('Loading the lobby game…');onGameProgress('Loading the lobby game…');void client.current?.memberAcquisition(target.id,target.chatMembership,'loading');
   if(!onAcquired(result.file,current))throw Error('The lobby game could not start loading. Retry download.');
   operation.loading=true;
  }catch(error){if(member.current===operation){onGameProgress('');onNotice(error instanceof MemberReservationExpiredError?'Your place expired. Join again.':error instanceof Error?error.message:'Download failed. Retry download.');void client.current?.memberAcquisition(target.id,target.chatMembership,'failed');}}
 };
 const loadIncluded=async(id:CatalogId)=>{
  const entry=catalogEntry(id),currentRoom=room.current;
  if(currentRoom?.established&&currentRoom.catalogId!==id||currentRoom?.role==='member'&&currentRoom.catalogId!==id){onNotice('Return to a lobby before changing the game.');return;}
  if(fingerprint&&player()?.isLoaded(fingerprint)&&catalogId(fingerprint)===id&&(currentRoom?.role!=='host'||currentRoom.catalogId===id)){if(currentRoom?.role==='member')void client.current?.memberAcquisition(currentRoom.id,currentRoom.chatMembership,'loaded');onNotice('');return;}
  if(client.current?.beginSelection()===false)return;cancelIncluded();
  const operation:IncludedOperation={id,membership:currentRoom?`${currentRoom.id}:${currentRoom.role}:${currentRoom.chatMembership}`:'',target:currentRoom,controller:new AbortController(),loading:false,candidate:false};included.current=operation;
  const current=()=>included.current===operation&&!operation.controller.signal.aborted&&(currentRoom?room.current?.id===currentRoom.id&&room.current.chatMembership===currentRoom.chatMembership&&room.current.role===currentRoom.role&&(currentRoom.started?acquisitionCurrent(currentRoom):!room.current.started):!room.current);
  const progress=(message:string)=>onGameProgress(message);
  onNotice(`Downloading ${entry.title}…`);progress(`Downloading ${entry.title}…`);if(currentRoom)void client.current?.memberAcquisition(currentRoom.id,currentRoom.chatMembership,'downloading');
  const timeout=setTimeout(()=>operation.controller.abort(Error('The download timed out. Retry.')),15000);
  try{
   const file=await downloadCatalogEntry(entry,operation.controller.signal,()=>{if(current()){onNotice(`Downloading ${entry.title}…`);progress(`Downloading ${entry.title}…`);}});
   if(!current())return;
   operation.candidate=true;onNotice(`Loading ${entry.title}…`);progress(`Loading ${entry.title}…`);if(currentRoom)void client.current?.memberAcquisition(currentRoom.id,currentRoom.chatMembership,'loading');
   if(!onAcquired(file,current))throw Error(`Could not load ${entry.title}. Retry.`);
  }catch(error){if(included.current===operation){if(currentRoom)void client.current?.memberAcquisition(currentRoom.id,currentRoom.chatMembership,'failed');onNotice(error instanceof Error?error.message:`Could not load ${entry.title}. Retry.`);progress('');included.current=undefined;}}
  finally{clearTimeout(timeout);}
 };

 useEffect(()=>{const rooms=new RoomClient(onState,player);client.current=rooms;void rooms.watchDirectory();return()=>{cancelIncluded();cancelMember();rooms.dispose();client.current=null;};},[]);
 useEffect(()=>{if(invite)void client.current?.preview(invite);else client.current?.clearPreview();},[invite]);
 useEffect(()=>{client.current?.voice.configureControls(controls);},[controls]);
 useEffect(()=>onVoice(state.voice),[state.voice,onVoice]);
 useEffect(()=>{const id=state.room?.id;if(!id){voiceStartedRoom.current='';return;}if(state.voice?.connected&&voiceStartedRoom.current!==id){voiceStartedRoom.current=id;const voice=client.current?.voice;if(voice){voice.microphone.mode('push');void voice.enable();}}},[state.room?.id,state.voice?.connected]);
 useEffect(()=>onConnection(connectionStatus(state)),[state.connection,state.room?.peers,onConnection]);
 useEffect(()=>{if(state.session)onNickname(state.session.nickname);},[state.session,onNickname]);
 useEffect(()=>onRoomChange(state.room),[state.room,onRoomChange]);
 useEffect(()=>{if(included.current&&included.current.membership!==membership)cancelIncluded();if(state.releaseNotice){cancelIncluded();cancelMember();}},[membership,state.releaseNotice]);
 // Server confirmation can render before the local candidate commits; that selection still owns loading.
 useEffect(()=>{const target=room.current;if(target?.role==='host'&&!target.started&&(selectionLoading||client.current?.selectionPending()))return;if(state.connected&&target&&!target.catalogId&&target.fingerprint){if(fingerprint&&matchesFile(target.fingerprint,fingerprint)&&player()?.isLoaded(fingerprint)){void client.current?.memberAcquisition(target.id,target.chatMembership,'loaded');onNotice('');}else void acquireMember(target);}else cancelMember();return()=>cancelMember();},[state.connected,membership,state.room?.fingerprint?.romSha256,state.room?.game.epoch,state.room?.game.controllers.revision,state.room?.slot]);
 useEffect(()=>{if(!state.connected&&member.current){cancelMember();onNotice('Connection lost. Reconnect to retry the game download.');}},[state.connected]);
 useEffect(()=>{const operation=member.current;if(!operation||!memberCurrent(operation)||!operation.loading)return;if(selectionLoading)return;onGameProgress('');if(fingerprint&&room.current?.fingerprint&&matchesFile(room.current.fingerprint,fingerprint)&&player()?.isLoaded(fingerprint)){operation.loading=false;onNotice('');void client.current?.memberAcquisition(operation.roomId,operation.membership,'loaded');}else{operation.loading=false;onNotice('The game could not load. Retry download.');void client.current?.memberAcquisition(operation.roomId,operation.membership,'failed');}},[selectionLoading,fingerprint]);
 useEffect(()=>{const operation=included.current;if(!operation?.candidate)return;if(selectionLoading){operation.loading=true;return;}if(operation.loading){operation.candidate=false;const loaded=!!fingerprint&&catalogId(fingerprint)===operation.id;included.current=undefined;onNotice(loaded?'':'The game could not load. Retry.');onGameProgress('');}},[selectionLoading,fingerprint]);
 useEffect(()=>{const target=state.room;if(!target?.catalogId){attemptedIncluded.current='';return;}if(!state.connected)return;const key=`${membership}:${target.catalogId}`;if(attemptedIncluded.current===key)return;attemptedIncluded.current=key;if(!selectionLoading&&(!fingerprint||!player()?.isLoaded(fingerprint)||catalogId(fingerprint)!==target.catalogId))void loadIncluded(target.catalogId);},[state.connected,membership,state.room?.catalogId]);
 useEffect(()=>{if(!fingerprint||seenFile.current===fingerprint)return;seenFile.current=fingerprint;client.current?.selectedGame(fingerprint);},[fingerprint]);
 useEffect(()=>{const target=state.room;if(!fingerprint||target?.role!=='member'){sentFile.current='';return;}const key=target.id+fingerprint.romSha256+fingerprint.coreSha256;if(sentFile.current!==key){sentFile.current=key;void client.current?.act({type:'file',fingerprint});}},[fingerprint,state.room?.id,state.room?.role]);

 useImperativeHandle(ref,()=>({
  prepareFile(file,signal){return client.current?.prepareFile(file,signal)??Promise.reject(Error('The game service is unavailable. Retry.'));},
  async reconcileSelection(){const complete=player()?.selectionCompletion();const result=await client.current?.reconcileGameSelection();if(result)complete?.(result);},
  loadSaved(record,current){return client.current?.loadSaved(record,current)??Promise.reject(Error('Lobby unavailable.'));},decideLoad(accept){return client.current?.decideLoad(accept)??Promise.reject(Error('Lobby unavailable.'));},cancelLoad(){return client.current?.cancelLoad()??Promise.reject(Error('Lobby unavailable.'));},
  currentMembership(roomId,membership,unusedHost){return client.current?.currentMembership(roomId,membership,unusedHost)??false;},restoreGame(frame,hash,current){return client.current?.restoreGame(frame,hash,current)??Promise.reject(Error('Lobby unavailable.'));},voice:()=>client.current?.voice,setNickname(name){return client.current?.act({type:'nickname',nickname:name})??Promise.resolve(false);},localPlayIntent(){client.current?.localPlayIntent();},observeGame(){client.current?.retryGame();},cancelPreparation(){client.current?.cancelSynchronization();},readyToResume(){client.current?.readyToResume();},resumeTogether(){client.current?.resumeTogether();},pauseTogether(){client.current?.pauseTogether();},
  cancelSelection(){cancelIncluded();cancelMember();client.current?.cancelGameSelection();onGameProgress('');},cancelCreation(){client.current?.cancelCreation();},
  // A rejected exit keeps preparation alive; successful membership loss owns cancellation.
  async leaveNow(){const target=room.current;if(!target)return true;const ok=target.role==='host'?await client.current?.act({type:'close',roomId:target.id}):await client.current?.act({type:'leave',intent:target.reservationIntent});if(ok){cancelIncluded();cancelMember();}return !!ok;},
  joinCode(code,password){return client.current?.joinCode(code,password)??Promise.resolve();},joinInvite(value,password){return client.current?.join(value,password)??Promise.resolve();},retryDirectory(){return client.current?.watchDirectory()??Promise.resolve();},reconnect(){return client.current?.reconnect()??Promise.resolve();},retryPeer(pairId){return client.current?.retryPeer(pairId)??Promise.resolve();},clearAdmissionError(){client.current?.clearAdmissionError();},cancelJoin(){client.current?.cancelJoin();},
  act(command){return client.current?.act(command)??Promise.resolve(false);},chatDraft(text){client.current?.chatDraft(text);},sendChat(){return client.current?.sendChat()??Promise.resolve();},discardChat(){client.current?.discardChat();},ready(){client.current?.prepareMember();},unready(){client.current?.cancelSynchronization();},start(file){return client.current?.startRoom(file)??Promise.resolve();},loadIncluded,retryMemberGame(){const target=room.current;return target&&!target.catalogId&&target.fingerprint?acquireMember(target):Promise.resolve();},syncInvitation(value){setInvite(value);},
  beforeSelection(){if(state.startingRoom||state.room?.role==='member'&&!state.room.catalogId)return false;if(client.current?.beginSelection()===false)return false;cancelIncluded();return true;},
  approveSelection(value,isCurrent){if(state.room?.role==='member'&&!state.room.catalogId){const operation=member.current;return Promise.resolve(!!operation&&memberCurrent(operation)&&isCurrent()&&!!state.room.fingerprint&&matchesFile(state.room.fingerprint,value));}return client.current?.approveSelection(value,isCurrent)??Promise.resolve(isCurrent());},
  createLobby(label,visibility,password){return client.current?.createLobby(label,visibility,password)??Promise.resolve({ok:false,message:'Could not create the lobby. Retry.'});},
  async selectLobbyGame(file,value,title,current){const result=await client.current?.selectLobbyGame(file,value,title,current)??{ok:false,message:'Could not add this NES game to the lobby. Retry or choose another.'};if(result.ok)onNotice('');if(current())onGameProgress('');return result;}
 }));
 return null;
});
