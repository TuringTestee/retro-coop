const $=id=>document.getElementById(id),screen=$('screen'),canvas=$('canvas'),ctx=canvas.getContext('2d');
const testMuted=new URLSearchParams(location.search).get('muted')==='1';
let loadRequest=0,muted=testMuted;
let worker,loaded=false,paused=false,busy=false,saved=false,keys=0,last=0,audioContext,nextAudio=0,sound=false;
const sources=new Set(),keyMap={KeyX:1,KeyZ:2,ShiftLeft:4,ShiftRight:4,Enter:8,ArrowUp:16,ArrowDown:32,ArrowLeft:64,ArrowRight:128};
function status(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
function flush(){for(const s of sources){try{s.stop()}catch{}}sources.clear();nextAudio=0;}
function playAudio(buffer){if(!sound||audioContext?.state!=='running')return;const samples=new Float32Array(buffer);if(!samples.length)return;
  if(nextAudio<audioContext.currentTime||nextAudio>audioContext.currentTime+.15){flush();nextAudio=audioContext.currentTime+.035;}
  const b=audioContext.createBuffer(1,samples.length,48000);b.copyToChannel(samples,0);const source=audioContext.createBufferSource();source.buffer=b;source.connect(audioContext.destination);sources.add(source);source.onended=()=>sources.delete(source);source.start(nextAudio);nextAudio+=b.duration;
}
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
function validRom(bytes){if(bytes.length<16||bytes.length>8*1024*1024)throw Error('Choose a .nes ROM smaller than 8 MiB.');if(bytes[0]!==78||bytes[1]!==69||bytes[2]!==83||bytes[3]!==26)throw Error('This file is not an NES ROM.');
  const mapper=(bytes[6]>>4)|(bytes[7]&240),nes2=(bytes[7]&12)===8;
  if(nes2||mapper!==0||![1,2].includes(bytes[4])||bytes[5]>1)throw Error('This demo supports NROM games such as From Below. Broader NES support is still being built.');
  const expected=16+((bytes[6]&4)?512:0)+bytes[4]*16384+bytes[5]*8192;if(bytes.length!==expected)throw Error('This ROM has an unexpected size or is incomplete.');
}
async function load(file){if(!file)return;enableSound();const request=++loadRequest;try{if(file.size>8*1024*1024)throw Error('Choose a .nes ROM smaller than 8 MiB.');const bytes=new Uint8Array(await file.arrayBuffer());validRom(bytes);
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(b=>b.toString(16).padStart(2,'0')).join('');
  if(request!==loadRequest)return;
  const title=hash==='1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555'?'From Below':file.name.replace(/\.nes$/i,'');
  worker?.terminate();flush();loaded=false;paused=false;busy=false;saved=false;keys=0;last=0;for(const id of ['pause','sound','fullscreen','save','restore'])$(id).disabled=true;
  status('Starting your game…');worker=new Worker('worker.js');const currentWorker=worker;worker.onerror=()=>{if(worker===currentWorker)status('The emulator stopped. Choose the ROM again to retry.',true)};
  worker.onmessage=({data})=>{if(worker!==currentWorker)return;if(data.type==='ready'){loaded=true;$('title').textContent=title;$('empty').hidden=true;canvas.style.display='block';for(const id of ['pause','sound','fullscreen','save'])$(id).disabled=false;pause(false);screen.focus();}
    else if(data.type==='frame'){busy=false;ctx.putImageData(new ImageData(new Uint8ClampedArray(data.pixels),256,240),0,0);if(!paused)playAudio(data.audio);}
    else if(data.type==='paused'){if(paused){screen.dataset.paused='true';flush();}}
    else if(data.type==='saved'){saved=true;$('restore').disabled=false;status('Saved in this tab.');}
    else if(data.type==='restored'){flush();status('Save restored.');}
    else if(data.type==='error'){loaded=false;busy=false;flush();status(data.message+' Choose your ROM again to retry.',true);}};
  worker.postMessage({type:'load',rom:bytes.buffer},[bytes.buffer]);
 }catch(error){if(request===loadRequest)status(error.message,true)}}
$('choose').onclick=$('change').onclick=()=>{enableSound();$('file').value='';$('file').click()};$('file').onchange=()=>load($('file').files[0]);
screen.ondragover=e=>{e.preventDefault();screen.classList.add('drag')};screen.ondragleave=()=>screen.classList.remove('drag');screen.ondrop=e=>{e.preventDefault();screen.classList.remove('drag');load(e.dataTransfer.files[0])};
$('pause').onclick=()=>{pause(!paused);screen.focus()};$('sound').onclick=()=>{if(sound)setMuted(true);else setMuted(false);screen.focus()};
$('fullscreen').onclick=()=>screen.requestFullscreen().catch(()=>status('Fullscreen unavailable in this browser.',true));
$('save').onclick=()=>{worker?.postMessage({type:'save'});screen.focus()};$('restore').onclick=()=>{if(saved){flush();worker?.postMessage({type:'restore'});screen.focus()}};
screen.addEventListener('keydown',e=>{if(!muted)enableSound();if(keyMap[e.code]){e.preventDefault();keys|=keyMap[e.code]}});window.addEventListener('keyup',e=>{if(keyMap[e.code])keys&=~keyMap[e.code]});
screen.addEventListener('blur',()=>{keys=0});window.addEventListener('blur',()=>{if(loaded)pause(true)});document.addEventListener('visibilitychange',()=>{if(document.hidden&&loaded)pause(true)});
function pad(){const p=[...navigator.getGamepads()].find(Boolean);if(!p)return 0;$('gamepad').textContent='Gamepad connected · Player 1';let m=0;for(const [i,b]of [[0,1],[1,2],[8,4],[9,8],[12,16],[13,32],[14,64],[15,128]])if(p.buttons[i]?.pressed)m|=b;if(p.axes[0]<-.5)m|=64;if(p.axes[0]>.5)m|=128;if(p.axes[1]<-.5)m|=16;if(p.axes[1]>.5)m|=32;return m;}
function tick(now){requestAnimationFrame(tick);if(!loaded||paused||busy)return;if(now-last<1000/60)return;last=now-(now-last)%(1000/60);busy=true;worker.postMessage({type:'frame',p1:keys|pad(),p2:0})}requestAnimationFrame(tick);
