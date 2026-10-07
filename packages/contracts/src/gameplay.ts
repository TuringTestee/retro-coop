import {object,keys,token,integer,sha256} from './protocol-validation.ts';
import type {Fingerprint} from './fingerprint.ts';
import type {SlotId,SlotRole} from './slots.ts';
/** Bounded member-authorized control protocol; participant identities are opaque. */
export const gameplayProtocol=2 as const;
export const gameplayLimits={leaseMs:3000,leaseRenewMs:1000,inputHeartbeatMs:100,catchupBatch:32,hashInterval:120,packetBytes:512,barrierMs:10_000,stallMs:3000,historyFrames:2048,checkpointMs:30_000,catchupMs:15_000} as const;
const reasons=['focus','device','network','mismatch','cancelled','user'] as const;
export type GameReason=typeof reasons[number];
const validReason=(value:unknown):value is GameReason=>typeof value==='string'&&(reasons as readonly string[]).includes(value);
export type ControllerAssignment={owners:[string|null,string|null];revision:number};
export type RoleTransaction={id:string;revision:number;roles:{slotId:SlotId;role:SlotRole}[];status:'freezing'|'synchronizing'|'failed';reason?:string};
export type CartridgeCandidate={intent:string;fingerprint:Fingerprint;title:string};
export type SaveLoadView={replacement?:CartridgeCandidate;freezeRequired?:string[];id:string;epoch:string;phase:'freezing'|'staging'|'committing'|'rolling_back';frame:number;hash:string;identity:string;savedAt:number;required:string[];expiresAt:number;priorFrame?:number;priorHash?:string;reason?:string};
export type GameView={hostRecovery?:string;load?:SaveLoadView;controllers:ControllerAssignment;pending?:RoleTransaction;ready:string[];startRequested:boolean;status:'waiting'|'starting'|'countdown'|'playing'|'pausing'|'resume_ready'|'paused'|'failed';epoch?:string;protocol?:typeof gameplayProtocol;startAt?:number;frame?:number;reason?:string};
export type CheckpointPurpose='live'|'controller'|'load';
export type GameCommand=
 | {type:'gameLoadPropose';requestId:string;revision:number;roomRevision:number;frame:number;hash:string;identity:string;savedAt:number;selectionIntent?:string}
 | {type:'gameLoadBoundary'|'gameLoadPrepared'|'gameLoadCommitted'|'gameLoadRolledBack';requestId:string;transactionId:string;frame:number;hash:string}
 | {type:'gameLoadFailed';requestId:string;transactionId:string}
 | {type:'gameRestore';requestId:string;revision:number;roomRevision:number;frame:number;hash:string;previousEpoch?:string}
 | {type:'gameReady';requestId:string;revision:number;roomRevision:number;frame:number;fresh:boolean;hash:string;protocol:typeof gameplayProtocol}
 | {type:'gameResynchronize';requestId:string;epoch:string;revision:number;recipient:string}
 | {type:'gameCatchupBoundary';requestId:string;epoch:string;transferId:string;frame:number;hash:string}
 | {type:'gameUnready'|'gameObserve';requestId:string;revision:number}
 | {type:'gameRoleCancel'|'gameRoleRetry';requestId:string;transactionId:string}
 | {type:'gameAck';requestId:string;epoch:string;hash:string}
 | {type:'gamePause';requestId:string;epoch:string;frame:number;reason:GameReason}
 | {type:'gameFrozen';requestId:string;epoch:string;frame:number;hash:string}
 | {type:'gameCaptured';requestId:string;epoch:string;transferId:string;frame:number;hash:string}
 | {type:'gameCheckpointReady';requestId:string;epoch:string;transferId:string}
 | {type:'gameCheckpointAck';requestId:string;epoch:string;transferId:string;frame:number;hash:string}
 | {type:'gameObserved';requestId:string;epoch:string;transferId:string;frame:number;hash:string}
 | {type:'gameCheckpointFailed';requestId:string;epoch:string;transferId:string}
 | {type:'gamePaused';requestId:string;epoch:string;frame:number;hash:string}
 | {type:'gameResume';requestId:string;epoch:string}
 | {type:'gameAbort';requestId:string;epoch:string;reason:GameReason};
