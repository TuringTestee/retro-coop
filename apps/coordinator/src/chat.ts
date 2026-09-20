import {createHash,randomUUID} from 'node:crypto';
import {type ChatAck,type ChatMessage} from '../../../packages/contracts/src/chat.ts';

/** Room-owned retry receipts only: raw messages are broadcast without server history. */
export class RoomChat {
 private accepted=new Map<string,{clientId:string;digest:string;id:string}>();
 send(member:string,clientId:string,text:string,sender:'host'|'guest',nickname:string,at:number):{ack:ChatAck;message?:ChatMessage} {
  const digest=createHash('sha256').update(text).digest('hex'),last=this.accepted.get(member);
  if(last?.clientId===clientId) {
   if(last.digest!==digest) throw Error('chat_retry_changed');
   return {ack:{clientId,messageId:last.id}};
  }
  const message:ChatMessage={id:randomUUID(),clientId,sender,nickname,text,at};
  this.accepted.set(member,{clientId,digest,id:message.id});
  return {ack:{clientId,messageId:message.id},message};
 }
 leave(member:string){this.accepted.delete(member);}
}
