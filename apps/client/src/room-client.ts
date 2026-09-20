import { clientConfig } from './config.ts';
import {matchesFile} from '../../../packages/contracts/src/rooms.ts';
import type { Fingerprint, RoomCommand, RoomData, RoomEvent, RoomPreview, RoomView, SessionInfo, Visibility } from '../../../packages/contracts/src/rooms.ts';
type Command = RoomCommand extends infer T ? T extends RoomCommand ? Omit<T,'requestId'> : never : never;
export type RoomState = { room?:RoomView; preview?:RoomPreview; session?:SessionInfo; status:string; busy:boolean; connected:boolean; retryAfterMs?:number; needsNewGuest?:boolean };
const messages:Record<string,string> = {
 capacity:'Room capacity is full. Your local game is preserved. Try again later.',rate_limited:'Too many attempts. Wait before retrying.',place_taken:'That place was just taken. Try joining again when it becomes available.',
 room_unavailable:'This room is closed, unavailable, or the invitation has expired.',session_expired:'Your guest session expired or the service restarted. Start a new guest session to continue.',
 host_only:'Only the host can change this room.',host_reconnecting:'The host is reconnecting. Try joining again later.',reservation_expired:'Your 120-second reservation expired. Retry join to claim a new place.',
 host_expired:'The host did not return. This room has closed.',host_closed:'The host closed the room.',removed:'The host removed you from this room.',left:'You left the room. Your local game is still available.',
 service_restarted:'The service restarted. Ephemeral rooms have closed.',creation_cancelled:'Room creation cancelled. Your game stays local.',creation_expired:'Room creation timed out. Your game stays local.',cancelled:'Room creation cancelled.',
};
export class RoomClient {
 private socket?:WebSocket;
 private connecting?:Promise<void>;
 private heartbeat?:ReturnType<typeof setInterval>;
 private disposed = false;
 private token?:string;
 private intent?:string;
 private generation = 0;
 private joining?:string;
 private pending = new Map<string,{resolve:(data:RoomData)=>void;reject:(error:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
 private state:RoomState = {status:'Choose a file to create a room. Your file stays here.',busy:false,connected:false};
 constructor(private update:(state:RoomState)=>void) {try {this.token = sessionStorage.getItem('retro-coop-guest') ?? undefined;}catch{}}
 private publish(patch:Partial<RoomState>) {if(this.disposed) return;this.state = {...this.state,...patch};this.update(this.state);}
 private apply(data:RoomData) {
  if(data.session) {this.token = data.session.token;try {sessionStorage.setItem('retro-coop-guest',this.token);}catch{}this.publish({session:data.session});}
  if(data.preview) this.publish({preview:data.preview});
  if(data.room) this.publish({room:data.room});
 }
 private request(command:Command):Promise<RoomData> {
  if(this.socket?.readyState !== WebSocket.OPEN) return Promise.reject(Error('The room service is disconnected. Your local game is preserved.'));
  const requestId = crypto.randomUUID();
  return new Promise((resolve,reject)=>{
   const timer = setTimeout(()=>{this.pending.delete(requestId);reject(Error('The room service did not respond. Retry or cancel; your local game is preserved.'));},8000);
   this.pending.set(requestId,{resolve,reject,timer});this.socket!.send(JSON.stringify({...command,requestId}));
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
     if(event.ok) pending.resolve(event.data);else {this.publish({retryAfterMs:event.retryAfterMs,needsNewGuest:event.error === 'session_expired'});pending.reject(Error(messages[event.error] ?? 'The room request was rejected. Your local game is preserved.'));}
    } else if(event.type === 'room') this.publish({room:event.room});
    else if(event.type === 'ended') this.publish({room:undefined,busy:false,status:messages[event.reason] ?? 'This room ended. Your local game is preserved.'});
   };
   socket.onopen = () => {void this.request({type:'hello',...(this.token ? {token:this.token}:{})}).then(data=>{
    clearTimeout(deadline);if(this.disposed) {socket.close();return;}this.publish({room:data.room});this.apply(data);this.publish({connected:true});
    this.heartbeat = setInterval(()=>{void this.request({type:'heartbeat'}).catch(()=>{});},10_000);resolve();
   }).catch(error=>{clearTimeout(deadline);socket.close();reject(error);});};
   socket.onerror = () => {clearTimeout(deadline);reject(Error('The room service is unavailable. Your local game is preserved.'));};
   socket.onclose = () => {
    if(this.socket !== socket) return;
    clearTimeout(deadline);clearInterval(this.heartbeat);for(const pending of this.pending.values()) {clearTimeout(pending.timer);pending.reject(Error('The room service disconnected. Your local game is preserved.'));}this.pending.clear();
    this.publish({connected:false,busy:false,status:'Room connection lost. Reconnect to recover an active room or unexpired reservation. Your local game is preserved.'});reject(Error('Room connection lost. Your local game is preserved.'));
   };
  }).finally(()=>{this.connecting = undefined;});
  return this.connecting;
 }
 private failure(error:unknown) {this.publish({busy:false,status:error instanceof Error ? error.message:'Unable to reach the room service.'});}
 async host(fingerprint:Fingerprint,visibility:Visibility) {
  this.cancelCreation();const intent = crypto.randomUUID(), generation = this.generation;this.intent = intent;
  this.publish({busy:true,status:'Creating your room…',retryAfterMs:undefined});
  try {
   await this.connect();if(this.intent !== intent || generation !== this.generation) return;
   if(this.state.room) {
    if(this.state.room.role !== 'host') {this.intent = undefined;this.publish({busy:false});return;}
    if(matchesFile(this.state.room.fingerprint,fingerprint)) {this.intent = undefined;this.publish({busy:false,status:'Your local file matches the existing room. Its guest reservation is preserved.'});return;}
    await this.request({type:'close'});if(this.intent !== intent) return;
   }
   await this.request({type:'create',intent,visibility,fingerprint});
   if(this.intent !== intent) {await this.request({type:'cancelCreate',intent});return;}
   const data = await this.request({type:'confirmCreate',intent});
   if(this.intent !== intent) {await this.request({type:'cancelCreate',intent});return;}
   this.apply(data);this.intent = undefined;this.publish({busy:false,status:'Room created. You can play locally while your friend prepares their matching file.'});
  }catch(error) {if(this.intent === intent) {this.intent = undefined;void this.request({type:'cancelCreate',intent}).catch(()=>{});this.failure(error);}}
 }
 cancelCreation() {++this.generation;const intent = this.intent;this.intent = undefined;if(intent) {void this.request({type:'cancelCreate',intent}).catch(()=>{});this.publish({busy:false,status:'Room creation cancelled. Your game stays local.'});}}
 async preview(invite:string) {const generation = ++this.generation;this.publish({busy:true,status:'Looking up invitation…'});try {await this.connect();if(generation !== this.generation) return;const data = await this.request({type:'preview',invite});if(generation !== this.generation) return;this.apply(data);this.publish({busy:false,status:'Join reserves Player 2 for 120 seconds. You will need your own matching file.'});}catch(error){if(generation === this.generation) this.failure(error);}}
 async join(invite:string) {const generation = ++this.generation,intent = crypto.randomUUID();this.joining = intent;this.publish({busy:true,status:'Reserving Player 2…'});try {await this.connect();if(generation !== this.generation) return;const data = await this.request({type:'join',invite,intent});if(generation !== this.generation) {void this.request({type:'leave',intent}).catch(()=>{});return;}this.apply(data);this.publish({busy:false,status:'Player 2 reserved for 120 seconds. Choose your matching file. Shared gameplay is not available in this build yet.'});}catch(error){if(generation === this.generation) this.failure(error);}finally{if(this.joining === intent) this.joining = undefined;}}
 cancelPending() {this.cancelCreation();const intent = this.joining;this.joining = undefined;if(intent) void this.request({type:'leave',intent}).catch(()=>{});this.publish({busy:false,status:'Cancelled. Your local game is preserved.'});}
 async act(command:Exclude<Command,{type:'hello'}>) {try {await this.connect();this.apply(await this.request(command));}catch(error){this.failure(error);}}
 async reconnect() {try {await this.connect();this.publish({status:this.state.room ? 'Room connection restored. Existing reservation deadlines are unchanged.' : 'Connection restored. Any previous room or reservation has expired; retry hosting or joining.'});}catch(error){this.failure(error);}}
 newGuest() {this.cancelCreation();this.token = undefined;try {sessionStorage.removeItem('retro-coop-guest');}catch{}this.socket?.close();this.publish({session:undefined,room:undefined,needsNewGuest:false,status:'Guest session cleared. Retry hosting or joining when ready.'});}
 dispose() {this.cancelCreation();this.disposed = true;clearInterval(this.heartbeat);this.socket?.close();for(const item of this.pending.values()) {clearTimeout(item.timer);item.reject(Error('Room client disposed'));}this.pending.clear();}
}