type StartContext={epoch:string;authority:string;hash:string;protocol:typeof gameplayProtocol;frame:number;controllers:ControllerAssignment};
export type GameEvent=
 | {type:'gameLoadHold';transactionId:string;epoch?:string;frame?:number;hash?:string}
 | {type:'gameLoadStage'|'gameLoadCommit';transactionId:string;epoch:string;frame:number;hash:string}
 | {type:'gameLoadRollback';transactionId:string;epoch?:string;frame:number;hash:string;reason:string}
 | {type:'gameLoadFinish';transactionId:string}
 | {type:'gameInspect'}
 | ({type:'gamePrepare'|'gameStart'}&StartContext)
 | {type:'gameFreeze';epoch:string;reason:string}
 | {type:'gameCapture';epoch:string;transferId:string;recipient:string;purpose:CheckpointPurpose}
 | {type:'gameCheckpoint';epoch:string;transferId:string;sender:string;recipient:string;purpose:CheckpointPurpose;frame:number;hash:string}
 | {type:'gameCheckpointSend';epoch:string;transferId:string;recipient:string}
 | {type:'gameCatchup';epoch:string;transferId:string;recipient:string;frame:number}
 | {type:'gameLive';epoch:string;transferId:string;recipient:string;frame:number;hash:string}
 | {type:'gameSyncStop';epoch:string;transferId:string;reason:string}
 | {type:'gamePauseAt';epoch:string;frame:number;hash:string;reason:string}
 | {type:'gameStop';epoch?:string;reason:string};
export type FramePacket={kind:'frame';epoch:string;stream:string;revision:number;frame:number;p1:number;p2:number};
export type InputPacket={kind:'input';epoch:string;revision:number;generation:string;lease:string;sequence:number;mask:number;release:boolean};
export type LeasePacket={kind:'lease';epoch:string;revision:number;generation:string;lease:string;expiresAt:number};
export type GamePacket=FramePacket|InputPacket|LeasePacket|{kind:'hash';epoch:string;stream:string;frame:number;hash:string};

