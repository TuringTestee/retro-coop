import argparse, re, hashlib, json, math, struct, time, wave, os, platform, urllib.request, signal, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, TimeoutError as BrowserTimeout
import sys
ROOT=Path(__file__).resolve().parents[1]
PRODUCT_ROOT=Path(os.environ['RETRO_QUALIFICATION_ROOT']).resolve()
sys.path.insert(0,str(PRODUCT_ROOT/'scripts/rooms'))
from ui_helpers import rename_lobby, choose_section
p=argparse.ArgumentParser();p.add_argument('--role',choices=['host','guest'],required=True);p.add_argument('--lobby',required=True);p.add_argument('--mode',choices=['direct','relay'],required=True);p.add_argument('--output',required=True);p.add_argument('--url',default='https://retro-coop.atobot.cloud/');p.add_argument('--check-enter',action='store_true');p.add_argument('--product-revision',required=True);p.add_argument('--core-sha256',required=True);p.add_argument('--play-seconds',type=int,default=10);p.add_argument('--password',default=os.environ.get('QUALIFICATION_PASSWORD'));p.add_argument('--exercise-recovery-at',type=int,default=0);p.add_argument('--max-recoveries',type=int,default=3);a=p.parse_args()
if subprocess.check_output(['git','rev-parse','HEAD'],cwd=PRODUCT_ROOT,text=True).strip()!=a.product_revision:p.error('Maintained helpers must match the declared product revision')
if not a.password:p.error('Configure the temporary qualification password before launch')
if not 1 <= a.play_seconds <= 7200:p.error('--play-seconds must be between 1 and 7200')
if not 0 <= a.exercise_recovery_at < a.play_seconds:p.error('--exercise-recovery-at must be shorter than play duration')
if not 0 <= a.max_recoveries <= 8:p.error('--max-recoveries must be between 0 and 8')
if os.environ.get('GITHUB_ACTIONS')=='true':
 assert not Path('/dev/snd').exists(),'Qualification runner must have no physical audio device'
else:
 assert os.environ.get('PULSE_SINK')=='retro-coop-test-audio','Dedicated silent output is required'
 graph=json.loads(subprocess.check_output(['jq','-s','-f',str(ROOT/'.qualification/silent-audio.jq')],input=subprocess.check_output(['pw-dump','-N'],text=True),text=True))
 sinks=[n for n in graph if n.get('info',{}).get('props',{}).get('node.name')=='retro-coop-test-audio' and n['info']['props'].get('factory.name')=='support.null-audio-sink']
 assert len(sinks)==1,'Silent null sink is missing'
 assert not any(str(n.get('info',{}).get('props',{}).get('link.output.node'))==str(sinks[0]['id']) for n in graph if n.get('type')=='PipeWire:Interface:Link'),'Test sink routes to another audio node'
interrupted=False
def stop(signum,frame):
 global interrupted
 # Raising inside Playwright's event-loop greenlet can strand synchronous waits.
 # Observe cancellation at an ordinary Python boundary so finally can close UI.
 interrupted=True
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
url=a.url
# Distinct inputs prevent the remote playback from matching the local fake
# microphone waveform under the product's enabled echo cancellation.
frequency=440 if a.role=='host' else 880
tone=out/'voice.wav'
with wave.open(str(tone),'wb') as w:
 w.setparams((1,2,48000,0,'NONE','not compressed'));w.writeframes(b''.join(struct.pack('<h',int(6000*math.sin(2*math.pi*frequency*i/48000))) for i in range(48000)))
