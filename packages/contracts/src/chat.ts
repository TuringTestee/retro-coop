export const CHAT_LIMITS={characters:500,retained:100,rateCount:5,rateWindowMs:10_000} as const;
export type ChatCommand={type:'chat';requestId:string;roomId:string;membership:string;clientId:string;text:string};
export type ChatMessage={id:string;clientId:string;sender:'host'|'guest';nickname:string;text:string;at:number};
export type ChatAck={clientId:string;messageId:string};
export type ChatEvent={type:'chat';roomId:string;membership:string;message:ChatMessage};
export function validChatText(value:unknown):value is string {return typeof value==='string' && value.trim().length>0 && [...value].length<=CHAT_LIMITS.characters && !/[\u0000-\u0008\u000b-\u001f\u007f]/u.test(value);}