export function parseGameCommand(value:unknown):GameCommand|undefined {
 if(!object(value)||!token(value.requestId))return;
 const base=['type','requestId'],frame=integer(value.frame,0,Number.MAX_SAFE_INTEGER);
 if(value.type==='gameLoadPropose'&&keys(value,[...base,'revision','roomRevision','frame','hash','identity','savedAt'],['selectionIntent'])&&(value.selectionIntent===undefined||token(value.selectionIntent))&&integer(value.revision,0,Number.MAX_SAFE_INTEGER)&&integer(value.roomRevision,0,Number.MAX_SAFE_INTEGER)&&frame&&sha256(value.hash)&&sha256(value.identity)&&integer(value.savedAt,0,8640000000000000))return value as GameCommand;
 if(['gameLoadBoundary','gameLoadPrepared','gameLoadCommitted','gameLoadRolledBack'].includes(String(value.type))&&keys(value,[...base,'transactionId','frame','hash'])&&token(value.transactionId)&&frame&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gameLoadFailed'&&keys(value,[...base,'transactionId'])&&token(value.transactionId))return value as GameCommand;

 if(value.type==='gameRestore'&&keys(value,[...base,'revision','roomRevision','frame','hash'],['previousEpoch'])&&(value.previousEpoch===undefined||token(value.previousEpoch))&&integer(value.revision,0,Number.MAX_SAFE_INTEGER)&&integer(value.roomRevision,0,Number.MAX_SAFE_INTEGER)&&frame&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gameReady'&&keys(value,[...base,'revision','roomRevision','frame','fresh','hash','protocol'])&&integer(value.revision,0,Number.MAX_SAFE_INTEGER)&&integer(value.roomRevision,0,Number.MAX_SAFE_INTEGER)&&frame&&typeof value.fresh==='boolean'&&sha256(value.hash)&&value.protocol===gameplayProtocol)return value as GameCommand;
 if((value.type==='gameUnready'||value.type==='gameObserve')&&keys(value,[...base,'revision'])&&integer(value.revision,0,Number.MAX_SAFE_INTEGER))return value as GameCommand;
 if((value.type==='gameRoleCancel'||value.type==='gameRoleRetry')&&keys(value,[...base,'transactionId'])&&token(value.transactionId))return value as GameCommand;
 if(!token(value.epoch))return;
 if(value.type==='gameResynchronize'&&keys(value,[...base,'epoch','revision','recipient'])&&integer(value.revision,0,Number.MAX_SAFE_INTEGER)&&token(value.recipient))return value as GameCommand;
 if(value.type==='gameCatchupBoundary'&&keys(value,[...base,'epoch','transferId','frame','hash'])&&token(value.transferId)&&frame&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gameAck'&&keys(value,[...base,'epoch','hash'])&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gamePause'&&keys(value,[...base,'epoch','frame','reason'])&&frame&&validReason(value.reason))return value as GameCommand;
 if(value.type==='gameAbort'&&keys(value,[...base,'epoch','reason'])&&validReason(value.reason))return value as GameCommand;
 if((value.type==='gameCheckpointReady'||value.type==='gameCheckpointFailed')&&keys(value,[...base,'epoch','transferId'])&&token(value.transferId))return value as GameCommand;
 if((value.type==='gameCheckpointAck'||value.type==='gameCaptured')&&keys(value,[...base,'epoch','transferId','frame','hash'])&&token(value.transferId)&&frame&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gameObserved'&&keys(value,[...base,'epoch','transferId','frame','hash'])&&token(value.transferId)&&frame&&sha256(value.hash))return value as GameCommand;
 if((value.type==='gamePaused'||value.type==='gameFrozen')&&keys(value,[...base,'epoch','frame','hash'])&&frame&&sha256(value.hash))return value as GameCommand;
 if(value.type==='gameResume'&&keys(value,[...base,'epoch']))return value as GameCommand;
}
export function parseGamePacket(raw:unknown):GamePacket|undefined {
 if(typeof raw!=='string'||raw.length>gameplayLimits.packetBytes)return;
 let value;try{value=JSON.parse(raw);}catch{return;}
 if(!object(value)||!token(value.epoch))return;
 const revision=integer(value.revision,0,Number.MAX_SAFE_INTEGER),frame=integer(value.frame,0,Number.MAX_SAFE_INTEGER);
 if(value.kind==='input'&&keys(value,['kind','epoch','revision','generation','lease','sequence','mask','release'])&&revision&&token(value.generation)&&token(value.lease)&&integer(value.sequence,1,Number.MAX_SAFE_INTEGER)&&integer(value.mask,0,255)&&typeof value.release==='boolean'&&(!value.release||value.mask===0))return value as InputPacket;
 if(value.kind==='lease'&&keys(value,['kind','epoch','revision','generation','lease','expiresAt'])&&revision&&token(value.generation)&&token(value.lease)&&typeof value.expiresAt==='number'&&Number.isFinite(value.expiresAt)&&value.expiresAt>=0)return value as LeasePacket;
 if(!frame||!token(value.stream))return;
 if(value.kind==='frame'&&keys(value,['kind','epoch','stream','revision','frame','p1','p2'])&&revision&&integer(value.p1,0,255)&&integer(value.p2,0,255))return value as FramePacket;
 if(value.kind==='hash'&&keys(value,['kind','epoch','stream','frame','hash'])&&typeof value.frame==='number'&&value.frame>0&&value.frame%gameplayLimits.hashInterval===0&&sha256(value.hash))return value as GamePacket;
}