public_ip=urllib.request.urlopen('https://api.ipify.org',timeout=10).read().strip()
started=time.monotonic();result={'public_ip_sha256':hashlib.sha256(public_ip).hexdigest(),'platform':platform.platform(),'github_run_id':os.environ.get('GITHUB_RUN_ID'),'role':a.role,'mode':a.mode,'url':url,'lobby':a.lobby,'page_errors':[],'helper_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'public_product_revision':a.product_revision,'product_revision_basis':'Root verifies deployment source and every asset separately before and after qualification; helper branch is never the product build','expected_core_sha256':a.core_sha256,'requested_play_seconds':a.play_seconds,'soak_scope':'Active native network/input/voice play with bounded recorded public-UI pause recovery, followed by pause/state agreement, relay signaling reconnect and resume; shared rewind is explicitly deferred in issue18','helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'recoveries':[],'diagnostics':[],'exercise_recovery_at':a.exercise_recovery_at,'max_recoveries':a.max_recoveries}
with sync_playwright() as pw:
 b=pw.chromium.launch(channel='chromium',ignore_default_args=['--mute-audio'],args=['--use-fake-device-for-media-stream',f'--use-file-for-fake-audio-capture={tone.resolve()}'])
 result['browser']=b.version
 c=b.new_context(viewport={'width':1366,'height':768},permissions=['microphone','clipboard-read','clipboard-write']);page=c.new_page();page.set_default_timeout(30000)
 page.on('pageerror',lambda e:result['page_errors'].append(str(e)))
 result['rom_downloads']=[];result['file_chooser_count']=0
 def chooser(_):result['file_chooser_count']+=1
 page.on('filechooser',chooser)
 init=(PRODUCT_ROOT/'scripts/gameplay/fixture.js').read_text()+"""
 // Bound only observation history during the two-hour run; native state and the
 // monotonically increasing frame counter remain untouched.
 setInterval(()=>{for(const rows of [proof.frames,proof.hashes,proof.sentHashes,proof.timing.frameGaps,proof.admission.nonceRttMs])if(rows?.length>1024)rows.splice(0,rows.length-1024)},1000);
 window.romDownloaded=[];const nativeFetch=window.fetch.bind(window);window.fetch=async(...args)=>{const response=await nativeFetch(...args);if(new URL(response.url).pathname.endsWith('/rom')){const bytes=await response.clone().arrayBuffer();const hash=await crypto.subtle.digest('SHA-256',bytes);romDownloaded.push({status:response.status,bytes:bytes.byteLength,sha256:Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('')})}return response};
 window.captureFailures=[];const capture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async(...args)=>{try{return await capture(...args)}catch(e){captureFailures.push({name:e.name,message:e.message});throw e}};
 window.rejectRelay=MODE==='relay'&&ROLE==='guest';window.pcs=[];const PC=RTCPeerConnection;window.RTCPeerConnection=class extends PC{constructor(config,...args){super({...config,...(MODE==='relay'?{iceTransportPolicy:'relay'}:{}),...(window.rejectRelay?{iceServers:config.iceServers.map(s=>({...s,credential:'qualification-invalid-credential'}))}:{})},...args);pcs.push(this);proof.events.push({at:Math.round(performance.now()),kind:'relay-configuration',iceServerCount:config.iceServers.length,invalidCredentialInjected:window.rejectRelay});this.addEventListener('icecandidateerror',e=>{proof.events.push({at:Math.round(performance.now()),kind:'icecandidateerror',errorCode:e.errorCode,errorText:e.errorText});if(proof.events.length>128)proof.events.shift()})}};
 window.readyRequests={};window.readyResults=[];const WS=WebSocket;window.WebSocket=class extends WS{send(raw){try{const v=JSON.parse(raw);if(v.type==='gameReady')readyRequests[v.requestId]={revision:v.revision,roomRevision:v.roomRevision,frame:v.frame,fresh:v.fresh,delay:v.delay}}catch{}return super.send(raw)}constructor(...args){super(...args);this.addEventListener('message',event=>{try{const p=JSON.parse(event.data);if(p.type==='result'&&readyRequests[p.requestId])readyResults.push({request:readyRequests[p.requestId],ok:p.ok,error:p.error});if(p.type==='result'&&p.ok&&p.data?.room)proof.room=p.data.room}catch{}})}};
 """.replace('MODE',json.dumps(a.mode)).replace('ROLE',json.dumps(a.role))
 page.add_init_script(init)
 def chat(text):
  field=page.get_by_role('textbox',name='Message everyone')
  expect(field).to_be_editable();expect(field).to_have_value('');field.fill(text)
  page.get_by_role('button',name='Send',exact=True).click()
  marker(text);expect(field).to_have_value('')
 def marker(text,timeout=120000):
  page.get_by_role('log',name='Lobby messages').get_by_text(text,exact=False).wait_for(timeout=timeout)
 def wait(expr,timeout=60000):
  deadline=time.monotonic()+timeout/1000
  while True:
   if interrupted:raise RuntimeError('Qualification interrupted')
   remaining=(deadline-time.monotonic())*1000
   if remaining<=0:raise BrowserTimeout(f'Qualification condition timed out: {expr}')
   try:
    page.wait_for_function(expr,timeout=min(5000,remaining),polling=100)
    if interrupted:raise RuntimeError('Qualification interrupted')
    return
   except BrowserTimeout:
    if time.monotonic()>=deadline:raise
 def capture(name):page.screenshot(path=str(out/f'{a.role}-{name}.png'))
 def diagnostic(label):
  # Candidate types/counters preserve transport evidence without IPs or credentials.
  observed=page.evaluate("""async()=>({frameCount:proof.frameCount,native:proof.frames.at(-1),game:proof.room?.game,peers:proof.room?.peers,events:proof.events,stops:proof.stopEvents.slice(-16),pcs:await Promise.all(pcs.map(async pc=>{const stats=await pc.getStats();const selected=[];for(const t of stats.values())if(t.type==='transport'&&t.selectedCandidatePairId){const pair=stats.get(t.selectedCandidatePairId),local=stats.get(pair.localCandidateId),remote=stats.get(pair.remoteCandidateId);selected.push({state:pair.state,local:local?.candidateType,remote:remote?.candidateType,protocol:local?.protocol,roundTripSeconds:pair.currentRoundTripTime,bytesSent:pair.bytesSent,bytesReceived:pair.bytesReceived})}return {connection:pc.connectionState,ice:pc.iceConnectionState,gathering:pc.iceGatheringState,selected,audio:[...stats.values()].filter(s=>s.type==='inbound-rtp'&&s.kind==='audio').map(s=>({packetsReceived:s.packetsReceived,packetsLost:s.packetsLost,jitter:s.jitter,totalAudioEnergy:s.totalAudioEnergy,totalSamplesDuration:s.totalSamplesDuration}))}}))})""")
  observed.update(label=label,elapsed_seconds=round(time.monotonic()-started,2),page_errors=list(result['page_errors']))
  result['diagnostics'].append(observed)
  if len(result['diagnostics'])>64:result['diagnostics'].pop(0)
  (out/f'{a.role}-live.json').write_text(json.dumps({'recoveries':result['recoveries'],'diagnostics':result['diagnostics']},indent=2))
  return observed
 def fresh_hash():
  return page.evaluate("""()=>new Promise((resolve,reject)=>{const worker=currentWorker,requestId=900003;const timer=setTimeout(()=>{worker.removeEventListener('message',receive);reject(Error('Fresh native state timed out'))},10000);function receive({data}){if(data.type==='state-hash'&&data.requestId===requestId){clearTimeout(timer);worker.removeEventListener('message',receive);resolve(data.info)}}worker.addEventListener('message',receive);worker.postMessage({type:'state-hash',requestId})})""")
 def recover(observed):
  if observed['game'].get('status')=='pausing':
   # A pause first freezes owners at a shared native boundary; retain both states.
   wait('proof.room.game.status!=="pausing"',15000)
   observed=diagnostic('pause-settled')
  game=observed['game'];reason=game.get('reason','');status=game.get('status')
  assert status=='paused' and ('network' in reason or a.exercise_recovery_at),{'status':status,'reason':reason}
  assert len(result['recoveries'])<a.max_recoveries,'Bounded recovery count exceeded'
  at=time.monotonic();entry={'before':observed,'result':'pending'};result['recoveries'].append(entry)
  capture(f'recovery-{len(result["recoveries"])}-paused')
  # Correlate a fresh native response from both helpers before either prepares.
  checkpoint=fresh_hash();entry['paused_native']=checkpoint;prefix='QUAL RECOVERY '+game['epoch']
  chat(prefix+' '+a.role+' '+json.dumps(checkpoint,sort_keys=True))
  other='guest' if a.role=='host' else 'host';marker(prefix+' '+other,30000)
  remote_text=page.get_by_role('log',name='Lobby messages').get_by_text(prefix+' '+other,exact=False).inner_text()
  remote=json.loads(remote_text.split(prefix+' '+other+' ',1)[1].splitlines()[0])
  assert checkpoint==remote,{'local':checkpoint,'remote':remote}
  entry['peer_paused_native']=remote
  prepare=page.get_by_role('button',name='Prepare to resume',exact=True);expect(prepare).to_be_enabled(timeout=10000);prepare.click()
  wait('proof.room.game.ready.includes(proof.room.chatMembership)',30000)
  if a.role=='host':
   wait('proof.room.game.status==="resume_ready"',30000)
   page.get_by_role('button',name='Resume together',exact=True).click()
  wait('proof.room.game.status==="playing" && proof.room.game.epoch!=='+json.dumps(game['epoch']),30000)
  # Input may be released by Pause/Prepare. Coordinate, then restore public keys.
  chat(prefix+' '+a.role+' INPUT');marker(prefix+' '+other+' INPUT',10000)
  page.locator('canvas').focus();page.keyboard.up('z' if a.role=='host' else 'c');page.keyboard.down('z' if a.role=='host' else 'c')
  before=page.evaluate('proof.frameCount');e0=page.evaluate(energy)
  page.wait_for_function('n=>proof.frameCount>n+30',arg=before,timeout=5000)
  page.wait_for_timeout(1500);entry['received_audio_energy']=page.evaluate(energy)-e0
  assert entry['received_audio_energy']>1e-5,entry['received_audio_energy']
  deadline=time.monotonic()+10
  while True:
   page.evaluate("delete proof.controllerRam;currentWorker.postMessage({type:'state-export',requestId:900000})");wait('Array.isArray(proof.controllerRam)',5000)
   entry['controller_ram']=page.evaluate('proof.controllerRam')
   if entry['controller_ram']==[128,64]:break
   assert time.monotonic()<deadline,entry['controller_ram']
   page.wait_for_timeout(100)
  entry['after']=diagnostic('recovered');entry['recovered_native']=fresh_hash();entry['seconds']=round(time.monotonic()-at,2)
  assert entry['seconds']<=90,'Recovery exceeded bounded90s'
  assert sum(e.get('seconds',0) for e in result['recoveries'])<=180,'Total recovery time exceeded bounded180s'
  assert entry['recovered_native']['frame']>checkpoint['frame'],entry['recovered_native']
  assert entry['after']['native']['epoch']==entry['after']['game']['epoch'],entry['after']['native']
  entry['result']='pass';capture(f'recovery-{len(result["recoveries"])}-playing');diagnostic('recovery-proof-complete')
 try:
  page.goto(url);page.locator('.rc-listing').wait_for()
  if a.role=='host':
   page.get_by_role('button',name='Host a new game').click();rename_lobby(page,a.lobby)
   if a.password:
    page.get_by_role('button',name='Set Password',exact=True).click()
    access=page.get_by_role('dialog',name='Lobby access',exact=True);access.wait_for()
    page.get_by_role('button',name='Require password',exact=True).click()
    page.get_by_label('New lobby password').fill(a.password);page.get_by_role('button',name='Save password',exact=True).click()
    page.get_by_text('Password protected',exact=True).wait_for()
    access.get_by_role('button',name='Done',exact=True).click()
   # This original diagnostic fixture is generated by the host only.
   rom=out/'public-diagnostic.nes';subprocess.run([sys.executable,str(PRODUCT_ROOT/'spikes/d02/original_fixture.py'),str(rom)],check=True)
   result['rom_sha256']=hashlib.sha256(rom.read_bytes()).hexdigest()
   page.get_by_role('button',name=re.compile(r'^Load NES game(?:\s|$)')).click()
   with page.expect_file_chooser() as chosen:
    page.get_by_role('button',name='Add game file',exact=True).click()
   chosen.value.set_files(str(rom));page.get_by_role('button',name='Change game').wait_for()
   print('HOST_READY '+json.dumps({'lobby':a.lobby,'rom':result['rom_sha256']}),flush=True)
   wait('proof.room?.occupancy===2',480000)
  else:
   first_download=[True]
   def reject_first_download(route):
    if first_download[0]:first_download[0]=False;route.abort('failed')
    else:route.continue_()
   page.route('**/rooms/*/rom',reject_first_download)
   page.get_by_placeholder('Search lobbies').fill(a.lobby)
   page.locator('.rc-lobby-card').filter(has_text=a.lobby).wait_for(timeout=60000);page.locator('.rc-lobby-card').filter(has_text=a.lobby).click()
   if a.password:
    page.get_by_role('textbox',name='Lobby password',exact=True).fill(a.password)
    page.get_by_role('button',name='Join lobby',exact=True).click()
   wait('proof.room?.role==="member" && proof.room.fingerprint')
   print('GUEST_ROOM '+json.dumps({'lobby':a.lobby}),flush=True)
   result['rom_sha256']=page.evaluate('proof.room.fingerprint.romSha256')
   page.get_by_role('button',name='Retry game',exact=True).wait_for();capture('download-failed')
   result['download_failure_visible']=True
   page.get_by_role('button',name='Retry game',exact=True).click()
   page.unroute('**/rooms/*/rom',reject_first_download)
   if a.mode=='relay':
    page.get_by_role('button',name='Retry connection',exact=True).wait_for(timeout=60000);capture('relay-failed');result['induced_relay_auth_failure_visible']=True
    page.evaluate('window.rejectRelay=false');page.get_by_role('button',name='Retry connection',exact=True).click()
    wait('proof.room.peers.every(p=>p.status==="connected")');result['relay_retry_connected']=True
  result['public_fingerprint']=page.evaluate('proof.room.fingerprint')
  assert result['public_fingerprint']['coreSha256']==a.core_sha256,result['public_fingerprint']
  # The guest deliberately fails acquisition first. Observe its completed
  # download/connection/Ready before the host prepares, rather than racing it.
  if a.role=='host':
   wait('proof.room.peers.length===1 && proof.room.peers[0].status==="connected" && proof.room.game.ready.includes(proof.room.peers[0].member)')
  prepare=page.get_by_role('button',name=re.compile(r'^(Prepare|Retry preparation|Ready)$'));expect(prepare).to_be_enabled(timeout=60000);prepare.click()
  if a.role=='host':
   wait('proof.room.game.ready.includes(proof.room.chatMembership)')
   expect(page.get_by_role('button',name='Start →')).to_be_enabled(timeout=60000);page.get_by_role('button',name='Start →').click()
  wait('proof.room?.game?.status==="playing"');page.evaluate('releaseFrames()');wait('proof.frameCount>=10')
  choose_section(page,'Audio');page.get_by_role('combobox',name='Audio setting').select_option(label='Game sound');page.get_by_role('button',name='Mute game',exact=True).click()
  page.get_by_role('combobox',name='Audio setting').select_option(label='Voice');page.get_by_label('Voice mode').select_option('open')
  chat('HOST PLAYING' if a.role=='host' else 'GUEST PLAYING')
  marker('GUEST PLAYING' if a.role=='host' else 'HOST PLAYING')
  if a.check_enter:
   field=page.get_by_role('textbox',name='Message everyone');expect(field).to_be_editable();expect(field).to_have_value('')
   text='HOST ENTER CHAT' if a.role=='host' else 'GUEST ENTER CHAT'
   field.press_sequentially(text);result['enter_before']=field.evaluate('(n)=>({value:n.value,readOnly:n.readOnly,disabled:n.disabled,sendDisabled:n.form.querySelector("button").disabled})')
   field.press('Enter');marker(text,10000);marker('GUEST ENTER CHAT' if a.role=='host' else 'HOST ENTER CHAT',10000)
   result['enter_chat_acknowledged_both']=True
  energy="async()=>{let n=0;for(const p of pcs)for(const s of(await p.getStats()).values())if(s.type==='inbound-rtp'&&s.kind==='audio')n+=s.totalAudioEnergy||0;return n}"
  e0=page.evaluate(energy);page.wait_for_timeout(1500);result['received_audio_energy']=page.evaluate(energy)-e0
  assert result['received_audio_energy']>1e-5,result
  page.locator('canvas').focus();page.keyboard.down('z' if a.role=='host' else 'c')
  # Observe both real controller ports while each participant still holds its key.
  input_deadline=time.monotonic()+15
  while True:
   page.evaluate("delete proof.controllerRam;currentWorker.postMessage({type:'state-export',requestId:900000})");wait('Array.isArray(proof.controllerRam)',5000)
   result['controller_ram']=page.evaluate('proof.controllerRam')
   if result['controller_ram']==[128,64]:break
   assert time.monotonic()<input_deadline,result['controller_ram']
   sampled=page.evaluate('proof.frameCount');page.wait_for_function('n=>proof.frameCount>n+30',arg=sampled,timeout=5000)
  play_at=time.monotonic();frame0=page.evaluate('proof.frameCount');previous=frame0;active_seconds=0;last_progress=play_at;exercised=False
  audio_at=play_at;audio_previous=page.evaluate(energy);audio_frame=frame0
  result['continuous_audio_samples']=[]
  diagnostic('play-start')
  while active_seconds<a.play_seconds:
   if interrupted:raise RuntimeError('Qualification interrupted')
   if a.role=='host' and a.exercise_recovery_at and not exercised and active_seconds>=a.exercise_recovery_at:
    page.get_by_role('button',name='Pause',exact=True).click();exercised=True
   try:page.wait_for_function('n=>proof.frameCount>n || proof.room.game.status!=="playing"',arg=previous,timeout=5000)
   except BrowserTimeout:
    observed=diagnostic('five-second-progress-deadline')
    if observed['game']['status']=='playing':raise
    recover(observed);previous=page.evaluate('proof.frameCount');last_progress=time.monotonic();audio_at=last_progress;audio_previous=page.evaluate(energy);audio_frame=previous;continue
   if not page.evaluate('proof.room.game.status==="playing"'):
    recover(diagnostic('pause-observed'));previous=page.evaluate('proof.frameCount');last_progress=time.monotonic();audio_at=last_progress;audio_previous=page.evaluate(energy);audio_frame=previous;continue
   current=page.evaluate('proof.frameCount')
   assert current>previous,{'previous':previous,'current':current}
   now=time.monotonic();active_seconds+=now-last_progress;last_progress=now;previous=current
   if time.monotonic()-audio_at>=10:
    current_audio=page.evaluate(energy)
    sample={'elapsed_seconds':round(active_seconds,2),'interval_seconds':round(time.monotonic()-audio_at,2),'received_audio_energy':current_audio-audio_previous,'native_frames':previous-audio_frame}
    result['continuous_audio_samples'].append(sample)
    diagnostic('active-play-sample')
    assert sample['received_audio_energy']>1e-5 and sample['native_frames']>0,sample
    audio_at=time.monotonic();audio_previous=current_audio;audio_frame=previous
   page.wait_for_timeout(100)
  result['play_seconds']=round(active_seconds,2);result['play_wall_seconds']=round(time.monotonic()-play_at,2);assert result['play_seconds']>=a.play_seconds
  if a.exercise_recovery_at:assert result['recoveries'],'Requested public Pause recovery was not exercised'
  current_audio=page.evaluate(energy)
  sample={'elapsed_seconds':result['play_seconds'],'interval_seconds':round(time.monotonic()-audio_at,2),'received_audio_energy':current_audio-audio_previous,'native_frames':previous-audio_frame}
  result['continuous_audio_samples'].append(sample)
  if sample['interval_seconds']>=1:
   assert sample['received_audio_energy']>1e-5 and sample['native_frames']>0,sample
  result['measured_fps']=round((previous-frame0)/result['play_seconds'],2)
  wait('proof.frameCount>=220')
  page.keyboard.up('z' if a.role=='host' else 'c')
  result['ready_results']=page.evaluate('window.readyResults')
  result['received_gameplay']=page.evaluate('proof.admission.received')
  assert result['received_gameplay']['input' if a.role=='host' else 'frame']>0,result['received_gameplay']
  result['selected_candidates']=page.evaluate("""async()=>{const all=[];for(const pc of pcs){const s=await pc.getStats();for(const t of s.values())if(t.type==='transport'&&t.selectedCandidatePairId){const p=s.get(t.selectedCandidatePairId),l=s.get(p.localCandidateId),r=s.get(p.remoteCandidateId);all.push({local:l.candidateType,remote:r.candidateType,protocol:l.protocol,roundTripSeconds:p.currentRoundTripTime})}}return all}""")
  assert result['selected_candidates']
  assert all(('relay' in [x['local'],x['remote']])==(a.mode=='relay') for x in result['selected_candidates']),result['selected_candidates']
  capture('playing');chat('HOST SAMPLED' if a.role=='host' else 'GUEST SAMPLED');marker('GUEST SAMPLED' if a.role=='host' else 'HOST SAMPLED')
  if a.role=='host':page.get_by_role('button',name='Pause',exact=True).click()
  wait('proof.room?.game?.status==="paused"')
  # Capture the response to this request, never a retained or unrelated hash.
  result['paused_hash']=page.evaluate("""()=>new Promise((resolve,reject)=>{
   const worker=currentWorker,requestId=900003;
   const timer=setTimeout(()=>{worker.removeEventListener('message',receive);reject(new Error('Fresh paused native state timed out'))},10000);
   function receive({data}){if(data.type==='state-hash'&&data.requestId===requestId){clearTimeout(timer);worker.removeEventListener('message',receive);resolve(data.info)}}
   worker.addEventListener('message',receive);worker.postMessage({type:'state-hash',requestId});
  })""")
  result['page_url']=page.url;result['room_id']=page.evaluate('proof.room.id');result['frames']=page.evaluate('proof.frameCount');capture('paused')
  chat('HOST PAUSED' if a.role=='host' else 'GUEST PAUSED');marker('GUEST PAUSED' if a.role=='host' else 'HOST PAUSED')
  if a.mode=='relay':
   if a.role=='guest':
    chat('GUEST RECONNECTING');marker('HOST RECONNECT READY');membership=page.evaluate('proof.room.chatMembership');epoch=page.evaluate('proof.room.peers[0].epoch')
    page.evaluate('proof.roomSocket.close()');page.get_by_role('button',name='Retry connection',exact=True).wait_for();capture('signaling-disconnected')
    page.get_by_role('button',name='Retry connection',exact=True).click();wait('proof.room.peers[0].status==="connected" && proof.room.peers[0].epoch!=='+json.dumps(epoch))
    assert page.evaluate('proof.room.chatMembership')==membership;result['same_membership_reconnected']=True;capture('reconnected');chat('GUEST RECONNECTED')
   else:marker('GUEST RECONNECTING');chat('HOST RECONNECT READY');marker('GUEST RECONNECTED')
  page.get_by_role('button',name='Prepare to resume',exact=True).click()
  wait('proof.room?.game?.ready?.includes(proof.room.chatMembership)')
  if a.role=='host':wait('proof.room?.game?.status==="resume_ready"');page.get_by_role('button',name='Resume together',exact=True).click()
  wait('proof.room?.game?.status==="playing"');before=page.evaluate('proof.frameCount');page.wait_for_function('n=>proof.frameCount>n+30',arg=before)
  result['resumed']=True;chat('HOST COMPLETE' if a.role=='host' else 'GUEST COMPLETE');marker('GUEST COMPLETE' if a.role=='host' else 'HOST COMPLETE');capture('resumed')
  if a.role=='guest':
   page.get_by_role('button',name='Back to Main Page').click();page.get_by_role('alertdialog').get_by_role('button',name='Leave lobby',exact=True).click();page.locator('.rc-listing').wait_for();result['left']=True
  else:
   wait('proof.room?.occupancy===1');page.get_by_role('button',name='Back to Main Page').click();page.get_by_role('alertdialog').get_by_role('button',name='Close lobby',exact=True).click();page.locator('.rc-listing').wait_for();result['closed']=True
  if a.role=='guest':
   result['rom_downloads']=page.evaluate('romDownloaded')
   assert result['file_chooser_count']==0
   assert any(r['status']==200 and r['sha256']==result['rom_sha256'] for r in result['rom_downloads']),result['rom_downloads']
  assert not result['page_errors'],result['page_errors']
  result['result']='pass'
 except Exception as e:
  result['result']='fail';result['error']=str(e);diagnostic('failure-before-cleanup');result['body']=page.locator('body').inner_text();result['ready_results']=page.evaluate('window.readyResults');result['capture_failures']=page.evaluate('window.captureFailures');result['observed_room']=page.evaluate('window.proof?.room');result['events']=page.evaluate('window.proof?.events');raise
 finally:
  try:
   page.set_default_timeout(3000)
   if page.get_by_role('button',name='Back to Main Page').is_visible():
    page.get_by_role('button',name='Back to Main Page').click()
    page.get_by_role('alertdialog').get_by_role('button',name='Close lobby' if a.role=='host' else 'Leave lobby',exact=True).click()
    page.locator('.rc-listing').wait_for()
    result['cleanup_closed']=True
  except Exception as cleanup_error:result['cleanup_error']=str(cleanup_error)
  result['elapsed_seconds']=round(time.monotonic()-started,2)
  encoded=json.dumps(result,indent=2)
  if a.password:encoded=encoded.replace(a.password,'[redacted qualification password]')
  (out/f'{a.role}.json').write_text(encoded)
  print(json.dumps({k:result.get(k) for k in ['result','role','mode','play_seconds','play_wall_seconds','elapsed_seconds']}),flush=True);b.close()
