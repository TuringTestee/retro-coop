import {object,keys,token,integer} from './protocol-validation.ts';
export type ConnectionPolicy = 'standard'|'relay';
export const validPolicy = (value:unknown):value is ConnectionPolicy => value==='standard' || value==='relay';
export const effectivePolicy = (a:ConnectionPolicy,b:ConnectionPolicy):ConnectionPolicy => a==='relay' || b==='relay' ? 'relay':'standard';
export const peerLimits = {sdp:12_000,candidate:1024,candidates:64,frame:16_384,prepareMs:15_000,connectMs:20_000} as const;
export type IceServer = {urls:string[];username?:string;credential?:string};
export type PeerView = {epoch?:string;policy:ConnectionPolicy;status:'waiting'|'preparing'|'connecting'|'connected'|'failed'|'relay_unavailable'|'relay_capacity'};
export type Signal = {kind:'description';description:{type:'offer'|'answer';sdp:string}} | {kind:'candidate';candidate:{candidate:string;sdpMid:string|null;sdpMLineIndex:number|null;usernameFragment?:string|null}};
export type PeerCommand = {type:'peerPolicy';requestId:string;policy:ConnectionPolicy} | {type:'peerAck'|'peerRetry'|'peerConnected'|'peerFailed';requestId:string;epoch:string} | {type:'peerSignal';requestId:string;epoch:string;signal:Signal};
export type PeerEvent = {type:'peerPrepare';epoch:string;policy:ConnectionPolicy;role:'host'|'guest';iceServers:IceServer[]} | {type:'peerStart';epoch:string} | {type:'peerSignal';epoch:string;signal:Signal} | {type:'peerStop';reason:string};
export function validSignal(value:unknown):value is Signal {
 if(!object(value)) return false;
 if(value.kind==='description') {const d=value.description;return keys(value,['kind','description']) && object(d) && keys(d,['type','sdp']) && (d.type==='offer'||d.type==='answer') && typeof d.sdp==='string' && d.sdp.startsWith('v=0') && d.sdp.length<=peerLimits.sdp;}
 if(value.kind==='candidate') {const c=value.candidate;return keys(value,['kind','candidate']) && object(c) && keys(c,['candidate','sdpMid','sdpMLineIndex'],['usernameFragment']) && typeof c.candidate==='string' && c.candidate.startsWith('candidate:') && c.candidate.length<=peerLimits.candidate && (c.sdpMid===null || typeof c.sdpMid==='string' && c.sdpMid.length<=32) && (c.sdpMLineIndex===null || integer(c.sdpMLineIndex,0,8)) && (c.usernameFragment===undefined || c.usernameFragment===null || typeof c.usernameFragment==='string' && c.usernameFragment.length<=256);}
 return false;
}
export function parsePeerCommand(value:unknown):PeerCommand|undefined {
 if(!object(value)||!token(value.requestId)) return;
 if(value.type==='peerPolicy' && keys(value,['type','requestId','policy']) && validPolicy(value.policy)) return value as PeerCommand;
 if(!token(value.epoch)) return;
 if(['peerAck','peerRetry','peerConnected','peerFailed'].includes(value.type as string) && keys(value,['type','requestId','epoch'])) return value as PeerCommand;
 if(value.type==='peerSignal' && keys(value,['type','requestId','epoch','signal']) && validSignal(value.signal)) return value as PeerCommand;
}
export function relaySafe(signal:Signal) {
 const candidates=signal.kind==='candidate' ? [signal.candidate.candidate] : signal.description.sdp.split(/\r?\n/).filter(line=>line.startsWith('a=candidate:'));
 return candidates.every(candidate=>{const fields=candidate.trim().split(/\s+/);return fields[6]==='typ' && fields[7]==='relay';});
}
