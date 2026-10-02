import {GameClient,type GameplayState} from './game-client.ts';
import type {GameEvent} from '../../../packages/contracts/src/gameplay.ts';
import type {LocalPlayer} from './player.ts';
import {VoiceSession,type VoiceState} from './voice.ts';
import {ChatClient,type ChatState} from './chat-client.ts';
import {PeerConnection,type ConnectionState} from './peer.ts';
import type {PeerEvent} from '../../../packages/contracts/src/peer.ts';
import { clientConfig } from './config.ts';
import {matchesFile} from '../../../packages/contracts/src/rooms.ts';
import {TabSession} from './tab-session.ts';
import {uploadRoomFile} from './room-upload.ts';
import {catalogId} from '../../../packages/contracts/src/catalog.ts';
import type { Fingerprint, RoomCommand, RoomData, RoomEvent, RoomPreview, RoomView, SessionInfo, NewVisibility } from '../../../packages/contracts/src/rooms.ts';
type Command = RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'> : never : never;
export type RoomState = { gameplay?:GameplayState; voice?:VoiceState; chat?:ChatState; connection?:ConnectionState; directory?:RoomPreview[]; directoryStatus?:'loading'|'live'|'stale'; directoryError?:string; room?:RoomView; preview?:RoomPreview; session?:SessionInfo; status:string; busy:boolean; hostFailure?:boolean; uploading?:boolean; confirmingRoom?:boolean; startingRoom?:boolean; releaseNotice?:string; connected:boolean; retryAfterMs?:number; admissionError?:{code?:string;message:string}; needsNewGuest?:boolean; admissionBlocked?:boolean };
const messages:Record<string,string> = {
 capacity:'Lobby capacity is full. Your local game is preserved. Try again later.',rate_limited:'Too many attempts. Wait before retrying.',room_full:'All five slots are occupied or closed. Review the lobby or try another.',
 room_unavailable:'This lobby is closed, unavailable, or the invitation has expired.',session_expired:'Your guest session expired or the service restarted. Start a new guest session to continue.',
 room_changed:'That lobby has changed. Review the current lobby before trying again.',membership_changed:'That member has left or rejoined. Review the current slot before trying again.',
 slot_occupied:'Remove the member before closing this slot.',slot_empty:'That player has left. Check the slot and try again.',slot_closed:'Open the destination slot before moving someone there.',controller_occupied:'An empty slot cannot take an occupied controller role.',role_change_pending:'Finish or cancel the current player change first.',game_not_playing:'Finish initial preparation before changing roles. If preparation fails, use Retry shared play.',stale_controllers:'The players changed. Review the current slots and retry.',game_prerequisites:'Wait until every player has the game, is connected, and is Ready before starting.',unsupported_role:'This game does not support that controller role.',
 host_only:'Only the host can change this lobby.',host_reconnecting:'The host is reconnecting. Try joining again later.',reservation_expired:'Your 120-second reservation expired. Retry join to claim a new place.',
 host_expired:'The host did not return. This lobby has closed.',host_closed:'The host closed the lobby.',removed:'The host removed you from this lobby.',left:'You left the lobby. Your local game is still available.',
 operator_removed:'An operator closed this lobby. Your local game is preserved.',admission_blocked:'Access is temporarily restricted by an operator. Retry later. Your local game is preserved.',
 service_restarted:'The service restarted. Ephemeral lobbies have closed.',creation_cancelled:'Lobby creation cancelled. Your game stays local.',creation_expired:'Upload timed out. Retry upload to create a fresh lobby.',upload_expired:'Upload timed out. Retry upload to create a fresh lobby.',cancelled:'Lobby creation cancelled.',
 host_not_ready:'Wait for your game to finish loading before Start.',game_mismatch:'The loaded game does not match this lobby. Choose the matching file before Start.',
 game_not_selected:'Load a NES game before starting.',game_selection_pending:'Wait for the game upload to finish.',game_selection_changed:'The game selection changed. Choose the game again.',
 password_required:'Enter the lobby password to join.',bad_password:"Password didn't work. Try again.",invalid_password:'Use a lobby password of 8 to 128 characters.',
};
export class RoomClient {
 readonly voice=new VoiceSession(voice=>this.publish({voice}));
 private chat=new ChatClient(chat=>this.publish({chat}),command=>this.request(command));
 private socket?:WebSocket;
 private game=new GameClient(()=>this.player(),command=>this.request(command),gameplay=>this.publish({gameplay}));
 private peers=new Map<string,PeerConnection>();
 private peerStates=new Map<string,ConnectionState>();
 private closePeers(status='Lobby connections closed.',leave=false){for(const peer of this.peers.values())peer.close(status);this.peers.clear();this.peerStates.clear();if(leave)this.voice.close();}
 private peerEvent(event:PeerEvent){
  let peer=this.peers.get(event.pairId);
  if(event.type==='peerPrepare'&&!peer){
   const member=event.member;peer=new PeerConnection(command=>this.request(command),connection=>{this.peerStates.set(event.pairId,connection);const states=[...this.peerStates.values()],routes=states.map(value=>value.route);this.publish({connection:{status:connection.status,route:routes.includes('relay')?'relay':routes.every(route=>route==='direct')?'direct':undefined,pingMs:Math.max(...states.map(value=>value.pingMs??0))}});},{media:this.voice.forPeer(event.pairId),...(event.gameplay?{checkpoint:(channel:RTCDataChannel,epoch:string)=>this.game.checkpointChannel(member,channel,epoch),ready:(channel:RTCDataChannel,epoch:string,roundTripMs:number)=>this.game.ready(member,channel,epoch,roundTripMs),closed:(epoch:string|undefined)=>this.game.closed(member,epoch)}:{})});this.peers.set(event.pairId,peer);
  }
  peer?.handle(event);if(event.type==='peerStop')this.peerStates.delete(event.pairId);
 }

