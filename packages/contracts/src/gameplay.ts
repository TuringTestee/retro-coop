import {object,keys,token,integer,sha256} from './protocol-validation.ts';
import type {SlotId,SlotRole} from './slots.ts';
/** Bounded member-authorized control protocol; participant identities are opaque. */
export const gameplayLimits={delayMin:3,delayMax:8,delayDefault:6,inputWindow:120,hashInterval:120,packetBytes:512,consentMs:15_000,barrierMs:10_000,stallMs:3000,historyFrames:2048,checkpointMs:30_000,catchupMs:15_000} as const;
const reasons=['focus','device','network','mismatch','cancelled','user'] as const;
export type GameReason=typeof reasons[number];
const validReason=(value:unknown):value is GameReason=>typeof value==='string'&&(reasons as readonly string[]).includes(value);
export type ControllerAssignment={owners:[string|null,string|null];revision:number};
export type RoleTransaction={id:string;revision:number;roles:{slotId:SlotId;role:SlotRole}[];status:'freezing'|'synchronizing'|'failed';reason?:string};
export type GameView={controllers:ControllerAssignment;pending?:RoleTransaction;ready:string[];startRequested:boolean;status:'waiting'|'starting'|'playing'|'pausing'|'resume_ready'|'paused'|'failed';epoch?:string;delay?:number;frame?:number;reason?:string};
export type CheckpointPurpose='observer'|'controller';
export type GameCommand=
 | {type:'gameReady';requestId:string;revision:number;roomRevision:number;frame:number;fresh:boolean;hash:string;delay:number}
 | {type:'gameUnready'|'gameObserve';requestId:string;revision:number}
 | {type:'gameRoleCancel'|'gameRoleRetry';requestId:string;transactionId:string}
 | {type:'gameAck';requestId:string;epoch:string;hash:string}
 | {type:'gamePause';requestId:string;epoch:string;frame:number;reason:GameReason}
 | {type:'gameFrozen';requestId:string;epoch:string;frame:number;hash:string}
 | {type:'gameCaptured';requestId:string;epoch:string;transferId:string;frame:number;hash:string}
 | {type:'gameCheckpointReady';requestId:string;epoch:string;transferId:string}
 | {type:'gameCheckpointAck';requestId:string;epoch:string;transferId:string;frame:number;hash:string}
 | {type:'gameObserved';requestId:string;epoch:string;transferId:string;frame:number}
 | {type:'gameCheckpointFailed';requestId:string;epoch:string;transferId:string}
 | {type:'gamePaused';requestId:string;epoch:string;frame:number;hash:string}
 | {type:'gameResume';requestId:string;epoch:string}
 | {type:'gameAbort';requestId:string;epoch:string;reason:GameReason};
type StartContext={epoch:string;authority:string;hash:string;delay:number;frame:number;controllers:ControllerAssignment};
export type GameEvent=
 | {type:'gameInspect'}
 | ({type:'gamePrepare'|'gameStart'}&StartContext)
 | {type:'gameFreeze';epoch:string;reason:string}
 | {type:'gameCapture';epoch:string;transferId:string;recipient:string;purpose:CheckpointPurpose}
 | {type:'gameCheckpoint';epoch:string;transferId:string;sender:string;recipient:string;purpose:CheckpointPurpose;frame:number;hash:string}
 | {type:'gameCheckpointSend';epoch:string;transferId:string;recipient:string}
 | {type:'gameCatchup';epoch:string;transferId:string;recipient:string;frame:number}
 | {type:'gameSyncStop';epoch:string;transferId:string;reason:string}
 | {type:'gamePauseAt';epoch:string;frame:number;reason:string}
 | {type:'gameStop';epoch?:string;reason:string};
export type FramePacket={kind:'frame';epoch:string;frame:number;p1:number;p2:number};
export type GamePacket=FramePacket|{kind:'input';epoch:string;frame:number;mask:number}|{kind:'hash';epoch:string;frame:number;hash:string};

export function parseGameCommand(value:unknown):GameCommand|undefined {
 if(!object(value)||!token(value.requestId))return;
 const base=['type','requestId'],frame=integer(value.frame,0,Number.MAX_SAFE_INTEGER);
 if(value.type==='gameReady'&&keys(value,[...base,'revision','roomRevision','frame','fresh','hash','delay'])&&integer(value.revision,0,Number.MAX_SAFE_INTEGER)&&integer(value.roomRevision,0,Number.MAX_SAFE_INTEGER)&&frame&&typeof value.fresh==='boolean'&&sha256(value.hash)&&integer(value.delay,gameplayLimits.delayMin,gameplayLimits.delayMax))return value as GameCommand;
 if((value.type==='gameUnready'||value.type==='gameObserve')&&keys(value,[...base,'revision'])&&integer(value.revision,0,Number.MAX_SAFE_INTEGER))return value as GameCommand;
 if((value.type==='gameRoleCancel'||value.type==='gameRoleRetry')&&keys(value,[...base,'transactionId'])&&token(value.transactionId))return value as GameCommand;
 if(!token(value.epoch))return;
 if(value.type==='gameAck'&&keys(value,[...base,'epoch','hash'])&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gamePause'&&keys(value,[...base,'epoch','frame','reason'])&&frame&&validReason(value.reason))return value as GameCommand;
 if(value.type==='gameAbort'&&keys(value,[...base,'epoch','reason'])&&validReason(value.reason))return value as GameCommand;
 if((value.type==='gameCheckpointReady'||value.type==='gameCheckpointFailed')&&keys(value,[...base,'epoch','transferId'])&&token(value.transferId))return value as GameCommand;
 if((value.type==='gameCheckpointAck'||value.type==='gameCaptured')&&keys(value,[...base,'epoch','transferId','frame','hash'])&&token(value.transferId)&&frame&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gameObserved'&&keys(value,[...base,'epoch','transferId','frame'])&&token(value.transferId)&&frame)return value as GameCommand;
 if((value.type==='gamePaused'||value.type==='gameFrozen')&&keys(value,[...base,'epoch','frame','hash'])&&frame&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gameResume'&&keys(value,[...base,'epoch']))return value as GameCommand;
}
export function parseGamePacket(raw:unknown):GamePacket|undefined {
 if(typeof raw!=='string' || raw.length>gameplayLimits.packetBytes) return;
 let value;try{value=JSON.parse(raw);}catch{return;}
 if(!object(value)||!token(value.epoch)||!integer(value.frame,0,Number.MAX_SAFE_INTEGER)) return;
 if(value.kind==='frame' && keys(value,['kind','epoch','frame','p1','p2']) && integer(value.p1,0,255) && integer(value.p2,0,255))return value as GamePacket;
 if(value.kind==='input' && keys(value,['kind','epoch','frame','mask']) && integer(value.mask,0,255)) return value as GamePacket;
 if(value.kind==='hash' && keys(value,['kind','epoch','frame','hash']) && typeof value.frame==='number' && value.frame>0 && value.frame%gameplayLimits.hashInterval===0 && sha256(value.hash)) return value as GamePacket;
}
