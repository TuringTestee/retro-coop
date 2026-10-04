import React,{useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {LocalPlayer,type PlayerState} from './player.ts';
import {neutralDefaults} from './cartridge.ts';
import {RoomController,type RoomControllerHandle} from './RoomController.tsx';
import type {RoomState} from './room-client.ts';
import type {VoiceState} from './voice.ts';
import {AppShell,type ShellPage} from './AppShell.tsx';
import {LobbyDirectory} from './UnifiedScreens.tsx';
import {SessionStage} from './SessionStage.tsx';
import {Settings} from './Settings.tsx';
import {Saves} from './Saves.tsx';
import {Rewind} from './Rewind.tsx';
import {LocalData} from './LocalData.tsx';
import {defaults,type Controls} from './controls.ts';
import {usePreferences} from './preferences.ts';
import {fileIdentity} from '../../../packages/contracts/src/fingerprint.ts';
import {savedCandidate,candidateStillStored} from './rom-library.ts';
import {HostRecoveryCapture,recoveryOffer,validRecovery,type RecoveryOffer} from './host-recovery.ts';
import {catalog} from '../../../packages/contracts/src/catalog.ts';
import {downloadCatalogEntry} from './catalog-download.ts';
import {rememberImport} from './rom-library.ts';
import {readRecovery,changeRecovery,listSaves,putSave,sameRecord,type SaveSlot} from './saves.ts';
import {matchesFile,validRoomPassword,type Fingerprint,type RoomView} from '../../../packages/contracts/src/rooms.ts';
import type {RoomSlot} from '../../../packages/contracts/src/slots.ts';
import './unified.css';

type Side='identity'|'voice'|'settings'|'lobby'|null;
type Tool='saves'|'rewind'|'localData'|null;
type GameAction={label:string;run:()=>void;disabled?:boolean;keyboard?:boolean};
const initialPlayer:PlayerState={status:'Choose a game to start playing.',loading:false,running:false,loaded:false,frames:0};
const initialRooms:RoomState={status:'',busy:false,connected:false};
const inviteFromUrl=()=>new URLSearchParams(location.hash.slice(1)).get('invite');
const randomLobbyName=()=>{
 const words=['Amber Arcade','Copper Castle','Pixel Harbor','Silver Quest','Maple Station','Golden Valley'];
 const values=crypto.getRandomValues(new Uint32Array(2));
 return `${words[values[0]%words.length]} ${String(values[1]%10000).padStart(4,'0')}`;
};

function App(){
 const canvas=useRef<HTMLCanvasElement>(null),picker=useRef<HTMLInputElement>(null),player=useRef<LocalPlayer|null>(null),rooms=useRef<RoomControllerHandle>(null);
 const [playerState,setPlayerState]=useState<PlayerState>(initialPlayer),[roomState,setRoomState]=useState<RoomState>(initialRooms),[room,setRoom]=useState<RoomView>();
 const [page,setPage]=useState<'main'|'lobbies'|'local'>(()=>inviteFromUrl()?'lobbies':'main');
 const [invite,setInvite]=useState<string|null>(inviteFromUrl),[invitePassword,setInvitePassword]=useState(''),[side,setSide]=useState<Side>(null),[tool,setTool]=useState<Tool>(null);
 const [inviteCopyFallback,setInviteCopyFallback]=useState<{roomId:string;membership:string;link:string}|null>(null);
 const inviteAttempt=useRef(0);
 const [recovery,setRecovery]=useState<RecoveryOffer>(),[recoveryIndex,setRecoveryIndex]=useState(0),[recoveryError,setRecoveryError]=useState(''),[recoveryBusy,setRecoveryBusy]=useState(false),[recoveryCommitting,setRecoveryCommitting]=useState(false),[automaticIssue,setAutomaticIssue]=useState('');
 const recoverySerial=useRef(0),recoveryCommit=useRef(false),recoveryAbort=useRef<AbortController|undefined>(undefined),captureOwner=useRef<HostRecoveryCapture|undefined>(undefined);
 const [quickLoad,setQuickLoad]=useState<SaveSlot>();
 const quickBusy=useRef(false);
 const quickEpoch=useRef(0),quickLoadVersion=useRef(0);
 const quickScope=useRef<{page:ShellPage;roomId?:string;membership?:string;leaving:boolean}>({page:'main',leaving:false});
 const [editTarget,setEditTarget]=useState<'name'|'lobby'|null>(null),[editDraft,setEditDraft]=useState(''),[editError,setEditError]=useState(''),[editBusy,setEditBusy]=useState(false);
 const editReturnFocus=useRef<HTMLButtonElement|null>(null);
 const [statusOverride,setStatusOverride]=useState(''),[slotFeedback,setSlotFeedback]=useState(''),[slotInspect,setSlotInspect]=useState(''),[gameProgress,setGameProgress]=useState(''),[exitPrompt,setExitPrompt]=useState(false),[exitBusy,setExitBusy]=useState(false),[kick,setKick]=useState<{id:string;name:string}>();
 const [clock,setClock]=useState(Date.now());
 const [guest,setGuest]=useState(()=>neutralDefaults().guest),[voice,setVoice]=useState<VoiceState>(),[connection,setConnection]=useState(''),[controls,setControls]=useState<Controls>(defaults),[filter,setFilter]=useState<'nearest'|'scanlines'>('nearest'),[volume,setVolume]=useState(1),[muted,setMuted]=useState(false);
 const [imported,setImported]=useState<File|null>(null),[persistenceMessage,setPersistenceMessage]=useState('');
 const [viewport,setViewport]=useState(()=>({width:window.innerWidth,height:window.innerHeight}));
 const [theme,setTheme]=useState<'light'|'dark'>(()=>document.documentElement.dataset.theme==='dark'?'dark':'light');
 useEffect(()=>{document.documentElement.dataset.theme=theme;},[theme]);
 const toggleTheme=()=>{const next=theme==='light'?'dark':'light';setTheme(next);try{localStorage.setItem('retro-coop-theme',next);}catch{}};
 const selection=useRef<{file:File;serial:number}|undefined>(undefined),selectionSerial=useRef(0),createSerial=useRef(0),joinSerial=useRef(0),exitTarget=useRef<string|undefined>(undefined);
 const previousRoom=useRef<string|undefined>(undefined),exitInProgress=useRef(false);
 const inviteContext=useRef({roomId:room?.id,membership:room?.chatMembership,leaving:exitPrompt||exitBusy});
 inviteContext.current={roomId:room?.id,membership:room?.chatMembership,leaving:exitPrompt||exitBusy};
 const recoveryContext=useRef({room,playerState,leaving:exitPrompt||exitBusy});
 recoveryContext.current={room,playerState,leaving:exitPrompt||exitBusy};
 useEffect(()=>{
  const active=player.current,file=playerState.fingerprint;
  if(!active||room?.role!=='host'||!room.started||!file||!room.fingerprint||!matchesFile(room.fingerprint,file))return;
  const id=room.id,membership=room.chatMembership,version=active.selectionVersion();
  const current=()=>{const context=recoveryContext.current;return !!rooms.current?.currentMembership(id,membership)&&context.room?.id===id&&context.room.chatMembership===membership&&context.room.role==='host'&&!context.leaving&&active.selectionVersion()===version&&active.isLoaded(file);};
  const owner=new HostRecoveryCapture(active,file,room.gameTitle??'NES game',current,setAutomaticIssue);captureOwner.current=owner;
  return()=>{owner.stop();if(captureOwner.current===owner)captureOwner.current=undefined;};
 },[room?.id,room?.started,room?.role,playerState.fingerprint]);
 useEffect(()=>{if(room?.game.status==='paused'&&!playerState.running&&!playerState.loading)void captureOwner.current?.capture();},[room?.game.status,playerState.running,playerState.loading]);
 useEffect(()=>{if(!room||room.role!=='host'||room.started){++recoverySerial.current;setRecovery(undefined);setRecoveryBusy(false);setRecoveryCommitting(false);recoveryCommit.current=false;}},[room?.id,room?.role,room?.started]);
 const preferencesIdentity=playerState.fingerprint?fileIdentity(playerState.fingerprint):undefined;
 const preferences=usePreferences(preferencesIdentity,value=>{setControls(value.controls);player.current?.configureControls(value.controls);setFilter(value.filter);setVolume(value.volume);player.current?.setVolume(value.volume);});
 useEffect(()=>{if(!canvas.current)return;const current=new LocalPlayer(canvas.current,setPlayerState);player.current=current;return()=>{current.dispose();if(player.current===current)player.current=null;};},[]);
 useEffect(()=>{player.current?.setMuted(muted);},[muted]);
 useEffect(()=>{if(room?.game.status!=='countdown')return;setClock(Date.now());const timer=setInterval(()=>setClock(Date.now()),100);return()=>clearInterval(timer);},[room?.game.status,room?.game.startAt]);
 useEffect(()=>{setSlotFeedback('');setSlotInspect('');},[room?.id,room?.revision,room?.game.status,playerState.loading]);
 useEffect(()=>{if(!playerState.loaded||!playerState.fingerprint||!imported)return;const file=imported;setImported(null);void rememberImport(file,playerState.fingerprint.romSha256).then(()=>setPersistenceMessage('')).catch(()=>setPersistenceMessage('This game is available in this tab only.'));},[playerState.loaded,playerState.fingerprint,imported]);
 useEffect(()=>{const pending=selection.current,file=playerState.fingerprint;if(!pending||playerState.selectionPhase!=='loaded'||!playerState.loaded||!file||!player.current?.isLoaded(file))return;selection.current=undefined;if(room?.role!=='host'||room.started)return;const title=pending.file.name.replace(/\.nes$/i,'').replace(/[\p{C}]/gu,'').trim().slice(0,80)||'NES game';void rooms.current?.selectLobbyGame(pending.file,file,title,()=>selectionSerial.current===pending.serial&&!!player.current?.isLoaded(file)).then(result=>{if(!result.ok&&selectionSerial.current===pending.serial)setStatusOverride(result.message??'Could not add this NES game to the lobby. Retry or choose another.');});},[playerState.selectionPhase,playerState.loaded,playerState.fingerprint,room?.id]);
 useEffect(()=>{if(!selection.current||playerState.selectionPhase!=='failed'&&playerState.selectionPhase!=='cancelled')return;selection.current=undefined;++selectionSerial.current;setGameProgress('');if(playerState.selectionPhase==='failed')setStatusOverride(playerState.status);},[playerState.selectionPhase,playerState.status]);
 useEffect(()=>{if(room?.id){if(previousRoom.current!==room.id){history.replaceState(null,'','/');history.pushState({lobby:room.id},'','/#lobby');}previousRoom.current=room.id;return;}if(!previousRoom.current)return;previousRoom.current=undefined;if(exitInProgress.current)return;exitTarget.current=undefined;player.current?.pause();void player.current?.quit().then(()=>{setPage('main');setInvite(null);rooms.current?.syncInvitation(null);setSide(null);setTool(null);setExitPrompt(false);setKick(undefined);setStatusOverride('');history.replaceState(null,'','/');});},[room?.id,exitBusy]);
 useEffect(()=>{const clicked=(event:PointerEvent)=>{if(side&&!room&&!(event.target as Element).closest('.rc-side-panel,.rc-mobile-side-panel,.rc-identity,.rc-public-side,.rc-game-links'))setSide(null);};const escaped=(event:KeyboardEvent)=>{if(event.key==='Escape'&&!event.defaultPrevented){if(kick)setKick(undefined);else if(exitPrompt){exitTarget.current=undefined;setExitPrompt(false);}else if(quickLoad)setQuickLoad(undefined);else if(inviteCopyFallback)setInviteCopyFallback(null);else if(editTarget&&!editBusy){setEditTarget(null);requestAnimationFrame(()=>editReturnFocus.current?.focus());}else if(tool)setTool(null);else if(!room)setSide(null);}};document.addEventListener('pointerdown',clicked);document.addEventListener('keydown',escaped);return()=>{document.removeEventListener('pointerdown',clicked);document.removeEventListener('keydown',escaped);};},[side,room,kick,exitPrompt,quickLoad,inviteCopyFallback,editTarget,editBusy,tool]);
 useEffect(()=>{if(editTarget==='lobby'&&room?.role!=='host')setEditTarget(null);},[editTarget,room?.role]);
 useEffect(()=>{if(!inviteCopyFallback)return;const frame=requestAnimationFrame(()=>{const field=document.querySelector<HTMLTextAreaElement>('.rc-invite-link');field?.focus();field?.select();});return()=>cancelAnimationFrame(frame);},[inviteCopyFallback]);
 useEffect(()=>{if(!['Invitation copied.','Saved to quick slot 1.','Quick slot 1 loaded. Choose Resume to play.'].includes(statusOverride))return;const timer=setTimeout(()=>setStatusOverride(''),3000);return()=>clearTimeout(timer);},[statusOverride]);
 useEffect(()=>{if(kick||exitPrompt||quickLoad)requestAnimationFrame(()=>document.querySelector<HTMLButtonElement>('.rc-dialog-card button')?.focus());},[kick,exitPrompt,quickLoad]);
 useEffect(()=>{const update=()=>setViewport({width:window.innerWidth,height:window.innerHeight});window.addEventListener('resize',update);return()=>window.removeEventListener('resize',update);},[]);
 const load=(file?:File,current?:()=>boolean):boolean=>{const isCurrent=current??(()=>true);if(!file||!player.current||!isCurrent()||!current&&rooms.current?.beforeSelection()===false)return false;++quickEpoch.current;setQuickLoad(undefined);if(room?.role==='host'&&!room.started)selection.current={file,serial:++selectionSerial.current};setStatusOverride('');setSlotFeedback('');setImported(file);void player.current.load(file,(fingerprint,stillCurrent)=>rooms.current?.approveSelection(fingerprint,stillCurrent)??Promise.resolve(stillCurrent()),true,isCurrent);return true;};
 const choose=()=>{picker.current!.value='';picker.current!.click();};
 const openSettings=(_section:'controls'|'voice')=>{setSide('settings');setTool(null);};
 const chooseKeyboard=()=>{const next={...controls,device:null};setControls(next);player.current?.useKeyboard();preferences.remember({controls:next,filter,volume});};
 const cancelGameSelection=()=>{selection.current=undefined;++selectionSerial.current;player.current?.cancel();rooms.current?.cancelSelection();setGameProgress('');setStatusOverride(room?'Selection cancelled. The lobby stays open.':playerState.loaded?'Selection cancelled. Your previous game is still here.':'Selection cancelled. Choose a game whenever you’re ready.');};
 const changePage=(next:'main'|'lobbies')=>{++createSerial.current;++joinSerial.current;rooms.current?.cancelCreation();rooms.current?.cancelJoin();setInvite(null);rooms.current?.syncInvitation(null);setPage(next);setSide(null);setSlotInspect('');setStatusOverride('');history.pushState(null,'','/');};
 const finishExit=async()=>{if(exitBusy)return;++inviteAttempt.current;setInviteCopyFallback(null);const requestedDestination=exitTarget.current;exitInProgress.current=true;setExitBusy(true);setStatusOverride('Leaving the current game…');try{if(room&&!await rooms.current?.leaveNow()){setStatusOverride('Could not leave. Retry or stay in the lobby.');return;}await player.current?.quit();const destination=requestedDestination?new URL(requestedDestination):undefined,nextInvite=destination?new URLSearchParams(destination.hash.slice(1)).get('invite'):null;previousRoom.current=undefined;setRoom(undefined);setInvite(nextInvite);rooms.current?.syncInvitation(nextInvite);setExitPrompt(false);setKick(undefined);setSide(null);setTool(null);setPage(nextInvite?'lobbies':'main');history.replaceState(null,'',destination?.pathname==='/create'?'/':destination?.href??'/');exitTarget.current=undefined;setStatusOverride('');}finally{exitInProgress.current=false;setExitBusy(false);}};
 const backToMain=(destination?:string)=>{++quickEpoch.current;++inviteAttempt.current;setQuickLoad(undefined);setInviteCopyFallback(null);exitTarget.current=destination;if(room){setStatusOverride('');setExitPrompt(true);setSide(null);return;}if(page==='local'||playerState.loaded||playerState.loading){void finishExit();return;}changePage('main');};
 useEffect(()=>{const route=()=>{const target=location.href,nextInvite=inviteFromUrl();if(room){history.replaceState(null,'','/');history.pushState({lobby:room.id},'','/#lobby');if(!exitTarget.current)backToMain(location.origin+'/');return;}if(page==='local'||playerState.loaded||playerState.loading){history.replaceState(null,'','/');if(!exitTarget.current)backToMain(target);return;}++createSerial.current;++joinSerial.current;rooms.current?.cancelCreation();rooms.current?.cancelJoin();setInvite(nextInvite);rooms.current?.syncInvitation(nextInvite);setPage(nextInvite?'lobbies':'main');setSide(null);setTool(null);setSlotInspect('');setStatusOverride('');};addEventListener('popstate',route);addEventListener('hashchange',route);return()=>{removeEventListener('popstate',route);removeEventListener('hashchange',route);};},[room,page,playerState.loaded,playerState.loading]);
 const createLobby=async()=>{if(roomState.busy)return;const serial=++createSerial.current;setStatusOverride('Creating lobby…');const result=await rooms.current?.createLobby(randomLobbyName(),'public');if(serial!==createSerial.current)return;if(result?.ok){setStatusOverride('');try{const offer=await recoveryOffer();if(serial!==createSerial.current)return;setRecoveryIndex(0);setRecoveryError('');setRecovery(offer);}catch(error){setStatusOverride(error instanceof Error?error.message:'Recovery storage is unavailable. Load a game normally.');}}else setStatusOverride(result?.message??'Could not create the lobby. Retry.');};
 const joinCode=(code:string,secret?:string)=>{const serial=++joinSerial.current;setStatusOverride('Joining lobby…');void rooms.current?.joinCode(code,secret).finally(()=>{if(serial===joinSerial.current)setStatusOverride('');});};
 const joinInvite=()=>{if(!invite)return;const serial=++joinSerial.current;setStatusOverride('Joining lobby…');void rooms.current?.joinInvite(invite,roomState.preview?.visibility==='protected'?invitePassword:undefined).finally(()=>{if(serial===joinSerial.current)setStatusOverride('');});};
 const requestKick=(slot:RoomSlot)=>{if(slot.member){setStatusOverride('');setSlotFeedback('');setKick({id:slot.member.id,name:slot.member.nickname});}};
 const confirmKick=async()=>{if(!room||!kick)return;const ok=await rooms.current?.act({type:'memberRemove',roomId:room.id,membership:kick.id,expectedRevision:room.revision});if(ok){setKick(undefined);setStatusOverride('');}else setStatusOverride(`Could not kick ${kick.name}.`);};
 const inviteLink=room?`${location.origin}/#invite=${room.invite}`:undefined;
 const copyInvite=()=>{if(!inviteLink||!room)return;const attempt=++inviteAttempt.current,context={roomId:room.id,membership:room.chatMembership,link:inviteLink};setInviteCopyFallback(null);const current=()=>inviteAttempt.current===attempt&&inviteContext.current.roomId===context.roomId&&inviteContext.current.membership===context.membership&&!inviteContext.current.leaving;void (async()=>{try{await navigator.clipboard.writeText(context.link);if(current()){setStatusOverride('Invitation copied.');setInviteCopyFallback(null);}}catch{if(current())setInviteCopyFallback(context);}})();};
 const currentPage:ShellPage=room?.started?'playing':room?'lobby':playerState.loaded?'local':page;
 quickScope.current={page:currentPage,roomId:room?.id,membership:room?.chatMembership,leaving:exitPrompt||exitBusy};
 useEffect(()=>{if(currentPage!=='local'||playerState.loading)setQuickLoad(undefined);},[currentPage,playerState.loading]);
 useEffect(()=>{
  const shortcut=(event:KeyboardEvent)=>{
   if(!playerState.loaded||playerState.loading||tool||exitPrompt||kick||quickLoad||editTarget||recovery||event.repeat||event.altKey||event.ctrlKey||event.metaKey||((event.target as Element)?.closest('input,textarea,select,[contenteditable="true"],dialog')))return;
   if(event.code==='KeyM'&&(currentPage==='local'||currentPage==='playing')&&!Object.values(controls.keyboard).some(bindings=>bindings.includes('KeyM'))){
    event.preventDefault();setMuted(value=>!value);return;
   }
   if(!['local','playing'].includes(currentPage)||event.code!=='KeyQ'&&!(currentPage==='local'&&event.code==='KeyE')||Object.values(controls.keyboard).some(bindings=>bindings.includes(event.code)))return;
   event.preventDefault();if(quickBusy.current)return;
   const active=player.current,fingerprint=playerState.fingerprint;if(!active||!fingerprint)return;
   const version=active.selectionVersion(),epoch=quickEpoch.current,roomId=room?.id,membership=room?.chatMembership;
   const current=()=>active===player.current&&version===active.selectionVersion()&&epoch===quickEpoch.current&&!quickScope.current.leaving&&quickScope.current.page===currentPage&&quickScope.current.roomId===roomId&&quickScope.current.membership===membership&&active.isLoaded(fingerprint);
   quickBusy.current=true;
   void (async()=>{
    try{
     const info=await active.saveInfo();if(!current())return;
     const prior=(await listSaves(info.identity)).find(row=>row.slot===1);if(!current())return;
     if(event.code==='KeyQ'){
      const bytes=await active.exportSave();if(!current())return;
      await putSave({identity:info.identity,slot:1,savedAt:Date.now(),bytes},prior);
      if(current())setStatusOverride('Saved to quick slot 1.');
     }else if(prior){quickLoadVersion.current=version;setQuickLoad(prior);}
     else setStatusOverride('Quick slot 1 is empty. Press Q to save.');
    }catch(error){if(current())setStatusOverride(error instanceof Error?error.message:'Save shortcut failed. Open Saves to retry.');}
    finally{quickBusy.current=false;}
   })();
  };
  window.addEventListener('keydown',shortcut);return()=>window.removeEventListener('keydown',shortcut);
 },[currentPage,playerState.loaded,playerState.loading,playerState.fingerprint,room?.id,room?.chatMembership,controls,tool,exitPrompt,kick,quickLoad,editTarget,recovery]);
 const confirmQuickLoad=()=>{const active=player.current,fingerprint=playerState.fingerprint,selected=quickLoad;if(!active||!fingerprint||!selected)return;const version=quickLoadVersion.current,epoch=quickEpoch.current;const current=()=>player.current===active&&active.selectionVersion()===version&&quickEpoch.current===epoch&&quickScope.current.page==='local'&&!quickScope.current.leaving&&active.isLoaded(fingerprint);setQuickLoad(undefined);void (async()=>{try{if(!current())return;const latest=(await listSaves(selected.identity)).find(row=>row.slot===1);if(!current())return;if(!sameRecord(latest,selected))throw Error('Quick save changed. Press E again to load the current slot.');await active.loadSave(selected.bytes);if(current())setStatusOverride('Quick slot 1 loaded. Choose Resume to play.');}catch(error){if(current())setStatusOverride(error instanceof Error?error.message:'Could not load quick slot 1.');}})();};
 const tooSmall=viewport.width<320||viewport.height<568&&['lobby','playing','local'].includes(currentPage);
 useEffect(()=>{if(tooSmall){setTool(null);setSide(null);}},[tooSmall]);
 const self=room?.slots.find(slot=>slot.member?.id===room.chatMembership),observer=self?.role==='observer',ready=!!room?.game.ready.includes(room.chatMembership);
 const unready=room?.slots.filter(slot=>slot.member&&slot.role!=='observer'&&!room.game.ready.includes(slot.member.id)).map(slot=>slot.member!.id===room.chatMembership?'you':slot.member!.nickname)??[];
 const unsupported=room?.slots.filter(slot=>slot.member&&slot.role!=='observer'&&!room.controllerRoles.includes(slot.role))??[];
 const authorityReady=!!room&&room.game.ready.includes(room.hostMembership);
 const linked=room?.peers.filter(peer=>room.game.controllers.owners.includes(peer.member)||peer.member===room.hostMembership).every(peer=>peer.status==='connected')??true;
 const failedPeer=room?.peers.find(peer=>['failed','relay_unavailable','relay_capacity'].includes(peer.status));
 const roleFailure=room?.game.pending?.status==='failed'?room.game.pending.reason??'Player change failed.':undefined;
 const localMatch=!!room?.fingerprint&&!!playerState.fingerprint&&room.matches&&player.current?.isLoaded(playerState.fingerprint);
 const canReady=!!room&&!!room.fingerprint&&!observer&&!!self?.member?.connected&&self.member.acquisition==='loaded'&&!!localMatch&&roomState.connected&&!roomState.busy&&!playerState.loading;
 const readyError=currentPage==='lobby'&&!ready?roomState.gameplay?.preparationError:undefined;
 const hostObserverNeedsPreparation=currentPage==='lobby'&&room?.role==='host'&&!!room.fingerprint&&!!observer&&!authorityReady&&!!readyError;
 const activeOwner=!!room?.game.controllers.owners.includes(room.chatMembership);
 const needsObservation=currentPage==='playing'&&room?.game.status==='playing'&&!!observer&&room.role!=='host'&&!roomState.gameplay?.observing;
 const needsActivation=currentPage==='playing'&&room?.game.status==='playing'&&!observer&&!activeOwner;
 const canJoinRunning=!!room&&!!room.fingerprint&&!!localMatch&&self?.member?.acquisition==='loaded'&&roomState.connected&&!room.game.pending&&!roomState.gameplay?.busy;
 const canStart=!!room&&room.role==='host'&&!room.started&&!!room.fingerprint&&!!localMatch&&authorityReady&&unready.length===0&&unsupported.length===0&&linked&&roomState.connected&&!roomState.busy&&!playerState.loading&&!room.game.startRequested;
 const gameBusyLabel=currentPage==='local'&&playerState.loading?playerState.status:room?.role==='host'&&!room.started&&!room.game.startRequested?(playerState.loading?playerState.status:roomState.uploading||roomState.busy&&/^Preparing NES game/.test(roomState.status)?roomState.status:gameProgress)||undefined:undefined;
 const countdown=room?.game.status==='countdown'&&room.game.startAt!==undefined?Math.max(1,Math.ceil((room.game.startAt-clock)/1000)):undefined;
 const playingStatus=needsObservation?room?.game.pending?'Changing player roles. Please wait.':roomState.gameplay?.busy?roomState.gameplay.status:'The game is live. Choose Observe game to watch or retry.':needsActivation?room?.game.pending?'Joining the current game…':roomState.gameplay?.busy?roomState.gameplay.status:'The game is live. Prepare to play when you are ready.':undefined;
 const playAction:GameAction|undefined=roomState.gameplay?.synchronizing?{label:'Cancel preparation',run:()=>rooms.current?.cancelPreparation()}:needsObservation?{label:'Observe game',disabled:!canJoinRunning,run:()=>rooms.current?.observeGame()}:needsActivation?{label:'Prepare to play',disabled:!canJoinRunning,keyboard:true,run:()=>rooms.current?.readyToResume()}:room?.game.status==='playing'&&!observer&&activeOwner?{label:'Pause',keyboard:true,run:()=>rooms.current?.pauseTogether()}:room?.game.status==='resume_ready'&&room.role==='host'?{label:'Resume together',keyboard:true,run:()=>rooms.current?.resumeTogether()}:room?.game.status&&['paused','failed','waiting'].includes(room.game.status)&&(!observer||room.role==='host')?{label:'Prepare to resume',keyboard:true,run:()=>rooms.current?.readyToResume()}:undefined;
 const pauseAction:GameAction|undefined=playerState.loading?undefined:currentPage==='local'?{label:playerState.running?'Pause':'Resume',run:()=>playerState.running?player.current?.pause():player.current?.resume()&&rooms.current?.localPlayIntent()}:currentPage==='playing'&&roomState.connected&&playAction?.keyboard&&!playAction.disabled?playAction:undefined;
 const inviteUnavailable=!!roomState.preview&&(!('openSlots' in roomState.preview)||roomState.preview.openSlots===0||roomState.preview.status==='reconnecting');
 const inviteStatus=roomState.admissionError?.message??(!roomState.preview?roomState.status:inviteUnavailable?roomState.preview.status==='reconnecting'?'The host is reconnecting. Try again soon.':'No open places. Browse other lobbies or wait for the host.':roomState.preview.visibility==='protected'?'Enter the password to join this lobby.':'Join this lobby when you are ready.');
 const start=()=>{if(canStart&&playerState.fingerprint)void rooms.current?.start(playerState.fingerprint);};
 const localRecovery=playerState.storageIssue
  ? playerState.storageIssue.includes('cleared in another view')
   ? {message:'Local data was cleared elsewhere. Export a backup.',tool:'saves' as const,label:'Saves'}
   : playerState.storageIssue.includes('restored')
   ? {message:'Battery restore failed. Game still works.',tool:'localData' as const,label:'Local data'}
   : {message:'Battery saving failed. Export a backup.',tool:'saves' as const,label:'Saves'}
  : preferences.issue
   ? {message:'Saved settings need attention.',tool:'localData' as const,label:'Local data'}
   : undefined;
 const lobbyGuidance=()=>{
  if(!roomState.connected)return 'Connection lost. Retry connection.';
  if(!room?.fingerprint)return room?.role==='host'?'Load a NES game while players join.':'';
  if(unsupported.length)return room.role==='host'?`${unsupported[0].role==='player1'?'Player 1':'Player 2'} cannot play this game. Set as Observer or change game.`:'The host is updating player roles.';
  if(self&&self.role!=='observer'&&!ready){
   if(self.member?.acquisition==='failed')return 'Game failed to load. Choose Retry game.';
   if(self.member?.acquisition==='loaded'&&!localMatch)return 'Game does not match. Choose Retry game.';
   return canReady?'Choose Ready when you are prepared.':'Your game is preparing. Ready will be available soon.';
  }
  if(unready.length)return room.role==='host'?`${unready.length} ${unready.length===1?'player':'players'} not ready. Wait or kick.`:`Waiting for ${unready.length} ${unready.length===1?'player':'players'} to get ready.`;
  if(!authorityReady)return 'Preparing the host game…';
  if(!linked)return 'Connecting players. Wait before starting.';
  return room.role==='host'?'Everyone playing is ready. Choose Start.':'Everyone playing is ready. Waiting for the host.';
 };
 const directoryGuidance=roomState.admissionBlocked?'Access to lobbies is temporarily restricted. Retry later.':roomState.directoryStatus==='stale'?'Lobbies are unavailable. Retry.':roomState.directoryStatus==='live'?'':'Finding lobbies…';
 const status=statusOverride||automaticIssue||roomState.storageIssue||slotFeedback||roomState.releaseNotice||roleFailure||readyError||(roomState.connected&&failedPeer?'Connection failed. Retry connection.':undefined)||playingStatus||slotInspect||({main:directoryGuidance,lobbies:invite?inviteStatus:directoryGuidance,lobby:lobbyGuidance(),playing:!roomState.connected?'Connection lost. Retry connection.':countdown?`Game starts in ${countdown}…`:room?.game.reason??(room?.game.status==='playing'?'Playing together.':'Starting together…'),local:playerState.loading?playerState.status:playerState.inputIssue||localRecovery?.message||persistenceMessage||playerState.status} as Record<ShellPage,string>)[currentPage];
 const settingsContent=<Settings key={`${room?.id??'local'}:${!!room?.started}`} inline initialSection={room?.started||currentPage==='local'?'game':room?.role==='host'?'lobby':'controls'} room={room} localGame={currentPage==='local'} pauseActionLabel={pauseAction?.label} onAct={command=>rooms.current?.act(command)??Promise.resolve(false)} voiceState={voice} voiceSession={rooms.current?.voice()} localData={()=>setTool('localData')} connection={connection} open controls={controls} change={value=>{setControls(value);player.current?.configureControls(value);preferences.remember({controls:value,filter,volume});}} filter={filter} setFilter={value=>{setFilter(value);preferences.remember({controls,filter:value,volume});}} volume={volume} setVolume={value=>{setVolume(value);player.current?.setVolume(value);preferences.remember({controls,filter,volume:value});}} muted={muted} toggleMute={()=>{const value=!muted;setMuted(value);player.current?.setMuted(value);}} audioIssue={playerState.audioIssue} audioState={playerState.audioState} retryAudio={()=>player.current?.retryAudio()}/>;
 const sideContent=room?settingsContent:side==='settings'?settingsContent:null;
 const title=currentPage==='main'||currentPage==='lobbies'?'Lobbies':currentPage==='local'?'Local game':room?.label??'Lobby';
 const openNameEdit=(target:'name'|'lobby',button:HTMLButtonElement)=>{editReturnFocus.current=button;setEditDraft(target==='name'?guest:room?.label??'');setEditError('');setEditTarget(target);};
 const closeNameEdit=()=>{setEditTarget(null);setEditError('');requestAnimationFrame(()=>editReturnFocus.current?.focus());};
 const saveNameEdit=async()=>{if(!editTarget||editBusy)return;const name=editDraft.trim();if(!name){setEditError('Enter a name.');return;}if(name=== (editTarget==='name'?guest:room?.label)){closeNameEdit();return;}setEditBusy(true);const ok=editTarget==='name'?await rooms.current?.setNickname(name):room?.role==='host'?await rooms.current?.act({type:'rename',roomId:room.id,label:name}):false;setEditBusy(false);if(ok)closeNameEdit();else setEditError(editTarget==='name'?'Could not change your name. Try again.':'Could not rename lobby. Try again.');};
 const titleControl=room?<span className="rc-lobby-heading"><span className="rc-header-name"><span>Lobby name:</span>{room.role==='host'?<button type="button" className="rc-header-edit" aria-label={`Edit lobby name: ${room.label}`} onClick={event=>openNameEdit('lobby',event.currentTarget)}>{room.label} <span className="rc-edit-hint" aria-hidden="true">✎</span></button>:<span>{room.label}</span>}</span><button type="button" className="rc-header-invite" aria-label="Copy invite" onClick={copyInvite}><span className="rc-invite-long">Copy invite</span><span className="rc-invite-short">Invite</span></button></span>:undefined;
 const identityControl=<span className="rc-header-name"><span>Your name:</span><button type="button" className="rc-header-edit" aria-label={`Edit your name: ${guest}`} onClick={event=>openNameEdit('name',event.currentTarget)}>{guest} <span className="rc-edit-hint" aria-hidden="true">✎</span></button></span>;
 const back=currentPage==='main'?null:<button onClick={()=>backToMain()}>Back to Main Page</button>;
 useEffect(()=>{
  const shortcut=(event:KeyboardEvent)=>{
   if(event.code!=='KeyP'||event.repeat||event.altKey||event.ctrlKey||event.metaKey||!pauseAction||pauseAction.disabled||playerState.loading||tool||exitPrompt||kick||quickLoad||editTarget||recovery||!roomState.connected&&currentPage==='playing'||Object.values(controls.keyboard).some(bindings=>bindings.includes('KeyP'))||(event.target as Element)?.closest('input,textarea,select,[contenteditable="true"],dialog'))return;
   event.preventDefault();pauseAction.run();
  };
  window.addEventListener('keydown',shortcut);return()=>window.removeEventListener('keydown',shortcut);
 },[pauseAction,currentPage,playerState.loading,roomState.connected,controls,tool,exitPrompt,kick,quickLoad,editTarget,recovery]);
 const actions=currentPage==='main'||currentPage==='lobbies'?null:currentPage==='lobby'?<>{hostObserverNeedsPreparation&&<button disabled={!localMatch||!roomState.connected||!!roomState.gameplay?.busy} onClick={()=>rooms.current?.ready()}>Retry game setup</button>}{!observer&&<span className="rc-action-slot rc-ready-slot">{(canReady||ready||!!readyError)&&<button className={ready?'rc-secondary-action':undefined} disabled={!canReady&&!ready} onClick={()=>ready?rooms.current?.unready():rooms.current?.ready()}>{ready?'Cancel Ready':readyError?'Try Ready again':'Ready'}</button>}</span>}{room?.role==='host'&&<span className="rc-action-slot rc-start-slot">{canStart&&<button onClick={start}>Start →</button>}</span>}</>:currentPage==='playing'?playAction?<button disabled={playAction.disabled} onClick={playAction.run}>{playAction.label}</button>:null:pauseAction?<button onClick={pauseAction.run}>{pauseAction.label}</button>:null;
 const restoreRecovery=async()=>{
  const active=player.current,offer=recovery,capture=offer?.record.captures[recoveryIndex],target=room;
  if(!active||!offer||!target||target.role!=='host'||target.started||recoveryBusy)return;
  const serial=++recoverySerial.current,abort=new AbortController();recoveryAbort.current=abort;setRecoveryBusy(true);setRecoveryError('');
  const current=()=>recoverySerial.current===serial&&!!rooms.current?.currentMembership(target.id,target.chatMembership)&&recoveryContext.current.room?.id===target.id&&recoveryContext.current.room.chatMembership===target.chatMembership&&!recoveryContext.current.leaving;
  try{
   if(!validRecovery(capture))throw Error('This saved progress is damaged.');
   const stored=await readRecovery();if(!current()||stored.generation!==offer.generation||stored.record?.revision!==offer.record.revision)throw Error('Recovery data changed or was cleared.');
   const included=catalog.find(entry=>entry.sha256===capture.fingerprint.romSha256);
   const saved=included?undefined:await savedCandidate(capture.fingerprint.romSha256);
   const file=included?await downloadCatalogEntry(included,abort.signal,()=>{}):saved!.file;
   if(!current())return;
   await active.loadRecovery(file,current);if(!current())return;
   const fingerprint=active.recoveryFingerprint();if(!fingerprint||!matchesFile(fingerprint,capture.fingerprint))throw Error('This saved progress belongs to another emulator version or game settings.');
   if(saved&&!await candidateStillStored(saved,fingerprint))throw Error('The saved NES file was deleted or changed.');
   const info=await active.saveInfo();if(info.identity!==capture.identity)throw Error('Saved progress does not match this game.');
   const selected=await rooms.current?.selectLobbyGame(file,fingerprint,capture.title,current);if(!selected?.ok)throw Error(selected?.message??'Could not select the saved game.');
   if(!current())return;recoveryCommit.current=true;setRecoveryCommitting(true);
   await active.holdForGame(false);
   await active.importPeerCheckpoint(crypto.randomUUID().replaceAll('-',''),capture.frame,capture.bytes,capture.identity,capture.hash,current);
   if(!current())return;
   const latest=await readRecovery();if(latest.generation!==offer.generation||latest.record?.revision!==offer.record.revision)throw Error('Recovery data was cleared or changed before restoration.');
   await rooms.current?.restoreGame(capture.frame,capture.hash,current);
   setRecovery(undefined);setStatusOverride('');
  }catch(error){if(current()){
   const message=error instanceof Error?error.message:'Restoration could not complete.';
   if(recoveryIndex+1<offer.record.captures.length){setRecoveryIndex(recoveryIndex+1);setRecoveryError(`${message} You can try the older save shown below.`);}
   else{setRecovery(undefined);setStatusOverride(`${message} Load a NES game normally.`);}
  }}finally{if(recoverySerial.current===serial){setRecoveryBusy(false);setRecoveryCommitting(false);recoveryCommit.current=false;recoveryAbort.current=undefined;}}
 };
 const startFreshRecovery=async()=>{if(!recovery||recoveryCommit.current)return;++recoverySerial.current;recoveryAbort.current?.abort();recoveryAbort.current=undefined;if(recoveryBusy){rooms.current?.cancelSelection();player.current?.cancelPeerCheckpoint();player.current?.cancel();}setRecoveryBusy(true);try{await changeRecovery(recovery.record,recovery.generation,undefined);setRecovery(undefined);setRecoveryError('');setStatusOverride('');}catch(error){setRecoveryError(error instanceof Error?error.message:'Could not discard the saved progress.');}finally{setRecoveryBusy(false);}};
 const recoveryCapture=recovery?.record.captures[recoveryIndex];
 const recoveryDialog=recovery?<div className="rc-dialog-card" role="alertdialog" aria-modal="true" aria-labelledby="rc-recovery-title"><h2 id="rc-recovery-title">Restore your last hosted game?</h2><p>{validRecovery(recoveryCapture)?recoveryCapture.title:'Saved game'} · {recoveryCapture&&Number.isFinite(recoveryCapture.savedAt)?new Date(recoveryCapture.savedAt).toLocaleString():'Unknown saved time'}</p>{recoveryError&&<p role="alert">{recoveryError}</p>}<div className="rc-dialog-actions"><button disabled={recoveryCommitting} onClick={()=>void startFreshRecovery()}>Start fresh</button><button autoFocus disabled={recoveryBusy} onClick={()=>void restoreRecovery()}>{recoveryBusy?'Restoring…':'Restore game'}</button></div></div>:undefined;
 const blocker=exitPrompt?<div className="rc-dialog-card" role="alertdialog" aria-modal="true" aria-labelledby="rc-exit-title" aria-describedby="rc-exit-detail"><h2 id="rc-exit-title">{room?.role==='host'?'Close this lobby?':'Leave this lobby?'}</h2><p id="rc-exit-detail">{room?.role==='host'?'Everyone will leave the lobby and the game will stop.':'You will leave the lobby and the game will stop on this device.'}</p>{statusOverride&&<p role="alert">{statusOverride}</p>}<div className="rc-dialog-actions"><button onClick={()=>{exitTarget.current=undefined;setExitPrompt(false);setStatusOverride('');}}>Stay</button><button disabled={exitBusy} onClick={()=>void finishExit()}>{room?.role==='host'?'Close lobby':'Leave lobby'}</button></div></div>:kick?<div className="rc-dialog-card" role="alertdialog" aria-modal="true" aria-labelledby="rc-kick-title" aria-describedby="rc-kick-detail"><h2 id="rc-kick-title">Kick {kick.name}?</h2><p id="rc-kick-detail">They will leave this lobby and cannot rejoin it.</p>{statusOverride&&<p role="alert">{statusOverride}</p>}<div className="rc-dialog-actions"><button onClick={()=>{setKick(undefined);setStatusOverride('');}}>Cancel</button><button onClick={()=>void confirmKick()}>{statusOverride.startsWith('Could not kick ')?'Retry kick':'Kick player'}</button></div></div>:quickLoad?<div className="rc-dialog-card" role="alertdialog" aria-modal="true" aria-labelledby="rc-quick-load-title"><h2 id="rc-quick-load-title">Load quick save?</h2><p>Your current unsaved progress will be replaced by Slot 1.</p><div className="rc-dialog-actions"><button onClick={()=>setQuickLoad(undefined)}>Keep playing</button><button onClick={confirmQuickLoad}>Load Slot 1</button></div></div>:editTarget?<form className="rc-dialog-card" role="dialog" aria-modal="true" aria-labelledby="rc-name-edit-title" onSubmit={event=>{event.preventDefault();void saveNameEdit();}}><h2 id="rc-name-edit-title">{editTarget==='name'?'Change your name':'Change lobby name'}</h2><label htmlFor="rc-name-edit-input">{editTarget==='name'?'Your name':'Lobby name'}</label><input id="rc-name-edit-input" className="rc-name-dialog-input" autoFocus maxLength={editTarget==='name'?32:80} value={editDraft} onChange={event=>{setEditDraft(event.target.value);setEditError('');}} aria-invalid={!!editError} aria-describedby={editError?'rc-name-edit-error':undefined}/>{editError&&<p id="rc-name-edit-error" role="alert">{editError}</p>}<div className="rc-dialog-actions"><button type="button" disabled={editBusy} onClick={closeNameEdit}>Cancel</button><button type="submit" disabled={editBusy||!editDraft.trim()}>Save name</button></div></form>:inviteCopyFallback&&room?.id===inviteCopyFallback.roomId&&room.chatMembership===inviteCopyFallback.membership&&inviteLink===inviteCopyFallback.link&&!exitPrompt?<div className="rc-dialog-card" role="dialog" aria-modal="true" aria-labelledby="rc-invite-title"><h2 id="rc-invite-title">Invitation link</h2><p>Copy this link to invite someone.</p><textarea className="rc-invite-link" readOnly aria-label="Invitation link" value={inviteLink} onFocus={event=>event.currentTarget.select()} onClick={event=>event.currentTarget.select()}/><div className="rc-dialog-actions"><button onClick={()=>setInviteCopyFallback(null)}>Done</button></div></div>:recoveryDialog;
 const publicSide=side&&['main','lobbies'].includes(currentPage);
 return <><AppShell page={currentPage} title={title} guest={guest} titleControl={titleControl} identityControl={identityControl} theme={theme} onTheme={toggleTheme} status={tooSmall&&!exitPrompt&&!kick?'Window too small for this screen.':status} statusAction={tooSmall?undefined:currentPage==='lobbies'&&!!invite&&!roomState.preview&&!roomState.busy?<button className="rc-status-action" onClick={()=>void rooms.current?.reconnect()}>Retry invitation</button>:currentPage==='main'&&roomState.directoryStatus==='stale'?<button className="rc-status-action" onClick={()=>void rooms.current?.retryDirectory()}>Retry</button>:currentPage==='local'&&playerState.loading&&playerState.loaded?<button className="rc-status-action" onClick={cancelGameSelection}>Cancel selection</button>:currentPage==='local'&&!!playerState.inputIssue&&!playerState.loading?<button className="rc-status-action" onClick={chooseKeyboard}>Use keyboard</button>:currentPage==='local'&&!playerState.loading&&!playerState.inputIssue&&!statusOverride&&localRecovery?<button className="rc-status-action" onClick={()=>{setSide(null);setTool(localRecovery.tool);}}>{localRecovery.label}</button>:room&&!roomState.connected&&!exitPrompt&&!kick?<button className="rc-status-action" onClick={()=>{setStatusOverride('');void rooms.current?.reconnect();}}>Retry connection</button>:room&&roomState.connected&&failedPeer&&!exitPrompt&&!kick?<button className="rc-status-action" onClick={()=>void rooms.current?.retryPeer(failedPeer.pairId)}>Retry connection</button>:undefined} attention={tooSmall||currentPage==='lobby'&&(!room?.fingerprint||!!readyError)||currentPage==='local'&&(playerState.loading||!!playerState.inputIssue||!!localRecovery)} identityOpen={side==='identity'} onIdentity={()=>setSide(side==='identity'?null:'identity')} onHome={()=>backToMain()} modal={!!tool} blocker={blocker} tooSmall={tooSmall} back={back} actions={actions}>
  <div className={`rc-public-content${publicSide?' rc-public-with-side':''}`} hidden={!['main','lobbies'].includes(currentPage)} inert={!!tool} aria-hidden={!!tool}><div className="rc-public-main" hidden={publicSide?false:undefined}>{currentPage==='lobbies'&&invite?<section className="rc-invite-entry"><h1>{roomState.preview?.label??'Lobby invitation'}</h1>{roomState.preview?.visibility==='protected'&&<input aria-label="Lobby password" type="password" value={invitePassword} onChange={event=>{setInvitePassword(event.target.value);rooms.current?.clearAdmissionError();}}/>}<button disabled={!roomState.preview||inviteUnavailable||roomState.busy||roomState.preview.visibility==='protected'&&!validRoomPassword(invitePassword)} onClick={joinInvite}>Join lobby</button></section>:<LobbyDirectory rooms={roomState.directory??[]} status={roomState.directoryStatus} busy={roomState.busy} error={roomState.admissionError?.message??roomState.directoryError} onHost={()=>void createLobby()} onJoin={joinCode} onDismissError={()=>rooms.current?.clearAdmissionError()} onCancelJoin={()=>rooms.current?.cancelJoin()} onInspect={setSlotInspect}/>}</div><aside className="rc-public-side" hidden={!publicSide}><div className="rc-section-head"><span className="rc-eyebrow">{side?.toUpperCase()}</span><button onClick={()=>setSide(null)}>×</button></div><div className="rc-side-content">{publicSide&&sideContent}</div></aside></div>
  <div className="rc-session-holder" hidden={!['lobby','playing','local'].includes(currentPage)} inert={!!tool} aria-hidden={!!tool}><SessionStage room={room} chat={roomState.chat} connected={roomState.connected} canvas={<canvas ref={canvas} width={256} height={240} tabIndex={0} aria-label="NES game screen" data-frame-count={playerState.frames}/>} canvasLoaded={playerState.loaded&&(!room?.fingerprint||!!playerState.fingerprint&&matchesFile(room.fingerprint,playerState.fingerprint))} gameTitle={room?.gameTitle} previewImage={room?.fingerprint&&playerState.fingerprint&&matchesFile(room.fingerprint,playerState.fingerprint)?playerState.previewImage:undefined} scanlines={filter==='scanlines'} side={room?'settings':side} onSide={setSide} onAct={command=>rooms.current?.act(command)??Promise.resolve(false)} onKick={requestKick} onSlotFeedback={setSlotFeedback} onSlotInspect={setSlotInspect} onChoose={choose} onIncluded={id=>{setStatusOverride('');void rooms.current?.loadIncluded(id);}} onSaved={file=>load(file)} onRetryMember={()=>void rooms.current?.retryMemberGame()} onDraft={text=>rooms.current?.chatDraft(text)} onSend={()=>void rooms.current?.sendChat()} onDiscard={()=>rooms.current?.discardChat()} onCancelSelection={cancelGameSelection} loadingLabel={gameBusyLabel} sideContent={sideContent} local={currentPage==='local'} compactUtilities={viewport.width<=650} selectionAllowed={!exitPrompt&&!exitBusy&&['lobby','local'].includes(currentPage)} controls={controls} muted={muted} volume={volume} onMute={()=>{const value=!muted;setMuted(value);player.current?.setMuted(value);}} onVolume={value=>{setVolume(value);player.current?.setVolume(value);preferences.remember({controls,filter,volume:value});}} onConfigure={()=>openSettings('controls')} onVoiceSettings={()=>openSettings('voice')}/></div>
  {tool&&<div className="rc-tool-overlay"><button className="rc-tool-back" onClick={()=>setTool(null)}>Back</button><Saves open={tool==='saves'} player={player.current} shared={!!playerState.shared} batteryAvailable={!!playerState.batteryAvailable} storageIssue={playerState.storageIssue} game={`${playerState.fingerprint?.romSha256}:${playerState.fingerprint?.coreSha256}`}/><Rewind open={tool==='rewind'} player={player.current}/><LocalData open={tool==='localData'} player={player.current} preferencesIdentity={preferencesIdentity} beforeClear={()=>{captureOwner.current?.stop();++recoverySerial.current;setRecovery(undefined);player.current?.stopPersistence();preferences.stop();}} afterClear={()=>setPersistenceMessage('Local data deleted. Current progress remains in memory.')}/></div>}
 </AppShell>
 <input ref={picker} type="file" accept=".nes" hidden aria-label="NES cartridge file" onChange={event=>{const file=event.target.files?.[0];if(file)load(file);}}/>
 <RoomController onAcquired={load} selectionLoading={playerState.loading} ref={rooms} controls={controls} onVoice={setVoice} player={()=>player.current} fingerprint={playerState.fingerprint} onNickname={setGuest} onConnection={setConnection} onRoomChange={next=>{if(inviteContext.current.roomId!==next?.id||inviteContext.current.membership!==next?.chatMembership){++inviteAttempt.current;setInviteCopyFallback(null);}inviteContext.current={roomId:next?.id,membership:next?.chatMembership,leaving:exitPrompt||exitBusy};setRoom(next);}} onState={setRoomState} onNotice={setStatusOverride} onGameProgress={setGameProgress}/>
 </>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