 private connecting?:Promise<void>;
 private heartbeat?:ReturnType<typeof setInterval>;
 private disposed = false;
 private watchingDirectory = false;
 private token?:string;
 private tabSession=new TabSession();
 private tokenCheck?:Promise<void>;
 private intent?:string;
 private lobbyIntent?:string;
 private uploadAbort?:AbortController;
 private generation = 0;
 private creationGeneration = 0;
 private gameSelection?:string;
 private selectedFile?:Fingerprint;private loadedReport?:string;
 private joining?:string;
 private previewingId?:string;
 private previewingInvite?:string;
 private voluntaryExitRoomId?:string;
 private pending = new Map<string,{kind:Command['type'];resolve:(data:RoomData)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
 private state:RoomState = {status:'No lobby selected.',busy:false,connected:false};
 constructor(private update:(state:RoomState)=>void,private player:()=>LocalPlayer|null=()=>null) {try {this.token = sessionStorage.getItem('retro-coop-guest') ?? undefined;}catch{}this.publish({voice:this.voice.current()});}
 private publish(patch:Partial<RoomState>) {if(this.disposed) return;this.state = {...this.state,...patch};this.update(this.state);}
 private setRoom(room?:RoomView){
  if(room&&room.id!==this.voluntaryExitRoomId)this.voluntaryExitRoomId=undefined;
  // A member admitted from an invitation still needs its preview after removal.
  if(room&&room.id!==this.previewingId){this.previewingInvite=undefined;this.previewingId=undefined;}
  this.game.enter(room);this.publish({room,chat:this.chat.enter(room),...(room?{releaseNotice:undefined}:{})});this.reportLoadedGame();
  if(room?.role==='host'&&!room.started&&room.fingerprint&&room.slots.find(slot=>slot.member?.id===room.chatMembership)?.role==='observer'&&!this.state.gameplay?.intent&&this.selectedFile&&matchesFile(room.fingerprint,this.selectedFile)&&this.player()?.isLoaded(this.selectedFile))this.game.playIntent();
  if(!room)this.closePeers('Lobby closed.',true);else for(const [id,peer] of this.peers)if(!room.peers.some(view=>view.pairId===id)){peer.close('Member left.');this.peers.delete(id);this.peerStates.delete(id);}
 }
 private apply(data:RoomData) {
  if(data.session) {this.token = data.session.token;try {sessionStorage.setItem('retro-coop-guest',this.token);}catch{}this.publish({session:data.session});}
  if(data.directory) this.publish({directory:data.directory,directoryStatus:'live',directoryError:undefined});
  if(data.preview) this.publish({preview:data.preview});
  if(data.room) this.setRoom(data.room);
 }
 private request(command:Command):Promise<RoomData> {
  if(this.socket?.readyState !== WebSocket.OPEN) return Promise.reject(Error('The lobby service is disconnected. Your local game is preserved.'));
  const requestId = crypto.randomUUID();
  return new Promise((resolve,reject)=>{
   const timer = setTimeout(()=>{this.pending.delete(requestId);reject(Error('The lobby service did not respond. Retry or cancel; your local game is preserved.'));},8000);
   this.pending.set(requestId,{kind:command.type,resolve,reject,timer});this.socket!.send(JSON.stringify({...command,requestId}));
  });
 }
 private async connect() {
  if(this.state.connected && this.socket?.readyState === WebSocket.OPEN) return;
  if(this.connecting) return this.connecting;
  if(this.token){
   this.tokenCheck??=this.tabSession.claim(this.token).then(claimed=>{
    if(!claimed){this.token=undefined;try{sessionStorage.removeItem('retro-coop-guest');}catch{}}
   }).finally(()=>{this.tokenCheck=undefined;});
   await this.tokenCheck;
  }
  if(this.disposed)throw Error('Room client disposed');
  if(this.connecting)return this.connecting;
  const endpoint = new URL(clientConfig.coordinatorUrl,location.href);endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:':'ws:';endpoint.pathname = endpoint.pathname.replace(/\/$/,'')+'/ws';endpoint.hash = '';endpoint.search = '';
  const socket = new WebSocket(endpoint);this.socket = socket;
  this.connecting = new Promise<void>((resolve,reject)=>{
   const deadline = setTimeout(()=>{socket.close();reject(Error('The lobby service is unavailable. Your local game is preserved.'));},8000);
   socket.onmessage = ({data}) => {
    if(this.socket !== socket) return;
    let event:RoomEvent;try {event = JSON.parse(data);}catch{return;}
    if(event.type === 'result') {
     const pending = this.pending.get(event.requestId);if(!pending) return;clearTimeout(pending.timer);this.pending.delete(event.requestId);
     if(event.ok) pending.resolve(event.data);else {this.publish({...(pending.kind==='chat' ? {}:{retryAfterMs:event.retryAfterMs}),needsNewGuest:event.error === 'session_expired'});pending.reject(Object.assign(Error(event.error==='place_taken'&&pending.kind==='claimCode'?'Someone claimed Host first. Review the updated row to join an open slot or choose another lobby.':messages[event.error] ?? 'The lobby request was rejected. Your local game is preserved.'),{code:event.error,retryAfterMs:event.retryAfterMs}));}
    } else if(event.type==='chat') this.chat.receive(event);
    else if(event.type.startsWith('game'))this.game.handle(event as GameEvent);
    else if(event.type.startsWith('peer')) this.peerEvent(event as PeerEvent);
    else if(event.type === 'directory') this.publish({directory:event.rooms,directoryStatus:'live',directoryError:undefined});
    else if(event.type === 'preview'&&!this.state.room&&this.previewingId===event.preview.id)this.publish({preview:event.preview,status:'openSlots' in event.preview&&event.preview.openSlots>0?'A slot is open. Join when ready.':messages.room_full});
    // Admission results and reconnect hello install a room; broadcasts only update one already installed.
    else if(event.type === 'room') {if(this.state.room?.id===event.room.id)this.setRoom(event.room);}
    else if(event.type === 'ended') {
     // cancelCreate is our own exact-intent command. Its late notice must not replace a newer attempt.
     if(event.reason==='creation_cancelled')return;
     // A canceled, uninstalled claim can still emit ended after a newer selection begins.
     if(!this.state.room && !this.intent)return;
     const priorRoom=this.state.room;
     const voluntaryExit=!!this.voluntaryExitRoomId&&(!priorRoom||priorRoom.id===this.voluntaryExitRoomId)&&['left','host_closed'].includes(event.reason);
     this.voluntaryExitRoomId=undefined;
     this.closePeers();this.setRoom(undefined);const status=messages[event.reason] ?? 'This lobby ended. Your local game is preserved.';
     if(['creation_expired','upload_expired'].includes(event.reason)&&this.intent) {
      ++this.creationGeneration;this.uploadAbort?.abort();this.uploadAbort=undefined;this.intent=undefined;
      this.publish({busy:false,uploading:false,hostFailure:true,status:'Upload timed out. Retry upload to create a fresh lobby.',releaseNotice:undefined});
     }else this.publish({busy:false,status:voluntaryExit&&event.reason==='host_closed'?'Lobby closed.':status,releaseNotice:voluntaryExit||event.reason==='left'||event.reason==='host_closed'&&priorRoom?.role==='host'?undefined:status});}
   };
   socket.onopen = () => {void this.request({type:'hello',...(this.token ? {token:this.token}:{})}).then(async data=>{
    clearTimeout(deadline);if(this.disposed) {socket.close();return;}if(data.session&&!await this.tabSession.claim(data.session.token))throw Error('This browser cannot reserve a separate lobby session. Close the other tab or retry in a supported browser.');if(this.state.admissionBlocked && !data.room)this.closePeers('No peer connection.');this.setRoom(data.room);this.apply(data);this.publish({connected:true,admissionBlocked:false,...(this.state.admissionBlocked?{status:'Access restored. You can host or join a lobby.'}:{})});
    if(this.watchingDirectory) void this.refreshDirectory();
    this.heartbeat = setInterval(()=>{void this.request({type:'heartbeat'}).catch(()=>{if(this.socket===socket) socket.close();});},10_000);resolve();
   }).catch(error=>{clearTimeout(deadline);socket.close();reject(error);});};
   socket.onerror = () => {clearTimeout(deadline);reject(Error('The lobby service is unavailable. Your local game is preserved.'));};
   socket.onclose = ({code}) => {
    if(this.socket !== socket) return;
    this.closePeers('Signaling disconnected. Reconnect the lobby before retrying peers.');
    const status=code===4003?messages.admission_blocked:'Lobby connection lost. Reconnect to recover an active lobby or unexpired reservation. Your local game is preserved.';
    clearTimeout(deadline);clearInterval(this.heartbeat);for(const pending of this.pending.values()) {clearTimeout(pending.timer);pending.reject(Error(status));}this.pending.clear();
    this.publish({connected:false,busy:false,admissionBlocked:code===4003,...(code===4003&&(this.state.room||this.state.releaseNotice)?{releaseNotice:status}:{}),...(this.watchingDirectory ? {directoryStatus:'stale' as const,directoryError:code===4003?status:'Lobby service disconnected.'}:{}),status});reject(Error(status));
   };
  }).finally(()=>{this.connecting = undefined;});
  return this.connecting;
 }
 private failure(error:unknown) {this.publish({busy:false,startingRoom:false,status:error instanceof Error ? error.message:'Unable to reach the lobby service.'});}
 beginSelection() {this.game.cancelIntent();this.cancelGameSelection();if(this.joining)this.cancelPending();else this.cancelCreation();this.publish({hostFailure:false,releaseNotice:undefined});}
 cancelGameSelection(){const intent=this.gameSelection,room=this.state.room;this.gameSelection=undefined;this.uploadAbort?.abort();this.uploadAbort=undefined;if(intent&&room?.role==='host'){void this.request({type:'cancelGameSelection',roomId:room.id,intent}).catch(()=>{});this.publish({busy:false,uploading:false,status:'Game selection cancelled. The lobby stays open.'});}}
 async approveSelection(fingerprint:Fingerprint,isCurrent:()=>boolean):Promise<boolean> {
  if(!this.token && !this.state.room) return isCurrent();
  try {await this.connect();}catch {return isCurrent();} // Local play remains available offline; hosting still requires consent.
  if(!isCurrent()) return false;
  const room=this.state.room;
  if(room?.established&&!(room.role==='member'&&room.fingerprint&&matchesFile(room.fingerprint,fingerprint)&&!this.player()?.isLoaded(fingerprint))){this.publish({status:'Leave shared play before replacing the game. Your current game is preserved.'});return false;}
  if(room?.role==='member'&&room.fingerprint&&!matchesFile(room.fingerprint,fingerprint)){this.publish({status:'Choose the lobby game before getting ready.'});return false;}
  return true;
 }
 async createLobby(label:string,visibility:NewVisibility,password?:string){
  const intent=this.lobbyIntent??crypto.randomUUID(),generation=this.creationGeneration;this.lobbyIntent=intent;
  this.publish({busy:true,status:'Creating lobby…',retryAfterMs:undefined});
  try{await this.connect();if(generation!==this.creationGeneration)return {ok:false};if(this.state.room)throw Error('Leave the current lobby first.');const data=await this.request({type:'createLobby',intent,label,visibility,password});if(generation!==this.creationGeneration){void this.request({type:'cancelCreate',intent}).catch(()=>{});return {ok:false};}this.lobbyIntent=undefined;this.apply(data);this.publish({busy:false,status:'Lobby created. Load a NES game while players join.'});return {ok:true};}
  catch(error){if(generation===this.creationGeneration)this.failure(error);return {ok:false,message:error instanceof Error?error.message:'Could not create the lobby. Retry.'};}
 }
 async selectLobbyGame(file:File,fingerprint:Fingerprint,title:string,current:()=>boolean){
  const room=this.state.room;if(room?.role!=='host'||room.started||room.established||!current()||!this.player()?.isLoaded(fingerprint))return {ok:false,message:'The lobby or selected game changed. Choose the game again.'};
  const intent=crypto.randomUUID();this.gameSelection=intent;this.uploadAbort?.abort();const controller=new AbortController();this.uploadAbort=controller;
  this.publish({busy:true,uploading:false,status:'Preparing NES game…'});
  try{
   await this.connect();const latest=this.state.room;if(!latest||latest.id!==room.id||latest.role!=='host'||!current())return {ok:false,message:'The lobby changed. Choose the game again.'};
   const begun=await this.request({type:'beginGameSelection',roomId:room.id,intent,expectedRevision:latest.revision,fingerprint,title});
   if(this.gameSelection!==intent||!current())return {ok:false,message:'Game selection cancelled.'};
   if(catalogId(fingerprint)){this.apply(begun);this.publish({busy:false,status:'NES game loaded. Players can get ready.'});return {ok:true};}
   if(!this.token)throw Error('The lobby session expired. Reconnect and retry.');
   this.publish({uploading:true,status:'Uploading NES game…'});
   const receipt=await uploadRoomFile(clientConfig.coordinatorUrl,room.id,intent,this.token,file,(sent,total)=>{if(this.gameSelection===intent)this.publish({status:`Uploading NES game… ${Math.round(sent/1024)} / ${Math.ceil(total/1024)} KiB`});},controller.signal);
   if(receipt.sha256!==fingerprint.romSha256)throw Error('The uploaded game did not match the selected file.');
   if(this.gameSelection!==intent||!current())return {ok:false,message:'Game selection cancelled.'};
   const fresh=this.state.room;if(!fresh||fresh.id!==room.id)throw Error('The lobby changed. Retry loading the game.');
   this.apply(await this.request({type:'confirmGameSelection',roomId:room.id,intent,expectedRevision:fresh.revision}));
   this.publish({busy:false,uploading:false,status:'NES game loaded. Players can get ready.'});return {ok:true};
  }catch(error){if(this.gameSelection===intent){void this.request({type:'cancelGameSelection',roomId:room.id,intent}).catch(()=>{});this.failure(error);}return {ok:false,message:error instanceof Error?error.message:'Could not add this NES game to the lobby. Retry or choose another.'};}
  finally{if(this.gameSelection===intent){this.gameSelection=undefined;this.uploadAbort=undefined;this.publish({busy:false,uploading:false});}}
 }
 async host(file:File,fingerprint:Fingerprint,visibility:NewVisibility,password:string|undefined,current:()=>boolean) {
  if(!current()||!this.player()?.isLoaded(fingerprint)||file.size!==fingerprint.cartridge.bytes){this.publish({hostFailure:true,status:'The selected game changed or is not loaded. Select it again.'});return;}
  this.cancelCreation();const intent = crypto.randomUUID(), generation = this.creationGeneration;this.intent = intent;
  this.publish({busy:true,hostFailure:false,uploading:false,confirmingRoom:false,status:'Preparing lobby…',retryAfterMs:undefined});
  try {
   await this.connect();if(this.intent !== intent || generation !== this.creationGeneration || !current()) return;
   if(this.state.room)throw Error('Leave the current lobby before creating another.');
   const created=await this.request({type:'create',intent,visibility,password,fingerprint});
   if(this.intent !== intent || !current()) {await this.request({type:'cancelCreate',intent});return;}
   if(!created.room?.id||!this.token)throw Error('The lobby service did not return an upload session. Retry upload.');
   const controller=new AbortController();this.uploadAbort=controller;
   this.publish({uploading:true,status:'Uploading game…'});
   const receipt=await uploadRoomFile(clientConfig.coordinatorUrl,created.room.id,intent,this.token,file,(sent,total)=>{
    if(this.intent===intent&&generation===this.creationGeneration)this.publish({status:`Uploading game… ${Math.round(sent/1024)} / ${Math.ceil(total/1024)} KiB`});
   },controller.signal);
   if(this.uploadAbort===controller)this.uploadAbort=undefined;
   if(receipt.sha256!==fingerprint.romSha256)throw Error('The lobby server verified a different game. Retry upload.');
   if(this.intent !== intent || generation !== this.creationGeneration || !current() || !this.player()?.isLoaded(fingerprint)) {await this.request({type:'cancelCreate',intent});return;}
   this.publish({uploading:false,confirmingRoom:true,status:'Publishing lobby…'});
   const data = await this.request({type:'confirmCreate',intent});
   if(this.intent !== intent || !current() || !this.player()?.isLoaded(fingerprint)) {await this.request({type:'cancelCreate',intent});return;}
   this.apply(data);this.intent = undefined;this.publish({busy:false,uploading:false,confirmingRoom:false,hostFailure:false,status:'Lobby created. Everyone can get Ready, then the host can start.'});
  }catch(error) {if(this.intent === intent) {this.intent = undefined;this.uploadAbort=undefined;void this.request({type:'cancelCreate',intent}).catch(()=>{});this.publish({hostFailure:true,uploading:false,confirmingRoom:false});this.failure(error);}}
 }
 async startRoom(fingerprint:Fingerprint) {
  const room=this.state.room;if(!room||room.role!=='host')return;
  if(!this.player()?.isLoaded(fingerprint)){this.publish({status:messages.host_not_ready});return;}
  this.publish({busy:true,startingRoom:true,status:'Starting lobby…'});
  try {await this.connect();if(!this.player()?.isLoaded(fingerprint))throw Error(messages.host_not_ready);
   this.apply(await this.request({type:'prepareHost',roomId:room.id,membership:room.chatMembership,fingerprint}));
   if(this.state.room?.id!==room.id||this.state.room.chatMembership!==room.chatMembership||!this.player()?.isLoaded(fingerprint))throw Error('The lobby or loaded game changed. Review it before Start.');
   this.apply(await this.request({type:'startRoom',roomId:room.id,membership:room.chatMembership,fingerprint}));this.publish({busy:false,startingRoom:false});}
  catch(error){if(this.state.room?.started)this.publish({busy:false,startingRoom:false});else this.failure(error);}
  finally {this.publish({startingRoom:false});}
 }
 dismissRelease(){this.publish({releaseNotice:undefined});}
 cancelCreation() {++this.creationGeneration;this.uploadAbort?.abort();this.uploadAbort=undefined;const intent = this.intent??this.lobbyIntent;this.intent = undefined;this.lobbyIntent=undefined;if(intent) {void this.request({type:'cancelCreate',intent}).catch(()=>{});this.publish({busy:false,hostFailure:true,uploading:false,confirmingRoom:false,status:'Creation cancelled. The lobby was not opened.'});}}
 async preview(invite:string) {const generation = ++this.generation;this.previewingInvite=invite;this.previewingId=undefined;this.publish({busy:true,status:'Looking up invitation…'});try {await this.connect();if(generation !== this.generation) return;const data = await this.request({type:'preview',invite});if(generation !== this.generation) return;this.previewingId=data.preview?.id;this.apply(data);this.publish({busy:false,status:data.preview&&'openSlots' in data.preview&&data.preview.openSlots===0?'No open slots. Wait for the host or choose another lobby.':'Join reserves a slot and downloads the lobby game.'});}catch(error){if(generation === this.generation){this.publish({preview:undefined});this.failure(error);}}}
 clearPreview(){const pending=!!this.previewingInvite;if(pending)++this.generation;this.previewingInvite=undefined;this.previewingId=undefined;this.publish({preview:undefined,...(pending?{busy:false}:{}),status:'No lobby selected.'});}
 async join(invite:string,password?:string) {return this.joinTarget({type:'join',invite,password});}
 async joinCode(code:string,password?:string) {return this.joinTarget({type:'joinCode',code,password});}
 async claimCode(code:string,fingerprint:Fingerprint,visibility:NewVisibility='public',password?:string) {return this.joinTarget({type:'claimCode',code,fingerprint,visibility,password});}
 private async joinTarget(target:{type:'join';invite:string;password?:string}|{type:'joinCode';code:string;password?:string}|{type:'claimCode';code:string;fingerprint:Fingerprint;visibility:NewVisibility;password?:string}) {const generation = ++this.generation,intent = crypto.randomUUID(),claim=target.type==='claimCode';this.joining = intent;this.publish({busy:true,retryAfterMs:undefined,admissionError:undefined,status:claim?'Claiming Host…':'Joining lobby…'});try {await this.connect();if(generation !== this.generation) return;const data = await this.request({...target,intent});if(generation !== this.generation) {void this.request({type:'leave',intent}).catch(()=>{});return;}this.game.cancelIntent();this.apply(data);this.publish({busy:false,admissionError:undefined,status:claim?'You are Host. Load a NES game, then get Ready.':data.room?.fingerprint?'Joined lobby. Preparing the NES game…':'Joined lobby. Waiting for the host to load a NES game.'});}catch(error){if(generation === this.generation){const code=(error as Error & {code?:string}).code;if(target.type==='join'&&code==='room_full'){void this.request({type:'preview',invite:target.invite}).then(data=>{if(generation===this.generation)this.apply(data);}).catch(()=>{});}else if(target.type==='join'&&['room_unavailable','host_reconnecting'].includes(code??''))this.publish({preview:undefined});if(!claim)this.publish({admissionError:{code,message:error instanceof Error?error.message:'Unable to reach the lobby service.'}});this.failure(error);if(claim)throw error;}}finally{if(this.joining === intent) this.joining = undefined;}}
 clearAdmissionError() {this.publish({admissionError:undefined,retryAfterMs:undefined});}
 cancelJoin() {if(this.joining)this.cancelPending();this.clearAdmissionError();}
 cancelPending() {++this.generation;this.cancelCreation();const intent = this.joining;this.joining = undefined;if(intent) void this.request({type:'leave',intent}).catch(()=>{});this.publish({busy:false,status:'Cancelled. Your local game is preserved.'});}
 async act(command:Exclude<Command,{type:'hello'}>) {const leaving=(command.type==='close'||command.type==='leave')&&!!this.state.room;
  if(leaving)this.voluntaryExitRoomId=this.state.room!.id;
  try {await this.connect();this.apply(await this.request(command));if(leaving){this.setRoom(undefined);this.publish({releaseNotice:undefined});}return true;}
  catch(error){if(leaving)this.voluntaryExitRoomId=undefined;this.failure(error);return false;}}
 private async refreshDirectory() {try {this.apply(await this.request({type:'directory'}));if(!this.state.room&&!this.previewingInvite&&this.state.status.startsWith('Lobby connection lost.'))this.publish({status:'No lobby selected.'});}catch(error){this.publish({directoryStatus:'stale',directoryError:error instanceof Error ? error.message:'The directory is unavailable.'});}}
 async watchDirectory() {this.watchingDirectory=true;this.publish({directoryStatus:'loading',directoryError:undefined});const connected=this.state.connected;try {await this.connect();if(connected) await this.refreshDirectory();}catch(error){this.publish({directoryStatus:'stale',directoryError:error instanceof Error ? error.message:'The directory is unavailable.'});}}
 async retryPeer(pairId?:string){for(const peer of this.state.room?.peers??[])if(peer.epoch&&(!pairId||peer.pairId===pairId))await this.act({type:'peerRetry',pairId:peer.pairId,epoch:peer.epoch});}
 async reconnect() {try {await this.connect();if(!this.state.room&&this.previewingInvite){await this.preview(this.previewingInvite);return;}this.publish({status:this.state.room ? 'Lobby connection restored. Existing reservation deadlines are unchanged.' : 'Connection restored. Any previous lobby or reservation has expired; retry hosting or joining.'});}catch(error){this.failure(error);}}
 newGuest() {++this.generation;this.cancelCreation();this.tabSession.close();this.token = undefined;try {sessionStorage.removeItem('retro-coop-guest');}catch{}this.socket?.close();this.setRoom(undefined);this.publish({session:undefined,room:undefined,needsNewGuest:false,status:'Guest session cleared. Retry hosting or joining when ready.'});}
 localPlayIntent(){this.game.playIntent();}
 prepareMember(){const room=this.state.room;if(!room?.fingerprint||!this.selectedFile||!matchesFile(room.fingerprint,this.selectedFile)||!this.player()?.isLoaded(this.selectedFile))return;this.game.playIntent();}
 memberToken(){return this.token;}
 async memberAcquisition(roomId:string,membership:string,phase:'checking'|'downloading'|'loading'|'loaded'|'failed'){if(this.state.room?.id!==roomId||this.state.room.chatMembership!==membership)return false;try{await this.request({type:'memberAcquisition',roomId,membership,phase});return true;}catch(error){if(this.state.room?.id===roomId&&this.state.room.chatMembership===membership)this.publish({status:error instanceof Error?error.message:'Lobby status could not update. Reconnect lobbies.'});return false;}}

 private reportLoadedGame(){const room=this.state.room,file=this.selectedFile;if(!room?.fingerprint||room.role==='member'&&!room.catalogId||!file||!matchesFile(room.fingerprint,file)||!this.player()?.isLoaded(file)||room.slots.find(slot=>slot.member?.id===room.chatMembership)?.member?.acquisition==='loaded')return;const key=room.id+room.chatMembership;if(this.loadedReport===key)return;this.loadedReport=key;void this.request({type:'memberAcquisition',roomId:room.id,membership:room.chatMembership,phase:'loaded'}).then(data=>{if(this.state.room?.id===room.id&&this.state.room.chatMembership===room.chatMembership)this.apply(data);}).catch(error=>{if(this.loadedReport===key){this.loadedReport=undefined;this.failure(error);}}).finally(()=>{if(this.loadedReport===key)this.loadedReport=undefined;});}
 selectedGame(file:Fingerprint){this.selectedFile=file;this.game.selected(file);this.reportLoadedGame();}
 isMember(){return this.state.room?.role==='member';}
 observe(){this.game.observe();}
 retryGame(){const room=this.state.room,file=this.selectedFile;if(room?.role==='host'&&!room.established&&file){void this.game.resumeReady().then(()=>this.startRoom(file));return;}this.game.retry();}
 cancelSynchronization(){this.game.cancelIntent();}
 readyToResume(){void this.game.resumeReady();}
 resumeTogether(){void this.game.resumeTogether();}
 pauseTogether(){this.game.requestPause();}
 chatDraft(text:string){this.chat.draft(text);}
 async sendChat(){await this.chat.send(this.state.session?.nickname ?? 'Guest');}
 discardChat(){this.chat.discard();}
 dispose() {++this.generation;this.game.dispose();this.closePeers();this.cancelCreation();this.disposed = true;this.tabSession.close();this.voice.dispose();clearInterval(this.heartbeat);this.socket?.close();for(const item of this.pending.values()) {clearTimeout(item.timer);item.reject(Error('Room client disposed'));}this.pending.clear();}
}
