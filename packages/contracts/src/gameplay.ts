import type {RoomRole} from './rooms.ts';
import {object,keys,token,integer,sha256} from './protocol-validation.ts';
/** One protocol owner for frame discipline, independent of local file admission. */
export const gameplayLimits={delayMin:3,delayMax:8,delayDefault:6,inputWindow:120,hashInterval:120,packetBytes:512,consentMs:15_000,barrierMs:10_000,stallMs:1000} as const;
export type GameRole=RoomRole;
const reasons=['focus','device','network','mismatch','cancelled','user'] as const;
export type GameReason=typeof reasons[number];
const validReason=(value:unknown):value is GameReason=>typeof value==='string'&&(reasons as readonly string[]).includes(value);
export type ControllerAssignment={mode:'separate'|'shared';p1:GameRole;revision:number};
export type ControllerProposal=ControllerAssignment & {id:string;accepted:GameRole[]};
export const defaultControllers:ControllerAssignment={mode:'separate',p1:'host',revision:0};
export type GameView={controllers?:ControllerAssignment;controllerProposal?:ControllerProposal} & {ready?:GameRole[];startRequested?:boolean;status:'waiting'|'starting'|'playing'|'pausing'|'resume_ready'|'paused'|'late_join'|'failed';epoch?:string;delay?:number;reason?:string};
export type GameCommand=
 | {type:'gameControllerPropose';requestId:string;peerEpoch:string;epoch?:string;revision:number;mode:'separate'|'shared';p1:GameRole}
 | {type:'gameControllerRespond';requestId:string;peerEpoch:string;epoch?:string;proposalId:string;accept:boolean}
 | {type:'gameControllerCancel';requestId:string;peerEpoch:string;epoch?:string;proposalId:string}
 | {type:'gameReady';requestId:string;peerEpoch:string;frame:number;fresh:boolean;hash:string;delay:number;controllerRevision?:number}
 | {type:'gameUnready';requestId:string;peerEpoch:string}
 | {type:'gameAck';requestId:string;epoch:string;hash:string}
 | {type:'gamePause';requestId:string;epoch:string;frame:number;reason:GameReason}
 | {type:'gamePaused';requestId:string;epoch:string;frame:number;hash:string}
 | {type:'gameResume';requestId:string;epoch:string}
 | {type:'gameAbort';requestId:string;epoch:string;reason:GameReason};
export type GameEvent=
 | {type:'gameInspect';peerEpoch:string}
 | {type:'gamePrepare';peerEpoch:string;epoch:string;hash:string;delay:number;controllers?:ControllerAssignment}
 | {type:'gameStart';peerEpoch:string;epoch:string;delay:number;controllers?:ControllerAssignment}
 | {type:'gamePauseAt';epoch:string;frame:number;reason:string}
 | {type:'gameStop';epoch?:string;reason:string};
export type GamePacket={kind:'input';epoch:string;frame:number;mask:number}|{kind:'hash';epoch:string;frame:number;hash:string};

export function parseGameCommand(value:unknown):GameCommand|undefined {
 if(!object(value)||!token(value.requestId)) return;
 const base=['type','requestId'];
 if(token(value.peerEpoch)&&(value.epoch===undefined||token(value.epoch))) {
  const context=[...base,'peerEpoch'];
  if(value.type==='gameControllerPropose'&&keys(value,[...context,'revision','mode','p1'],['epoch'])&&integer(value.revision,0,Number.MAX_SAFE_INTEGER)&&(value.mode==='separate'||value.mode==='shared')&&(value.p1==='host'||value.p1==='guest'))return value as GameCommand;
  if(value.type==='gameControllerRespond'&&keys(value,[...context,'proposalId','accept'],['epoch'])&&token(value.proposalId)&&typeof value.accept==='boolean')return value as GameCommand;
  if(value.type==='gameControllerCancel'&&keys(value,[...context,'proposalId'],['epoch'])&&token(value.proposalId))return value as GameCommand;
 }
 if(value.type==='gameReady' && keys(value,[...base,'peerEpoch','frame','fresh','hash','delay'],['controllerRevision']) && token(value.peerEpoch) && integer(value.frame,0,Number.MAX_SAFE_INTEGER) && typeof value.fresh==='boolean' && sha256(value.hash) && integer(value.delay,gameplayLimits.delayMin,gameplayLimits.delayMax) && (value.controllerRevision===undefined||integer(value.controllerRevision,0,Number.MAX_SAFE_INTEGER))) return value as GameCommand;
 if(value.type==='gameUnready' && keys(value,[...base,'peerEpoch']) && token(value.peerEpoch)) return value as GameCommand;
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
