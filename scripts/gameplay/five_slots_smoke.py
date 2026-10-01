"""Five real members through the public lobby; native state proves local observation."""
import argparse,contextlib,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--relay',action='store_true');parser.add_argument('--initial-stall',action='store_true');parser.add_argument('--turnserver',default='turnserver');parser.add_argument('--output',default='/tmp/five-slots.json');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);started=time.monotonic();sys.path.insert(0,str(root/'scripts/peer'))
from fixture import LocalTurn
static=Path(os.environ.get('RETRO_COOP_STATIC_ROOT',root/'apps/client/dist'))
provenance={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'build':{str(path.relative_to(static)):hashlib.sha256(path.read_bytes()).hexdigest() for path in static.rglob('*') if path.is_file() and path.suffix in ['.html','.js','.wasm']}}
with contextlib.ExitStack() as stack:
 turn=stack.enter_context(LocalTurn(args.turnserver)) if args.relay else None
 env={**os.environ,**(turn.environment() if turn else {'TURN_URLS':'','TURN_SECRET':''})}
 if turn:env['TURN_PAIR_LIMIT']='10'
 server=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env=env,stdout=subprocess.PIPE,text=True)
 stack.callback(server.wait);stack.callback(server.terminate)
 url=json.loads(server.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes();errors=[];pages=[];geometry={}
 p=stack.enter_context(sync_playwright())
 if True:
  browsers=[p.chromium.launch(ignore_default_args=['--mute-audio']) for _ in range(3)]
  for browser in browsers:stack.callback(browser.close)
  # Two tabs share one browser context/origin; others use separate processes.
  contexts=[browsers[0].new_context(viewport={'width':1440,'height':1100}),browsers[1].new_context(viewport={'width':1440,'height':1100}),browsers[2].new_context(viewport={'width':1440,'height':1100})]
  for index in range(5):
   page=contexts[0 if index<2 else 1 if index<4 else 2].new_page();page.set_default_timeout(20000);page.add_init_script(path=root/'scripts/gameplay/fixture.js')
   if args.relay:page.add_init_script("window.forceRelayTransport=true")
   # Preserve the transfer header so delayed packets remain attributable to the failed attempt.
   page.add_init_script("const sendCheckpoint=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(window.holdCheckpoint&&this.label==='retro-coop-checkpoint'&&typeof data!=='string')return;if(window.corruptRoleCheckpoint&&this.label==='retro-coop-checkpoint'&&data instanceof ArrayBuffer){const bad=data.slice(0),bytes=new Uint8Array(bad);bytes[bytes.length-1]^=1;window.corruptRoleChunks=(window.corruptRoleChunks??0)+1;return sendCheckpoint.call(this,bad)}return sendCheckpoint.call(this,data)};window.gamePeers=[];const Base=RTCPeerConnection;window.RTCPeerConnection=class extends Base{constructor(...args){super(window.forceRelayTransport?{...(args[0]??{}),iceTransportPolicy:'relay'}:args[0],...args.slice(1));gamePeers.push(this);this.addEventListener('icecandidateerror',event=>{(window.iceErrors??=[]).push({code:event.errorCode,text:event.errorText})})}}")
   page.add_init_script("window.slotEvidence={events:[],imports:[],errors:[],wireerrors:[]};const Socket=WebSocket;window.WebSocket=class extends Socket{constructor(...a){super(...a);this.addEventListener('message',({data})=>{const event=JSON.parse(data);if(event.type.startsWith('game'))slotEvidence.events.push(event);if(event.type==='error')slotEvidence.wireerrors.push(event);})}};const Core=Worker;window.Worker=class extends Core{constructor(...a){super(...a);this.addEventListener('message',({data})=>{if(data.type==='peer-checkpoint-imported')slotEvidence.imports.push(data);if(data.type.includes('error'))slotEvidence.errors.push(data);})}}")
   page.on('pageerror',lambda error:errors.append(str(error)));pages.append(page)
  def boxes(page,label):
   value=page.evaluate("""()=>{const root=document.querySelector('.room-slots'),origin=root.getBoundingClientRect();return [...root.querySelectorAll('[data-slot-id]')].map(row=>{const r=row.getBoundingClientRect();return {id:row.dataset.slotId,x:r.x-origin.x,y:r.y-origin.y,width:r.width,height:r.height,regions:[...row.querySelectorAll('[data-slot-region]')].map(region=>{const b=region.getBoundingClientRect();return {name:region.dataset.slotRegion,x:b.x-r.x,y:b.y-r.y,width:b.width,height:b.height}})}})}""")
   assert len(value)==5,value
   for previous in geometry.values():
    if previous[0]['width']==value[0]['width'] and previous[0]['height']==value[0]['height']:assert previous==value,(label,previous,value)
   geometry[label]=value
  def manage(slot):
   if not host.locator('.room-slots').count():host.get_by_role('button',name='Players',exact=True).click()
   return host.locator(f'[data-slot-id=slot-{slot}] [data-slot-action]')
  def role(slot,value):
   manage(slot).select_option(f'role:{value}')
  def remove(slot):
   manage(slot).select_option('kick')
   host.get_by_role('button',name='Kick member',exact=True).click()
  def state(page):return page.evaluate("({room:proof.room,status:document.querySelector('[data-testid=game-status]')?.textContent,evidence:slotEvidence,iceErrors:window.iceErrors})")
  def native(page):return page.evaluate("""()=>new Promise((resolve,reject)=>{const requestId=window.nativeRequest=(window.nativeRequest??800000)+1;const timer=setTimeout(()=>reject(Error('native hash timed out')),3000);function done({data}){if(data.requestId!==requestId)return;clearTimeout(timer);currentWorker.removeEventListener('message',done);if(data.type==='error')reject(Error(data.message));else resolve(data.info);}currentWorker.addEventListener('message',done);currentWorker.postMessage({type:'state-hash',requestId});})""")
  def resume_host():
   if host.evaluate("proof.room.game.status")!='resume_ready':
    try:host.get_by_role('button',name='Ready to resume',exact=True).click(timeout=3000)
    except PlaywrightTimeoutError:
     assert host.evaluate("proof.room.game.status")=='resume_ready',state(host)
   host.get_by_role('button',name='Resume together',exact=True).click()
  try:
   host=pages[0];host.goto(url);host.get_by_role('button',name='Create game',exact=True).click();host.set_input_files('input[type=file]',{'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});host.get_by_role('button',name='Create room',exact=True).click();host.get_by_role('button',name='Copy invite',exact=True).wait_for();invite=host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite");boxes(host,'waiting')
   for page in pages[1:]:
    page.goto(invite);page.get_by_role('button',name='Join room',exact=True).click();page.wait_for_function("proof.room?.matches&&proof.room.slots.find(slot=>slot.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'",polling=50)
   for page in pages:
    page.wait_for_function("proof.room?.occupancy===5&&proof.room.peers.length===4&&proof.room.peers.every(peer=>peer.status==='connected')",polling=50)
    assert page.get_by_test_id('room-slot').count()==5
   host.screenshot(path=str(out.with_suffix('.waiting-desktop.png')),full_page=True)
   host.set_viewport_size({'width':390,'height':800})
   host.screenshot(path=str(out.with_suffix('.waiting-mobile.png')),full_page=True)
   host.locator('.room-panel').evaluate('node=>node.scrollTop=node.scrollHeight')
   host.screenshot(path=str(out.with_suffix('.waiting-mobile-actions.png')),full_page=True)
   host.set_viewport_size({'width':1440,'height':1100})
   routes=[page.evaluate("async()=>Promise.all(gamePeers.map(async pc=>{const report=await pc.getStats();const transport=[...report.values()].find(v=>v.type==='transport'&&v.selectedCandidatePairId);const pair=transport&&report.get(transport.selectedCandidatePairId);return {state:pc.connectionState,local:pair&&report.get(pair.localCandidateId)?.candidateType,remote:pair&&report.get(pair.remoteCandidateId)?.candidateType}}))") for page in pages]
   assert all(len(values)==4 for values in routes),routes
   if args.relay:assert all(value['local']=='relay' and value['remote']=='relay' for values in routes for value in values),routes
   boxes(host,'full')
   for page in pages:page.locator('details.chat-disclosure summary').click()
   for index,page in enumerate(pages):
    page.get_by_label('Chat message',exact=True).fill(f'Member {index+1} connected');page.get_by_role('button',name='Send message',exact=True).click()
   for page in pages:
    for index in range(5):page.get_by_role('log',name='Room messages').get_by_text(f'Member {index+1} connected',exact=True).wait_for()
   members=[page.evaluate('proof.room.chatMembership') for page in pages];assert len(set(members))==5
   if args.initial_stall:pages[1].evaluate("window.gameFault='drop-input'")
   for page in pages:
    page.get_by_role('button',name='Ready',exact=True).click()
    page.wait_for_function('proof.room.game.ready.includes(proof.room.chatMembership)',polling=20)
   host.screenshot(path=str(out.with_suffix('.everyone-ready.png')),full_page=True)
   host.get_by_role('button',name='Start game',exact=True).click()
   for page in pages:page.evaluate('releaseFrames()')
   if args.initial_stall:
    host.wait_for_function("proof.room.game.status==='paused'",polling=20)
    boundary=native(host);assert boundary['frame']==0,boundary
    remove(2)
    host.wait_for_function('!proof.room.slots[1].member',polling=20)
    role(3,'player2')
    host.wait_for_function("proof.room.game.status==='playing'&&proof.room.game.controllers.owners[1]===proof.room.slots[2].member.id",polling=20)
    starts=host.evaluate("slotEvidence.events.filter(event=>event.type==='gameStart')");assert starts[-1]['frame']==0 and starts[-1]['hash']==boundary['hash']
    imports=pages[2].evaluate('slotEvidence.imports');assert any(item['frame']==0 and item['hash']==boundary['hash'] for item in imports)
    host.wait_for_function('proof.frames.at(-1)?.frame>=120',polling=20)
    host.get_by_role('button',name='Pause',exact=True).click();remaining=[page for index,page in enumerate(pages) if index!=1]
    for page in remaining:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
    deadline=time.monotonic()+5
    while True:
     states=[native(page) for page in remaining]
     if all(value==states[0] for value in states):break
     assert time.monotonic()<deadline,states
     time.sleep(.05)
    host.screenshot(path=str(out.with_suffix('.poweron.png')))
    result={'result':'pass','source':provenance,'selected_routes':routes,'initial_stall':True,'boundary':boundary,'native_states':states,'errors':errors,'elapsed':round(time.monotonic()-started,2)};assert not errors,errors;out.write_text(json.dumps(result,indent=2));print(json.dumps({key:value for key,value in result.items() if key not in ['events','slot_geometry','source']}));sys.exit(0)
   for page in pages[:2]:page.wait_for_function("proof.room.game.status==='playing'",polling=20)
   for page in pages[2:]:page.wait_for_function('proof.frames.at(-1)?.frame>=10', polling=20)
   host.wait_for_function('proof.frames.at(-1)?.frame>=240',polling=20)
   # Observer reconnect retains its slot and never pauses the active owners.
   observer_member=members[4];epoch_before=host.evaluate('proof.room.game.epoch')
   pages[4].reload();pages[4].evaluate('releaseFrames()')
   pages[4].wait_for_function('member=>proof.room?.chatMembership===member',arg=observer_member,polling=20)
   pages[4].wait_for_function('proof.frames.at(-1)?.frame>=10',polling=20)
   assert host.evaluate("proof.room.game.status==='playing'&&proof.room.game.epoch") == epoch_before
   host.get_by_role('button',name='Pause',exact=True).click()
   for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    states=[native(page) for page in pages]
    if all(value==states[0] for value in states):break
    assert time.monotonic()<deadline,states
    time.sleep(.05)
   initial=states;host.get_by_role('button',name='Players',exact=True).click();boxes(host,'playing-paused')
   host.screenshot(path=str(out.with_suffix('.five.png')))
   # Host administration is independent of controller ownership.
   role(1,'observer')
   host.wait_for_function("proof.room.slots[0].role==='observer'&&proof.room.game.status==='playing'",polling=20)
   host.wait_for_function('start=>proof.frames.at(-1)?.frame>start+120',arg=initial[0]['frame'],polling=20)
   host.get_by_role('button',name='Pause',exact=True).click()
   for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    states=[native(page) for page in pages]
    if all(value==states[0] for value in states):break
    assert time.monotonic()<deadline,states
    time.sleep(.05)
   host_observer=states;boxes(host,'host-observer')
   host.screenshot(path=str(out.with_suffix('.host-observer.png')))
   # Promoting an observer atomically swaps the occupied Player 2 role.
   role(3,'player2')
   host.wait_for_function("proof.room.slots[2].role==='player2'&&proof.room.slots[1].role==='observer'&&proof.room.game.status==='playing'",polling=20)
   host.wait_for_function('start=>proof.frames.at(-1)?.frame>start+120',arg=host_observer[0]['frame'],polling=20)
   host.get_by_role('button',name='Pause',exact=True).click()
   for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    states=[native(page) for page in pages]
    if all(value==states[0] for value in states):break
    assert time.monotonic()<deadline,states
    time.sleep(.05)
   promotion=states
   evidence=[page.evaluate('slotEvidence') for page in pages]
   for boundary in [initial[0],host_observer[0]]:
    starts=[event for event in evidence[0]['events'] if event['type']=='gameStart' and event['frame']==boundary['frame']]
    assert starts and starts[-1]['hash']==boundary['hash'],(boundary,starts)
   assert any(item['frame']==host_observer[0]['frame'] and item['hash']==host_observer[0]['hash'] for item in evidence[2]['imports'])

   # A departed owner cannot supply another frame or acknowledgement. Freeze the
   # reachable completed boundary, then replace that owner from an observer slot.
   pages[2].get_by_role('button',name='Ready to resume',exact=True).click()
   host.get_by_role('button',name='Ready to resume',exact=True).click()
   host.get_by_role('button',name='Resume together',exact=True).click()
   host.wait_for_function("proof.room.game.status==='playing'",polling=20)
   pages[2].evaluate("window.gameFault='drop-input'")
   host.wait_for_function("proof.room.game.status==='paused'",polling=20)
   stalled=native(host)
   remove(3)
   host.wait_for_function('!proof.room.slots[2].member',polling=20)
   assert native(host)==stalled
   role(4,'player2')
   host.wait_for_function("proof.room.game.status==='playing'&&proof.room.game.controllers.owners[1]===proof.room.slots[3].member.id",polling=20)
   starts=host.evaluate("slotEvidence.events.filter(event=>event.type==='gameStart')")
   assert starts[-1]['frame']==stalled['frame'] and starts[-1]['hash']==stalled['hash'],(stalled,starts[-1])
   imports=pages[3].evaluate('slotEvidence.imports')
   assert any(item['frame']==stalled['frame'] and item['hash']==stalled['hash'] for item in imports)
   host.wait_for_function('start=>proof.frames.at(-1)?.frame>start+120',arg=stalled['frame'],polling=20)
   host.get_by_role('button',name='Pause',exact=True).click()
   remaining=[page for index,page in enumerate(pages) if index!=2]
   for page in remaining:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    replacement=[native(page) for page in remaining]
    if all(value==replacement[0] for value in replacement):break
    assert time.monotonic()<deadline,replacement
    time.sleep(.05)
   host.screenshot(path=str(out.with_suffix('.replacement.png')))
   host.evaluate('window.holdCheckpoint=true')
   role(5,'player2')
   host.wait_for_function("proof.room.game.pending?.status==='synchronizing'",polling=20)
   manage(5).select_option('cancel')
   host.wait_for_function("!proof.room.game.pending&&proof.room.slots[3].role==='player2'&&proof.room.slots[4].role==='observer'&&proof.room.game.status==='paused'",polling=20)
   boxes(host,'cancelled');cancelled=[native(page) for page in remaining]
   assert all(value==replacement[0] for value in cancelled),(replacement,cancelled)
   host.screenshot(path=str(out.with_suffix('.cancelled.png')))
   host.evaluate('window.holdCheckpoint=false;window.corruptRoleCheckpoint=true')
   role(5,'player2')
   host.wait_for_function("proof.room.game.pending?.status==='failed'",polling=20)
   failed=host.evaluate("""()=>{const box=selector=>{const node=document.querySelector(selector),rect=node?.getBoundingClientRect();return rect&&{top:rect.top,bottom:rect.bottom,height:rect.height,scrollHeight:node.scrollHeight,clientHeight:node.clientHeight}};return {transaction:proof.room.game.pending,owners:proof.room.game.controllers.owners,roles:proof.room.slots.map(slot=>slot.role),corruptChunks:window.corruptRoleChunks,geometry:{gameActions:box('.shared-gameplay-actions'),details:box('.room-detail-scroll'),slots:box('.room-slots'),feedback:box('.slot-feedback')}}}""")
   assert failed['corruptChunks']>0 and failed['roles'][3]=='player2' and failed['roles'][4]=='observer',failed
   assert failed['owners'][1]==host.evaluate('proof.room.slots[3].member.id'),failed
   assert native(host)==replacement[0],(failed,replacement[0])
   assert failed['geometry']['details']['top']>=failed['geometry']['gameActions']['bottom'],failed['geometry']
   assert failed['geometry']['feedback']['scrollHeight']<=failed['geometry']['feedback']['clientHeight'],failed['geometry']
   manage(5).locator('option[value="retry"]').wait_for(state='attached')
   assert manage(5).locator('option[value="retry"]').is_enabled()
   assert 'Role change failed' in host.locator('[data-slot-id=slot-5] [data-slot-region=status]').inner_text()
   host.locator('.slot-feedback').scroll_into_view_if_needed()
   host.screenshot(path=str(out.with_suffix('.role-failed.png')))
   host.evaluate('window.corruptRoleCheckpoint=false')
   manage(5).select_option('retry')
   host.wait_for_function("proof.room.game.status==='playing'&&proof.room.game.controllers.owners[1]===proof.room.slots[4].member.id",polling=20)
   retry_start=host.evaluate("slotEvidence.events.filter(event=>event.type==='gameStart').at(-1)")
   assert retry_start['frame']==replacement[0]['frame'] and retry_start['hash']==replacement[0]['hash'],(replacement[0],retry_start)
   assert any(item['frame']==replacement[0]['frame'] and item['hash']==replacement[0]['hash'] for item in pages[4].evaluate('slotEvidence.imports'))
   host.wait_for_function('start=>proof.frames.at(-1)?.frame>start+120',arg=replacement[0]['frame'],polling=20)
   host.get_by_role('button',name='Pause',exact=True).click()
   for page in remaining:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    retried=[native(page) for page in remaining]
    if all(value==retried[0] for value in retried):break
    assert time.monotonic()<deadline,retried
    time.sleep(.05)
   host.locator('[data-slot-id=slot-5]').scroll_into_view_if_needed()
   host.screenshot(path=str(out.with_suffix('.role-retried.png')))
   # An active owner's reload preserves membership, pauses authority, and imports
   # its current state before the same owner resumes.
   pages[4].get_by_role('button',name='Ready to resume',exact=True).click();resume_host()
   host.wait_for_function("proof.room.game.status==='playing'",polling=20)
   pages[4].reload();pages[4].evaluate('releaseFrames()')
   host.wait_for_function("proof.room.game.status==='paused'",polling=20)
   pages[4].wait_for_function('member=>proof.room?.chatMembership===member&&proof.room.matches&&proof.room.peers.every(peer=>peer.status==="connected")',arg=members[4],polling=20)
   reconnect_boundary=native(host)
   pages[4].get_by_role('button',name='Ready to resume',exact=True).click();resume_host()
   host.wait_for_function('start=>proof.frames.at(-1)?.frame>start+120',arg=reconnect_boundary['frame'],polling=20)
   assert any(item['frame']==reconnect_boundary['frame'] and item['hash']==reconnect_boundary['hash'] for item in pages[4].evaluate('slotEvidence.imports'))
   host.get_by_role('button',name='Pause',exact=True).click()
   for page in remaining:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    reconnected=[native(page) for page in remaining]
    if all(value==reconnected[0] for value in reconnected):break
    assert time.monotonic()<deadline,reconnected
    time.sleep(.05)
   evidence=[page.evaluate('slotEvidence') for page in pages]
   host.get_by_role('button',name='Leave room',exact=True).click();host.get_by_role('button',name='Confirm leave',exact=True).click()
   for page in remaining:page.wait_for_function("gamePeers.every(pc=>pc.connectionState==='closed')",polling=20)
   if turn:
    deadline=time.monotonic()+5
    while turn.allocation_counts()['live_allocations'] and time.monotonic()<deadline:time.sleep(.05)
    assert turn.allocation_counts()['peak_live_allocations']<=32,turn.allocation_counts()
    assert turn.error_codes().get('486',0)==0,turn.error_codes()
   result={'result':'pass','source':provenance,'selected_routes':routes,'members':5,'native_states':states,'initial':initial,'host_observer':host_observer,'promotion':promotion,'stalled':stalled,'replacement':replacement,'cancelled':cancelled,'failed':failed,'retry_start':retry_start,'retried':retried,'reconnect_boundary':reconnect_boundary,'reconnected':reconnected,'events':evidence,'slot_geometry':geometry,'turn_allocations':turn.allocation_counts() if turn else None,'turn_error_codes':turn.error_codes() if turn else {},'all_member_chat':True,'same_origin_tabs':True,'browser_processes':3,'errors':errors,'elapsed':round(time.monotonic()-started,2)};assert not errors,errors;out.write_text(json.dumps(result,indent=2));print(json.dumps({key:value for key,value in result.items() if key not in ['events','slot_geometry','source']}))
  except Exception:
   for index,page in enumerate(pages):
    try:out.with_suffix(f'.member{index}.json').write_text(json.dumps(state(page),indent=2));page.screenshot(path=str(out.with_suffix(f'.member{index}.png')))
    except Exception:pass
   out.with_suffix('.errors.json').write_text(json.dumps({'page_errors':errors,'turn_error_codes':turn.error_codes() if turn else {},'turn_allocations':turn.allocation_counts() if turn else None}));raise
