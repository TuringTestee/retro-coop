// Browser verification only: actual fake-device capture plus controlled permission/attachment failures.
window.pcs=[];
window.captures=[];
const replace=RTCRtpSender.prototype.replaceTrack;RTCRtpSender.prototype.replaceTrack=function(track){if(window.rejectAttachment&&track)return Promise.reject(new DOMException('fixture attach failure','InvalidModificationError'));return replace.call(this,track)};
window.voiceAudio=[];
const NativeAudio=Audio;
window.Audio=class extends NativeAudio{constructor(...args){super(...args);voiceAudio.push(this)}play(){if(window.blockPlayback)return Promise.reject(Error('fixture playback denial'));return super.play()}};

const Native=RTCPeerConnection;
window.RTCPeerConnection=class extends Native{constructor(...args){super(...args);pcs.push(this)}};

const capture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{
const s=await capture(c);captures.push(s);return s};

// Invoke the installed production callback to model a source ending; a synthetic
// event does not unplug hardware. Actual hardware removal remains a release check.
const endedCallbacks=new WeakMap(),trackListen=MediaStreamTrack.prototype.addEventListener;
MediaStreamTrack.prototype.addEventListener=function(kind,callback,...args){
 if(kind==='ended' && typeof callback==='function'){const callbacks=endedCallbacks.get(this)||[];callbacks.push(callback);endedCallbacks.set(this,callbacks);}
 return trackListen.call(this,kind,callback,...args);
};
window.modelMicrophoneRemoval=track=>{const callbacks=endedCallbacks.get(track);if(!callbacks?.length)throw Error('No microphone removal listener installed');for(const callback of callbacks)callback.call(track,new Event('ended'));};
