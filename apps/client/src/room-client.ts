import {VoiceSession,type VoiceState} from './voice.ts';
import {ChatClient,type ChatState} from './chat-client.ts';
import {PeerConnection,type ConnectionState} from './peer.ts';
import type {ConnectionPolicy,PeerEvent} from '../../../packages/contracts/src/peer.ts';
import { clientConfig } from './config.ts';
import {matchesFile} from '../../../packages/contracts/src/rooms.ts';
import type { Fingerprint, RoomCommand, RoomData, RoomEvent, RoomPreview, RoomView, SessionInfo, Visibility } from '../../../packages/contracts/src/rooms.ts';
type Command = RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'> : never : never;
export type RoomState = { voice?:VoiceState; chat?:ChatState; connection?:ConnectionState; directory?:RoomPreview[]; directoryStatus?:'loading'|'live'|'stale'; directoryError?:string; room?:RoomView; preview?:RoomPreview; session?:SessionInfo; status:string; busy:boolean; connected:boolean; retryAfterMs?:number; needsNewGuest?:boolean };
export function connectionStatus(state:RoomState) {
 const status=state.room?.peer.status;
 if(status==='relay_unavailable') return 'Relay service is unavailable. Stay in the room or retry; Relay only will not switch to direct.';
 if(status==='relay_capacity') return 'Relay capacity is full. Stay in the room or retry; Relay only will not switch to direct.';
 return (state.connection?.status ?? 'No peer connection.')+(state.connection?.route ? ` Route: ${state.connection.route}.`:'');
}
const messages:Record<string,string> = {
 capacity:'Room capacity is full. Your local game is preserved. Try again later.',rate_limited:'Too many attempts. Wait before retrying.',place_taken:'That place was just taken. Try joining again when it becomes available.',
 room_unavailable:'This room is closed, unavailable, or the invitation has expired.',session_expired:'Your guest session expired or the service restarted. Start a new guest session to continue.',
 host_only:'Only the host can change this room.',host_reconnecting:'The host is reconnecting. Try joining again later.',reservation_expired:'Your 120-second reservation expired. Retry join to claim a new place.',
 host_expired:'The host did not return. This room has closed.',host_closed:'The host closed the room.',removed:'The host removed you from this room.',left:'You left the room. Your local game is still available.',
 service_restarted:'The service restarted. Ephemeral rooms have closed.',creation_cancelled:'Room creation cancelled. Your game stays local.',creation_expired:'Room creation timed out. Your game stays local.',cancelled:'Room creation cancelled.',
};
export class RoomClient {
 readonly voice=new VoiceSession(voice=>this.publish({voice}));
 private chat=new ChatClient(chat=>this.publish({chat}),command=>this.request(command));
 private socket?:WebSocket;
 private policy:ConnectionPolicy='standard';
 private peer=new PeerConnection(command=>this.request(command),connection=>this.publish({connection}),undefined,()=>this.policy,this.voice);
 private connecting?:Promise<void>;
 private heartbeat?:ReturnType<typeof setInterval>;
 private disposed = false;
 private watchingDirectory = false;
 private token?:string;
 private intent?:string;
 private generation = 0;
 private replacement?:{room:string;fingerprint:Fingerprint};
 private joining?:string;
 private pending = new Map<string,{kind:Command['type'];resolve:(data:RoomData)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
 private state:RoomState = {status:'Choose a file to create a room. Your file stays here.',busy:false,connected:false};
 constructor(private update:(state:RoomState)=>void,private confirmReplacement:()=>boolean = ()=>false,policy:ConnectionPolicy='standard') {this.policy=policy;try {this.token = sessionStorage.getItem('retro-coop-guest') ?? undefined;}catch{}this.publish({voice:this.voice.current()});}
 private publish(patch:Partial<RoomState>) {if(this.disposed) return;this.state = {...this.state,...patch};this.update(this.state);}
 private setRoom(room?:RoomView){this.publish({room,chat:this.chat.enter(room)});}
 private apply(data:RoomData) {
  if(data.session) {this.token = data.session.token;try {sessionStorage.setItem('retro-coop-guest',this.token);}catch{}this.publish({session:data.session});}
  if(data.directory) this.publish({directory:data.directory,directoryStatus:'live',directoryError:undefined});
  if(data.preview) this.publish({preview:data.preview});
  if(data.room) this.setRoom(data.room);
 }
 private request(command:Command):Promise<RoomData> {
  if(this.socket?.readyState !== WebSocket.OPEN) return Promise.reject(Error('The room service is disconnected. Your local game is preserved.'));
  const requestId = crypto.randomUUID();
  return new Promise((resolve,reject)=>{
   const timer = setTimeout(()=>{this.pending.delete(requestId);reject(Error('The room service did not respond. Retry or cancel; your local game is preserved.'));},8000);
   this.pending.set(requestId,{kind:command.type,resolve,reject,timer});this.socket!.send(JSON.stringify({...command,requestId}));
  });
 }
 private async connect() {
  if(this.state.connected && this.socket?.readyState === WebSocket.OPEN) return;
  if(this.connecting) return this.connecting;
  const endpoint = new URL(clientConfig.coordinatorUrl,location.href);endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:':'ws:';endpoint.pathname = endpoint.pathname.replace(/\/$/,'')+'/ws';endpoint.hash = '';endpoint.search = '';
  const socket = new WebSocket(endpoint);this.socket = socket;
  this.connecting = new Promise<void>((resolve,reject)=>{
   const deadline = setTimeout(()=>{socket.close();reject(Error('The room service is unavailable. Your local game is preserved.'));},8000);
   socket.onmessage = ({data}) => {
    if(this.socket !== socket) return;
    let event:RoomEvent;try {event = JSON.parse(data);}catch{return;}
    if(event.type === 'result') {
     const pending = this.pending.get(event.requestId);if(!pending) return;clearTimeout(pending.timer);this.pending.delete(event.requestId);
     if(event.ok) pending.resolve(event.data);else {this.publish({...(pending.kind==='chat' ? {}:{retryAfterMs:event.retryAfterMs}),needsNewGuest:event.error === 'session_expired'});pending.reject(Object.assign(Error(messages[event.error] ?? 'The room request was rejected. Your local game is preserved.'),{retryAfterMs:event.retryAfterMs}));}
    } else if(event.type==='chat') this.chat.receive(event);
    else if(event.type.startsWith('peer')) this.peer.handle(event as PeerEvent);
    else if(event.type === 'directory') this.publish({directory:event.rooms,directoryStatus:'live',directoryError:undefined});
    else if(event.type === 'room') this.setRoom(event.room);
    else if(event.type === 'ended') {this.peer.close();this.setRoom(undefined);this.publish({busy:false,status:messages[event.reason] ?? 'This room ended. Your local game is preserved.'});}
   };
   socket.onopen = () => {void this.request({type:'hello',policy:this.policy,...(this.token ? {token:this.token}:{})}).then(data=>{
    clearTimeout(deadline);if(this.disposed) {socket.close();return;}this.setRoom(data.room);this.apply(data);this.publish({connected:true});
    if(this.watchingDirectory) void this.refreshDirectory();
    this.heartbeat = setInterval(()=>{void this.request({type:'heartbeat'}).catch(()=>{if(this.socket===socket) socket.close();});},10_000);resolve();
   }).catch(error=>{clearTimeout(deadline);socket.close();reject(error);});};
   socket.onerror = () => {clearTimeout(deadline);reject(Error('The room service is unavailable. Your local game is preserved.'));};
   socket.onclose = () => {
    if(this.socket !== socket) return;
    this.peer.close('Signaling disconnected. Reconnect the room before retrying peers.');
    clearTimeout(deadline);clearInterval(this.heartbeat);for(const pending of this.pending.values()) {clearTimeout(pending.timer);pending.reject(Error('The room service disconnected. Your local game is preserved.'));}this.pending.clear();
    this.publish({connected:false,busy:false,...(this.watchingDirectory ? {directoryStatus:'stale' as const,directoryError:'The room service disconnected. Retry for current availability.'}:{}),status:'Room connection lost. Reconnect to recover an active room or unexpired reservation. Your local game is preserved.'});reject(Error('Room connection lost. Your local game is preserved.'));
   };
  }).finally(()=>{this.connecting = undefined;});
  return this.connecting;
 }
 private failure(error:unknown) {this.publish({busy:false,status:error instanceof Error ? error.message:'Unable to reach the room service.'});}
 beginSelection() {this.replacement=undefined;this.cancelCreation();}
 async approveSelection(fingerprint:Fingerprint,isCurrent:()=>boolean):Promise<boolean> {
  if(!this.token && !this.state.room) return isCurrent();
  try {await this.connect();}catch {return isCurrent();} // Local play remains available offline; hosting still requires consent.
  if(!isCurrent()) return false;
  const room=this.state.room;
  if(!room || room.role!=='host' || matchesFile(room.fingerprint,fingerprint)) return true;
  if(!this.confirmReplacement()) return false;
  if(!isCurrent()) return false;
  this.replacement={room:room.id,fingerprint};return true;
 }
 async host(fingerprint:Fingerprint,visibility:Visibility) {
  this.cancelCreation();const intent = crypto.randomUUID(), generation = this.generation;this.intent = intent;
  this.publish({busy:true,status:'Creating your room…',retryAfterMs:undefined});
  try {
   await this.connect();if(this.intent !== intent || generation !== this.generation) return;
   if(this.state.room) {
    if(this.state.room.role !== 'host') {this.intent = undefined;this.publish({busy:false});return;}
    if(matchesFile(this.state.room.fingerprint,fingerprint)) {this.intent = undefined;this.publish({busy:false,status:'Your local file matches the existing room. Its guest reservation is preserved.'});return;}
    const approved=this.replacement?.room===this.state.room.id && matchesFile(this.replacement.fingerprint,fingerprint);
    if(!approved && !this.confirmReplacement()) {this.intent=undefined;this.publish({busy:false,status:'Room replacement cancelled. Your existing room is preserved.'});return;}
    this.replacement=undefined;
    await this.request({type:'close'});if(this.intent !== intent) return;
   }
   await this.request({type:'create',intent,visibility,fingerprint,policy:this.policy});
   if(this.intent !== intent) {await this.request({type:'cancelCreate',intent});return;}
   const data = await this.request({type:'confirmCreate',intent});
   if(this.intent !== intent) {await this.request({type:'cancelCreate',intent});return;}
   this.apply(data);this.intent = undefined;this.publish({busy:false,status:'Room created. You can play locally while your friend prepares their matching file.'});
  }catch(error) {if(this.intent === intent) {this.intent = undefined;void this.request({type:'cancelCreate',intent}).catch(()=>{});this.failure(error);}}
 }
 cancelCreation() {++this.generation;const intent = this.intent;this.intent = undefined;if(intent) {void this.request({type:'cancelCreate',intent}).catch(()=>{});this.publish({busy:false,status:'Room creation cancelled. Your game stays local.'});}}
 async preview(invite:string) {const generation = ++this.generation;this.publish({busy:true,status:'Looking up invitation…'});try {await this.connect();if(generation !== this.generation) return;const data = await this.request({type:'preview',invite});if(generation !== this.generation) return;this.apply(data);this.publish({busy:false,status:'Join reserves Player 2 for 120 seconds. You will need your own matching file.'});}catch(error){if(generation === this.generation) this.failure(error);}}
 async join(invite:string) {return this.joinTarget({type:'join',invite});}
 async joinCode(code:string) {return this.joinTarget({type:'joinCode',code});}
 private async joinTarget(target:{type:'join';invite:string}|{type:'joinCode';code:string}) {const generation = ++this.generation,intent = crypto.randomUUID();this.joining = intent;this.publish({busy:true,status:'Reserving Player 2…'});try {await this.connect();if(generation !== this.generation) return;const data = await this.request({...target,intent,policy:this.policy});if(generation !== this.generation) {void this.request({type:'leave',intent}).catch(()=>{});return;}this.apply(data);this.publish({busy:false,status:'Player 2 reserved for 120 seconds. Choose your matching file. Shared gameplay is not available in this build yet.'});}catch(error){if(generation === this.generation) this.failure(error);}finally{if(this.joining === intent) this.joining = undefined;}}
 cancelPending() {this.cancelCreation();const intent = this.joining;this.joining = undefined;if(intent) void this.request({type:'leave',intent}).catch(()=>{});this.publish({busy:false,status:'Cancelled. Your local game is preserved.'});}
 async act(command:Exclude<Command,{type:'hello'}>) {try {await this.connect();this.apply(await this.request(command));}catch(error){this.failure(error);}}
 private async refreshDirectory() {try {this.apply(await this.request({type:'directory'}));}catch(error){this.publish({directoryStatus:'stale',directoryError:error instanceof Error ? error.message:'The directory is unavailable.'});}}
 async watchDirectory() {this.watchingDirectory=true;this.publish({directoryStatus:'loading',directoryError:undefined});const connected=this.state.connected;try {await this.connect();if(connected) await this.refreshDirectory();}catch(error){this.publish({directoryStatus:'stale',directoryError:error instanceof Error ? error.message:'The directory is unavailable.'});}}
 async setPolicy(policy:ConnectionPolicy) {if(policy===this.policy) return;this.policy=policy;this.peer.close(this.state.room?.peer.epoch ? 'Connection policy changed. Preparing a new connection…':'Connection preference saved. Choose a game or join a room.');if(this.state.connected) await this.act({type:'peerPolicy',policy});}
 async retryPeer() {const epoch=this.state.room?.peer.epoch;if(epoch) await this.act({type:'peerRetry',epoch});}
 async reconnect() {try {await this.connect();this.publish({status:this.state.room ? 'Room connection restored. Existing reservation deadlines are unchanged.' : 'Connection restored. Any previous room or reservation has expired; retry hosting or joining.'});}catch(error){this.failure(error);}}
 newGuest() {this.cancelCreation();this.token = undefined;try {sessionStorage.removeItem('retro-coop-guest');}catch{}this.socket?.close();this.setRoom(undefined);this.publish({session:undefined,room:undefined,needsNewGuest:false,status:'Guest session cleared. Retry hosting or joining when ready.'});}
 chatDraft(text:string){this.chat.draft(text);}
 async sendChat(){await this.chat.send(this.state.session?.nickname ?? 'Guest');}
 discardChat(){this.chat.discard();}
 dispose() {this.peer.close();this.cancelCreation();this.disposed = true;this.voice.dispose();clearInterval(this.heartbeat);this.socket?.close();for(const item of this.pending.values()) {clearTimeout(item.timer);item.reject(Error('Room client disposed'));}this.pending.clear();}
}
