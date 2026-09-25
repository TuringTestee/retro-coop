import {createHmac,randomBytes} from 'node:crypto';
import {effectivePolicy,peerLimits,relaySafe,type ConnectionPolicy,type PeerView,type PeerCommand,type PeerEvent,type IceServer} from '../../../packages/contracts/src/peer.ts';
export type RelayConfig = {urls:string[];secret:string;rooms:number};
export function relayConfig(env:NodeJS.ProcessEnv):RelayConfig|undefined {
 if(!env.TURN_URLS && !env.TURN_SECRET) return;
 const urls=(env.TURN_URLS??'').split(',');const rooms=Number(env.TURN_ROOM_LIMIT??'0');
 if(!urls.length || urls.some(url=>!/^turns?:[A-Za-z0-9.\[\]:-]+(?:\?transport=(?:udp|tcp))?$/.test(url)) || (env.TURN_SECRET?.length??0)<32 || !Number.isInteger(rooms) || rooms<0 || rooms>20) throw Error('TURN needs explicit URLs, a secret of at least 32 characters, and TURN_ROOM_LIMIT from 0 to 20');
 return {urls,secret:env.TURN_SECRET!,rooms};
}
type Member={token:string;policy:ConnectionPolicy;send?:(event:PeerEvent)=>void};
type Pair={id:string;host:Member;guest:Member;reservation:string};
type Round={pair:Pair;epoch:string;policy:ConnectionPolicy;status:PeerView['status'];acks:Set<string>;connected:Set<string>;routes:Map<string,'direct'|'relay'>;candidates:Map<string,number>;descriptions:Set<string>;deadline:number;relay:boolean};
export class PeerError extends Error {}
/** No signaling history: only the current bounded, authenticated negotiation is retained. */
export class PeerBroker {
 private rounds=new Map<string,Round>();
 private now:()=>number;private relay?:RelayConfig;
 constructor(now:()=>number,relay?:RelayConfig) {this.now=now;this.relay=relay;}
 private stop(round:Round,reason:string) {for(const member of [round.pair.host,round.pair.guest]) member.send?.({type:'peerStop',reason});}
 clear(id:string,reason='Peer left the room.') {const round=this.rounds.get(id);if(round) this.stop(round,reason);this.rounds.delete(id);}
 view(id:string,policy:ConnectionPolicy):PeerView {const round=this.rounds.get(id);return round ? {epoch:round.epoch,policy:round.policy,status:round.status}:{policy,status:'waiting'};}
 sync(pair:Pair|undefined,id:string) {
  if(!pair?.host.send || !pair.guest.send) {this.clear(id);return;}
  const policy=effectivePolicy(pair.host.policy,pair.guest.policy),old=this.rounds.get(id);
  if(old && old.pair.reservation===pair.reservation && old.policy===policy && old.pair.host.policy===pair.host.policy && old.pair.guest.policy===pair.guest.policy && old.pair.host.send===pair.host.send && old.pair.guest.send===pair.guest.send) return;
  this.clear(id,'Connection policy or membership changed.');
  const occupied=[...this.rounds.values()].filter(round=>round.relay).length;
  const relay=!!this.relay && occupied<this.relay.rooms;
  const status:Round['status']=policy==='relay' && !relay ? this.relay ? 'relay_capacity':'relay_unavailable':'preparing';
  const round:Round={pair:{...pair,host:{...pair.host},guest:{...pair.guest}},epoch:randomBytes(24).toString('base64url'),policy,status,acks:new Set(),connected:new Set(),routes:new Map(),candidates:new Map(),descriptions:new Set(),deadline:this.now()+peerLimits.prepareMs,relay};
  this.rounds.set(id,round);
  if(status!=='preparing') return;
  for(const member of [pair.host,pair.guest]) {
   const iceServers:IceServer[]=[];
   if(relay) {
    // Coturn's documented short-lived REST credentials, never the shared secret.
    const username=`${Math.floor(this.now()/1000)+300}:${randomBytes(12).toString('hex')}`;
    iceServers.push({urls:this.relay!.urls,username,credential:createHmac('sha1',this.relay!.secret).update(username).digest('base64')});
   }
   member.send!({type:'peerPrepare',epoch:round.epoch,role:member.token===pair.host.token?'host':'guest',policy,iceServers});
  }
 }
 handle(id:string,token:string,command:Exclude<PeerCommand,{type:'peerPolicy'}>) {
  const round=this.rounds.get(id);
  if(!round || round.epoch!==command.epoch || ![round.pair.host.token,round.pair.guest.token].includes(token)) throw new PeerError('stale_peer');
  if(command.type==='peerRetry') {this.clear(id,'Retrying connection.');return;}
  if(command.type==='peerFailed') {round.status='failed';round.relay=false;this.stop(round,'Connection failed. Retry or stay in the room.');return;}
  if(command.type==='peerAck') {
   if(round.status!=='preparing') throw new PeerError('stale_peer');
   round.acks.add(token);
   if(round.acks.size===2) {round.status='connecting';round.deadline=this.now()+peerLimits.connectMs;for(const member of [round.pair.host,round.pair.guest]) member.send!({type:'peerStart',epoch:round.epoch});}
   return;
  }
  if(command.type==='peerConnected') {if(!['connecting','connected'].includes(round.status)) throw new PeerError('stale_peer');round.connected.add(token);if(round.connected.size===2) round.status='connected';return;}
  if(command.type==='peerRoute') {
   if(!['connecting','connected'].includes(round.status)||!round.connected.has(token))throw new PeerError('peer_not_connected');
   if(round.routes.get(token)!==command.route){round.routes.set(token,command.route);console.info(JSON.stringify({event:'peer_route',room:id,role:token===round.pair.host.token?'host':'guest',policy:round.policy,route:command.route}));}
   return;
  }
  if(!['connecting','connected'].includes(round.status) || round.acks.size!==2) throw new PeerError('peer_not_prepared');
  if(command.type!=='peerSignal') throw new PeerError('invalid_peer');
  const host=token===round.pair.host.token,signal=command.signal;
  if(round.policy==='relay' && !relaySafe(signal)) throw new PeerError('relay_required');
  if(signal.kind==='description') {
   if(signal.description.type!==(host?'offer':'answer') || round.descriptions.has(token)) throw new PeerError('invalid_peer_description');
   round.descriptions.add(token);
  } else {const count=(round.candidates.get(token)??0)+1;if(count>peerLimits.candidates) throw new PeerError('peer_candidate_limit');round.candidates.set(token,count);}
  (host?round.pair.guest:round.pair.host).send!({type:'peerSignal',epoch:round.epoch,signal});
 }
 sweep():string[] {
  const changed:string[]=[];
  for(const [id,round] of this.rounds) if(['preparing','connecting'].includes(round.status) && this.now()>=round.deadline) {round.status='failed';round.relay=false;this.stop(round,'Connection timed out. Retry or stay in the room.');changed.push(id);}
  return changed;
 }
}
