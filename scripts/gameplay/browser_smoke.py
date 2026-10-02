"""Production worker/barrier proof. The host is held at its genuine power-on state before shared start."""
import argparse,contextlib,hashlib,json,math,os,subprocess,sys,time,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from workload import active_seconds as measured_active_seconds
from verify import normalized_periodic_hashes
from browser_errors import classify_page_errors
parser=argparse.ArgumentParser();parser.add_argument('--runtime-root',type=Path,default=Path(__file__).resolve().parents[2]);parser.add_argument('--checkpoint',choices=['success','corrupt','cancel']);parser.add_argument('--initial-manual-frames',type=int,choices=[240,508],default=240,help='Retain the manual-input phase to exercise slow qualification setup');parser.add_argument('--controllers',action='store_true');parser.add_argument('--delay-join',action='store_true');parser.add_argument('--stale-peer-view',action='store_true',help='Keep the guest peer view connecting after transport connects');parser.add_argument('--operator-playing',choices=['remove','block']);parser.add_argument('--worker-floor-ms',type=int,choices=[0,14],default=0,help='Diagnostic only: minimum Firefox worker response latency');parser.add_argument('--kick-playing',action='store_true');parser.add_argument('--retry-barrier',choices=['guest-first','host-first']);parser.add_argument('--relay',action='store_true',help='Force relay transport in the browser test fixture');parser.add_argument('--standard-fallback',action='store_true',help='Force relay ICE while the application uses automatic routing, modeling unavailable direct transport');parser.add_argument('--turnserver',default='turnserver');parser.add_argument('--output',default='/tmp/gameplay.json');parser.add_argument('--seconds',type=int,choices=[8,30,600],default=8);parser.add_argument('--pair',choices=['Chrome-Chrome','Firefox-Firefox','Chrome-Firefox'],default='Chrome-Chrome');parser.add_argument('--firefox-executable');parser.add_argument('--cancel-barrier',action='store_true');parser.add_argument('--delay-start',action='store_true');parser.add_argument('--delay-final-hash',action='store_true',help='Delay one final native hash response to exercise pause proof synchronization');parser.add_argument('--barrier-timeout',action='store_true');parser.add_argument('--screenshots',action='store_true');parser.add_argument('--short-viewport',action='store_true');parser.add_argument('--leave-interaction',action='store_true');parser.add_argument('--late-join',action='store_true');parser.add_argument('--fault',choices=['none','drop-input','bad-hash','old-epoch','future-input','duplicate-input','focus','device'],default='none');args=parser.parse_args();assert not(args.relay and args.standard_fallback)
root=args.runtime_root.resolve();static=Path(os.environ.get('RETRO_COOP_STATIC_ROOT',root/'apps/client/dist'));build_files={str(p.relative_to(static)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (static).rglob('*') if p.is_file() and p.suffix in ['.js','.wasm']};out=Path(args.output);run_id=os.environ.get('GAMEPLAY_RUN_ID');started=time.monotonic()
source={key:subprocess.check_output(['git','rev-parse',ref],cwd=root,text=True).strip() for key,ref in [('commit','HEAD'),('tree','HEAD^{tree}')]}
sys.path.insert(0,str(root/'scripts/peer'))
from fixture import LocalTurn
sys.path.insert(0,str(root/'spikes/d02'))
import firefox_driver
firefox_evidence=firefox_driver.evidence(args.firefox_executable) if args.firefox_executable else {'firefox_driver':'Playwright bundled patched Firefox'}
stack=contextlib.ExitStack();operator_dir=stack.enter_context(tempfile.TemporaryDirectory(prefix='retro-game-op-')) if args.operator_playing else None;turn=stack.enter_context(LocalTurn(args.turnserver)) if args.relay or args.standard_fallback else None
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,**({'COORDINATOR_OPERATOR_DIR':operator_dir} if operator_dir else {}),**(turn.environment() if turn else {'TURN_URLS':'','TURN_SECRET':''})},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url'];rom=(static/'generated/diagnostic.nes').read_bytes()
 with sync_playwright() as p, contextlib.ExitStack() as browser_stack:
  browsers=[]
  for kind in args.pair.split('-'):
   browser=p.chromium.launch(ignore_default_args=['--mute-audio']) if kind=='Chrome' else p.firefox.launch(firefox_user_prefs={'media.peerconnection.ice.loopback':True} if args.relay or args.standard_fallback else {},**(firefox_driver.launch_options(args.firefox_executable) if args.firefox_executable else {}))
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
   kind,browser=next(kinds);tab=browser.new_page(**(firefox_driver.page_options() if kind=='Firefox' and args.firefox_executable else {'viewport':{'width':1366,'height':682} if args.short_viewport else {'width':1280,'height':1050}}));pages.append(tab);tab.set_default_timeout(10000);tab.on('pageerror',lambda e:errors.append({'message':str(e),'stack':e.stack,'elapsed':round(time.monotonic()-started,3)}))
   if kind=='Chrome':tab.context.grant_permissions(['clipboard-read','clipboard-write'])
   fixtures[tab]=[]
   if args.firefox_executable:
    def document(route):
     scripts=''.join('<script>(()=>{'+script.replace('</script','<\\/script')+'\n})();</script>' for script in fixtures[tab])
     route.fulfill(status=200,content_type='text/html',body=(static/'index.html').read_text().replace('<head>','<head>'+scripts,1))
    tab.route(url+'/',document)
   install_script(tab,path=root/'scripts/gameplay/fixture.js');install_script(tab,f'window.workerFloorMs={args.worker_floor_ms if kind=="Firefox" else 0}');install_script(tab,"window.gamePeers=[];const P=RTCPeerConnection;window.RTCPeerConnection=class extends P{constructor(...a){super(...a);gamePeers.push(this)}}" if not (args.relay or args.standard_fallback) else "window.gamePeers=[];const P=RTCPeerConnection;window.RTCPeerConnection=class extends P{constructor(config){super({...config,iceTransportPolicy:'relay'});gamePeers.push(this)}}")
   tab.goto(url)
   return tab
  def invitation(tab):
   tab.get_by_role('button',name='Copy invite',exact=True).click()
   try:return tab.evaluate('navigator.clipboard.readText()')
   except Exception:return tab.evaluate('`${location.origin}/#invite=${proof.room.invite}`')
  def paused_hashes():
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   frame=h.evaluate('proof.room.game.frame')
   for tab in [h,g]:tab.wait_for_function("frame=>proof.room.game.frame===frame && proof.hashes.at(-1)?.frame===frame",arg=frame,timeout=15000,polling=50)
   states=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]]
   assert states[0]==states[1],states
   return states
  def open_room(tab):
   shell=tab.locator('.rc-shell')
   shell.wait_for(state='visible');return shell
  try:
   h=page();g=page()
   if args.screenshots:h.screenshot(path=str(out.with_name('initial.png')),full_page=True)
   h.get_by_role('button',name='Browse lobbies →').click();h.get_by_role('button',name='Create lobby →').click();h.get_by_label('Lobby name').fill('Network Proof')
   if args.late_join:
    h.get_by_label('Password protected').check()
    h.get_by_label('Lobby password').fill('late-observer-pass')
   h.get_by_role('button',name='Create lobby →').click();h.get_by_role('button',name='Load NES game').wait_for();h.locator('input[aria-label="NES cartridge file"]').set_input_files({'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});h.get_by_role('button',name='Change game').wait_for(timeout=30000)
   if args.late_join:
    # The public host chooses an observer slot before starting alone.
    h.locator('[data-slot-id="slot-2"] .slot-row').click()
    h.locator('[data-slot-id="slot-2"] .slot-menu').get_by_role('menuitem',name='Set as Observer').click()
    try:h.wait_for_function("proof.room.slots[1].role==='observer'",polling=50,timeout=15000)
    except PlaywrightTimeoutError:
     print(json.dumps({'observer_slot_setup':h.evaluate('''()=>({slot:proof.room?.slots[1],revision:proof.room?.revision,status:document.querySelector('.rc-status')?.textContent})''')}),flush=True)
     raise

    h.get_by_role('button',name='Ready',exact=True).click()
    h.get_by_role('button',name='Start →',exact=True).click();h.evaluate('releaseFrames()')
    h.wait_for_function('proof.frameCount>=120',polling=50)
    invite=invitation(h)
    assert 'late-observer-pass' not in invite
    if args.screenshots:h.screenshot(path=str(out.with_name('late-observer-invite.png')))
    prior_frame=h.evaluate('proof.frames.at(-1).frame');prior_epoch=h.evaluate('proof.activeEpoch')
    g.goto(invite)
    g.get_by_label('Lobby password').fill('late-observer-pass')
    g.get_by_role('button',name='Join lobby',exact=True).click()
    g.locator('[data-page="playing"]').wait_for();g.evaluate('releaseFrames()')
    g.wait_for_function('proof.frames.at(-1)?.frame>=10', polling=20)
    if args.screenshots:g.screenshot(path=str(out.with_name('late-observer-joined.png')))
    h.wait_for_function('frame=>proof.frames.at(-1).frame>frame+60',arg=prior_frame,polling=50)
    assert h.evaluate('proof.activeEpoch')==prior_epoch,'Observer admission changed the host timeline'
    assert g.evaluate("proof.room.slots.find(slot=>slot.member?.id===proof.room.chatMembership).role")== 'observer'
    assert g.evaluate('proof.gameReadies??0')==0,'Passive observer offered controller readiness'
    h.get_by_role('button',name='Pause',exact=True).click()
    for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",polling=20)
    from checkpoint_smoke import worker
    states=[worker(tab,{'type':'state-hash'})['info'] for tab in [h,g]]
    deadline=time.monotonic()+5
    while states[0]!=states[1] and time.monotonic()<deadline:
     time.sleep(.05);states=[worker(tab,{'type':'state-hash'})['info'] for tab in [h,g]]
    assert states[0]==states[1] and states[0]['frame']>prior_frame,states
    if args.screenshots:h.screenshot(path=str(out.with_name('late-observer-playing.png')))
    result={'result':'pass','source':source,'build_files':build_files,'scenario':'late observer joins running host','host_frame_before_join':prior_frame,'epoch_preserved':True,'native_states':states,'seconds':round(time.monotonic()-started,2),'page_errors':errors};assert not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
   if args.delay_join:
    install_script(g,"""const Native=WebSocket;window.WebSocket=class extends Native{set onmessage(handler){super.onmessage=event=>{const e=JSON.parse(event.data);if(!window.releaseJoin&&e.type==='result'&&e.ok&&e.data?.room?.role==='member'){window.releaseJoin=()=>handler(event)}else handler(event)}}};""")

   if args.stale_peer_view:
    install_script(g,"""const Native=WebSocket;window.stalePeerViews=0;window.WebSocket=class extends Native{set onmessage(handler){super.onmessage=event=>{const e=JSON.parse(event.data),room=e.type==='room'?e.room:e.type==='result'&&e.ok?e.data?.room:undefined;if(room?.peers?.some(peer=>peer.status==='connected')){room.peers=room.peers.map(peer=>peer.status==='connected'?{...peer,status:'connecting'}:peer);window.stalePeerViews++;handler(new MessageEvent('message',{data:JSON.stringify(e)}))}else handler(event)}}};""")
   invite=invitation(h);g.goto(invite);g.get_by_role('button',name='Join lobby',exact=True).click()
   if args.delay_join:
    g.wait_for_function('typeof releaseJoin === "function"');g.evaluate('releaseJoin()')
   g.locator('[data-page="lobby"]').wait_for()
   assert h.locator('canvas').get_attribute('data-frame-count')=='0'
   g.get_by_role('button',name='Ready',exact=True).wait_for(timeout=30000)
   g.wait_for_function("proof.room.slots.find(slot=>slot.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'",polling=20)
   lease=g.evaluate('proof.room.reservationUntil')
   initial_members=g.evaluate('proof.room.slots.filter(slot=>slot.member).map(slot=>({id:slot.member.id,role:slot.role,slot:slot.id}))')
   if args.delay_start:g.evaluate('window.delayStart=true')
   if args.barrier_timeout or args.cancel_barrier or args.retry_barrier:g.evaluate('window.dropGameAck=true')
   try:
    g.get_by_role('button',name='Ready',exact=True).click(timeout=30000)
   except PlaywrightTimeoutError:
    readiness=g.evaluate('''()=>{const room=proof.room,member=room?.slots.find(slot=>slot.member?.id===room.chatMembership)?.member,ready=[...document.querySelectorAll('button')].find(button=>button.textContent?.trim()==='Ready');return {roomMatches:room?.matches,memberAcquisition:member?.acquisition,memberConnected:member?.connected,peerStatuses:room?.peers.map(peer=>({status:peer.status,gameplay:peer.gameplay})),readyDisabled:ready?.disabled,localStatus:document.querySelector('.rc-status')?.textContent,readiness:document.querySelector('.rc-footer-actions')?.textContent}}''')
    print(json.dumps({'ready_timeout':readiness}),flush=True)
    raise
   if args.stale_peer_view:
    g.wait_for_function("window.stalePeerViews>0 && proof.room.peers.some(peer=>peer.status==='connected')",polling=20)
   h.wait_for_function("member=>proof.room?.game?.ready?.includes(member)",arg=g.evaluate('proof.room.chatMembership'),timeout=15000,polling=50)
   h.get_by_role('button',name='Ready',exact=True).click()
   h.get_by_role('button',name='Start →',exact=True).click()
   if args.cancel_barrier:
    g.wait_for_function('proof.droppedAcks===1',timeout=10000,polling=50)
    g.get_by_role('button',name='Back to Main Page').click();g.get_by_role('button',name='Leave lobby',exact=True).click();g.get_by_role('button',name='Browse lobbies →').wait_for()
    h.wait_for_function("proof.room.occupancy===1 && proof.room.slots.filter(slot=>slot.member).length===1",polling=50)
    assert not h.evaluate('proof.room.established') and h.locator('canvas').get_attribute('data-frame-count')=='0'
    h.get_by_role('button',name='Back to Main Page').click()
    h.get_by_role('button',name='Close lobby',exact=True).click();h.get_by_role('button',name='Browse lobbies →').wait_for()
    assert h.get_by_role('button',name='Resume',exact=True).count()==0
    assert h.locator('canvas').get_attribute('data-frame-count')=='0'
    result={'source':source,'build_files':build_files,'quit_before_directory':True,'result':'pass','scenario':'cancel unacknowledged initial barrier','host_frames':0,'navigation_preserved_frames':0,'seconds':round(time.monotonic()-started,2),'page_errors':errors};assert not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
   if args.barrier_timeout or args.retry_barrier:
    for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='failed'",timeout=15000,polling=50)
    assert g.evaluate('proof.droppedAcks')==1
    assert all(not tab.evaluate('proof.room.established') for tab in [h,g])
    assert g.evaluate('proof.room.reservationUntil')==lease
    assert g.evaluate('proof.room.slots.filter(slot=>slot.member).map(slot=>({id:slot.member.id,role:slot.role,slot:slot.id}))')==initial_members
    assert h.locator('canvas').get_attribute('data-frame-count')=='0'
    result={'result':'pass','injection':'drop guest initial barrier acknowledgement','lease_preserved':True,'membership_preserved':True,'host_frames':0,'seconds':round(time.monotonic()-started,2),'statuses':[tab.locator('.rc-status').inner_text() for tab in [h,g]],'page_errors':errors};assert not errors
    if not args.retry_barrier:
     out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
    g.evaluate('window.dropGameAck=false')
    first,second=(g,h) if args.retry_barrier=='guest-first' else (h,g)
    open_room(first).get_by_role('button',name='Prepare to resume',exact=True).click();first.wait_for_function('proof.gameReadies===2',polling=50)
    assert second.evaluate('proof.gameReadies')==1,'background retry renewed the other player intent'
    open_room(second).get_by_role('button',name='Prepare to resume',exact=True).click();second.wait_for_function('proof.gameReadies===2',polling=50)
   for tab in [h,g]:tab.wait_for_function("proof.room?.established && proof.room.game.status==='playing'",timeout=15000,polling=50)
   established_at=round(time.monotonic()-started,3)
   def shared_layout(tab):
    layout=tab.evaluate("""()=>{const box=selector=>{const node=document.querySelector(selector),r=node?.getBoundingClientRect();return r&&{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom,scroll:node.scrollHeight,client:node.clientHeight}};return {viewport:{width:innerWidth,height:innerHeight},document:{width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight},shell:box('.rc-shell'),stage:box('.rc-stage'),game:box('.rc-game-zone'),canvas:box('.rc-game-display canvas'),chat:box('.rc-chat'),footer:box('.rc-footer')}}""")
    viewport=layout['viewport'];canvas=layout['canvas'];game=layout['game']
    assert canvas['width']>=240 and canvas['height']>=225 and canvas['x']>=game['x'] and canvas['right']<=game['right']+1 and canvas['y']>=game['y'] and canvas['bottom']<=game['bottom']+1,layout
    assert layout['document']['width']<=viewport['width'] and layout['document']['height']<=viewport['height'],layout
    assert all(layout[region]['scroll']<=layout[region]['client']+1 for region in ('shell','stage','game','footer')),layout
    assert layout['chat']['bottom']<=layout['footer']['y'] and tab.get_by_role('button',name='Back to Main Page').is_visible(),layout
    assert tab.get_by_label('Message everyone').is_visible() and tab.get_by_role('button',name='Pause',exact=True).is_visible(),layout
    return layout
   shared_layouts=[shared_layout(tab) for tab in [h,g]]
   if args.leave_interaction:
    for tab in [h,g]:
     panel=open_room(tab)
     panel.get_by_role('button',name='Back to Main Page').click()
     panel.get_by_text('return to Main Page?',exact=False).wait_for()
     panel.get_by_role('button',name='Stay',exact=True).click()
     assert tab.locator('[data-page="playing"]').count()==1
   if args.screenshots:
    for role,tab in [('host',h),('guest',g)]:tab.screenshot(path=str(out.with_name(out.stem+f'.{role}.shared-playing.png')))
   fps=h.evaluate('proof.fps');assert fps==g.evaluate('proof.fps');target_frames=max(360,math.ceil(args.seconds*fps))
   play_started=time.monotonic()
   for tab in [h,g]:tab.evaluate('releaseFrames()')
   for tab in [h,g]:tab.wait_for_function('proof.frameCount>=1',timeout=5000,polling=20)
   h.locator('canvas').focus();h.keyboard.down('x');g.locator('canvas').focus();g.keyboard.down('z')
   for tab in [h,g]:tab.wait_for_function('n=>proof.frameCount>=n',arg=args.initial_manual_frames,timeout=20000,polling=50)
   for tab in [h,g]:
    tab.evaluate("currentWorker.postMessage({type:'state-export',requestId:900000})");tab.wait_for_function('proof.controllerRam',polling=50);assert tab.evaluate('proof.controllerRam')==[128,64]
    assert tab.get_by_role('button',name='Rewind',exact=True).count()==0
    tab.evaluate("currentWorker.postMessage({type:'state-history',requestId:900002})");tab.wait_for_function('proof.localHistory',polling=50);history=tab.evaluate('proof.localHistory');assert history['inputs']==0 and history['checkpoints']==0 and history['retainedBytes']==0
   if args.checkpoint:
    from checkpoint_smoke import run
    result=run(h,g,args.checkpoint,bool(args.relay or args.standard_fallback),out);result.update({'source':source,'build_files':build_files,'page_errors':errors});assert not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
   if args.controllers:
    from controller_smoke import run
    result=run(h,g,out,root,errors,source,build_files)
    result.update({'pair':args.pair,'browser_instances':[{'kind':kind,'version':browser.version} for kind,browser in zip(args.pair.split('-'),browsers)],**firefox_evidence,'total_seconds':round(time.monotonic()-started,2)})
    out.write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(0)
   if args.kick_playing or args.operator_playing:
    if args.screenshots:h.screenshot(path=str(out.with_suffix('.before.png')),full_page=True)
    if args.kick_playing:
     # Remove this precise member through the current host slot control.
     member=h.evaluate('proof.room.slots[1].member.nickname')
     h.locator('.rc-players [data-slot-id="slot-2"] .slot-row').click()
     h.locator('.rc-players [data-slot-id="slot-2"] .slot-menu').get_by_role('menuitem',name=f'Kick {member}').click()
     h.get_by_role('button',name='Kick player',exact=True).click()
     g.get_by_role('button',name='Browse lobbies →').wait_for()
    else:
     cli=['node','apps/coordinator/src/operator-cli.ts',operator_dir]
     listing=json.loads(subprocess.run([*cli,'list'],cwd=root,capture_output=True,text=True,check=True,timeout=5).stdout)
     action=['remove-room',h.evaluate('proof.room.id')] if args.operator_playing=='remove' else ['block-address',listing['subjects'][0]['id'],'60']
     applied=subprocess.run([*cli,*action],cwd=root,input='CONFIRM\n',capture_output=True,text=True,check=True,timeout=5)
     assert 'Done.' in applied.stdout
     for tab in [h,g]:
      tab.get_by_role('button',name='Browse lobbies →').wait_for()

    for tab in [h,g]:tab.wait_for_function("gamePeers.length>0 && gamePeers.every(p=>p.connectionState==='closed')")
    stopped=[tab.evaluate('proof.frameCount') for tab in [h,g]]
    local=[int(tab.locator('canvas').get_attribute('data-frame-count').split()[0]) for tab in [h,g]]
    h.wait_for_timeout(250)
    assert stopped==[tab.evaluate('proof.frameCount') for tab in [h,g]]
    assert local==[int(tab.locator('canvas').get_attribute('data-frame-count').split()[0]) for tab in [h,g]]
    assert local[1]==0,'The departed guest retained a game behind Main Page'
    if args.screenshots:h.screenshot(path=str(out.with_suffix('.after.png')),full_page=True)
    if args.kick_playing:
     h.get_by_role('button',name='Back to Main Page').click()
     h.get_by_role('button',name='Close lobby',exact=True).click();h.get_by_role('button',name='Browse lobbies →').wait_for()
     assert h.locator('canvas').get_attribute('data-frame-count')=='0'
    else:
     assert local==[0,0],'An operator-ended game remained active behind Main Page'
    assert g.evaluate('proof.frameCount')==stopped[1]
    result={'result':'pass','source':source,'scenario':f'operator {args.operator_playing} during shared play' if args.operator_playing else 'kick during shared play','stopped_shared_frames':stopped,'post_exit_local_frames':local,'voluntary_exit_quits_game':bool(args.kick_playing),'both_peers_closed':True,'page_errors':errors,'seconds':round(time.monotonic()-started,2)}
    assert not errors,errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0)
   if args.screenshots:
    count=h.evaluate('proof.frameCount');h.get_by_label('Message everyone',exact=True).press_sequentially('xz shared hello')
    h.wait_for_function('n=>proof.frameCount>=n+12',arg=count,polling=20)
    h.evaluate("currentWorker.postMessage({type:'state-export',requestId:900001})");h.wait_for_function('proof.chatRam',polling=20);assert h.evaluate('proof.chatRam')==[0,64]
    assert h.evaluate('proof.room.game.status')=='playing'
    shared_layouts=[shared_layout(tab) for tab in [h,g]]
   if args.screenshots:h.screenshot(path=str(out.with_name('playing.png')),full_page=True)
   first_active=time.monotonic()-play_started
   h.keyboard.up('x');g.keyboard.up('z')
   focus_recovery=None
   if args.fault=='device':
    h.evaluate((root/'scripts/foundation/gamepad_fixture.js').read_text());h.locator('.rc-game-links').get_by_role('button',name='Settings').click();h.locator('.rc-side-panel').get_by_role('button',name='Controls',exact=True).click();h.get_by_label('Input device',exact=True).select_option('0');h.get_by_role('button',name='Back',exact=True).click();h.evaluate('padConnected=false')
   elif args.fault=='focus':
    h.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true}); window.dispatchEvent(new Event('blur')); document.dispatchEvent(new Event('visibilitychange'))")
    before=h.evaluate('proof.frameCount')
    h.wait_for_function('frames=>proof.frameCount>=frames+60',arg=before,timeout=15000,polling=50)
    epoch=h.evaluate('proof.activeEpoch')
    hash_floor=max(tab.evaluate('proof.hashes.at(-1)?.frame ?? 0') for tab in [h,g])
    h.evaluate("const until=performance.now()+1200; while(performance.now()<until){}")
    stalled_frames=[tab.evaluate('proof.frameCount') for tab in [h,g]]
    for tab,frame in zip([h,g],stalled_frames):
     tab.wait_for_function("state=>proof.activeEpoch===state.epoch && proof.room.game.status==='playing' && proof.frameCount>=state.frame+24",arg={'epoch':epoch,'frame':frame},timeout=15000,polling=50)
    hash_frame=hash_floor+120
    for tab in [h,g]:
     tab.wait_for_function('frame=>proof.hashes.some(hash=>hash.frame===frame)',arg=hash_frame,timeout=15000,polling=50)
    hashes=[tab.evaluate('frame=>proof.hashes.find(hash=>hash.frame===frame)',hash_frame) for tab in [h,g]]
    assert hashes[0]==hashes[1],hashes
    focus_recovery={'epoch':epoch,'stalled_frames':stalled_frames,'resumed_frames':[tab.evaluate('proof.frameCount') for tab in [h,g]],'matching_hash':hashes[0],'statuses':[tab.evaluate('proof.room.game.status') for tab in [h,g]]}
    h.get_by_role('button',name='Pause',exact=True).click()
   else:h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   if args.screenshots:
    for role,tab in [('host',h),('guest',g)]:tab.screenshot(path=str(out.with_name(f'{role}.paused.png')),full_page=True)
    h.set_viewport_size({'width':390,'height':844});h.screenshot(path=str(out.with_name('paused-mobile.png')),full_page=True);h.set_viewport_size({'width':1280,'height':1050})
   before=paused_hashes()
   if args.fault=='device':
    open_room(h).get_by_role('button',name='Prepare to resume',exact=True).click()
    assert h.evaluate('proof.room.game.status')=='paused'
    h.locator('.rc-side-panel').get_by_role('button',name='Controls',exact=True).click();h.get_by_label('Input device',exact=True).select_option('keyboard');h.get_by_role('button',name='Back',exact=True).click()
   open_room(h).get_by_role('button',name='Prepare to resume',exact=True).click()
   h.wait_for_function("proof.room.game.ready?.includes(proof.room.chatMembership)",polling=50)
   assert h.get_by_role('button',name='Resume together',exact=True).count()==0
   assert not h.evaluate("proof.room.game.ready.includes(proof.room.slots[1].member.id)")
   open_room(g).get_by_role('button',name='Prepare to resume',exact=True).click()
   # Arm while paused: every resumed frame belongs to the scripted workload.
   h.evaluate("window.scriptKey='KeyX'");g.evaluate("window.scriptKey='KeyZ'")
   if args.delay_final_hash:g.evaluate('frame=>proof.finalHashDelay={armedFrame:frame,periodic:[]}',before[1]['frame'])
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
   route='relay' if args.relay or args.standard_fallback else 'direct'
   route_probe="""async expected=>{for(const pc of gamePeers){if(pc.connectionState!=='connected')continue;const stats=await pc.getStats();let pair;for(const value of stats.values())if(value.type==='transport'&&value.selectedCandidatePairId)pair=stats.get(value.selectedCandidatePairId);else if(value.type==='candidate-pair'&&value.selected)pair=value;if(!pair)continue;const local=stats.get(pair.localCandidateId)?.candidateType,remote=stats.get(pair.remoteCandidateId)?.candidateType;if(!local||!remote||!pair.bytesSent||!pair.bytesReceived)continue;if(expected==='relay'?local==='relay'&&remote==='relay':local!=='relay'&&remote!=='relay')return true;}return false;}"""
   for tab in [h,g]:tab.wait_for_function(route_probe,arg=route,timeout=10000)
   for tab in [h,g]:assert tab.get_by_text('Relay-only',exact=True).count()==0 and tab.get_by_text('Standard',exact=True).count()==0,'Technical transport choices leaked into shared play'
   if args.screenshots:
    h.set_viewport_size({'width':390,'height':844})
    assert h.locator('.rc-session').is_visible()
    assert h.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Mobile room overflows horizontally'
    h.screenshot(path=str(out.with_suffix('.mobile.shared-playing.png')),full_page=True)
    h.set_viewport_size({'width':1366 if args.short_viewport else 1280,'height':682 if args.short_viewport else 1050})
   if args.delay_final_hash:assert g.evaluate('proof.finalHashDelay.periodic.length')>0,'An actual periodic hash must pass between arming and final pause'
   h.get_by_role('button',name='Pause',exact=True).click()
   final=paused_hashes()
   if args.delay_final_hash:
    delayed=g.evaluate('proof.finalHashDelay')
    assert g.evaluate('proof.delayedHashes')==1
    assert delayed['requestId']==delayed['response']['requestId'] and delayed['frame']==final[1]['frame']==delayed['response']['frame'],delayed
    assert delayed['response']['hash']==final[1]['hash'],delayed
    assert all(record['requestId']!=delayed['requestId'] and record['frame']<delayed['frame'] for record in delayed['periodic']),delayed
   hashes=[normalized_periodic_hashes(tab.evaluate('proof.sentHashes'),pause,completed) for tab,pause,completed in zip([h,g],before,final)];assert hashes[0]==hashes[1], 'Every interior epoch/frame hash must be present and identical on both peers';assert len(hashes[0])>=2
   for tab in [h,g]:assert tab.evaluate(route_probe,route),'Selected transport changed before pause'
   identity=h.evaluate('proof.room.fingerprint');assert identity['romSha256']==hashlib.sha256(rom).hexdigest();assert identity['coreSha256'] in build_files.values()
   if args.delay_start:assert g.evaluate('proof.delayedStarts')==1
   if args.firefox_executable:assert firefox_driver.evidence(args.firefox_executable)==firefox_evidence,'Firefox binary changed during probe'
   if args.leave_interaction:
    for tab in [g,h]:
     tab.get_by_role('button',name='Back to Main Page').click()
     tab.get_by_role('button',name='Leave lobby' if tab==g else 'Close lobby',exact=True).click()
     tab.get_by_role('button',name='Browse lobbies →').wait_for()
   # A recovered Firefox localhost WebSocket startup interruption is still
   # recorded, while unrelated page errors continue to fail the journey.
   socket=f"{url.replace('http:','ws:',1).replace('https:','wss:',1).rstrip('/')}/coordinator/ws"
   recovered_socket_errors,fatal_errors=classify_page_errors(errors,socket,established_at, bool(args.firefox_executable))
   result={**firefox_evidence,'controlled_worker_delivery_floor_ms':args.worker_floor_ms,'recovery_order':args.retry_barrier,'source':source,'route':route,'turn_error_codes':turn.error_codes() if turn else {},'build_files':build_files,'identity':identity,'delayed_start':args.delay_start,'run_id':run_id,'result':'pass','browser_instances':[{'kind':kind,'version':b.version} for kind,b in zip(args.pair.split('-'),browsers)],'browsers':{kind:b.version for kind,b in zip(args.pair.split('-'),browsers)},'pair':args.pair,'injection':args.fault,'initial_manual_frames':args.initial_manual_frames,'target_seconds':args.seconds,'target_frames':target_frames,'active_seconds':active_seconds,'shared_layouts':shared_layouts,'focus_recovery':focus_recovery,'final':final,'seconds':round(time.monotonic()-started,2),'pause':before,'peers':[tab.evaluate('(({room,...proof})=>proof)(proof)') for tab in [h,g]],'page_errors':fatal_errors,'recovered_socket_errors':recovered_socket_errors,'established_at':established_at};assert not fatal_errors,fatal_errors
   out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','seconds':result['seconds']}))
  except Exception:
   failure={**firefox_evidence,'controlled_worker_delivery_floor_ms':args.worker_floor_ms,'build_files':build_files,'browser_instances':[{'kind':kind,'version':b.version} for kind,b in zip(args.pair.split('-'),browsers)],'browsers':{kind:b.version for kind,b in zip(args.pair.split('-'),browsers)},'pair':args.pair,'source':source,'run_id':run_id,'result':'fail','page_errors':errors,'peers':[tab.evaluate("""({proof:(({room,...p})=>p)(proof),status:document.querySelector('.rc-status')?.textContent,game:proof.room?.game,established:proof.room?.established})""") for tab in pages if not tab.is_closed()]}
   out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True);raise

finally:
 if run_id:
  (out.parent/'result-pointer.json').write_text(json.dumps({'run_id':run_id,'output':str(out.resolve())})+'\n')
 service.terminate();service.wait(timeout=5);stack.close()
