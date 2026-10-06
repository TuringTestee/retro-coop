import sys,json,time,re,traceback,argparse,subprocess,math,struct,wave,hashlib,os
from urllib.parse import urlsplit
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
parser=argparse.ArgumentParser(description='Temporary final-source public five-member qualification; not a shipped test.')
parser.add_argument('--root',type=Path,required=True);parser.add_argument('--source',required=True);parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
# Keep diagnostic voice decoded in the browser, but never play it on desktop speakers.
if os.environ.get('GITHUB_ACTIONS')=='true':
 assert not Path('/dev/snd').exists(),'Qualification runner must have no physical audio device'
 audio_output='Isolated GitHub runner with no /dev/snd; browser decoding/playback remains active'
else:
 assert os.environ.get('PULSE_SINK')=='retro-coop-test-audio','Dedicated silent test output is required'
 audio_graph=json.loads(subprocess.check_output(['pw-dump'],text=True))
 sinks=[n for n in audio_graph if n.get('info',{}).get('props',{}).get('node.name')=='retro-coop-test-audio' and n['info']['props'].get('factory.name')=='support.null-audio-sink']
 assert len(sinks)==1,'Silent audio sink is missing; do not launch audible test browsers'
 assert not any(str(n.get('info',{}).get('props',{}).get('link.output.node'))==str(sinks[0]['id']) for n in audio_graph if n.get('type')=='PipeWire:Interface:Link'),'Test sink routes to another audio node'
 audio_output='Verified PipeWire null sink: browser decoding/playback remains active; no physical speaker qualification'
