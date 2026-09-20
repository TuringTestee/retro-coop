import {effectivePolicy,peerLimits,type ConnectionPolicy,type PeerEvent,type PeerCommand,type Signal} from '../../../packages/contracts/src/peer.ts';
type Command=PeerCommand extends infer T ? T extends PeerCommand ? Omit<T,'requestId'>:never:never;
export type PeerMedia={prepare(pc:RTCPeerConnection,role:'host'|'guest'):void;answer(pc:RTCPeerConnection):void;connected():void;close():void};
export type PeerOptions={ready?:(channel:RTCDataChannel,epoch:string)=>void;closed?:(epoch:string|undefined)=>void;preference?:()=>ConnectionPolicy;media?:PeerMedia};
export type ConnectionState={status:string;route?:'direct'|'relay';epoch?:string};
/** Browser transport boundary; D11 consumes the channel only after its independent gameplay barrier. */
export class PeerConnection {
 private pc?:RTCPeerConnection;
 private channel?:RTCDataChannel;
 private epoch?:string;
 private role?:'host'|'guest';
 private candidates:RTCIceCandidateInit[]=[];
 private timer?:ReturnType<typeof setTimeout>;
 private serial=Promise.resolve();
 constructor(private send:(command:Command)=>Promise<unknown>,private update:(state:ConnectionState)=>void,private options:PeerOptions={}) {}
 close(status='Peer connection closed. Your local game is preserved.') {const epoch=this.epoch;this.epoch=undefined;if(epoch)this.options.closed?.(epoch);this.options.media?.close();clearTimeout(this.timer);this.channel?.close();this.pc?.close();this.pc=undefined;this.channel=undefined;this.candidates=[];this.update({status});}
 private fail(epoch:string) {if(this.epoch!==epoch) return;this.close('Connection failed. Retry or stay in the room.');void this.send({type:'peerFailed',epoch}).catch(()=>{});}
 handle(event:PeerEvent) {
  if(event.type==='peerStop') {this.close(event.reason);return;}
  if(event.type==='peerPrepare') {
   this.close('Preparing connection privacy…');this.epoch=event.epoch;this.role=event.role;
   try {
    if(effectivePolicy(event.policy,this.options.preference?.() ?? 'standard')!==event.policy) throw Error('Privacy downgrade rejected');
    const pc=new RTCPeerConnection({iceTransportPolicy:event.policy==='relay'?'relay':'all',iceServers:event.iceServers,iceCandidatePoolSize:0});this.pc=pc;this.options.media?.prepare(pc,event.role);
    const epoch=event.epoch;
    pc.onicecandidate=({candidate})=>{if(candidate && this.epoch===epoch) void this.send({type:'peerSignal',epoch,signal:{kind:'candidate',candidate:candidate.toJSON() as Extract<Signal,{kind:'candidate'}>['candidate']}}).catch(()=>this.fail(epoch));};
    pc.onconnectionstatechange=()=>{if(this.epoch===epoch && ['failed','disconnected'].includes(pc.connectionState)) this.fail(epoch);};
    pc.ondatachannel=({channel})=>{if(this.epoch===epoch) this.wire(channel,epoch);else channel.close();};
    this.timer=setTimeout(()=>this.fail(epoch),peerLimits.prepareMs+peerLimits.connectMs);
    this.update({status:`Preparing ${event.policy==='relay'?'relay-only':'standard'} connection…`,epoch});
    // No offer/local description (and thus no gathering) until both peers acknowledge policy.
    void this.send({type:'peerAck',epoch}).catch(()=>this.fail(epoch));
   }catch {this.fail(event.epoch);}
   return;
  }
  const epoch=event.epoch;
  this.serial=this.serial.then(async()=>{
   const pc=this.pc;if(!pc || this.epoch!==epoch) return;
   if(event.type==='peerStart') {
    this.update({status:'Connecting… Your local game can continue.',epoch});
    if(this.role==='host') {this.wire(pc.createDataChannel('retro-coop-control',{ordered:true}),epoch);await pc.setLocalDescription(await pc.createOffer());if(this.epoch===epoch) await this.send({type:'peerSignal',epoch,signal:{kind:'description',description:{type:'offer',sdp:pc.localDescription!.sdp}}});}
   } else if(event.signal.kind==='description') {
    await pc.setRemoteDescription(event.signal.description);if(this.epoch!==epoch) return;
    const candidates=this.candidates;this.candidates=[];for(const candidate of candidates) {await pc.addIceCandidate(candidate);if(this.epoch!==epoch) return;}
    if(event.signal.description.type==='offer') {this.options.media?.answer(pc);await pc.setLocalDescription(await pc.createAnswer());if(this.epoch===epoch) await this.send({type:'peerSignal',epoch,signal:{kind:'description',description:{type:'answer',sdp:pc.localDescription!.sdp}}});}
   } else if(pc.remoteDescription) await pc.addIceCandidate(event.signal.candidate);
   else {if(this.candidates.length>=peerLimits.candidates) throw Error('Too many candidates');this.candidates.push(event.signal.candidate);}
  }).catch(()=>this.fail(epoch));
 }
 private wire(channel:RTCDataChannel,epoch:string) {
  if(this.channel || channel.label!=='retro-coop-control') {channel.close();this.fail(epoch);return;}
  this.channel=channel;
  const nonce=crypto.randomUUID();let verified=false,replied=false,announced=false;
  const complete=()=>{if(verified && replied && !announced) {announced=true;void this.connected(epoch,channel);}};
  channel.onopen=()=>{if(this.epoch===epoch) channel.send(JSON.stringify({type:'transportProbe',nonce}));};
  channel.onmessage=({data})=>{
   if(this.epoch!==epoch || typeof data!=='string' || data.length>256) {this.fail(epoch);return;}
   let message;try {message=JSON.parse(data);}catch {this.fail(epoch);return;}
   if(message.type==='transportProbe' && !replied && typeof message.nonce==='string' && message.nonce.length===36) {replied=true;channel.send(JSON.stringify({type:'transportReply',nonce:message.nonce}));complete();}
   else if(message.type==='transportReply' && message.nonce===nonce && !verified) {verified=true;complete();}
   else this.fail(epoch);
  };
  channel.onclose=()=>{if(this.epoch===epoch) this.fail(epoch);};channel.onerror=()=>this.fail(epoch);
 }
 private async connected(epoch:string,channel:RTCDataChannel) {
  clearTimeout(this.timer);
  try {
   const stats=await this.pc!.getStats();if(this.epoch!==epoch) return;
   let route:'direct'|'relay'='direct';
   stats.forEach(report=>{if(report.type==='transport' && report.selectedCandidatePairId) {const pair=stats.get(report.selectedCandidatePairId);if(stats.get(pair?.localCandidateId)?.candidateType==='relay' || stats.get(pair?.remoteCandidateId)?.candidateType==='relay') route='relay';}});
   this.update({status:'Peer transport connected. Shared gameplay is not available yet.',route,epoch});
   await this.send({type:'peerConnected',epoch});if(this.epoch===epoch) {this.options.media?.connected();this.options.ready?.(channel,epoch);}
  }catch {this.fail(epoch);}
 }
}
