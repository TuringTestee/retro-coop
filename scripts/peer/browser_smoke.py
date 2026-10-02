"""Local direct and authenticated coturn route evidence; not public-network qualification."""
import argparse, json, os, subprocess, time
from fixture import LocalTurn
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser()
parser.add_argument('--chrome',action='store_true');parser.add_argument('--turnserver',default='turnserver');parser.add_argument('--output',default='peer.local.json')
args=parser.parse_args();root=Path(__file__).resolve().parents[2];out=Path(args.output);started=time.monotonic()
rom=(Path(os.environ.get('RETRO_COOP_STATIC_ROOT', root/'apps/client/dist'))/'generated/diagnostic.nes').read_bytes()
processes=[]
def service(extra):
 env={**os.environ,**extra};proc=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env=env,stdout=subprocess.PIPE,text=True);processes.append(proc)
 line=proc.stdout.readline();assert line, 'coordinator gateway did not start';return json.loads(line)['url']
try:
 with LocalTurn(args.turnserver) as turn, sync_playwright() as p:
  browser=p.chromium.launch(ignore_default_args=['--mute-audio'],**({'channel':'chrome'} if args.chrome else {}))
  errors=[]
  def page(url,force_relay=False):
   page=browser.new_page(viewport={'width':1280,'height':1050});page.on('pageerror',lambda error:errors.append(str(error)))
   page.context.grant_permissions(['clipboard-read','clipboard-write'])
   page.add_init_script(f'window.forceRelayTransport={str(force_relay).lower()}')
   page.add_init_script((root/'scripts/peer/diagnostics.js').read_text()+'''
    const dataSend=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(this.awaitingFirstInbound && window.modelEarlySendLoss && typeof data==='string' && JSON.parse(data).type==='transportProbe'){window.earlySendDrops=(window.earlySendDrops??0)+1;return;}if(window.suppressTransportProbe && typeof data==='string'){try{if(JSON.parse(data).type==='transportProbe'){window.suppressedProbes=(window.suppressedProbes??0)+1;return;}}catch{}}return dataSend.call(this,data)};
    window.peerProof={pcs:[],started:false,gatherBeforeStart:false,requestedPolicies:[],policies:[],sentCandidates:[],errors:[],ice:[]};
    const NativeSocket=WebSocket;window.WebSocket=class extends NativeSocket{
     set onmessage(fn){this.deliver=fn;super.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='room')peerProof.lastRoom=d.room;if(d.type==='result'&&d.ok&&d.data?.room)peerProof.lastRoom=d.data.room;if(d.type==='peerStart')peerProof.startedAt=performance.now();if(d.type==='peerStart'&&window.deadlineMode==='connecting')return;if(d.type==='result'&&!d.ok)peerProof.errors.push(d.error);if(d.type==='peerPrepare'){peerProof.offerer=d.offerer;peerProof.preparedAt=performance.now();peerProof.started=false};if(d.type==='peerStart')peerProof.started=true;fn(e)}}
     send(raw){const d=JSON.parse(raw);if(d.type==='peerAck'&&window.deadlineMode==='preparing'){queueMicrotask(()=>this.deliver(new MessageEvent('message',{data:JSON.stringify({type:'result',requestId:d.requestId,ok:true,data:{}})})));return;}if(d.type==='peerSignal'&&d.signal.kind==='candidate')peerProof.sentCandidates.push(d.signal.candidate.candidate);super.send(raw)}
    };
    const NativePeer=RTCPeerConnection;window.RTCPeerConnection=class extends NativePeer{
     constructor(c){peerProof.requestedPolicies.push(c.iceTransportPolicy);super(window.forceRelayTransport?{...c,iceTransportPolicy:'relay'}:c);this.addEventListener('datachannel',({channel})=>{channel.awaitingFirstInbound=true;channel.addEventListener('message',()=>{channel.awaitingFirstInbound=false},{once:true})});peerProof.pcs.push(this);peerProof.policies.push(this.getConfiguration().iceTransportPolicy);this.addEventListener('icecandidateerror',e=>peerProof.ice.push({error:e.errorCode}));this.addEventListener('iceconnectionstatechange',()=>peerProof.ice.push({state:this.iceConnectionState}));this.addEventListener('icecandidate',e=>{if(e.candidate)peerProof.ice.push({candidate:e.candidate.type})})}
     setLocalDescription(d){if(!peerProof.started)peerProof.gatherBeforeStart=true;return super.setLocalDescription(d)}
    };''');page.goto(url);return page
  def host(url,force_relay=False):
   h=page(url,force_relay);h.screenshot(path=str(out.with_suffix('.before.png')),full_page=True)
   h.get_by_role('button',name='Browse lobbies →').click()
   h.get_by_role('button',name='Create lobby →').click()
   h.get_by_role('button',name='Create lobby →').click()
   h.locator('[data-page="lobby"]').wait_for()
   h.locator('input[aria-label="NES cartridge file"]').set_input_files({'name':'PRIVATE-PEER.nes','mimeType':'application/octet-stream','buffer':rom})
   h.get_by_role('button',name='Change game').wait_for(timeout=30000)
   h.get_by_role('button',name='Copy invite',exact=True).click();invite=h.evaluate('navigator.clipboard.readText()');assert '#invite=' in invite
   return h,invite
  def join(invite,force_relay=False,early_loss=False):
   g=page(invite,force_relay);g.evaluate('(value)=>window.modelEarlySendLoss=value',early_loss);assert g.evaluate('peerProof.pcs.length')==0;g.locator('.rc-invite-entry').wait_for();g.get_by_role('button',name='Join lobby',exact=True).click();g.locator('[data-page="lobby"]').wait_for();return g
  def connected(h,g,route):
   try:
    for tab in [h,g]:tab.wait_for_function("peerProof.lastRoom?.peers[0]?.status==='connected'",timeout=25000)
   except Exception:
    failure={'connection_failure':[tab.evaluate("({status:document.querySelector('.rc-status')?.textContent,states:peerProof.pcs.map(pc=>pc.connectionState),earlySendModel:{enabled:window.modelEarlySendLoss===true,count:window.earlySendDrops??0},probeSuppression:{enabled:window.suppressTransportProbe===true,count:window.suppressedProbes??0},errors:peerProof.errors,ice:peerProof.ice,...peerDiagnostics()})") for tab in [h,g]],
     'turn_error_codes':turn.error_codes()}
    out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True)
    raise
   assert all(tab.evaluate('peerProof.lastRoom.peers.length')==1 for tab in [h,g])
   assert h.evaluate('peerProof.lastRoom.peers[0].pairId')==g.evaluate('peerProof.lastRoom.peers[0].pairId')
   result=[]
   probe='''async()=>{const pc=peerProof.pcs.at(-1),stats=await pc.getStats();let selected;
     stats.forEach(s=>{if(s.type==='transport'&&s.selectedCandidatePairId){const pair=stats.get(s.selectedCandidatePairId);selected={local:stats.get(pair.localCandidateId).candidateType,remote:stats.get(pair.remoteCandidateId).candidateType,bytesSent:pair.bytesSent,bytesReceived:pair.bytesReceived}}});
     return {...selected,policy:pc.getConfiguration().iceTransportPolicy,gatherBeforeStart:peerProof.gatherBeforeStart,relayCandidatesOnly:peerProof.sentCandidates.every(c=>c.includes(' typ relay '))};}'''
   for tab in [h,g]:
    data=tab.evaluate(probe)
    for _ in range(50):
     if data['bytesSent']>0 and data['bytesReceived']>0:break
     tab.wait_for_timeout(100);data=tab.evaluate(probe)
    assert not data['gatherBeforeStart'];assert data['bytesSent']>0 and data['bytesReceived']>0
    if route=='relay':assert data['local']=='relay' and data['remote']=='relay' and data['policy']=='relay'
    else:assert data['local']!='relay' and data['remote']!='relay'
    assert tab.evaluate("peerProof.requestedPolicies.every(policy=>policy==='all')"),'Application attempted to choose a visitor route'
    assert tab.locator('.rc-status-action').count()==0,'A connected peer should not ask for retry'
    result.append(data)
   assert g.evaluate("peerProof.lastRoom.role==='member'")
   return result
  # Model the observed native first-send discard before the remote channel receives data.
  # This deterministic timing model is not a claim to reproduce Chromium's internal race.
  modeled=service({'TURN_URLS':'','TURN_SECRET':''});mh,mi=host(modeled);mh.evaluate('window.modelEarlySendLoss=true');mg=join(mi,early_loss=True)
  modeled_route=connected(mh,mg,'direct')
  answerer=mg if not mg.evaluate('peerProof.offerer') else mh
  assert answerer.evaluate('window.earlySendDrops??0')==0
  trace=answerer.evaluate('peerDiagnostics().trace')
  received=next(i for i,e in enumerate(trace) if e['kind']=='channel-receive' and e['type']=='transportProbe')
  sent=next(i for i,e in enumerate(trace) if e['kind']=='channel-send' and e['type']=='transportProbe')
  assert received<sent
  mh.close();mg.close()
  direct=service({'TURN_URLS':'','TURN_SECRET':''});h,invite=host(direct);g=join(invite)
  direct_proof=connected(h,g,'direct');h.screenshot(path=str(out.with_suffix('.direct.png')),full_page=True)
  h.close();g.close()
  relay=service(turn.environment())
  h,invite=host(relay,force_relay=True);g=join(invite,force_relay=True);relay_proof=connected(h,g,'relay')
  for tab in [h,g]:assert tab.evaluate('peerProof.sentCandidates.every(c=>c.includes(" typ relay "))')
  h.screenshot(path=str(out.with_suffix('.relay.png')),full_page=True)
  h.set_viewport_size({'width':390,'height':844});assert h.evaluate('document.documentElement.scrollWidth<=innerWidth');h.screenshot(path=str(out.with_suffix('.mobile.png')),full_page=True);h.set_viewport_size({'width':1280,'height':1050})
  lease_before=g.evaluate('({member:peerProof.lastRoom.chatMembership,lease:peerProof.lastRoom.reservationUntil??null})')
  g.reload();recovery_proof=connected(h,g,'relay')
  assert g.evaluate('({member:peerProof.lastRoom.chatMembership,lease:peerProof.lastRoom.reservationUntil??null})')==lease_before
  assert g.evaluate('peerProof.policies.every(policy=>policy==="relay")')
  # A second pair still negotiates directly when the test TURN limit is occupied.
  capacity_host,capacity_invite=host(relay);capacity_guest=join(capacity_invite);capacity_proof=connected(capacity_host,capacity_guest,'direct')
  assert capacity_guest.evaluate('peerProof.lastRoom.peers[0].policy')=='standard'
  # Controlled probe loss after a failed link retains membership, then explicit Retry recovers.
  capacity_guest.wait_for_function("peerProof.lastRoom.slots.find(slot=>slot.member?.id===peerProof.lastRoom.chatMembership)?.member.acquisition==='loaded'")
  original=capacity_guest.evaluate('({id:peerProof.lastRoom.id,lease:peerProof.lastRoom.reservationUntil??null})')
  capacity_guest.evaluate('peerProof.pcs.at(-1).close()')
  capacity_guest.wait_for_function("peerProof.lastRoom?.peers[0]?.status==='failed'",timeout=10000)
  failed_slot=capacity_guest.evaluate("peerProof.lastRoom.slots.find(slot=>slot.member?.id===peerProof.lastRoom.peers[0].member).id")
  assert capacity_guest.locator(f'[data-slot-id="{failed_slot}"] .slot-state').inner_text()=='Connection failed'
  assert capacity_guest.locator('.rc-status').get_by_text('Connection failed. Retry connection.').is_visible()
  for tab in [capacity_host,capacity_guest]:tab.evaluate('window.suppressTransportProbe=true')
  capacity_guest.locator('.rc-status-action').click()
  for tab in [capacity_host,capacity_guest]:tab.wait_for_function("peerProof.lastRoom?.peers[0]?.status==='failed'",timeout=40000)
  observed_capacity=capacity_guest.evaluate('({id:peerProof.lastRoom.id,lease:peerProof.lastRoom.reservationUntil??null})')
  assert observed_capacity==original,(original,observed_capacity)
  assert capacity_guest.get_by_role('button',name='Back to Main Page',exact=True).is_visible()
  for tab in [capacity_host,capacity_guest]:tab.evaluate('window.suppressTransportProbe=false')
  capacity_guest.locator('.rc-status-action').click();retry_proof=connected(capacity_host,capacity_guest,'direct')
  # Exercise real coordinator wall-clock deadlines, without extending or accelerating them.
  # Suppress only preparation acknowledgement or Start delivery; answer a withheld request
  # locally so the unrelated 8-second client request timer cannot mask the server deadline.
  deadlines=[]
  for phase in ['preparing','connecting']:
   dh,di=host(direct);dg=page(di)
   for tab in [dh,dg]:tab.evaluate('(mode)=>window.deadlineMode=mode',phase)
   dg.get_by_role('button',name='Join lobby',exact=True).click();dg.locator('[data-page="lobby"]').wait_for()
   dg.wait_for_function("peerProof.lastRoom.slots.find(s=>s.member?.id===peerProof.lastRoom.chatMembership)?.member.acquisition==='loaded'")
   original=dg.evaluate('({id:peerProof.lastRoom.id,lease:peerProof.lastRoom.reservationUntil??null})')
   leases=[tab.evaluate('peerProof.lastRoom.reservationUntil??null') for tab in [dh,dg]]
   for tab in [dh,dg]:
    tab.wait_for_function("peerProof.lastRoom?.peers[0]?.status==='failed'",timeout=25000)
    elapsed=tab.evaluate("performance.now()-(window.deadlineMode==='preparing'?peerProof.preparedAt:peerProof.startedAt)")
    assert elapsed >= (14900 if phase=='preparing' else 19900), (phase,elapsed)
    observed=tab.evaluate('({status:peerProof.lastRoom.peers[0].status,id:peerProof.lastRoom.id,lease:peerProof.lastRoom.reservationUntil??null})')
    assert observed['status']=='failed' and observed['id']==original['id'] and observed.get('lease')==leases[[dh,dg].index(tab)],observed
    assert tab.locator('.rc-status-action').is_visible()
    assert tab.get_by_role('button',name='Back to Main Page',exact=True).is_visible()
   assert dg.evaluate('peerProof.lastRoom.reservationUntil??null')==original['lease']
   dg.screenshot(path=str(out.with_suffix(f'.{phase}-timeout.png')),full_page=True)
   for tab in [dh,dg]:tab.evaluate('window.deadlineMode=undefined')
   dg.locator('.rc-status-action').click();proof=connected(dh,dg,'direct')
   assert dg.evaluate('peerProof.lastRoom.reservationUntil??null')==original['lease']
   deadlines.append({'phase':phase,'both_received_failed_state':True,'retry_and_leave_visible':True,'original_room_and_lease_preserved':True,'retry_route':proof})
   dh.close();dg.close()
  assert not errors,errors
  result={'result':'pass','browser':browser.version,'seconds':round(time.monotonic()-started,2),'early_answerer_send_loss_model':{'connected':True,'answerer_waited_for_inbound_probe':True,'discarded_sends':0,'route':modeled_route},'direct':direct_proof,'forced_turn':relay_proof,'relay_reload_recovery':recovery_proof,'direct_with_relay_capacity_full':capacity_proof,'retry_after_peer_failure':retry_proof,'automatic_policy_before_gathering':True,'reservation_lease_unchanged':True,'stay_preserves_room_and_lease':True,'invite_discloses_source_before_any_peer':True,'scope':'Loopback coturn and local browser tabs; public network/provider load qualification remains D21/D24.','server_deadlines':deadlines,'page_errors':errors}
  out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));browser.close()
finally:
 for proc in reversed(processes):
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
