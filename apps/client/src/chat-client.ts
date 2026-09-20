import {CHAT_LIMITS,type ChatCommand,type ChatEvent,type ChatMessage} from '../../../packages/contracts/src/chat.ts';
import type {RoomData,RoomView} from '../../../packages/contracts/src/rooms.ts';
export type ChatRoom=Pick<RoomView,'id'|'chatMembership'|'role'>;
type Outbox={command:Omit<ChatCommand,'requestId'>;nickname:string;sender:'host'|'guest';at:number;error?:string;retryAt?:number};
export type ChatState={messages:ChatMessage[];draft:string;outbox?:Outbox;sending:boolean};
export class ChatClient {
 private room?:ChatRoom;
 private state:ChatState={messages:[],draft:'',sending:false};
 private update:(state:ChatState)=>void;
 private request:(command:Omit<ChatCommand,'requestId'>)=>Promise<RoomData>;
 constructor(update:(state:ChatState)=>void,request:(command:Omit<ChatCommand,'requestId'>)=>Promise<RoomData>){this.update=update;this.request=request;}
 private publish(patch:Partial<ChatState>){this.state={...this.state,...patch};this.update(this.state);}
 enter(room?:ChatRoom):ChatState {
  if(this.room?.id!==room?.id || this.room?.chatMembership!==room?.chatMembership) this.state={messages:[],draft:'',sending:false};
  this.room=room;return this.state;
 }
 draft(text:string){if(!this.state.outbox) this.publish({draft:text});}
 private append(message:ChatMessage){return this.state.messages.some(item=>item.id===message.id) ? this.state.messages:[...this.state.messages,message].slice(-CHAT_LIMITS.retained);}
 receive(event:ChatEvent){
  if(event.roomId!==this.room?.id || event.membership!==this.room?.chatMembership) return;
  const own=this.state.outbox?.command.clientId===event.message.clientId;
  this.publish({messages:this.append(event.message),...(own ? {outbox:undefined,draft:'',sending:false}:{})});
 }
 async send(nickname:string){
  if(!this.room || this.state.sending) return;
  const outbox=this.state.outbox ?? {command:{type:'chat' as const,roomId:this.room.id,membership:this.room.chatMembership,clientId:crypto.randomUUID(),text:this.state.draft},nickname,sender:this.room.role,at:Date.now()};
  this.publish({outbox,sending:true});
  try {
   const result=await this.request(outbox.command);
   if(this.state.outbox!==outbox) return;
   const ack=result.chatAck;if(!ack || ack.clientId!==outbox.command.clientId) throw Error('Delivery was not confirmed. Retry explicitly.');
   this.publish({messages:this.append({id:ack.messageId,clientId:ack.clientId,text:outbox.command.text,nickname:outbox.nickname,sender:outbox.sender,at:outbox.at}),draft:'',outbox:undefined,sending:false});
  }catch(error){if(this.state.outbox===outbox) this.publish({sending:false,outbox:{...outbox,error:error instanceof Error ? error.message:'Delivery unconfirmed. Retry explicitly.',retryAt:error instanceof Error && 'retryAfterMs' in error && typeof error.retryAfterMs==='number' ? Date.now()+error.retryAfterMs:undefined}});}
 }
 discard(){if(!this.state.sending) this.publish({outbox:undefined,draft:''});}
}
