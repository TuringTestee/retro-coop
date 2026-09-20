import {object,keys,token,integer,sha256} from './protocol-validation.ts';
/** One protocol owner for frame discipline, independent of local file admission. */
export const gameplayLimits={delayMin:3,delayMax:8,delayDefault:6,inputWindow:120,hashInterval:120,packetBytes:512,barrierMs:10_000,stallMs:1000} as const;
export type GameRole='host'|'guest';
const reasons=['focus','device','network','mismatch','cancelled','user'] as const;
export type GameReason=typeof reasons[number];
const validReason=(value:unknown):value is GameReason=>typeof value==='string'&&(reasons as readonly string[]).includes(value);
export type GameView={ready?:GameRole[];status:'waiting'|'starting'|'playing'|'pausing'|'resume_ready'|'paused'|'late_join'|'failed';epoch?:string;delay?:number;reason?:string};
export type GameCommand=
 | {type:'gameReady';requestId:string;peerEpoch:string;frame:number;fresh:boolean;hash:string;delay:number}
 | {type:'gameAck';requestId:string;epoch:string;hash:string}
 | {type:'gamePause';requestId:string;epoch:string;frame:number;reason:GameReason}
 | {type:'gamePaused';requestId:string;epoch:string;frame:number;hash:string}
 | {type:'gameResume';requestId:string;epoch:string}
 | {type:'gameAbort';requestId:string;epoch:string;reason:GameReason};
export type GameEvent=
 | {type:'gameInspect';peerEpoch:string}
 | {type:'gamePrepare';peerEpoch:string;epoch:string;hash:string;delay:number}
 | {type:'gameStart';peerEpoch:string;epoch:string;delay:number}
 | {type:'gamePauseAt';epoch:string;frame:number;reason:string}
 | {type:'gameStop';epoch?:string;reason:string};
export type GamePacket={kind:'input';epoch:string;frame:number;mask:number}|{kind:'hash';epoch:string;frame:number;hash:string};

export function parseGameCommand(value:unknown):GameCommand|undefined {
 if(!object(value)||!token(value.requestId)) return;
 const base=['type','requestId'];
 if(value.type==='gameReady' && keys(value,[...base,'peerEpoch','frame','fresh','hash','delay']) && token(value.peerEpoch) && integer(value.frame,0,Number.MAX_SAFE_INTEGER) && typeof value.fresh==='boolean' && sha256(value.hash) && integer(value.delay,gameplayLimits.delayMin,gameplayLimits.delayMax)) return value as GameCommand;
 if(value.type==='gameAck' && keys(value,[...base,'epoch','hash']) && token(value.epoch) && sha256(value.hash)) return value as GameCommand;
 if(value.type==='gamePause' && keys(value,[...base,'epoch','frame','reason']) && token(value.epoch) && integer(value.frame,0,Number.MAX_SAFE_INTEGER) && validReason(value.reason)) return value as GameCommand;
 if(value.type==='gameAbort' && keys(value,[...base,'epoch','reason']) && token(value.epoch) && validReason(value.reason))return value as GameCommand;
 if(value.type==='gamePaused' && keys(value,[...base,'epoch','frame','hash']) && token(value.epoch) && integer(value.frame,0,Number.MAX_SAFE_INTEGER) && sha256(value.hash))return value as GameCommand;
 if(value.type==='gameResume' && keys(value,[...base,'epoch']) && token(value.epoch))return value as GameCommand;
}
export function parseGamePacket(raw:unknown):GamePacket|undefined {
 if(typeof raw!=='string' || raw.length>gameplayLimits.packetBytes) return;
 let value;try{value=JSON.parse(raw);}catch{return;}
 if(!object(value)||!token(value.epoch)||!integer(value.frame,0,Number.MAX_SAFE_INTEGER)) return;
 if(value.kind==='input' && keys(value,['kind','epoch','frame','mask']) && integer(value.mask,0,255)) return value as GamePacket;
 if(value.kind==='hash' && keys(value,['kind','epoch','frame','hash']) && typeof value.frame==='number' && value.frame>0 && value.frame%gameplayLimits.hashInterval===0 && sha256(value.hash)) return value as GamePacket;
}
