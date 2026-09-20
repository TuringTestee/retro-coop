// Test-only, bounded transition evidence. Never retain SDP, addresses, credentials or payloads.
(() => {
 const trace=[], peers=[], epochs=new Map();
 const record=(kind,detail={})=>{trace.push({ms:Math.round(performance.now()),kind,...detail});if(trace.length>200)trace.shift();};
 const epoch=value=>{if(!value)return undefined;if(!epochs.has(value))epochs.set(value,epochs.size+1);return epochs.get(value);};
 const messageType=data=>{try{const type=JSON.parse(data).type;return ['transportProbe','transportReply'].includes(type)?type:'other';}catch{return 'invalid';}};
 const watch=(channel,id)=>{
  record('channel-observed',{id,state:channel.readyState});
  for(const kind of ['open','close','error'])channel.addEventListener(kind,()=>record(`channel-${kind}`,{id,state:channel.readyState}));
  channel.addEventListener('message',event=>record('channel-receive',{id,type:messageType(event.data)}));
  const send=channel.send.bind(channel);
  channel.send=data=>{record('channel-send',{id,type:messageType(data),state:channel.readyState});return send(data);};
 };
 const Socket=WebSocket;
 window.WebSocket=class extends Socket {
  constructor(...args){super(...args);this.addEventListener('message',event=>{
   const value=JSON.parse(event.data);
   if(['peerPrepare','peerStart','peerSignal','peerStop'].includes(value.type))record('signaling-in',{type:value.type,epoch:epoch(value.epoch)});
   if(value.type==='room')record('room',{epoch:epoch(value.room.peer.epoch),status:value.room.peer.status});
  });}
  send(raw){const value=JSON.parse(raw);if(['peerAck','peerSignal','peerConnected','peerFailed','peerRetry','peerPolicy'].includes(value.type))record('signaling-out',{type:value.type,epoch:epoch(value.epoch),signal:value.signal?.kind});super.send(raw);}
 };
 const Peer=RTCPeerConnection;
 window.RTCPeerConnection=class extends Peer {
  constructor(...args){
   super(...args);this.diagnosticId=peers.length;this.samples=[];peers.push(this);
   this.addEventListener('datachannel',event=>watch(event.channel,this.diagnosticId));
   const sample=async()=>{
    if(this.connectionState==='closed')return;
    try{
     const values=[];(await this.getStats()).forEach(value=>{
      if(value.type==='transport')values.push({type:value.type,dtls:value.dtlsState,ice:value.iceState,bytesSent:value.bytesSent,bytesReceived:value.bytesReceived});
      if(value.type==='data-channel')values.push({type:value.type,state:value.state,messagesSent:value.messagesSent,messagesReceived:value.messagesReceived});
     });
     this.samples.push(values);if(this.samples.length>5)this.samples.shift();
    }catch{record('stats-unavailable',{id:this.diagnosticId});}
    if(this.connectionState!=='closed')setTimeout(sample,250);
   };
   void sample();
  }
  createDataChannel(...args){const channel=super.createDataChannel(...args);watch(channel,this.diagnosticId);return channel;}
 };
 window.peerDiagnostics=()=>({trace,transport:peers.map(peer=>({state:peer.connectionState,sctp:peer.sctp?.state,samples:peer.samples}))});
})();
