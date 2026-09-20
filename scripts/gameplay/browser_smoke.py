"""Production worker/barrier proof. The host is held at its genuine power-on state before shared start."""
import argparse,contextlib,hashlib,json,math,os,subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--kick-playing',action='store_true');parser.add_argument('--retry-barrier',choices=['guest-first','host-first']);parser.add_argument('--relay',action='store_true');parser.add_argument('--turnserver',default='turnserver');parser.add_argument('--output',default='/tmp/gameplay.json');parser.add_argument('--seconds',type=int,choices=[8,30,600],default=8);parser.add_argument('--pair',choices=['Chrome-Chrome','Firefox-Firefox','Chrome-Firefox'],default='Chrome-Chrome');parser.add_argument('--firefox-executable');parser.add_argument('--cancel-barrier',action='store_true');parser.add_argument('--delay-start',action='store_true');parser.add_argument('--barrier-timeout',action='store_true');parser.add_argument('--screenshots',action='store_true');parser.add_argument('--late-join',action='store_true');parser.add_argument('--fault',choices=['none','drop-input','bad-hash','old-epoch','future-input','duplicate-input','focus','device'],default='none');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];build_files={str(p.relative_to(root/'apps/client/dist')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'apps/client/dist').rglob('*') if p.is_file() and p.suffix in ['.js','.wasm']};out=Path(args.output);run_id=os.environ.get('GAMEPLAY_RUN_ID');started=time.monotonic()
source={key:subprocess.check_output(['git','rev-parse',ref],cwd=root,text=True).strip() for key,ref in [('commit','HEAD'),('tree','HEAD^{tree}')]}
sys.path.insert(0,str(root/'scripts/peer'))
from fixture import LocalTurn
stack=contextlib.ExitStack();turn=stack.enter_context(LocalTurn(args.turnserver)) if args.relay else None
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,**(turn.environment() if turn else {'TURN_URLS':'','TURN_SECRET':''})},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
 with sync_playwright() as p:
  browsers={kind:(p.chromium.launch(ignore_default_args=['--mute-audio']) if kind=='Chrome' else p.firefox.launch(firefox_user_prefs={'media.peerconnection.ice.loopback':True} if args.relay else {},**({'executable_path':args.firefox_executable} if args.firefox_executable else {}))) for kind in set(args.pair.split('-'))};errors=[];pages=[];kinds=iter(args.pair.split('-'))
  def page():
   tab=browsers[next(kinds)].new_page(viewport={'width':1280,'height':1050});pages.append(tab);tab.set_default_timeout(10000);tab.on('pageerror',lambda e:errors.append(str(e)))
   tab.add_init_script(path=root/'scripts/gameplay/fixture.js');tab.add_init_script("window.gamePeers=[];const P=RTCPeerConnection;window.RTCPeerConnection=class extends P{constructor(...a){super(...a);gamePeers.push(this)}}");tab.goto(url)
   if args.relay:tab.get_by_label('Connection privacy',exact=True).first.select_option('relay')
   return tab
  try:
   h=page();g=page()
   if args.screenshots:h.screenshot(path=str(out.with_name('initial.png')),full_page=True)
   h.set_input_files('input[type=file]',{'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});h.get_by_test_id('room-view').wait_for()
   if args.late_join:
    h.evaluate('releaseFrames()');h.wait_for_function("parseInt(document.querySelector('[data-testid=frames]').textContent)>=30",polling=50)
   invite=h.get_by_label('Room invitation',exact=True).input_value();g.goto(invite);g.reload();g.get_by_role('button',name='Retry join / Join',exact=True).click();g.get_by_test_id('room-view').wait_for()
   if not args.late_join:assert h.get_by_test_id('frames').inner_text()=='0 frames'
   lease=g.evaluate('proof.room.reservationUntil')
   if args.delay_start:g.evaluate('window.delayStart=true')
   if args.barrier_timeout or args.cancel_barrier or args.retry_barrier:g.evaluate('window.dropGameAck=true')
   g.set_input_files('input[type=file]',{'name':'matching.nes','mimeType':'application/octet-stream','buffer':rom})
   if args.cancel_barrier:
    g.wait_for_function('proof.droppedAcks===1',timeout=10000,polling=50)
    g.get_by_role('button',name='Cancel join',exact=True).click();g.get_by_test_id('room-view').wait_for(state='detached')
    h.wait_for_function("!proof.room.guest && proof.room.reservationUntil===undefined",polling=50)
    assert not h.evaluate('proof.room.established') and h.get_by_test_id('frames').inner_text()=='0 frames'
    h.evaluate('releaseFrames()');h.get_by_role('button',name='Resume',exact=True).click();h.wait_for_function("parseInt(document.querySelector('[data-testid=frames]').textContent)>0",polling=50)
    result={'resumed_locally':True,'result':'pass','scenario':'cancel unacknowledged initial barrier','host_frames':0,'seconds':round(time.monotonic()-started,2),'page_errors':errors};assert not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));[browser.close() for browser in browsers.values()];raise SystemExit(0)
   if args.barrier_timeout or args.retry_barrier:
    for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='failed'",timeout=15000,polling=50)
    assert g.evaluate('proof.droppedAcks')==1
    assert all(not tab.evaluate('proof.room.established') for tab in [h,g])
    assert g.evaluate('proof.room.reservationUntil')==lease
    assert h.get_by_test_id('frames').inner_text()=='0 frames'
    result={'result':'pass','injection':'drop guest initial barrier acknowledgement','lease_preserved':True,'host_frames':0,'seconds':round(time.monotonic()-started,2),'statuses':[tab.get_by_test_id('game-status').inner_text() for tab in [h,g]],'page_errors':errors};assert not errors
    if not args.retry_barrier:
     out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));[browser.close() for browser in browsers.values()];raise SystemExit(0)
    g.evaluate('window.dropGameAck=false')
    first,second=(g,h) if args.retry_barrier=='guest-first' else (h,g)
    first.get_by_role('button',name='Retry shared play',exact=True).click();first.wait_for_function('proof.gameReadies===2',polling=50)
    assert second.evaluate('proof.gameReadies')==1,'background retry renewed the other player intent'
    second.get_by_role('button',name='Retry shared play',exact=True).click();second.wait_for_function('proof.gameReadies===2',polling=50)
   if args.late_join:
    for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='late_join'",timeout=15000,polling=50)
    observed=h.evaluate('proof.hashes.at(-1)');assert observed['frame']>=30 and not observed['fresh']
    count=h.get_by_test_id('frames').inner_text();h.wait_for_timeout(250);assert h.get_by_test_id('frames').inner_text()==count
    assert all(not tab.evaluate('proof.room.established') for tab in [h,g])
    result={'result':'pass','scenario':'progressed host pauses without reset','host_state':observed,'host_frames':count,'lease_preserved':g.evaluate('proof.room.reservationUntil>Date.now()'),'seconds':round(time.monotonic()-started,2),'page_errors':errors};assert result['lease_preserved'] and not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));[browser.close() for browser in browsers.values()];raise SystemExit(0)
   for tab in [h,g]:tab.wait_for_function("proof.room?.established && proof.room.game.status==='playing'",timeout=15000,polling=50)
   fps=h.evaluate('proof.fps');assert fps==g.evaluate('proof.fps');target_frames=max(360,math.ceil(args.seconds*fps))
   play_started=time.monotonic()
   for tab in [h,g]:tab.evaluate('releaseFrames()')
   for tab in [h,g]:tab.wait_for_function('proof.frameCount>=1',timeout=5000,polling=20)
   h.locator('canvas').focus();h.keyboard.down('x');g.locator('canvas').focus();g.keyboard.down('z')
   for tab in [h,g]:tab.wait_for_function('proof.frameCount>=240',timeout=20000,polling=50)
   for tab in [h,g]:
    tab.evaluate("currentWorker.postMessage({type:'state-export',requestId:900000})");tab.wait_for_function('proof.controllerRam',polling=50);assert tab.evaluate('proof.controllerRam')==[128,64]
    assert tab.get_by_role('button',name='Rewind',exact=True).is_disabled()
    tab.evaluate("currentWorker.postMessage({type:'state-history',requestId:900002})");tab.wait_for_function('proof.localHistory',polling=50);history=tab.evaluate('proof.localHistory');assert history['inputs']==0 and history['checkpoints']==0 and history['retainedBytes']==0
   if args.kick_playing:
    h.on('dialog',lambda dialog:dialog.accept())
    h.get_by_text('Connection and session settings',exact=True).click();h.get_by_text('Session settings',exact=True).click()
    h.get_by_role('button',name='Remove guest',exact=True).click();g.get_by_test_id('room-view').wait_for(state='detached')
    for tab in [h,g]:tab.wait_for_function("gamePeers.length>0 && gamePeers.every(p=>p.connectionState==='closed')")
    stopped=[tab.evaluate('proof.frameCount') for tab in [h,g]]
    local=[int(tab.get_by_test_id('frames').inner_text().split()[0]) for tab in [h,g]]
    h.wait_for_timeout(250)
    assert stopped==[tab.evaluate('proof.frameCount') for tab in [h,g]]
    assert local==[int(tab.get_by_test_id('frames').inner_text().split()[0]) for tab in [h,g]]
    assert min(local)>=240
    h.get_by_role('button',name='Resume',exact=True).click()
    h.wait_for_function("n=>parseInt(document.querySelector('[data-testid=frames]').textContent)>n",arg=local[0])
    assert g.evaluate('proof.frameCount')==stopped[1]
    result={'result':'pass','source':source,'scenario':'kick during shared play','stopped_shared_frames':stopped,'preserved_local_frames':local,'explicit_host_resume':True,'both_peers_closed':True,'page_errors':errors,'seconds':round(time.monotonic()-started,2)}
    assert not errors,errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));[browser.close() for browser in browsers.values()];raise SystemExit(0)
   if args.screenshots:
    count=h.evaluate('proof.frameCount');h.get_by_label('Chat message',exact=True).press_sequentially('xz shared hello')
    h.get_by_text('Typing in chat · game input released.',exact=False).wait_for()
    h.wait_for_function('n=>proof.frameCount>=n+12',arg=count,polling=20)
    h.evaluate("currentWorker.postMessage({type:'state-export',requestId:900001})");h.wait_for_function('proof.chatRam',polling=20);assert h.evaluate('proof.chatRam')==[0,64]
    assert h.evaluate('proof.room.game.status')=='playing'
    h.get_by_role('button',name='Send message',exact=True).click();g.get_by_role('log').get_by_text('xz shared hello',exact=True).wait_for()
   if args.screenshots:h.screenshot(path=str(out.with_name('playing.png')),full_page=True,mask=[h.locator('input[aria-label="Room invitation"]:visible')])
   first_active=time.monotonic()-play_started
   h.keyboard.up('x');g.keyboard.up('z')
   if args.fault=='device':
    h.evaluate((root/'scripts/foundation/gamepad_fixture.js').read_text());h.get_by_role('button',name='Settings',exact=True).click();h.get_by_label('Input device',exact=True).select_option('0');h.get_by_role('button',name='Close settings',exact=True).click();h.evaluate('padConnected=false')
   elif args.fault=='focus':h.evaluate("window.dispatchEvent(new Event('blur'))")
   else:h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   if args.screenshots:
    h.screenshot(path=str(out.with_name('paused.png')),full_page=True,mask=[h.locator('input[aria-label="Room invitation"]:visible')])
    h.set_viewport_size({'width':390,'height':844});h.screenshot(path=str(out.with_name('paused-mobile.png')),full_page=True,mask=[h.locator('input[aria-label="Room invitation"]:visible')]);h.set_viewport_size({'width':1280,'height':1050})
   before=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert before[0]==before[1],before
   if args.fault in ['focus','device']:
    h.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
    assert h.evaluate('proof.room.game.status')=='paused'
    if args.fault=='focus':h.evaluate("window.dispatchEvent(new Event('focus'))")
    else:h.get_by_role('button',name='Use keyboard',exact=True).click()
   h.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
   h.wait_for_function("proof.room.game.ready?.includes('host')",polling=50)
   assert h.get_by_role('button',name='Resume together',exact=True).is_disabled()
   h.get_by_text(f"Waiting for {h.evaluate('proof.room.guest')} to resume.",exact=True).wait_for()
   g.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
   h.get_by_role('button',name='Resume together',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='playing'",timeout=15000,polling=50)
   resumed=time.monotonic()
   h.evaluate("window.scriptKey='KeyX'");g.evaluate("window.scriptKey='KeyZ'")
   if args.fault not in ['none','focus','device']:
    g.evaluate('fault=>window.gameFault=fault',args.fault)
    if args.fault!='old-epoch':
     for tab in [h,g]:tab.wait_for_function("['failed','paused'].includes(proof.room.game.status)",timeout=10000,polling=50)
     stopped=[tab.evaluate('proof.frameCount') for tab in [h,g]]
     # Observe a bounded quiet interval after explicit state readiness, not a startup delay.
     h.wait_for_timeout(250)
     assert stopped==[tab.evaluate('proof.frameCount') for tab in [h,g]],'A stopped game advanced'
     assert all(tab.evaluate('proof.room.established') for tab in [h,g]),'Failure discarded room membership'
     result={'result':'pass','injection':args.fault,'seconds':round(time.monotonic()-started,2),'stopped_frames':stopped,'peers':[tab.evaluate('(({room,...p})=>({...p,game:room.game}))(proof)') for tab in [h,g]],'page_errors':errors}
     assert not errors,errors
     out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','injection':args.fault}));[browser.close() for browser in browsers.values()];raise SystemExit(0)
   for tab in [h,g]:tab.wait_for_function('n=>proof.frameCount>=n',arg=target_frames,timeout=(args.seconds+30)*1000,polling=100)
   # This is the measured workload interval, never a guessed startup wait.
   while first_active+time.monotonic()-resumed<args.seconds:h.wait_for_timeout(20)
   active_seconds=round(first_active+time.monotonic()-resumed,2)
   h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   final=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert final[0]==final[1],final
   hashes=[tab.evaluate('proof.sentHashes') for tab in [h,g]];assert hashes[0]==hashes[1], 'Every epoch/frame hash must be present and identical on both peers';assert len(hashes[0])>=2
   route='relay' if args.relay else 'direct'
   for tab in [h,g]:assert f'Route: {route}.' in tab.get_by_test_id('connection-status').inner_text()
   identity=h.evaluate('proof.room.fingerprint');assert identity['romSha256']==hashlib.sha256(rom).hexdigest();assert identity['coreSha256'] in build_files.values()
   if args.delay_start:assert g.evaluate('proof.delayedStarts')==1
   result={'recovery_order':args.retry_barrier,'source':source,'route':route,'turn_error_codes':turn.error_codes() if turn else {},'build_files':build_files,'identity':identity,'delayed_start':args.delay_start,'run_id':run_id,'result':'pass','browsers':{kind:b.version for kind,b in browsers.items()},'pair':args.pair,'injection':args.fault,'target_seconds':args.seconds,'target_frames':target_frames,'active_seconds':active_seconds,'final':final,'seconds':round(time.monotonic()-started,2),'pause':before,'peers':[tab.evaluate('(({room,...proof})=>proof)(proof)') for tab in [h,g]],'page_errors':errors};assert not errors,errors
   out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','seconds':result['seconds']}));[browser.close() for browser in browsers.values()]
  except Exception:
   failure={'source':source,'run_id':run_id,'result':'fail','page_errors':errors,'peers':[tab.evaluate("""({proof:(({room,...p})=>p)(proof),status:document.querySelector('[data-testid=game-status]')?.textContent,localStatus:document.querySelector('[data-testid=player-status]')?.textContent,game:proof.room?.game,established:proof.room?.established})""") for tab in pages if not tab.is_closed()]}
   out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True);raise

finally:
 if run_id:
  (out.parent/'result-pointer.json').write_text(json.dumps({'run_id':run_id,'output':str(out.resolve())})+'\n')
 service.terminate();service.wait(timeout=5);stack.close()
