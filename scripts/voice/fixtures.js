// Browser verification only: actual fake-device capture plus controlled permission/attachment failures.
window.candidateShapes=[];
const RawSocket=WebSocket;
window.WebSocket=class extends RawSocket{send(raw){const v=JSON.parse(raw);if(v.type==='peerSignal'&&v.signal.kind==='candidate'){const c=v.signal.candidate;candidateShapes.push({keys:Object.keys(c),empty:c.candidate==='',prefix:c.candidate?.startsWith('candidate:'),mid:c.sdpMid,index:c.sdpMLineIndex})}return super.send(raw)}};

window.peerErrors=[];
for(const name of ['setRemoteDescription','setLocalDescription','addIceCandidate','createAnswer','getStats']){const original=RTCPeerConnection.prototype[name];RTCPeerConnection.prototype[name]=async function(...args){try{return await original.apply(this,args)}catch(error){peerErrors.push({operation:name,name:error.name});throw error}}}window.iceErrors=[];
window.pcs=[];
window.captures=[];
const replace=RTCRtpSender.prototype.replaceTrack;RTCRtpSender.prototype.replaceTrack=function(track){if(window.rejectAttachment&&track)return Promise.reject(new DOMException('fixture attach failure','InvalidModificationError'));return replace.call(this,track)};
window.voiceAudio=[];
const NativeAudio=Audio;
window.Audio=class extends NativeAudio{constructor(...args){super(...args);voiceAudio.push(this)}play(){if(window.blockPlayback)return Promise.reject(Error('fixture playback denial'));return super.play()}};

const Native=RTCPeerConnection;
window.RTCPeerConnection=class extends Native{constructor(...args){super(...args);pcs.push(this);this.addEventListener('icecandidateerror',e=>iceErrors.push({code:e.errorCode}))}};

const capture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{if(window.denyCapture)throw new DOMException('fixture denial','NotAllowedError');if(window.missingDevice)throw new DOMException('fixture device missing','NotFoundError');if(window.holdCapture)await new Promise(resolve=>window.releaseCapture=resolve);
const s=await capture(c);captures.push(s);return s};

// Observe only counts: never retain ROM/save bytes or frame inputs.
window.timelineWrites={workers:0,loads:0,imports:0};
const NativeWorker=Worker;
window.Worker=class extends NativeWorker {
 constructor(...args){super(...args);timelineWrites.workers++;}
 postMessage(message,...args){if(message.type==='load')timelineWrites.loads++;if(message.type==='state-import'||message.type==='battery-import')timelineWrites.imports++;return super.postMessage(message,...args);}
};
