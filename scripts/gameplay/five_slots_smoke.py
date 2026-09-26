"""Five real members through the public lobby; native state proves local observation."""
import argparse,contextlib,json,os,subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--relay',action='store_true');parser.add_argument('--initial-stall',action='store_true');parser.add_argument('--turnserver',default='turnserver');parser.add_argument('--output',default='/tmp/five-slots.json');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];out=Path(args.output);started=time.monotonic();sys.path.insert(0,str(root/'scripts/peer'))
from fixture import LocalTurn
with contextlib.ExitStack() as stack:
 turn=stack.enter_context(LocalTurn(args.turnserver)) if args.relay else None
 env={**os.environ,**(turn.environment() if turn else {'TURN_URLS':'','TURN_SECRET':''})}
 if turn:env['TURN_PAIR_LIMIT']='10'
 server=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env=env,stdout=subprocess.PIPE,text=True)
 stack.callback(server.wait);stack.callback(server.terminate)
 url=json.loads(server.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes();errors=[];pages=[]
 p=stack.enter_context(sync_playwright())
 if True:
  browsers=[p.chromium.launch(ignore_default_args=['--mute-audio']) for _ in range(3)]
  for browser in browsers:stack.callback(browser.close)
  # Two tabs share one browser context/origin; others use separate processes.
  contexts=[browsers[0].new_context(viewport={'width':1440,'height':1100}),browsers[1].new_context(viewport={'width':1440,'height':1100}),browsers[2].new_context(viewport={'width':1440,'height':1100})]
  for index in range(5):
   page=contexts[0 if index<2 else 1 if index<4 else 2].new_page();page.set_default_timeout(20000);page.add_init_script(path=root/'scripts/gameplay/fixture.js')
   page.add_init_script("const sendCheckpoint=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(window.holdCheckpoint&&this.label==='retro-coop-checkpoint'&&typeof data!=='string')return;return sendCheckpoint.call(this,data)};window.gamePeers=[];const Base=RTCPeerConnection;window.RTCPeerConnection=class extends Base{constructor(...args){super(...args);gamePeers.push(this)}}")
   if args.relay:page.add_init_script("sessionStorage.setItem('retro-coop-connection-policy','relay')")
   page.add_init_script("window.slotEvidence={events:[],imports:[],errors:[],wireerrors:[]};const Socket=WebSocket;window.WebSocket=class extends Socket{constructor(...a){super(...a);this.addEventListener('message',({data})=>{const event=JSON.parse(data);if(event.type.startsWith('game'))slotEvidence.events.push(event);if(event.type==='error')slotEvidence.wireerrors.push(event);})}};const Core=Worker;window.Worker=class extends Core{constructor(...a){super(...a);this.addEventListener('message',({data})=>{if(data.type==='peer-checkpoint-imported')slotEvidence.imports.push(data);if(data.type.includes('error'))slotEvidence.errors.push(data);})}}")
   page.on('pageerror',lambda error:errors.append(str(error)));pages.append(page)
  def state(page):return page.evaluate("({room:proof.room,status:document.querySelector('[data-testid=game-status]')?.textContent,evidence:slotEvidence})")
  def native(page):return page.evaluate("""()=>new Promise((resolve,reject)=>{const requestId=window.nativeRequest=(window.nativeRequest??800000)+1;const timer=setTimeout(()=>reject(Error('native hash timed out')),3000);function done({data}){if(data.requestId!==requestId)return;clearTimeout(timer);currentWorker.removeEventListener('message',done);if(data.type==='error')reject(Error(data.message));else resolve(data.info);}currentWorker.addEventListener('message',done);currentWorker.postMessage({type:'state-hash',requestId});})""")
  try:
   host=pages[0];host.goto(url);host.get_by_role('button',name='Create game',exact=True).click();host.set_input_files('input[type=file]',{'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});host.get_by_role('button',name='Create room',exact=True).click();host.get_by_role('button',name='Copy invite',exact=True).wait_for();invite=host.get_by_label('Room invitation',exact=True).input_value()
   for page in pages[1:]:
    page.goto(invite);page.get_by_role('button',name='Join room',exact=True).click();page.wait_for_function("proof.room?.matches&&proof.room.slots.find(slot=>slot.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'",polling=50)
   for page in pages:
    page.wait_for_function("proof.room?.occupancy===5&&proof.room.peers.length===4&&proof.room.peers.every(peer=>peer.status==='connected')",polling=50)
    assert page.get_by_test_id('room-slot').count()==5
   members=[page.evaluate('proof.room.chatMembership') for page in pages];assert len(set(members))==5
   if args.initial_stall:pages[1].evaluate("window.gameFault='drop-input'")
   pages[1].get_by_role('button',name='Prepare to play',exact=True).click();pages[1].wait_for_function('proof.room.game.ready.includes(proof.room.chatMembership)',polling=20)
   host.get_by_role('button',name='Start game',exact=True).click()
   for page in pages:page.evaluate('releaseFrames()')
   if args.initial_stall:
    host.wait_for_function("proof.room.game.status==='paused'",polling=20)
    boundary=native(host);assert boundary['frame']==0,boundary
    slot=host.locator('[data-slot-id="slot-2"]');slot.get_by_role('button',name='Remove member',exact=True).click();slot.get_by_role('button',name='Confirm removal',exact=True).click()
    host.wait_for_function('!proof.room.slots[1].member',polling=20)
    host.get_by_label('Slot 3 role',exact=True).select_option('player2')
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
    result={'result':'pass','initial_stall':True,'boundary':boundary,'native_states':states,'errors':errors,'elapsed':round(time.monotonic()-started,2)};assert not errors,errors;out.write_text(json.dumps(result,indent=2));print(json.dumps(result));sys.exit(0)
   for page in pages[:2]:page.wait_for_function("proof.room.game.status==='playing'",polling=20)
   for page in pages[2:]:page.get_by_test_id('game-status').filter(has_text='Observing the current game.').wait_for()
   host.wait_for_function('proof.frames.at(-1)?.frame>=240',polling=20)
   # Observer reconnect retains its slot and never pauses the active owners.
   observer_member=members[4];epoch_before=host.evaluate('proof.room.game.epoch')
   pages[4].reload();pages[4].evaluate('releaseFrames()')
   pages[4].wait_for_function('member=>proof.room?.chatMembership===member',arg=observer_member,polling=20)
   pages[4].get_by_test_id('game-status').filter(has_text='Observing the current game.').wait_for()
   assert host.evaluate("proof.room.game.status==='playing'&&proof.room.game.epoch") == epoch_before
   host.get_by_role('button',name='Pause',exact=True).click()
   for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    states=[native(page) for page in pages]
    if all(value==states[0] for value in states):break
    assert time.monotonic()<deadline,states
    time.sleep(.05)
   initial=states
   host.screenshot(path=str(out.with_suffix('.five.png')))
   # Host administration is independent of controller ownership.
   host.get_by_label('Slot 1 role',exact=True).select_option('observer')
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
   host_observer=states
   host.screenshot(path=str(out.with_suffix('.host-observer.png')))
   # Promoting an observer atomically swaps the occupied Player 2 role.
   host.get_by_label('Slot 3 role',exact=True).select_option('player2')
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
   slot=host.locator('[data-slot-id="slot-3"]');slot.get_by_role('button',name='Remove member',exact=True).click();slot.get_by_role('button',name='Confirm removal',exact=True).click()
   host.wait_for_function('!proof.room.slots[2].member',polling=20)
   assert native(host)==stalled
   host.get_by_label('Slot 4 role',exact=True).select_option('player2')
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
   host.get_by_label('Slot 5 role',exact=True).select_option('player2')
   host.wait_for_function("proof.room.game.pending?.status==='synchronizing'",polling=20)
   host.get_by_role('button',name='Cancel role change',exact=True).click()
   host.wait_for_function("!proof.room.game.pending&&proof.room.slots[3].role==='player2'&&proof.room.slots[4].role==='observer'&&proof.room.game.status==='paused'",polling=20)
   cancelled=[native(page) for page in remaining]
   assert all(value==replacement[0] for value in cancelled),(replacement,cancelled)
   host.screenshot(path=str(out.with_suffix('.cancelled.png')))
   host.evaluate('window.holdCheckpoint=false')
   host.get_by_label('Slot 5 role',exact=True).select_option('player2')
   host.wait_for_function("proof.room.game.status==='playing'&&proof.room.game.controllers.owners[1]===proof.room.slots[4].member.id",polling=20)
   host.wait_for_function('start=>proof.frames.at(-1)?.frame>start+120',arg=replacement[0]['frame'],polling=20)
   host.get_by_role('button',name='Pause',exact=True).click()
   for page in remaining:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
   deadline=time.monotonic()+5
   while True:
    retried=[native(page) for page in remaining]
    if all(value==retried[0] for value in retried):break
    assert time.monotonic()<deadline,retried
    time.sleep(.05)
   # An active owner's reload preserves membership, pauses authority, and imports
   # its current state before the same owner resumes.
   pages[4].get_by_role('button',name='Ready to resume',exact=True).click();host.get_by_role('button',name='Ready to resume',exact=True).click();host.get_by_role('button',name='Resume together',exact=True).click()
   host.wait_for_function("proof.room.game.status==='playing'",polling=20)
   pages[4].reload();pages[4].evaluate('releaseFrames()')
   host.wait_for_function("proof.room.game.status==='paused'",polling=20)
   pages[4].wait_for_function('member=>proof.room?.chatMembership===member&&proof.room.matches&&proof.room.peers.every(peer=>peer.status==="connected")',arg=members[4],polling=20)
   reconnect_boundary=native(host)
   pages[4].get_by_role('button',name='Ready to resume',exact=True).click();host.get_by_role('button',name='Ready to resume',exact=True).click();host.get_by_role('button',name='Resume together',exact=True).click()
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
   result={'result':'pass','members':5,'native_states':states,'initial':initial,'host_observer':host_observer,'promotion':promotion,'stalled':stalled,'replacement':replacement,'cancelled':cancelled,'retried':retried,'reconnect_boundary':reconnect_boundary,'reconnected':reconnected,'events':evidence,'same_origin_tabs':True,'browser_processes':3,'errors':errors,'elapsed':round(time.monotonic()-started,2)};assert not errors,errors;out.write_text(json.dumps(result,indent=2));print(json.dumps(result))
  except Exception:
   for index,page in enumerate(pages):
    try:out.with_suffix(f'.member{index}.json').write_text(json.dumps(state(page),indent=2));page.screenshot(path=str(out.with_suffix(f'.member{index}.png')))
    except Exception:pass
   out.with_suffix('.errors.json').write_text(json.dumps(errors));raise
