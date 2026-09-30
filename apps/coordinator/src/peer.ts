import {createHmac,randomBytes,createHash} from 'node:crypto';
import {effectivePolicy,peerLimits,relaySafe,type ConnectionPolicy,type PeerView,type PeerCommand,type PeerEvent,type IceServer} from '../../../packages/contracts/src/peer.ts';
export type RelayConfig = {urls:string[];secret:string;pairs:number};
export function relayConfig(env:NodeJS.ProcessEnv):RelayConfig|undefined {
 if(!env.TURN_URLS && !env.TURN_SECRET) return;
 const urls=(env.TURN_URLS??'').split(',');const pairs=Number(env.TURN_PAIR_LIMIT??env.TURN_ROOM_LIMIT??'0');
 if(!urls.length || urls.some(url=>!/^turns?:[A-Za-z0-9.\[\]:-]+(?:\?transport=(?:udp|tcp))?$/.test(url)) || (env.TURN_SECRET?.length??0)<32 || !Number.isInteger(pairs) || pairs<0 || pairs>20) throw Error('TURN needs explicit URLs, a secret of at least 32 characters, and TURN_PAIR_LIMIT from 0 to 20 (legacy TURN_ROOM_LIMIT retains the same allocation count)');
 return {urls,secret:env.TURN_SECRET!,pairs};
}
export type PeerMember={id:string;token:string;policy:ConnectionPolicy;send?:(event:PeerEvent)=>void};
type Pair={id:string;roomId:string;offerer:PeerMember;answerer:PeerMember;gameplay:boolean;reservation:string};
type Round={pair:Pair;epoch:string;policy:ConnectionPolicy;status:PeerView['status'];acks:Set<string>;connected:Set<string>;routes:Map<string,'direct'|'relay'>;candidates:Map<string,number>;descriptions:Set<string>;deadline:number;relay:boolean};
export class PeerError extends Error {}
/** No signaling history: only the current bounded, authenticated negotiation is retained. */
export class PeerBroker {
 private rounds=new Map<string,Round>();
 private now:()=>number;private relay?:RelayConfig;
 constructor(now:()=>number,relay?:RelayConfig) {this.now=now;this.relay=relay;}
 private stop(round:Round,reason:string) {for(const member of [round.pair.offerer,round.pair.answerer]) member.send?.({type:'peerStop',pairId:round.pair.id,reason});}
 clear(id:string,reason='Peer left the room.') {const round=this.rounds.get(id);if(round) this.stop(round,reason);this.rounds.delete(id);}
 views(roomId:string,member:string):PeerView[]{return [...this.rounds.values()].filter(round=>round.pair.roomId===roomId&&[round.pair.offerer.id,round.pair.answerer.id].includes(member)).map(round=>({pairId:round.pair.id,member:round.pair.offerer.id===member?round.pair.answerer.id:round.pair.offerer.id,gameplay:round.pair.gameplay,epoch:round.epoch,policy:round.policy,status:round.status}));}
 clearRoom(roomId:string,reason='Room closed.'){for(const [pairId,round] of this.rounds)if(round.pair.roomId===roomId)this.clear(pairId,reason);}
 syncRoom(roomId:string,members:PeerMember[],authority:string){
  const sorted=[...members].sort((a,b)=>a.id.localeCompare(b.id)),retained=new Set<string>();
  for(let a=0;a<sorted.length;a++)for(let b=a+1;b<sorted.length;b++){
   const offerer=sorted[a],answerer=sorted[b],pairId=createHash('sha256').update(roomId+offerer.id+answerer.id).digest('hex');retained.add(pairId);
   this.sync({id:pairId,roomId,offerer,answerer,gameplay:offerer.id===authority||answerer.id===authority,reservation:offerer.id+answerer.id},pairId);
  }
  for(const [pairId,round] of this.rounds)if(round.pair.roomId===roomId&&!retained.has(pairId))this.clear(pairId);
 }
 sync(pair:Pair|undefined,id:string) {
  if(!pair?.offerer.send || !pair.answerer.send) {this.clear(id);return;}
  const policy=effectivePolicy(pair.offerer.policy,pair.answerer.policy),old=this.rounds.get(id);
  if(old && old.pair.reservation===pair.reservation && old.policy===policy && old.pair.offerer.policy===pair.offerer.policy && old.pair.answerer.policy===pair.answerer.policy && old.pair.offerer.send===pair.offerer.send && old.pair.answerer.send===pair.answerer.send) return;
  this.clear(id,'Connection policy or membership changed.');
  const occupied=[...this.rounds.values()].filter(round=>round.relay).length;
  const relay=!!this.relay && occupied<this.relay.pairs;
  const status:Round['status']=policy==='relay' && !relay ? this.relay ? 'relay_capacity':'relay_unavailable':'preparing';
  const round:Round={pair:{...pair,offerer:{...pair.offerer},answerer:{...pair.answerer}},epoch:randomBytes(24).toString('base64url'),policy,status,acks:new Set(),connected:new Set(),routes:new Map(),candidates:new Map(),descriptions:new Set(),deadline:this.now()+peerLimits.prepareMs,relay};
  this.rounds.set(id,round);
  if(status!=='preparing') return;
  for(const member of [pair.offerer,pair.answerer]) {
   const iceServers:IceServer[]=[];
   if(relay) {
    // Coturn's documented short-lived REST credentials, never the shared secret.
    const username=`${Math.floor(this.now()/1000)+300}:${randomBytes(12).toString('hex')}`;
    iceServers.push({urls:this.relay!.urls,username,credential:createHmac('sha1',this.relay!.secret).update(username).digest('base64')});
   }
   member.send!({type:'peerPrepare',pairId:pair.id,member:member.id===pair.offerer.id?pair.answerer.id:pair.offerer.id,gameplay:pair.gameplay,epoch:round.epoch,offerer:member.id===pair.offerer.id,policy,iceServers});
  }
 }
 handle(roomId:string,token:string,command:PeerCommand) {
  const id=command.pairId,round=this.rounds.get(id);
  if(!round || round.pair.roomId!==roomId || round.epoch!==command.epoch || ![round.pair.offerer.token,round.pair.answerer.token].includes(token)) throw new PeerError('stale_peer');
  if(command.type==='peerRetry') {this.clear(id,'Retrying connection.');return;}
  if(command.type==='peerFailed') {round.status='failed';round.relay=false;this.stop(round,'Connection failed. Retry the connection or leave the room.');return;}
  if(command.type==='peerAck') {
   if(round.status!=='preparing') throw new PeerError('stale_peer');
   round.acks.add(token);
   if(round.acks.size===2) {round.status='connecting';round.deadline=this.now()+peerLimits.connectMs;for(const member of [round.pair.offerer,round.pair.answerer]) member.send!({type:'peerStart',pairId:id,epoch:round.epoch});}
   return;
  }
  if(command.type==='peerConnected') {if(!['connecting','connected'].includes(round.status)) throw new PeerError('stale_peer');round.connected.add(token);if(round.connected.size===2) round.status='connected';return;}
  if(command.type==='peerRoute') {
   if(!['connecting','connected'].includes(round.status)||!round.connected.has(token))throw new PeerError('peer_not_connected');
   if(round.routes.get(token)!==command.route){round.routes.set(token,command.route);console.info(JSON.stringify({event:'peer_route',room:id,member:token===round.pair.offerer.token?round.pair.offerer.id:round.pair.answerer.id,policy:round.policy,route:command.route}));}
   return;
  }
  if(!['connecting','connected'].includes(round.status) || round.acks.size!==2) throw new PeerError('peer_not_prepared');
  if(command.type!=='peerSignal') throw new PeerError('invalid_peer');
  const offering=token===round.pair.offerer.token,signal=command.signal;
  if(round.policy==='relay' && !relaySafe(signal)) throw new PeerError('relay_required');
  if(signal.kind==='description') {
   if(signal.description.type!==(offering?'offer':'answer') || round.descriptions.has(token)) throw new PeerError('invalid_peer_description');
   round.descriptions.add(token);
  } else {const count=(round.candidates.get(token)??0)+1;if(count>peerLimits.candidates) throw new PeerError('peer_candidate_limit');round.candidates.set(token,count);}
  (offering?round.pair.answerer:round.pair.offerer).send!({type:'peerSignal',pairId:id,epoch:round.epoch,signal});
 }
 sweep():string[] {
  const changed:string[]=[];
  for(const [id,round] of this.rounds) if(['preparing','connecting'].includes(round.status) && this.now()>=round.deadline) {round.status='failed';round.relay=false;this.stop(round,'Connection timed out. Retry the connection or leave the room.');changed.push(round.pair.roomId);}
  return changed;
 }
}
