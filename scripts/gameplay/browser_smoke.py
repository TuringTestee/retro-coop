"""Production worker/barrier proof. The host is held at its genuine power-on state before shared start."""
import argparse,contextlib,hashlib,json,math,os,subprocess,sys,time,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from workload import active_seconds as measured_active_seconds
parser=argparse.ArgumentParser();parser.add_argument('--initial-manual-frames',type=int,choices=[240,508],default=240,help='Retain the manual-input phase to exercise slow qualification setup');parser.add_argument('--controllers',action='store_true');parser.add_argument('--delay-join',action='store_true');parser.add_argument('--operator-playing',choices=['remove','block']);parser.add_argument('--worker-floor-ms',type=int,choices=[0,14],default=0,help='Diagnostic only: minimum Firefox worker response latency');parser.add_argument('--kick-playing',action='store_true');parser.add_argument('--retry-barrier',choices=['guest-first','host-first']);parser.add_argument('--relay',action='store_true');parser.add_argument('--turnserver',default='turnserver');parser.add_argument('--output',default='/tmp/gameplay.json');parser.add_argument('--seconds',type=int,choices=[8,30,600],default=8);parser.add_argument('--pair',choices=['Chrome-Chrome','Firefox-Firefox','Chrome-Firefox'],default='Chrome-Chrome');parser.add_argument('--firefox-executable');parser.add_argument('--cancel-barrier',action='store_true');parser.add_argument('--delay-start',action='store_true');parser.add_argument('--barrier-timeout',action='store_true');parser.add_argument('--screenshots',action='store_true');parser.add_argument('--late-join',action='store_true');parser.add_argument('--fault',choices=['none','drop-input','bad-hash','old-epoch','future-input','duplicate-input','focus','device'],default='none');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];build_files={str(p.relative_to(root/'apps/client/dist')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'apps/client/dist').rglob('*') if p.is_file() and p.suffix in ['.js','.wasm']};out=Path(args.output);run_id=os.environ.get('GAMEPLAY_RUN_ID');started=time.monotonic()
source={key:subprocess.check_output(['git','rev-parse',ref],cwd=root,text=True).strip() for key,ref in [('commit','HEAD'),('tree','HEAD^{tree}')]}
sys.path.insert(0,str(root/'scripts/peer'))
from fixture import LocalTurn
sys.path.insert(0,str(root/'spikes/d02'))
import firefox_driver
firefox_evidence=firefox_driver.evidence(args.firefox_executable) if args.firefox_executable else {'firefox_driver':'Playwright bundled patched Firefox'}
stack=contextlib.ExitStack();operator_dir=stack.enter_context(tempfile.TemporaryDirectory(prefix='retro-game-op-')) if args.operator_playing else None;turn=stack.enter_context(LocalTurn(args.turnserver)) if args.relay else None
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,**({'COORDINATOR_OPERATOR_DIR':operator_dir} if operator_dir else {}),**(turn.environment() if turn else {'TURN_URLS':'','TURN_SECRET':''})},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
 with sync_playwright() as p, contextlib.ExitStack() as browser_stack:
  browsers=[]
  for kind in args.pair.split('-'):
   browser=p.chromium.launch(ignore_default_args=['--mute-audio']) if kind=='Chrome' else p.firefox.launch(firefox_user_prefs={'media.peerconnection.ice.loopback':True} if args.relay else {},**(firefox_driver.launch_options(args.firefox_executable) if args.firefox_executable else {}))
   browsers.append(browser);browser_stack.callback(browser.close)
  errors=[];pages=[];kinds=iter(zip(args.pair.split('-'),browsers))
  if args.firefox_executable:
   for kind,browser in zip(args.pair.split('-'),browsers):
    if kind=='Firefox':firefox_driver.validate_evidence(firefox_evidence,browser.version)
  fixtures={}
  def install_script(tab,content=None,path=None):
   script=Path(path).read_text() if path else content
   if args.firefox_executable:
    fixtures[tab].append(script)
   else:tab.add_init_script(script)
  def page():
   kind,browser=next(kinds);tab=browser.new_page(**(firefox_driver.page_options() if kind=='Firefox' and args.firefox_executable else {'viewport':{'width':1280,'height':1050}}));pages.append(tab);tab.set_default_timeout(10000);tab.on('pageerror',lambda e:errors.append({'message':str(e),'stack':e.stack,'elapsed':round(time.monotonic()-started,3)}))
   fixtures[tab]=[]
   if args.firefox_executable:
    def document(route):
     scripts=''.join('<script>(()=>{'+script.replace('</script','<\\/script')+'\n})();</script>' for script in fixtures[tab])
     route.fulfill(status=200,content_type='text/html',body=(root/'apps/client/dist/index.html').read_text().replace('<head>','<head>'+scripts,1))
    tab.route(url+'/',document)
   install_script(tab,path=root/'scripts/gameplay/fixture.js');install_script(tab,f'window.workerFloorMs={args.worker_floor_ms if kind=="Firefox" else 0}');install_script(tab,"window.gamePeers=[];const P=RTCPeerConnection;window.RTCPeerConnection=class extends P{constructor(...a){super(...a);gamePeers.push(this)}}")
   if args.relay:install_script(tab,"sessionStorage.setItem('retro-coop-connection-policy','relay')")
   tab.goto(url)
   return tab
  def open_room(tab):
   panel=tab.locator('.room-panel')
   if not panel.is_visible():tab.get_by_role('button',name='Room',exact=True).click()
   panel.wait_for(state='visible');return panel
  def open_connection(tab):
   panel=open_room(tab);connection=panel.locator('details.session-settings')
   if not connection.evaluate('(node)=>node.open'):connection.get_by_text('Connection and session settings',exact=True).click()
   return panel
  def open_host_session(tab):
   panel=open_connection(tab);session=panel.locator('details.session-settings details').filter(has_text='Session settings')
   if not session.evaluate('(node)=>node.open'):session.get_by_text('Session settings',exact=True).click()
   return panel
  try:
   h=page();g=page()
   if args.screenshots:h.screenshot(path=str(out.with_name('initial.png')),full_page=True)
   h.get_by_role('button',name='Create game',exact=True).click();h.set_input_files('input[type=file]',{'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});h.get_by_role('button',name='Create room',exact=True).click();h.get_by_role('button',name='Copy invite',exact=True).wait_for();h.get_by_test_id('room-view').wait_for(state='attached')
   if args.late_join:
    # Progress-preserving late Join is deferred: an active room offers no admission path.
    invite=h.get_by_label('Room invitation',exact=True).input_value();h.get_by_role('button',name='Start game',exact=True).click();h.evaluate('releaseFrames()');h.wait_for_function("parseInt(document.querySelector('[data-testid=frames]').textContent)>=30",polling=50)
    g.evaluate('invite=>{location.hash=new URL(invite).hash}',invite);g.reload()
    preview=g.locator('.room-panel.invitation');preview.get_by_text('playing',exact=False).wait_for()
    assert preview.get_by_role('button',name='Join room',exact=True).count()==0
    assert preview.get_by_role('button',name='Retry invitation',exact=True).is_visible()
    denial=g.evaluate('''invite=>new Promise((resolve,reject)=>{
      const socket=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);
      const helloId=crypto.randomUUID(),joinId=crypto.randomUUID();
      const timeout=setTimeout(()=>{socket.close();reject(Error('late join probe timed out'))},5000);
      socket.onerror=()=>{clearTimeout(timeout);reject(Error('late join probe failed'))};
      socket.onopen=()=>socket.send(JSON.stringify({type:'hello',requestId:helloId}));
      socket.onmessage=event=>{const result=JSON.parse(event.data);if(result.type!=='result')return;
        if(result.requestId===helloId){if(!result.ok){clearTimeout(timeout);socket.close();reject(Error('late join hello failed'));return;}
          socket.send(JSON.stringify({type:'join',requestId:joinId,intent:crypto.randomUUID(),invite:new URLSearchParams(new URL(invite).hash.slice(1)).get('invite')}));}
        if(result.requestId===joinId){clearTimeout(timeout);socket.close();resolve({ok:result.ok,error:result.error});}
      };
    })''',invite)
    assert denial=={'ok':False,'error':'room_started'},denial
    host_after_denial=int(h.get_by_test_id('frames').inner_text().split()[0])
    preview.get_by_role('button',name='View public rooms',exact=True).click();g.get_by_role('heading',name='Public rooms',exact=True).wait_for()
    playing_row=g.locator('.room-list li').filter(has_text='Playing; Join unavailable');playing_row.wait_for()
    assert playing_row.get_by_role('button',name='Join',exact=True).count()==0
    assert g.get_by_test_id('room-view').count()==0
    h.wait_for_function("n=>parseInt(document.querySelector('[data-testid=frames]').textContent)>n",arg=host_after_denial,polling=50)
    result={'result':'pass','scenario':'late guest denied after solo Start','host_frames':h.get_by_test_id('frames').inner_text(),'invitation_join_hidden':True,'server_denied':'room_started','public_row_join_unavailable':True,'seconds':round(time.monotonic()-started,2),'page_errors':errors};assert not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
   if args.delay_join:
    install_script(g,"""const Native=WebSocket;window.WebSocket=class extends Native{set onmessage(handler){super.onmessage=event=>{const e=JSON.parse(event.data);if(!window.releaseJoin&&e.type==='result'&&e.ok&&e.data?.room?.role==='guest'){window.releaseJoin=()=>handler(event)}else handler(event)}}};""")
   invite=h.get_by_label('Room invitation',exact=True).input_value();g.evaluate('invite=>{location.hash=new URL(invite).hash}',invite);g.reload();g.get_by_role('button',name='Join room',exact=True).click();g.get_by_test_id('room-view').wait_for(state='attached')
   assert h.get_by_test_id('frames').inner_text()=='0 frames'
   lease=g.evaluate('proof.room.reservationUntil')
   if args.delay_start:g.evaluate('window.delayStart=true')
   if args.barrier_timeout or args.cancel_barrier or args.retry_barrier:g.evaluate('window.dropGameAck=true')
   g.set_input_files('input[type=file]',{'name':'matching.nes','mimeType':'application/octet-stream','buffer':rom})
   if args.delay_join:
    g.wait_for_function('typeof releaseJoin === \"function\"');g.evaluate('releaseJoin()')
   g.get_by_role('button',name='Prepare to play',exact=True).click()
   h.wait_for_function("proof.room?.game?.ready?.includes('guest')",timeout=15000,polling=50)
   h.get_by_role('button',name='Start game',exact=True).click()
   if args.cancel_barrier:
    g.wait_for_function('proof.droppedAcks===1',timeout=10000,polling=50)
    open_room(g).get_by_role('button',name='Leave room',exact=True).click();g.get_by_test_id('room-view').wait_for(state='detached')
    h.wait_for_function("!proof.room.guest && proof.room.reservationUntil===undefined",polling=50)
    assert not h.evaluate('proof.room.established') and h.get_by_test_id('frames').inner_text()=='0 frames'
    h.evaluate('releaseFrames()');h.get_by_role('button',name='Resume',exact=True).click();h.wait_for_function("parseInt(document.querySelector('[data-testid=frames]').textContent)>0",polling=50)
    result={'resumed_locally':True,'result':'pass','scenario':'cancel unacknowledged initial barrier','host_frames':0,'seconds':round(time.monotonic()-started,2),'page_errors':errors};assert not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
   if args.barrier_timeout or args.retry_barrier:
    for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='failed'",timeout=15000,polling=50)
    assert g.evaluate('proof.droppedAcks')==1
    assert all(not tab.evaluate('proof.room.established') for tab in [h,g])
    assert g.evaluate('proof.room.reservationUntil')==lease
    assert h.get_by_test_id('frames').inner_text()=='0 frames'
    result={'result':'pass','injection':'drop guest initial barrier acknowledgement','lease_preserved':True,'host_frames':0,'seconds':round(time.monotonic()-started,2),'statuses':[tab.get_by_test_id('game-status').inner_text() for tab in [h,g]],'page_errors':errors};assert not errors
    if not args.retry_barrier:
     out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
    g.evaluate('window.dropGameAck=false')
    first,second=(g,h) if args.retry_barrier=='guest-first' else (h,g)
    open_room(first).get_by_role('button',name='Retry shared play',exact=True).click();first.wait_for_function('proof.gameReadies===2',polling=50)
    assert second.evaluate('proof.gameReadies')==1,'background retry renewed the other player intent'
    open_room(second).get_by_role('button',name='Retry shared play',exact=True).click();second.wait_for_function('proof.gameReadies===2',polling=50)
   for tab in [h,g]:tab.wait_for_function("proof.room?.established && proof.room.game.status==='playing'",timeout=15000,polling=50)
   def shared_layout(tab):
    layout=tab.evaluate("""()=>{const canvas=document.querySelector('canvas'),room=document.querySelector('.room-panel'),box=canvas.getBoundingClientRect();return {viewport:{width:innerWidth,height:innerHeight},canvas:{width:box.width,height:box.height,areaRatio:box.width*box.height/(innerWidth*innerHeight)},document:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight},room:{scrollHeight:room.scrollHeight,clientHeight:room.clientHeight}}}""")
    assert layout['canvas']['width']>=layout['viewport']['width']*.40 and layout['canvas']['height']>=layout['viewport']['height']*.75,layout
    assert layout['canvas']['areaRatio']>=.30,layout
    assert layout['document']['width']<=layout['viewport']['width'] and layout['document']['height']<=layout['viewport']['height'],layout
    assert layout['room']['scrollHeight']<=layout['room']['clientHeight'],layout
    return layout
   shared_layouts=[shared_layout(tab) for tab in [h,g]]
   if args.screenshots:h.screenshot(path=str(out.with_name(out.stem+'.shared-playing.png')),mask=[h.locator('input[aria-label="Room invitation"]:visible')])
   fps=h.evaluate('proof.fps');assert fps==g.evaluate('proof.fps');target_frames=max(360,math.ceil(args.seconds*fps))
   play_started=time.monotonic()
   for tab in [h,g]:tab.evaluate('releaseFrames()')
   for tab in [h,g]:tab.wait_for_function('proof.frameCount>=1',timeout=5000,polling=20)
   h.locator('canvas').focus();h.keyboard.down('x');g.locator('canvas').focus();g.keyboard.down('z')
   for tab in [h,g]:tab.wait_for_function('n=>proof.frameCount>=n',arg=args.initial_manual_frames,timeout=20000,polling=50)
   for tab in [h,g]:
    tab.evaluate("currentWorker.postMessage({type:'state-export',requestId:900000})");tab.wait_for_function('proof.controllerRam',polling=50);assert tab.evaluate('proof.controllerRam')==[128,64]
    assert tab.get_by_role('button',name='Rewind',exact=True).is_disabled()
    tab.evaluate("currentWorker.postMessage({type:'state-history',requestId:900002})");tab.wait_for_function('proof.localHistory',polling=50);history=tab.evaluate('proof.localHistory');assert history['inputs']==0 and history['checkpoints']==0 and history['retainedBytes']==0
   if args.controllers:
    from controller_smoke import run
    result=run(h,g,out,root,errors,source,build_files)
    result.update({'pair':args.pair,'browser_instances':[{'kind':kind,'version':browser.version} for kind,browser in zip(args.pair.split('-'),browsers)],**firefox_evidence,'total_seconds':round(time.monotonic()-started,2)})
    out.write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(0)
   if args.kick_playing or args.operator_playing:
    if args.screenshots:h.screenshot(path=str(out.with_suffix('.before.png')),full_page=True,mask=[h.locator('input[aria-label="Room invitation"]:visible')])
    if args.kick_playing:
     # The waiting-room Remove guest control intentionally disappears after Start.
     # Keep the established-play teardown regression through the host protocol.
     assert open_room(h).get_by_role('button',name='Remove guest',exact=True).count()==0
     h.evaluate("""()=>{const room=proof.room;proof.roomSocket.send(JSON.stringify({type:'kick',requestId:crypto.randomUUID(),roomId:room.id,guestMembership:room.guestMembership}))}""")
     g.get_by_test_id('room-view').wait_for(state='detached')
    else:
     cli=['node','apps/coordinator/src/operator-cli.ts',operator_dir]
     listing=json.loads(subprocess.run([*cli,'list'],cwd=root,capture_output=True,text=True,check=True,timeout=5).stdout)
     action=['remove-room',h.evaluate('proof.room.id')] if args.operator_playing=='remove' else ['block-address',listing['subjects'][0]['id'],'60']
     applied=subprocess.run([*cli,*action],cwd=root,input='CONFIRM\n',capture_output=True,text=True,check=True,timeout=5)
     assert 'Done.' in applied.stdout
     for tab in [h,g]:
      tab.get_by_test_id('room-view').wait_for(state='detached')
      tab.get_by_text('An operator closed' if args.operator_playing=='remove' else 'Access is temporarily restricted',exact=False).first.wait_for()

    for tab in [h,g]:tab.wait_for_function("gamePeers.length>0 && gamePeers.every(p=>p.connectionState==='closed')")
    stopped=[tab.evaluate('proof.frameCount') for tab in [h,g]]
    local=[int(tab.get_by_test_id('frames').inner_text().split()[0]) for tab in [h,g]]
    h.wait_for_timeout(250)
    assert stopped==[tab.evaluate('proof.frameCount') for tab in [h,g]]
    assert local==[int(tab.get_by_test_id('frames').inner_text().split()[0]) for tab in [h,g]]
    assert min(local)>=240
    if args.screenshots:h.screenshot(path=str(out.with_suffix('.after.png')),full_page=True)
    h.get_by_role('button',name='Resume',exact=True).click()
    h.wait_for_function("n=>parseInt(document.querySelector('[data-testid=frames]').textContent)>n",arg=local[0])
    assert g.evaluate('proof.frameCount')==stopped[1]
    result={'result':'pass','source':source,'scenario':f'operator {args.operator_playing} during shared play' if args.operator_playing else 'kick during shared play','stopped_shared_frames':stopped,'preserved_local_frames':local,'explicit_host_resume':True,'both_peers_closed':True,'page_errors':errors,'seconds':round(time.monotonic()-started,2)}
    assert not errors,errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
   if args.screenshots:
    open_room(h).locator('details.chat-disclosure').evaluate('(node)=>node.open=true')
    count=h.evaluate('proof.frameCount');h.get_by_label('Chat message',exact=True).press_sequentially('xz shared hello')
    h.get_by_text('Typing in chat · game input released.',exact=False).wait_for()
    h.wait_for_function('n=>proof.frameCount>=n+12',arg=count,polling=20)
    h.evaluate("currentWorker.postMessage({type:'state-export',requestId:900001})");h.wait_for_function('proof.chatRam',polling=20);assert h.evaluate('proof.chatRam')==[0,64]
    assert h.evaluate('proof.room.game.status')=='playing'
    h.get_by_role('button',name='Close room',exact=True).click()
    shared_layouts=[shared_layout(tab) for tab in [h,g]]
   if args.screenshots:h.screenshot(path=str(out.with_name('playing.png')),full_page=True,mask=[h.locator('input[aria-label="Room invitation"]:visible')])
   first_active=time.monotonic()-play_started
   h.keyboard.up('x');g.keyboard.up('z')
   if args.fault=='device':
    h.evaluate((root/'scripts/foundation/gamepad_fixture.js').read_text());h.get_by_role('button',name='Settings',exact=True).click();h.get_by_label('Input device',exact=True).select_option('0');h.get_by_role('button',name='Close settings',exact=True).click();h.evaluate('padConnected=false')
   elif args.fault=='focus':
    h.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); window.dispatchEvent(new Event('blur')); document.dispatchEvent(new Event('visibilitychange'))")
    before=h.evaluate('proof.frameCount')
    h.wait_for_function('frames=>proof.frameCount>=frames+60',arg=before,timeout=15000,polling=50)
    assert all(tab.evaluate("proof.room.game.status==='playing'") for tab in [h,g])
    h.get_by_role('button',name='Pause',exact=True).click()
   else:h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   if args.screenshots:
    h.screenshot(path=str(out.with_name('paused.png')),full_page=True,mask=[h.locator('input[aria-label="Room invitation"]:visible')])
    h.set_viewport_size({'width':390,'height':844});h.screenshot(path=str(out.with_name('paused-mobile.png')),full_page=True,mask=[h.locator('input[aria-label="Room invitation"]:visible')]);h.set_viewport_size({'width':1280,'height':1050})
   before=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert before[0]==before[1],before
   if args.fault=='device':
    open_room(h).get_by_role('button',name='Ready to resume',exact=True).click()
    assert h.evaluate('proof.room.game.status')=='paused'
    h.get_by_role('button',name='Use keyboard',exact=True).click()
   open_room(h).get_by_role('button',name='Ready to resume',exact=True).click()
   h.wait_for_function("proof.room.game.ready?.includes('host')",polling=50)
   assert h.get_by_role('button',name='Resume together',exact=True).is_disabled()
   h.get_by_text(f"Waiting for {h.evaluate('proof.room.guest')} to resume.",exact=True).wait_for()
   open_room(g).get_by_role('button',name='Ready to resume',exact=True).click()
   # Arm while paused: every resumed frame belongs to the scripted workload.
   h.evaluate("window.scriptKey='KeyX'");g.evaluate("window.scriptKey='KeyZ'")
   h.get_by_role('button',name='Resume together',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='playing'",timeout=15000,polling=50)
   resumed=time.monotonic()
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
     out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','injection':args.fault}));raise SystemExit(0)
   for tab in [h,g]:
    tab.wait_for_function("n=>proof.frameCount>=n || proof.workloadStopped || proof.room?.game?.status!=='playing'",arg=target_frames,timeout=(args.seconds+30)*1000,polling=100)
    assert tab.evaluate('proof.frameCount')>=target_frames,'Shared gameplay stopped before the required workload completed'
   # This is the measured workload interval, never a guessed startup wait.
   while measured_active_seconds(args.seconds,first_active,time.monotonic()-resumed)<args.seconds:h.wait_for_timeout(20)
   active_seconds=round(measured_active_seconds(args.seconds,first_active,time.monotonic()-resumed),2)
   h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   final=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert final[0]==final[1],final
   hashes=[tab.evaluate('proof.sentHashes') for tab in [h,g]];assert hashes[0]==hashes[1], 'Every epoch/frame hash must be present and identical on both peers';assert len(hashes[0])>=2
   route='relay' if args.relay else 'direct'
   for tab in [h,g]:assert f'Route: {route}.' in tab.get_by_test_id('connection-status').inner_text()
   identity=h.evaluate('proof.room.fingerprint');assert identity['romSha256']==hashlib.sha256(rom).hexdigest();assert identity['coreSha256'] in build_files.values()
   if args.delay_start:assert g.evaluate('proof.delayedStarts')==1
   if args.firefox_executable:assert firefox_driver.evidence(args.firefox_executable)==firefox_evidence,'Firefox binary changed during probe'
   result={**firefox_evidence,'controlled_worker_delivery_floor_ms':args.worker_floor_ms,'recovery_order':args.retry_barrier,'source':source,'route':route,'turn_error_codes':turn.error_codes() if turn else {},'build_files':build_files,'identity':identity,'delayed_start':args.delay_start,'run_id':run_id,'result':'pass','browser_instances':[{'kind':kind,'version':b.version} for kind,b in zip(args.pair.split('-'),browsers)],'browsers':{kind:b.version for kind,b in zip(args.pair.split('-'),browsers)},'pair':args.pair,'injection':args.fault,'initial_manual_frames':args.initial_manual_frames,'target_seconds':args.seconds,'target_frames':target_frames,'active_seconds':active_seconds,'shared_layouts':shared_layouts,'final':final,'seconds':round(time.monotonic()-started,2),'pause':before,'peers':[tab.evaluate('(({room,...proof})=>proof)(proof)') for tab in [h,g]],'page_errors':errors};assert not errors,errors
   out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','seconds':result['seconds']}))
  except Exception:
   failure={**firefox_evidence,'controlled_worker_delivery_floor_ms':args.worker_floor_ms,'build_files':build_files,'browser_instances':[{'kind':kind,'version':b.version} for kind,b in zip(args.pair.split('-'),browsers)],'browsers':{kind:b.version for kind,b in zip(args.pair.split('-'),browsers)},'pair':args.pair,'source':source,'run_id':run_id,'result':'fail','page_errors':errors,'peers':[tab.evaluate("""({proof:(({room,...p})=>p)(proof),status:document.querySelector('[data-testid=game-status]')?.textContent,localStatus:document.querySelector('[data-testid=player-status]')?.textContent,game:proof.room?.game,established:proof.room?.established})""") for tab in pages if not tab.is_closed()]}
   out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True);raise

finally:
 if run_id:
  (out.parent/'result-pointer.json').write_text(json.dumps({'run_id':run_id,'output':str(out.resolve())})+'\n')
 service.terminate();service.wait(timeout=5);stack.close()