ROOT=args.root.resolve()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==args.source,'Qualification helper checkout must match declared source'
sys.path.insert(0,str(ROOT/'scripts/rooms'));sys.path.insert(0,str(ROOT/'spikes/d02'))
from ui_helpers import rename_lobby,choose_section,choose_panel
from unified_shell_browser import regions,controller_fits,game_fits,text_fits
from layout_geometry import control_visibility
from original_fixture import build
OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=False)
URL='https://retro-coop.atobot.cloud/';NAME='Five release '+str(time.time_ns())[-6:]
result={'url':URL,'deployed_source':args.source,'observation_helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'audio_output':audio_output,'scope':'Live swaps/host observer, empty close/reopen, grace Retry and deliberately stalled-owner recovery; five members across four Chromium processes, with Host/P2 sharing one browser context: native input/state, all-member decoded voice/playback, chat, phone panels/Return/release, moderation, promotion and rejoin. Generated diagnostic and four process-specific fake microphone tones (shared-context pair shares one tone) prove browser transport/decoding, not physical-device or conversational quality. Production asset identity verified separately before/after.','errors':[]}
fixture=(ROOT/'scripts/gameplay/fixture.js').read_text()+'''\n(()=>{const S=WebSocket;window.WebSocket=class extends S{constructor(...a){super(...a);this.addEventListener('message',({data})=>{try{const p=JSON.parse(data);if(p.type==='result'&&p.ok&&p.data?.room)proof.room=p.data.room;}catch{}})}}})();'''
def wait(p,s):p.wait_for_function(s,timeout=30000,polling=100)
def rename(p,n):
 p.get_by_role('button',name=re.compile('^Edit your name:')).click();d=p.get_by_role('dialog');d.get_by_role('textbox').fill(n);d.get_by_role('button',name='Save name',exact=True).click();expect(d).not_to_be_visible()
def mute(p):
 if p.evaluate('proof.room?.game?.status')!='playing':return
 wait(p,'proof.frameCount>0')
 choose_section(p,'Audio')
 p.get_by_role('combobox',name='Audio setting').select_option(label='Game sound')
 b=p.get_by_role('button',name='Mute game',exact=True)
 if b.is_visible():b.click()
 expect(p.get_by_role('button',name='Unmute game',exact=True)).to_be_visible()
 choose_section(p,'Controls')
def ready(p):
 for n in ['Prepare','Retry preparation','Ready','Prepare to play','Prepare to resume']:
  b=p.get_by_role('button',name=n,exact=True)
  if b.count() and b.is_enabled():b.click();return n
 return None
def join(p,established=None):
 p.evaluate('proof.frames=[];proof.frameCount=0')
 recovery=None
 if established:
  before=[{'membership':member(q),'frame_count':q.evaluate('proof.frameCount'),'epoch':room(q)['game']['epoch']} for q in established]
  old_members=[member(q) for q in established];old_owners=owners(established[0]);requests=[]
  for q in established:q.evaluate('proof.release.roomStates=[]')
  def fail_first_rom(route):
   if route.request.method=='GET' and not requests:
    requests.append({'method':'GET','path':urlsplit(route.request.url).path,'failure':'deliberate route abort of first actual ROM GET'});route.abort('failed')
   else:route.continue_()
  p.route('**/rooms/*/rom',fail_first_rom)
 p.get_by_placeholder('Search lobbies').fill(NAME);p.locator('.rc-lobby-card').filter(has_text=NAME).click();wait(p,'proof.room?.role==="member"')
 if established:
  retry=p.get_by_role('button',name='Retry game',exact=True);expect(retry).to_be_visible(timeout=30000)
  assert len(requests)==1,'First ROM GET was not actually attempted/aborted (cached bytes are not this proof)'
  failed_member=member(p)
  for q,prior in zip(established,before):
   wait(q,f'proof.frameCount>{prior["frame_count"]+10}')
   wait(q,f'proof.room.slots.find(s=>s.member?.id==={json.dumps(failed_member)})?.member.acquisition==="failed"')
   current=room(q);ids=[x['member']['id'] for x in current['slots'] if x.get('member')]
   assert all(x in ids for x in old_members) and current['game']['controllers']['owners']==old_owners
   assert current['game']['status']=='playing' and current['game']['epoch']==prior['epoch']
  recovery={'failed_request':requests[0],'failed_membership':failed_member,'established_before':before,'old_memberships':old_members,'committed_owners':old_owners,
   'frames_during_failure':[q.evaluate('proof.frameCount') for q in established]}
  p.screenshot(path=str(OUT/'late-observer-download-failed.png'))
  retry.focus();control_visibility(retry,require_focus=True);p.keyboard.press('Enter')
 wait(p,'proof.room.slots.find(s=>s.member?.id===proof.room.chatMembership)?.member.acquisition==="loaded"')
 if established:
  playing(p)
  for q,prior in zip(established,before):
   wait(q,f'proof.frameCount>{prior["frame_count"]+20}')
   states=q.evaluate('proof.release.roomStates');assert states,'No actual room publications observed during failure/retry'
   assert all(x['status']=='playing' and x['epoch']==prior['epoch'] and x['owners']==old_owners and all(m in x['members'] for m in old_members) for x in states),states
   current=room(q);assert all(m in [x['member']['id'] for x in current['slots'] if x.get('member')] for m in old_members)
  recovery['room_publications_during_failure_retry']=[q.evaluate('proof.release.roomStates') for q in established]
  recovery['frames_after_retry']=[q.evaluate('proof.frameCount') for q in established];recovery['observer_native_current_epoch']=p.evaluate('proof.frames.at(-1)')
  result['late_observer_download_recovery']=recovery
  p.unroute('**/rooms/*/rom',fail_first_rom)

 if p.viewport_size['width']==320:
  expect(p.get_by_role('button',name='Return to lobby view',exact=True)).to_be_visible(timeout=30000);controller_fits(p);game_fits(p);p.screenshot(path=str(OUT/'phone-observer-automatic-entry.png'));result['phone_automatic_entry']=True
 mute(p)
def playing(p):
 wait(p,'proof.room?.game?.status==="playing" && proof.frames.at(-1)?.epoch===proof.room.game.epoch')
def hashes(ps):
 # Correlate each reply with this explicit native request, never retained periodic proof.
 return [p.evaluate('''()=>new Promise((resolve,reject)=>{
  const id=900003,worker=currentWorker;
  const timer=setTimeout(()=>{worker.removeEventListener('message',receive);reject(Error('Native state hash timeout'))},5000);
  function receive({data}){if(data.type==='state-hash'&&data.requestId===id){clearTimeout(timer);worker.removeEventListener('message',receive);resolve(data.info)}}
  worker.addEventListener('message',receive);worker.postMessage({type:'state-hash',requestId:id});
 })''') for p in ps]

# Browser-only observers: call the real browser APIs unchanged. No production hooks.
VOICE_OBSERVER="""(() => {
 window.releaseVoice={pcs:[],audio:[],captures:[]};
 const Peer=RTCPeerConnection;
 window.RTCPeerConnection=class extends Peer{constructor(...args){super(...args);releaseVoice.pcs.push(this)}};
 const NativeAudio=Audio;
 window.Audio=class extends NativeAudio{constructor(...args){super(...args);releaseVoice.audio.push(this)}};
 const capture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
 navigator.mediaDevices.getUserMedia=async(...args)=>{const stream=await capture(...args);releaseVoice.captures.push(stream);return stream};
 window.releaseVoiceSample=async()=>{
  const peers=[];
  for(const pc of releaseVoice.pcs){
   if(pc.connectionState!=='connected')continue;
   const tracks=pc.getReceivers().map(r=>r.track).filter(t=>t?.kind==='audio'&&t.readyState==='live');
   if(!tracks.length)continue;
   const stats=[...(await pc.getStats()).values()].filter(s=>s.type==='inbound-rtp'&&s.kind==='audio'&&!s.isRemote);
   peers.push({id:releaseVoice.pcs.indexOf(pc),tracks:tracks.map(t=>({id:t.id,muted:t.muted,state:t.readyState})),
    stats:stats.map(s=>({id:s.id,track:s.trackIdentifier,energy:s.totalAudioEnergy,samples:s.totalSamplesReceived,packets:s.packetsReceived}))});
  }
  return {peers,audio:releaseVoice.audio.filter(a=>a.srcObject?.getAudioTracks().some(t=>t.readyState==='live'))
   .map(a=>({tracks:a.srcObject.getAudioTracks().map(t=>t.id),paused:a.paused,muted:a.muted,volume:a.volume,time:a.currentTime,ready:a.readyState})),
   captures:releaseVoice.captures.flatMap(s=>s.getAudioTracks()).map(t=>({id:t.id,state:t.readyState,enabled:t.enabled,muted:t.muted,settings:t.getSettings()}))};
 };
})();"""

def microphone_tone(index):
 frequency=440+137*index
 path=OUT/f'microphone-{index+1}.wav'
 with wave.open(str(path),'wb') as wav:
  wav.setparams((1,2,48000,0,'NONE','not compressed'))
  wav.writeframes(b''.join(struct.pack('<h',int(6000*math.sin(2*math.pi*frequency*n/48000))) for n in range(48000)))
 result.setdefault('microphone_inputs',[]).append({'member':index+1,'frequency_hz':frequency,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
 return path

def voice_on(p):
 choose_section(p,'Audio')
 p.get_by_role('combobox',name='Audio setting').select_option(label='Voice')
 selector=p.get_by_role('combobox',name='Voice setting',exact=True)
 if selector.is_visible():selector.select_option('mic')
 enable=p.get_by_role('button',name='Enable voice',exact=True)
 if enable.count() and enable.is_visible():enable.click()
 mode=p.get_by_label('Voice mode')
 expect(mode).to_be_visible();control_visibility(mode);mode.select_option('open')
 unmute=p.get_by_role('button',name=re.compile(r'^Unmute (microphone|mic)$'))
 if unmute.count() and unmute.is_visible():unmute.click()
 wait(p,'releaseVoice.captures.some(s=>s.getAudioTracks().some(t=>t.readyState==="live"&&t.enabled&&!t.muted))')
 choose_section(p,'Controls')

def voice_sample(p,count):
 sample=p.wait_for_function('''async count=>{
  const v=await releaseVoiceSample(),tracks=v.peers.flatMap(p=>p.tracks.map(t=>t.id));
  if(v.peers.length!==count||tracks.length!==count||new Set(tracks).size!==count)return false;
  if(v.peers.some(p=>p.stats.length!==1||p.tracks.some(t=>t.muted)||!p.stats.every(s=>Number.isFinite(s.energy)&&s.samples>0&&s.packets>0)))return false;
  if(v.audio.length!==count||v.audio.some(a=>a.paused||a.muted||a.volume<=0||a.ready<2||a.tracks.length!==1))return false;
  if(tracks.some(id=>v.audio.filter(a=>a.tracks.includes(id)).length!==1))return false;
  return v;
 }''',arg=count,timeout=30000,polling=100).json_value()
 return sample

def five_voice(ps):
 for p in ps:voice_on(p)
 before=[voice_sample(p,4) for p in ps]
 result['five_voice_baseline']=before
 frames=[p.evaluate('proof.frameCount') for p in ps]
 for p,f in zip(ps,frames):wait(p,f'proof.room.game.status==="playing"&&proof.frameCount>{f+60}')
 after=[]
 for p,old in zip(ps,before):
  v=p.wait_for_function('''async old=>{
   const v=await releaseVoiceSample();
   if(v.peers.length!==4||v.audio.length!==4||v.audio.some(a=>a.paused||a.muted||a.volume<=0))return false;
   for(const prior of old.peers){const now=v.peers.find(p=>p.id===prior.id);if(!now||now.stats.length!==1)return false;
    const a=prior.stats[0],b=now.stats[0];if(a.id!==b.id||!(b.energy>a.energy+1e-5&&b.samples>a.samples&&b.packets>a.packets))return false;}
   for(const a of old.audio){const b=v.audio.find(b=>b.tracks[0]===a.tracks[0]);if(!b||!(b.time>a.time))return false;}
   return v;
  }''',arg=old,timeout=10000,polling=100).json_value();after.append(v)
  assert p.evaluate('proof.room.game.status')=='playing'
 result['five_voice']={'before':before,'after':after,'frames_before':frames,'frames_after':[p.evaluate('proof.frameCount') for p in ps],
  'received_tracks_each':4,'directed_receive_paths':20,'undirected_pairs':10,'physical_device_quality':'not qualified by generated tones'}
 ps[0].screenshot(path=str(OUT/'five-voice.png'))

def native_ram(ps):
 values=[]
 for p in ps:
  p.evaluate("proof.controllerRam=null;currentWorker.postMessage({type:'state-export',requestId:900000})")
  wait(p,'Array.isArray(proof.controllerRam)');values.append(p.evaluate('proof.controllerRam'))
 return values

def phone_journey(host,player,observer,ps):
 observer.set_viewport_size({'width':320,'height':568})
 choose_panel(observer,'Players')
 expect(observer.get_by_role('navigation',name='Lobby sections')).to_be_visible()
 rows=observer.locator('[data-testid="room-slot"]');expect(rows).to_have_count(5)
 # The maintained geometry helper measures all persistent regions/panels without scroll repair.
 result['phone_observer_regions']=regions(observer)
 for panel in ['Players','Chat','Settings','Game']:
  choose_panel(observer,panel)
  if panel=='Players':
   for row in observer.locator('.room-slots .slot-row,.room-slots .slot-readonly').all():assert text_fits(row)
  assert observer.evaluate('document.documentElement.scrollWidth<=innerWidth+1&&document.documentElement.scrollHeight<=innerHeight+1&&scrollY===0')
 choose_panel(observer,'Game');observer.get_by_role('button',name='Expand game to full screen',exact=True).click()
 controller_fits(observer);game_fits(observer)
 before=observer.evaluate('proof.frameCount')
 # Observers have visible targets but no controller authority.
 assert observer.locator('[data-game-input] button').evaluate_all('nodes=>nodes.length===5&&nodes.every(n=>n.getAttribute("aria-disabled")==="true")')
 a_observer=observer.get_by_role('button',name='NES A',exact=True);box=a_observer.bounding_box();observer.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
 try:
  observer.mouse.down();before=host.evaluate('proof.frameCount');wait(host,f'proof.frameCount>{before+30}')
  neutral=native_ram(ps);assert neutral==[[0,0]]*5,neutral
  result['phone_observer_actual_input_attempt']={'pointer_down_on_A':True,'all_native_ram':neutral}
 finally:observer.mouse.up()
 observer.get_by_role('button',name='Return to lobby view',exact=True).click()
 wait(observer,f'proof.frameCount>{before+10}')
 expect(observer.get_by_role('navigation',name='Lobby sections').get_by_role('button',name='Game',exact=True)).to_have_attribute('aria-current','page')
 observer.screenshot(path=str(OUT/'phone-observer-return.png'))
 player.set_viewport_size({'width':320,'height':568});choose_panel(player,'Game')
 player.get_by_role('button',name='Expand game to full screen',exact=True).click();controller_fits(player);game_fits(player)
 a=player.get_by_role('button',name='NES A',exact=True);box=a.bounding_box();player.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
 try:
  player.mouse.down();expect(a).to_have_attribute('aria-pressed','true')
  before=host.evaluate('proof.frameCount');wait(host,f'proof.frameCount>{before+30}')
  held=native_ram(ps);assert held==[[0,128]]*5,held
  player.screenshot(path=str(OUT/'phone-player-held.png'))
  back=player.get_by_role('button',name='Return to lobby view',exact=True);back.focus();control_visibility(back,require_focus=True);player.keyboard.press('Enter')
  expect(player.locator('.rc-game-fullscreen')).to_have_count(0)
  before=host.evaluate('proof.frameCount');wait(host,f'proof.frameCount>{before+30}')
  released=native_ram(ps);assert released==[[0,0]]*5,released
  assert player.locator('[data-game-input] button').evaluate_all('nodes=>nodes.every(n=>n.getAttribute("aria-pressed")!=="true")')
  expect(player.get_by_role('navigation',name='Lobby sections').get_by_role('button',name='Game',exact=True)).to_have_attribute('aria-current','page')
  result['phone_player_return_release']={'held_native_ram':held,'released_native_ram':released,'game_continued':True,'frames':host.evaluate('proof.frameCount')}
  player.screenshot(path=str(OUT/'phone-player-return.png'))
 finally:player.mouse.up()
 # Restore the original desktop contexts so the parent's input/moderation checks remain unchanged.
 for p in [player,observer]:p.set_viewport_size({'width':1440,'height':900});choose_section(p,'Controls')

RELEASE_OBSERVER="(() => {\n proof.release={counts:{commands:0,dropped:0},held:[],checkpoints:[],dropped:[],hellos:[],commands:[],frameRequests:[],roomStates:[]};\n const note=(list,data)=>{if(list===proof.release.commands)proof.release.counts.commands++;if(list===proof.release.dropped)proof.release.counts.dropped++;list.push(data);if(list.length>128)list.shift()};\n const header=d=>({type:d.type,requestId:d.requestId,epoch:d.epoch,frame:d.frame,hash:d.hash});\n const W=Worker;\n window.Worker=class extends W{\n  postMessage(d,...a){if(d.type==='frame'&&d.epoch)note(proof.release.frameRequests,header(d));return super.postMessage(d,...a)}\n  constructor(...a){super(...a);this.addEventListener('message',event=>{\n   const d=event.data;\n   if(d.type.startsWith('peer-checkpoint-'))note(proof.release.checkpoints,header(d));\n   if(window.holdCheckpoint&&d.type==='peer-checkpoint-exported'&&!event.checkpointReleased){event.stopImmediatePropagation();proof.release.held.push({worker:this,data:d});}\n  })}\n };\n window.releaseCheckpointReplies=()=>{\n  window.holdCheckpoint=false;\n  for(const {worker,data} of proof.release.held.splice(0)){const event=new MessageEvent('message',{data});Object.defineProperty(event,'checkpointReleased',{value:true});worker.dispatchEvent(event)}\n };\n let hashId=910000;\n window.releaseNativeHash=()=>new Promise((resolve,reject)=>{\n  const worker=currentWorker,id=++hashId;\n  const timer=setTimeout(()=>{worker.removeEventListener('message',receive);reject(Error('Fresh native hash timeout'))},5000);\n  function receive({data}){if(data.type==='state-hash'&&data.requestId===id){clearTimeout(timer);worker.removeEventListener('message',receive);resolve(data.info)}}\n  worker.addEventListener('message',receive);worker.postMessage({type:'state-hash',requestId:id});\n });\n const send=RTCDataChannel.prototype.send;\n RTCDataChannel.prototype.send=function(data){if(typeof data==='string'){try{const d=JSON.parse(data);if(d.kind==='input'&&window.gameFault==='drop-input')note(proof.release.dropped,{epoch:d.epoch,frame:d.frame})}catch{}}return send.call(this,data)};\n const S=WebSocket;\n window.WebSocket=class extends S{\n  constructor(...a){super(...a);this.requests=new Map();this.addEventListener('message',({data})=>{try{const p=JSON.parse(data);const r=p.type==='room'?p.room:p.type==='result'&&p.ok?p.data?.room:undefined;if(r?.game)note(proof.release.roomStates,{status:r.game.status,epoch:r.game.epoch,owners:r.game.controllers.owners,members:r.slots.filter(s=>s.member).map(s=>s.member.id)});if(p.type==='result'&&p.ok&&this.requests.get(p.requestId)==='hello'&&p.data?.room){const r=p.data.room;note(proof.release.hellos,{id:r.id,chatMembership:r.chatMembership,slots:r.slots})}}catch{}})}\n  send(data){try{const d=JSON.parse(data);this.requests.set(d.requestId,d.type);if(d.type==='gameCheckpointAck'||d.type==='gameAck')note(proof.release.commands,{type:d.type,frame:d.frame,hash:d.hash,transferId:d.transferId})}catch{}return super.send(data)}\n };\n})();"

def native_hash(p):return p.evaluate('releaseNativeHash()')
def boundary(value):return {'frame':value['frame'],'hash':value['hash']}
def room(p):return p.evaluate('proof.room')
def owners(p):return room(p)['game']['controllers']['owners']
def member(p):return room(p)['chatMembership']
def slot_label(slot):return {'player1':'Player 1','player2':'Player 2'}.get(slot['role'],'Spectator '+str(int(slot['id'].split('-')[-1])))
def menu_action(host,slot_id,label):
 row=host.locator(f'[data-slot-id="{slot_id}"] .slot-row');row.focus();control_visibility(row,require_focus=True);row.press('ArrowDown')
 action=host.get_by_role('menuitem',name=label,exact=True);expect(action).to_be_visible()
 expect(host.locator('.slot-menu [role="menuitem"]').first).to_be_focused()
 # Exercise the menu's maintained keyboard traversal rather than clicking a hidden command.
 for _ in range(8):
  if action.evaluate('n=>n===document.activeElement'):break
  host.keyboard.press('ArrowDown')
 expect(action).to_be_focused();control_visibility(action,require_focus=True);host.keyboard.press('Enter')
def swap_members(host,a,b):
 slots=room(host)['slots'];source=next(s for s in slots if (s.get('member') or {}).get('id')==a);target=next(s for s in slots if (s.get('member') or {}).get('id')==b)
 menu_action(host,source['id'],f"Swap with {target['member']['nickname']} · {slot_label(target)}")
def hold(host):
 assert host.evaluate('proof.release.held.length')==0,'Undelivered real checkpoint reply from previous attempt'
 host.evaluate('window.holdCheckpoint=true')
def held_boundary(host):
 wait(host,'proof.release.held.length>0')
 return host.evaluate('({frame:proof.release.held[0].data.frame,hash:proof.release.held[0].data.hash})')
def pending_action(host,label):
 pending=room(host)['game']['pending'];assert pending['status']=='failed'
 menu_action(host,pending['roles'][0]['slotId'],label)
def countdown_boundary(host,ps,expected,b):
 wait(host,'!proof.room.game.pending&&proof.room.game.status==="countdown"')
 assert owners(host)==expected,(owners(host),expected)
 actual={};bound_replies={}
 for p in ps:
  if member(p) in expected:
   actual[member(p)]=boundary(native_hash(p));assert actual[member(p)]==b,(actual,b)
 # Actual native replies from newly imported checkpoint, not only coordinator state.
 for p in ps:
  if member(p) in expected and p is not host:
   bound_replies[member(p)]=[v for v in p.evaluate('proof.release.checkpoints') if v['type']=='peer-checkpoint-bound' and boundary(v)==b]
   assert bound_replies[member(p)], 'Incoming native checkpoint never bound at preserved boundary'
 for p in ps:playing(p)
 before=host.evaluate('proof.frameCount');wait(host,f'proof.frameCount>{before+10}')
 return {'fresh_native_hashes':actual,'actual_native_checkpoint_bound_replies':bound_replies}
def owner_input(host,p,ps,expected):
 p.locator('canvas').focus();before=host.evaluate('proof.frameCount');p.keyboard.down('c')
 try:
  wait(host,f'proof.frameCount>{before+30}');ram=native_ram(ps);assert ram==[expected]*len(ps),ram
 finally:p.keyboard.up('c')
 return ram
def live_swap(host,a,b,ps,label):
 before=owners(host);hold(host);swap_members(host,member(a),member(b));frozen=held_boundary(host)
 assert boundary(native_hash(host))==frozen;assert owners(host)==before
 expected=before.copy();ai=member(a);bi=member(b)
 expected=[bi if v==ai else ai if v==bi else v for v in expected]
 host.evaluate('releaseCheckpointReplies()');actual=countdown_boundary(host,ps,expected,frozen)
 evidence={'before':before,'after':expected,'completed_boundary':frozen,'native_at_countdown':actual,'host_role':next(s['role'] for s in room(host)['slots'] if (s.get('member') or {}).get('id')==member(host))}
 for i,owner in enumerate(expected):
  p=next(p for p in ps if member(p)==owner);evidence[f'player_{i+1}_native_input']=owner_input(host,p,ps,[64,0] if i==0 else [0,64])
 host.screenshot(path=str(OUT/f'{label}.png'));result.setdefault('live_role_changes',[]).append(evidence)
def empty_close_reopen(host,ps):
 slots=room(host)['slots'];empty=next(s for s in slots if not s.get('member'));old=owners(host);frames=host.evaluate('proof.frameCount')
 for label,opened in [('Close slot',False),('Open slot',True)]:
  menu_action(host,empty['id'],label)
  for p in ps:wait(p,f'proof.room.slots.find(s=>s.id==={json.dumps(empty["id"])}).open==={str(opened).lower()}')
  assert owners(host)==old
 wait(host,f'proof.frameCount>{frames+10}')
 result['empty_slot_close_reopen']={'slot':empty['id'],'owners':old,'members_unchanged':len(ps),'native_play_continued':True}
def grace_retry(host,p,ps):
 prior=room(p);slot=next(s for s in prior['slots'] if (s.get('member') or {}).get('id')==prior['chatMembership']);count=p.evaluate('proof.release.hellos.length');frames=host.evaluate('proof.frameCount')
 p.evaluate('proof.roomSocket.close()')
 retry=p.get_by_role('button',name='Retry connection',exact=True);expect(retry).to_be_visible(timeout=30000);retry.focus();control_visibility(retry,require_focus=True);p.keyboard.press('Enter')
 wait(p,f'proof.release.hellos.length>{count}&&proof.roomSocket.readyState===WebSocket.OPEN')
 now=room(p);current=next(s for s in now['slots'] if (s.get('member') or {}).get('id')==now['chatMembership'])
 assert (now['id'],now['chatMembership'],current['id'],current['role'])==(prior['id'],prior['chatMembership'],slot['id'],slot['role'])
 playing(p);wait(host,f'proof.frameCount>{frames+10}');voice_sample(p,len(ps)-1)
 result['observer_grace_retry']={'room':now['id'],'membership':now['chatMembership'],'slot':current['id'],'role':current['role'],'fresh_hello':p.evaluate('proof.release.hellos.at(-1)'),'host_native_play_continued':True}
def stalled_departure(host,departing,incoming,active):
 old=owners(host)
 departing.evaluate('proof.release.dropped=[];proof.release.counts.dropped=0;window.gameFault="drop-input"')
 wait(departing,'proof.release.dropped.length>0')
 first=departing.evaluate('proof.release.dropped[0]');target=first['frame']
 # Poll native responses until the input buffer is actually exhausted, before departure.
 deadline=time.monotonic()+2.5
 while True:
  state=native_hash(host)
  if state['frame']==target:break
  assert state['frame']<target,(state,first)
  if time.monotonic()>deadline:raise AssertionError('Real buffered-input exhaustion not observed before network pause')
 last=host.evaluate('proof.frames.at(-1)');assert last['frame']==target-1 and last['epoch']==first['epoch'],(last,first)
 assert room(host)['game']['status']=='playing','Input exhaustion must precede automatic network pause'
 held_before=boundary(state);hold(host)
 departing.get_by_role('button',name='Back to Main Page',exact=True).click();departing.get_by_role('alertdialog').get_by_role('button',name='Leave lobby',exact=True).click();departing.locator('.rc-listing').wait_for()
 departed_ack_count=departing.evaluate('proof.release.counts.commands');departed_packet_count=departing.evaluate('proof.release.counts.dropped')
 assert held_boundary(host)==held_before
 wait(host,'proof.room.game.pending?.status==="failed"')
 assert boundary(native_hash(host))==held_before and owners(host)==old
 failed=room(host)['game'];host.screenshot(path=str(OUT/'stalled-owner-failed.png'))
 pending_action(host,'Cancel change');wait(host,'!proof.room.game.pending&&proof.room.game.status==="paused"')
 assert owners(host)==old and boundary(native_hash(host))==held_before
 canceled=room(host)['game'];host.evaluate('releaseCheckpointReplies()')
 assert owners(host)==old and boundary(native_hash(host))==held_before
 # Public Prepare starts a new proposal for the already compacted incoming player.
 hold(host);assert ready(incoming) is not None
 assert held_boundary(host)==held_before;wait(host,'proof.room.game.pending?.status==="failed"')
 assert owners(host)==old and boundary(native_hash(host))==held_before
 retried_failure=room(host)['game'];host.evaluate('releaseCheckpointReplies()');pending_action(host,'Retry change')
 expected=[old[0],member(incoming)];actual=countdown_boundary(host,active,expected,held_before)
 assert departing.evaluate('proof.release.counts.commands')==departed_ack_count, 'Departed owner acknowledged its replacement'
 assert departing.evaluate('proof.release.counts.dropped')==departed_packet_count, 'Departed owner continued sampling input'
 departing.evaluate('window.gameFault=undefined')
 result['stalled_owner_recovery']={'fixture':'Existing drop-input transport fault plus held ACTUAL native checkpoint export replies; timeout is deliberately induced, not a natural race.',
  'first_missing_input':first,'last_completed_native_frame':last,'preserved_boundary':held_before,'old_committed_assignment':old,
  'failed':failed,'canceled':canceled,'second_failed_attempt':retried_failure,'committed_assignment':expected,'native_at_retry_countdown':actual,
  'departed_ack_count_before_after':[departed_ack_count,departing.evaluate('proof.release.counts.commands')],'departed_input_count_before_after':[departed_packet_count,departing.evaluate('proof.release.counts.dropped')],'dropped_packets':departing.evaluate('proof.release.dropped')}

start=time.monotonic()
with sync_playwright() as pw:
 browsers=[];pages=[]
 try:
  for i in range(5):
   if i==1:
    c=pages[0].context # Two true tabs share origin storage/locks and the browser fake microphone device.
   else:
    tone=microphone_tone(i);b=pw.chromium.launch(channel='chromium',ignore_default_args=['--mute-audio'],args=['--use-fake-device-for-media-stream',f'--use-file-for-fake-audio-capture={tone}']);browsers.append(b);c=b.new_context(permissions=['microphone'],viewport={'width':1440,'height':900});c.add_init_script(fixture+VOICE_OBSERVER+RELEASE_OBSERVER)
   p=c.new_page();p.set_default_timeout(15000);p.on('pageerror',lambda e:result['errors'].append(str(e)));pages.append(p);p.goto(URL);p.locator('.rc-listing').wait_for();p.evaluate('releaseFrames()');rename(p,'Release '+str(i+1))
  assert pages[0].context is pages[1].context and len(browsers)==4
  result['cohort']={'members':5,'browser_processes':4,'shared_context_members':['Release 1','Release 2'],
   'microphone_limit':'Shared-context members use the same real browser fake device/tone. Production capture constraints are unchanged; all real four-track decoding/playback and energy assertions remain. No synthetic energy, phase machinery or automatic exception.'}

  host=pages[0];host.get_by_role('button',name='Host a new game').click();rename_lobby(host,NAME);host.get_by_role('button',name=re.compile('^Load NES game')).click()
  with host.expect_file_chooser() as chooser:host.get_by_role('button',name='Add game file',exact=True).click()
  chooser.value.set_files({'name':'release-controller.nes','mimeType':'application/octet-stream','buffer':build()})
  wait(host,'proof.room?.fingerprint');mute(host)
  join(pages[1]);ready(host);assert host.get_by_role('button',name='Start →').count()==0 or not host.get_by_role('button',name='Start →').is_enabled();expect(host.locator('.rc-status')).to_contain_text('not ready');result['unprepared_player_blocks_start']=True;ready(pages[1]);expect(host.get_by_role('button',name='Start →')).to_be_enabled(timeout=30000);host.get_by_role('button',name='Start →').click()
  for p in pages[:2]:wait(p,'proof.room.game.status==="playing" && proof.frameCount>30');mute(p)
  for p in pages[2:]:
   if p==pages[3]:p.set_viewport_size({'width':320,'height':568})
   join(p,established=pages[:4] if p is pages[4] else None)
  identities=[member(p) for p in pages];assert len(set(identities))==5;result['cohort']['actual_membership_ids']=identities
  wait(host,'proof.room.occupancy===5');result['five_roster']=host.evaluate('proof.room.slots');print('FIVE joined',flush=True)
  message='Five-member chat '+NAME
  pages[4].get_by_role('textbox',name='Message everyone',exact=True).fill(message)
  pages[4].get_by_role('textbox',name='Message everyone',exact=True).press('Enter')
  for p in pages:
   choose_panel(p,'Chat');expect(p.get_by_role('log',name='Lobby messages')).to_be_visible();expect(p.get_by_role('log',name='Lobby messages')).to_contain_text(message)
   if p.viewport_size['width']==320:choose_section(p,'Controls')
  expect(pages[4].get_by_role('log',name='Lobby messages')).to_contain_text('(you) Release 5:')
  result['five_chat_broadcast']=True
  for p in pages:wait(p,'proof.frameCount>30')
  five_voice(pages)
  phone_journey(host,pages[1],pages[3],pages)
  pages[1].locator('canvas').focus();before=host.evaluate('proof.frameCount');pages[1].keyboard.down('c');wait(host,f'proof.frameCount>{before+60}')
  result['controller_ram']=[]
  for p in pages:
   p.evaluate("proof.controllerRam=null;currentWorker.postMessage({type:'state-export',requestId:900000})");wait(p,'Array.isArray(proof.controllerRam)');result['controller_ram'].append(p.evaluate('proof.controllerRam'))
  pages[1].keyboard.up('c');assert all(v==[0,64] for v in result['controller_ram']),result['controller_ram']
  host.get_by_role('button',name='Pause',exact=True).click()
  for p in pages:wait(p,'proof.room.game.status==="paused"')
  result['five_paused_hashes']=hashes(pages);assert all(v==result['five_paused_hashes'][0] for v in result['five_paused_hashes'])
  result['late_observer_download_recovery']['fresh_matching_native_boundary_after_catchup']=result['five_paused_hashes']
  host.screenshot(path=str(OUT/'five-paused.png'));result['passed_five_native']=True
  for p in pages[:2]:ready(p)
  host.get_by_role('button',name='Resume together',exact=True).click()
  for p in pages:playing(p)
  live_swap(host,pages[1],pages[2],pages,'live-player-two-swap')
  live_swap(host,pages[1],pages[2],pages,'live-player-two-restored')
  live_swap(host,host,pages[3],pages,'host-observing-admin')
  live_swap(host,host,pages[3],pages,'host-controller-restored')
  host.locator('[data-slot-id="slot-5"] .slot-row').click();host.get_by_role('menuitem',name=re.compile('Kick')).click();host.get_by_role('alertdialog').get_by_role('button',name='Kick player',exact=True).click();wait(host,'proof.room.occupancy===4');pages[4].locator('.rc-listing').wait_for();wait(host,'proof.room.game.status==="playing"');result['kick_spectator_midgame']=True
  result['voice_after_kick']=[voice_sample(p,3) for p in pages[:4]]
  wait(pages[4],'releaseVoice.captures.every(s=>s.getAudioTracks().every(t=>t.readyState==="ended"))&&releaseVoice.audio.every(a=>a.paused&&!a.srcObject)')
  empty_close_reopen(host,pages[:4]);grace_retry(host,pages[3],pages[:4])
  stalled_departure(host,pages[1],pages[2],[pages[0],pages[2],pages[3]])
  wait(host,'proof.room.occupancy===3');result['compacted_roster']=host.evaluate('proof.room.slots');result['voice_after_leave']=[voice_sample(p,2) for p in [pages[0],pages[2],pages[3]]];wait(pages[1],'releaseVoice.captures.every(s=>s.getAudioTracks().every(t=>t.readyState==="ended"))&&releaseVoice.audio.every(a=>a.paused&&!a.srcObject)');print('P2 LEFT',host.evaluate('proof.room.game'),flush=True)
  # Existing spectator should become P2 while retaining progressed machine state.
  wait(host,'proof.room.slots[1].member?.nickname==="Release 3"');result['spectator_promoted']=True
  for p in pages[:1]+pages[2:4]:ready(p)
  for label in ['Resume together','Start →']:
   b=host.get_by_role('button',name=label,exact=True)
   if b.count() and b.is_enabled():b.click()
  playing(host);playing(pages[2])
  before=host.evaluate('proof.frameCount');wait(host,f'proof.frameCount>{before+60}');pages[2].locator('canvas').focus();pages[2].keyboard.down('c');before=host.evaluate('proof.frameCount');wait(host,f'proof.frameCount>{before+30}')
  result['promoted_ram']=[]
  for p in [host,pages[2]]:
   p.evaluate("proof.controllerRam=null;currentWorker.postMessage({type:'state-export',requestId:900000})");wait(p,'Array.isArray(proof.controllerRam)');result['promoted_ram'].append(p.evaluate('proof.controllerRam'))
  pages[2].keyboard.up('c');assert result['promoted_ram']==[[0,64],[0,64]]
  join(pages[1]);wait(host,'proof.room.occupancy===4');wait(pages[1],'proof.frameCount>30');result['rejoin_midgame']=True
  voice_on(pages[1]);result['voice_after_rejoin']=[voice_sample(p,3) for p in [pages[0],pages[1],pages[2],pages[3]]]
  host.get_by_role('button',name='Pause',exact=True).click()
  active=[pages[0],pages[1],pages[2],pages[3]]
  for p in active:wait(p,'proof.room.game.status==="paused"')
  result['final_hashes']=hashes(active);assert all(v==result['final_hashes'][0] for v in result['final_hashes']);host.screenshot(path=str(OUT/'compacted-rejoined.png'));assert not result['errors'];result['passed']=True;print('PASS',flush=True)
 except Exception as e:
  result['failure']=str(e);traceback.print_exc();raise
 finally:
  result['elapsed_seconds']=time.monotonic()-start
  for i,p in enumerate(pages):
   try:result.setdefault('final_states',[]).append(p.evaluate('window.proof?.room'));result.setdefault('final_voice_observations',[]).append(p.evaluate('releaseVoiceSample()'))
   except Exception:pass
  if pages:
   try:
    h=pages[0]
    h.evaluate('releaseCheckpointReplies()')
    if h.evaluate('window.proof?.room?.role==="host"'):h.get_by_role('button',name='Back to Main Page',exact=True).click();h.get_by_role('alertdialog').get_by_role('button',name='Close lobby',exact=True).click();h.locator('.rc-listing').wait_for()
    for p in pages:wait(p,'releaseVoice.captures.every(s=>s.getAudioTracks().every(t=>t.readyState==="ended"))&&releaseVoice.audio.every(a=>a.paused&&!a.srcObject)&&releaseVoice.pcs.every(pc=>pc.connectionState==="closed")')
    result['voice_close_teardown']=True
   except Exception as e:result['cleanup_error']=str(e);result['passed']=False
  (OUT/'result.json').write_text(json.dumps(result,indent=2))
  for b in browsers:b.close()
  if result.get('cleanup_error'):raise RuntimeError(result['cleanup_error'])
