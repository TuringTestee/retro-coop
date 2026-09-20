"""Local direct and authenticated coturn route evidence; not public-network qualification."""
import argparse, json, os, subprocess, time
from fixture import LocalTurn
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser()
parser.add_argument('--chrome',action='store_true');parser.add_argument('--turnserver',default='turnserver');parser.add_argument('--output',default='peer.local.json')
args=parser.parse_args();root=Path(__file__).resolve().parents[2];out=Path(args.output);started=time.monotonic()
rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
processes=[]
def service(extra):
 env={**os.environ,**extra};proc=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env=env,stdout=subprocess.PIPE,text=True);processes.append(proc)
 line=proc.stdout.readline();assert line, 'coordinator gateway did not start';return json.loads(line)['url']
try:
 with LocalTurn(args.turnserver) as turn, sync_playwright() as p:
  browser=p.chromium.launch(ignore_default_args=['--mute-audio'],**({'channel':'chrome'} if args.chrome else {}))
  errors=[]
  def page(url):
   page=browser.new_page(viewport={'width':1280,'height':1050});page.on('pageerror',lambda error:errors.append(str(error)))
   page.add_init_script((root/'scripts/peer/diagnostics.js').read_text()+'''window.peerProof={pcs:[],started:false,gatherBeforeStart:false,policies:[],sentCandidates:[],errors:[],ice:[]};
    const NativeSocket=WebSocket;window.WebSocket=class extends NativeSocket{
     set onmessage(fn){this.deliver=fn;super.onmessage=e=>{const d=JSON.parse(e.data);if(d.type==='room')peerProof.lastRoom=d.room;if(d.type==='peerStart'&&window.deadlineMode==='connecting')return;if(d.type==='result'&&!d.ok)peerProof.errors.push(d.error);if(d.type==='peerPrepare'){peerProof.started=false;if(window.lowerPolicy){d.policy='standard';e=new MessageEvent('message',{data:JSON.stringify(d)})}};if(d.type==='peerStart')peerProof.started=true;fn(e)}}
     send(raw){const d=JSON.parse(raw);if(d.type==='peerAck'&&window.deadlineMode==='preparing'){queueMicrotask(()=>this.deliver(new MessageEvent('message',{data:JSON.stringify({type:'result',requestId:d.requestId,ok:true,data:{}})})));return;}if(d.type==='peerSignal'&&d.signal.kind==='candidate')peerProof.sentCandidates.push(d.signal.candidate.candidate);super.send(raw)}
    };
    const NativePeer=RTCPeerConnection;window.RTCPeerConnection=class extends NativePeer{
     constructor(c){super(c);peerProof.pcs.push(this);peerProof.policies.push(c.iceTransportPolicy);this.addEventListener('icecandidateerror',e=>peerProof.ice.push({error:e.errorCode}));this.addEventListener('iceconnectionstatechange',()=>peerProof.ice.push({state:this.iceConnectionState}));this.addEventListener('icecandidate',e=>{if(e.candidate)peerProof.ice.push({candidate:e.candidate.type})})}
     setLocalDescription(d){if(!peerProof.started)peerProof.gatherBeforeStart=true;return super.setLocalDescription(d)}
    };''');page.goto(url);return page
  def host(url,policy='standard'):
   h=page(url);h.screenshot(path=str(out.with_suffix('.before.png')),full_page=True);h.locator('.room-panel').get_by_label('Connection privacy',exact=True).select_option(policy)
   h.set_input_files('input[type=file]',{'name':'PRIVATE-PEER.nes','mimeType':'application/octet-stream','buffer':rom});h.get_by_test_id('room-view').wait_for()
   return h,h.get_by_label('Room invitation',exact=True).input_value()
  def join(invite,policy='standard'):
   g=page(invite);g.locator('.room-panel').get_by_label('Connection privacy',exact=True).select_option(policy);assert g.evaluate('peerProof.pcs.length')==0;g.get_by_text('Host-provided title. Bring your own matching local game file.',exact=False).wait_for();g.get_by_role('button',name='Retry join / Join',exact=True).click();g.get_by_test_id('room-view').wait_for();return g
  def connected(h,g,route):
   try:
    for tab in [h,g]:tab.wait_for_function("r=>document.querySelector('[data-testid=connection-status]').textContent.includes('Route: '+r)",arg=route,timeout=25000)
   except Exception:
    failure={'connection_failure':[tab.evaluate("({status:document.querySelector('[data-testid=connection-status]').textContent,states:peerProof.pcs.map(pc=>pc.connectionState),errors:peerProof.errors,ice:peerProof.ice,...peerDiagnostics()})") for tab in [h,g]],
     'turn_error_codes':turn.error_codes()}
    out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True)
    raise
   result=[]
   for tab in [h,g]:
    data=tab.evaluate('''async()=>{const pc=peerProof.pcs.at(-1),stats=await pc.getStats();let selected;
     stats.forEach(s=>{if(s.type==='transport'&&s.selectedCandidatePairId){const pair=stats.get(s.selectedCandidatePairId);selected={local:stats.get(pair.localCandidateId).candidateType,remote:stats.get(pair.remoteCandidateId).candidateType,bytesSent:pair.bytesSent,bytesReceived:pair.bytesReceived}}});
     return {...selected,policy:pc.getConfiguration().iceTransportPolicy,gatherBeforeStart:peerProof.gatherBeforeStart,relayCandidatesOnly:peerProof.sentCandidates.every(c=>c.includes(' typ relay '))};}''')
    assert not data['gatherBeforeStart'];assert data['bytesSent']>0 and data['bytesReceived']>0
    if route=='relay':assert data['local']=='relay' and data['remote']=='relay' and data['policy']=='relay'
    result.append(data)
   assert 'Player 2 (reserved)' in g.get_by_test_id('room-view').inner_text()
   return result
  direct=service({'TURN_URLS':'','TURN_SECRET':''});h,invite=host(direct);g=join(invite)
  direct_proof=connected(h,g,'direct');h.screenshot(path=str(out.with_suffix('.direct.png')),full_page=True)
  # Changing either participant to stricter policy tears down direct, and unavailable relay never falls back.
  g.locator('.room-panel').get_by_label('Connection privacy',exact=True).select_option('relay')
  h.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('Relay service is unavailable')")
  assert h.evaluate("peerProof.pcs.every(pc=>pc.connectionState==='closed')")
  before=g.evaluate('peerProof.pcs.length');g.get_by_role('button',name='Retry connection',exact=True).click()
  assert g.evaluate('peerProof.pcs.length')==before
  lease=g.get_by_test_id('room-view').inner_text();g.get_by_role('button',name='Stay in room',exact=True).click()
  assert g.get_by_test_id('room-view').inner_text()==lease and g.evaluate('peerProof.pcs.length')==before
  g.get_by_text('You stayed in the room.',exact=False).wait_for()
  g.screenshot(path=str(out.with_suffix('.unavailable.png')),full_page=True);h.close();g.close()
  relay=service(turn.environment())
  h,invite=host(relay);g=join(invite,'relay');relay_proof=connected(h,g,'relay')
  for tab in [h,g]:assert tab.evaluate('peerProof.sentCandidates.every(c=>c.includes(" typ relay "))')
  h.screenshot(path=str(out.with_suffix('.relay.png')),full_page=True)
  h.set_viewport_size({'width':390,'height':844});assert h.evaluate('document.documentElement.scrollWidth<=innerWidth');h.screenshot(path=str(out.with_suffix('.mobile.png')),full_page=True);h.set_viewport_size({'width':1280,'height':1050})
  lease_before=g.get_by_test_id('room-view').inner_text().split('Reservation expires at ')[1].split('.')[0]
  g.reload();recovery_proof=connected(h,g,'relay')
  assert g.locator('.room-panel').get_by_label('Connection privacy',exact=True).input_value()=='relay'
  assert lease_before in g.get_by_test_id('room-view').inner_text()
  assert g.evaluate('peerProof.policies.every(policy=>policy==="relay")')
  # Server admission denies a second relay pair before creating any RTCPeerConnection.
  denied,denied_invite=host(relay,'relay');waiting=page(relay)
  code=denied.get_by_test_id('room-view').locator('strong').inner_text().split(' · ')[1]
  waiting.locator('.directory-panel').get_by_label('Connection privacy',exact=True).select_option('standard')
  waiting.locator('.room-list li').filter(has_text=code).get_by_role('button',name='Join room',exact=True).click();waiting.get_by_test_id('room-view').wait_for()
  denied.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('Relay capacity is full')")
  assert denied.evaluate('peerProof.pcs.length')==0 and waiting.evaluate('peerProof.pcs.length')==0
  denied.screenshot(path=str(out.with_suffix('.capacity.png')),full_page=True)
  # Explicit cancellation frees capacity; retry retains the original reservation.
  lease=waiting.get_by_test_id('room-view').inner_text().split('Reservation expires at ')[1].split('.')[0]
  g.get_by_role('button',name='Cancel join',exact=True).click();g.get_by_test_id('room-view').wait_for(state='detached')
  waiting.get_by_role('button',name='Retry connection',exact=True).click();retry_proof=connected(denied,waiting,'relay')
  assert lease in waiting.get_by_test_id('room-view').inner_text()
  # A local choice change reconnects even if the other player's stricter policy remains effective.
  waiting.locator('.room-panel').get_by_label('Connection privacy',exact=True).select_option('relay')
  connected(denied,waiting,'relay')
  denied.locator('.room-panel').get_by_label('Connection privacy',exact=True).select_option('standard')
  connected(denied,waiting,'relay')
  # Settings reflects and changes the same privacy owner; shared gameplay is never promoted.
  denied.get_by_role('button',name='Settings',exact=True).click();assert denied.get_by_role('dialog').get_by_label('Connection privacy',exact=True).input_value()=='standard'
  denied.get_by_role('dialog').get_by_label('Connection privacy',exact=True).select_option('relay')
  connected(denied,waiting,'relay')
  assert denied.locator('.room-panel').get_by_label('Connection privacy',exact=True).input_value()=='relay'
  assert 'Paused' in denied.get_by_test_id('player-status').inner_text()
  denied.get_by_role('dialog').get_by_label('Connection privacy',exact=True).scroll_into_view_if_needed()
  denied.screenshot(path=str(out.with_suffix('.settings.png')),full_page=True)
  waiting.get_by_role('button',name='Cancel join',exact=True).click();waiting.get_by_test_id('room-view').wait_for(state='detached')
  guard=page(invite);guard.locator('.room-panel').get_by_label('Connection privacy',exact=True).select_option('relay');guard.evaluate('window.lowerPolicy=true')
  guard.get_by_role('button',name='Retry join / Join',exact=True).click()
  guard.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('failed')")
  assert guard.evaluate('peerProof.pcs.length')==0
  # Exercise real coordinator wall-clock deadlines, without extending or accelerating them.
  # Suppress only preparation acknowledgement or Start delivery; answer a withheld request
  # locally so the unrelated 8-second client request timer cannot mask the server deadline.
  deadlines=[]
  for phase in ['preparing','connecting']:
   dh,di=host(direct);dg=page(di)
   for tab in [dh,dg]:tab.evaluate('(mode)=>window.deadlineMode=mode',phase)
   dg.get_by_role('button',name='Retry join / Join',exact=True).click();dg.get_by_test_id('room-view').wait_for()
   original=dg.evaluate('({id:peerProof.lastRoom.id,lease:peerProof.lastRoom.reservationUntil})')
   for tab in [dh,dg]:
    tab.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('timed out')",timeout=25000)
    observed=tab.evaluate('({status:peerProof.lastRoom.peer.status,id:peerProof.lastRoom.id,lease:peerProof.lastRoom.reservationUntil})')
    assert observed=={'status':'failed',**original},observed
    assert tab.get_by_role('button',name='Retry connection',exact=True).count()==1
    assert tab.get_by_role('button',name='Stay in room',exact=True).count()==1
   dg.get_by_role('button',name='Stay in room',exact=True).click()
   assert dg.evaluate('peerProof.lastRoom.reservationUntil')==original['lease']
   dg.screenshot(path=str(out.with_suffix(f'.{phase}-timeout.png')),full_page=True)
   for tab in [dh,dg]:tab.evaluate('window.deadlineMode=undefined')
   dg.get_by_role('button',name='Retry connection',exact=True).click();proof=connected(dh,dg,'direct')
   assert dg.evaluate('peerProof.lastRoom.reservationUntil')==original['lease']
   deadlines.append({'phase':phase,'both_received_failed_state':True,'stay_and_retry_visible':True,'original_room_and_lease_preserved':True,'retry_route':proof})
   dh.close();dg.close()
  assert not errors,errors
  result={'result':'pass','browser':browser.version,'seconds':round(time.monotonic()-started,2),'direct':direct_proof,'forced_turn':relay_proof,'relay_reload_recovery':recovery_proof,'retry_after_capacity':retry_proof,'stricter_policy_before_gathering':True,'relay_unavailable_no_fallback':True,'capacity_denial_before_peer_creation':True,'reservation_lease_unchanged':True,'settings_same_policy':True,'stay_preserves_room_and_lease':True,'invite_discloses_source_before_any_peer':True,'public_code_join_same_policy':True,'client_rejects_policy_downgrade_before_peer_creation':True,'scope':'Loopback coturn and local browser tabs; public network/provider load qualification remains D21/D24.','server_deadlines':deadlines,'page_errors':errors}
  out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));browser.close()
finally:
 for proc in reversed(processes):
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
