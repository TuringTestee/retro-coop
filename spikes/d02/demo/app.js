import { keyMap, gamepadMask } from './runtime/input.js';
import { createAudioQueue } from './runtime/audio.js';
const $=id=>document.getElementById(id),screen=$('screen'),canvas=$('canvas'),ctx=canvas.getContext('2d');
const testMuted=new URLSearchParams(location.search).get('muted')==='1';
let loadRequest=0,muted=testMuted,frameMs=1000/60;
let pendingWorker,worker,loaded=false,paused=false,busy=false,saved=false,keys=0,last=0,audioContext,sound=false;
const {play:playAudio,flush}=createAudioQueue(()=>audioContext,()=>sound);
function status(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
function soundLabel(){ $('sound').textContent=muted?'Unmute':'Mute';$('sound').setAttribute('aria-label',muted?'Unmute game audio':'Mute game audio'); }
function setMuted(value){muted=value;sound=false;flush();soundLabel();if(!muted)enableSound();}
function enableSound(){
  if(muted)return;
  try{audioContext??=new AudioContext();
    const update=()=>{sound=!muted&&audioContext.state==='running';soundLabel();if(!sound&&!muted){$('sound').textContent='Unmute';$('sound').setAttribute('aria-label','Unmute game audio');}};
    audioContext.onstatechange=update;audioContext.resume().then(update).catch(()=>{setMuted(true);});update();
  }catch{setMuted(true);status('Sound could not start. Click Unmute to retry.',true);}
}
soundLabel();
function pause(value){paused=value;screen.dataset.paused='false';if(paused&&loaded)worker.postMessage({type:'pause'});keys=0;flush();$('pause').textContent=paused?'Resume':'Pause';if(loaded)status(paused?'Paused. Resume whenever you’re ready.':'Playing locally · Enter opens the game’s Start menu.');}
async function load(file){if(!file)return;enableSound();const request=++loadRequest;pendingWorker?.terminate();pendingWorker=undefined;try{const bytes=new Uint8Array(await file.arrayBuffer());
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
  if(request!==loadRequest)return;
  const title=hash==='1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555'?'From Below':file.name.replace(/\.nes$/i,'');
  status('Starting your game…');const candidate=new Worker('worker.js');pendingWorker=candidate;
  const fail=message=>{if(pendingWorker===candidate){pendingWorker=undefined;candidate.terminate();if(request===loadRequest)status(message,true);}else if(worker===candidate){loaded=false;busy=false;flush();status(message,true);}};
  candidate.onerror=()=>fail('The emulator could not run this file. Choose another ROM to retry.');
  candidate.onmessage=({data})=>{
    if(data.type==='error'){fail(data.message);return;}
    if(data.type==='ready'){
      if(request!==loadRequest||pendingWorker!==candidate){candidate.terminate();return;}
      worker?.terminate();worker=candidate;pendingWorker=undefined;flush();paused=false;busy=false;saved=false;keys=0;last=0;$('restore').disabled=true;
      frameMs=1000/data.fps;loaded=true;$('title').textContent=title;$('empty').hidden=true;canvas.style.display='block';for(const id of ['pause','sound','fullscreen','save'])$(id).disabled=false;pause(false);screen.focus();return;
    }
    if(worker!==candidate)return;
    if(data.type==='frame'){busy=false;ctx.putImageData(new ImageData(new Uint8ClampedArray(data.pixels),256,240),0,0);if(!paused)playAudio(data.audio);}
    else if(data.type==='paused'){if(paused){screen.dataset.paused='true';flush();}}
    else if(data.type==='saved'){saved=true;$('restore').disabled=false;status('Saved in this tab.');}
    else if(data.type==='restored'){flush();status('Save restored.');}
};
  candidate.postMessage({type:'load',rom:bytes.buffer},[bytes.buffer]);
 }catch(error){if(request===loadRequest)status(error.message,true)}}
$('choose').onclick=$('change').onclick=()=>{enableSound();$('file').value='';$('file').click()};$('file').onchange=()=>load($('file').files[0]);
screen.ondragover=e=>{e.preventDefault();screen.classList.add('drag')};screen.ondragleave=()=>screen.classList.remove('drag');screen.ondrop=e=>{e.preventDefault();screen.classList.remove('drag');load(e.dataTransfer.files[0])};
$('pause').onclick=()=>{pause(!paused);screen.focus()};$('sound').onclick=()=>{if(sound)setMuted(true);else setMuted(false);screen.focus()};
$('fullscreen').onclick=()=>screen.requestFullscreen().catch(()=>status('Fullscreen unavailable in this browser.',true));
$('save').onclick=()=>{worker?.postMessage({type:'save'});screen.focus()};$('restore').onclick=()=>{if(saved){flush();worker?.postMessage({type:'restore'});screen.focus()}};
screen.addEventListener('keydown',e=>{if(!muted)enableSound();if(keyMap[e.code]){e.preventDefault();keys|=keyMap[e.code]}});window.addEventListener('keyup',e=>{if(keyMap[e.code])keys&=~keyMap[e.code]});
screen.addEventListener('blur',()=>{keys=0});window.addEventListener('blur',()=>{if(loaded)pause(true)});document.addEventListener('visibilitychange',()=>{if(document.hidden&&loaded)pause(true)});
function pad(){const p=[...navigator.getGamepads()].find(Boolean);if(p)$('gamepad').textContent='Gamepad connected · Player 1';return gamepadMask(p);}
function tick(now){requestAnimationFrame(tick);if(!loaded||paused||busy)return;if(now-last<frameMs)return;last=now-(now-last)%frameMs;busy=true;worker.postMessage({type:'frame',p1:keys|pad(),p2:0})}requestAnimationFrame(tick);
