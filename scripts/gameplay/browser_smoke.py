"""Production worker/barrier proof. The host is held at its genuine power-on state before shared start."""
import argparse,json,os,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--output',default='/tmp/gameplay.json');parser.add_argument('--seconds',type=int,choices=[8,30,600],default=8);parser.add_argument('--pair',choices=['Chrome-Chrome','Firefox-Firefox','Chrome-Firefox'],default='Chrome-Chrome');parser.add_argument('--firefox-executable');parser.add_argument('--late-join',action='store_true');parser.add_argument('--fault',choices=['none','drop-input','bad-hash','old-epoch','future-input','duplicate-input','focus'],default='none');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];out=Path(args.output);run_id=os.environ.get('GAMEPLAY_RUN_ID');started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,'TURN_URLS':'','TURN_SECRET':''},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
 with sync_playwright() as p:
  browsers={kind:(p.chromium.launch(ignore_default_args=['--mute-audio']) if kind=='Chrome' else p.firefox.launch(**({'executable_path':args.firefox_executable} if args.firefox_executable else {}))) for kind in set(args.pair.split('-'))};errors=[];kinds=iter(args.pair.split('-'))
  def page():
   tab=browsers[next(kinds)].new_page(viewport={'width':1280,'height':1050});tab.on('pageerror',lambda e:errors.append(str(e)))
   tab.add_init_script(path=root/'scripts/gameplay/fixture.js');tab.goto(url);return tab
  try:
   h=page();g=page()
   h.set_input_files('input[type=file]',{'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});h.get_by_test_id('room-view').wait_for()
   if args.late_join:
    h.evaluate('releaseFrames()');h.wait_for_function("parseInt(document.querySelector('[data-testid=frames]').textContent)>=30",polling=50)
   invite=h.get_by_label('Room invitation',exact=True).input_value();g.goto(invite);g.reload();g.get_by_role('button',name='Retry join / Join',exact=True).click();g.get_by_test_id('room-view').wait_for()
   if not args.late_join:assert h.get_by_test_id('frames').inner_text()=='0 frames'
   g.set_input_files('input[type=file]',{'name':'matching.nes','mimeType':'application/octet-stream','buffer':rom})
   if args.late_join:
    for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='late_join'",timeout=15000,polling=50)
    observed=h.evaluate('proof.hashes.at(-1)');assert observed['frame']>=30 and not observed['fresh']
    count=h.get_by_test_id('frames').inner_text();h.wait_for_timeout(250);assert h.get_by_test_id('frames').inner_text()==count
    assert all(not tab.evaluate('proof.room.established') for tab in [h,g])
    result={'result':'pass','scenario':'progressed host pauses without reset','host_state':observed,'host_frames':count,'lease_preserved':g.evaluate('proof.room.reservationUntil>Date.now()'),'seconds':round(time.monotonic()-started,2),'page_errors':errors};assert result['lease_preserved'] and not errors
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));[browser.close() for browser in browsers.values()];raise SystemExit(0)
   for tab in [h,g]:tab.wait_for_function("proof.room?.established && proof.room.game.status==='playing'",timeout=15000,polling=50)
   play_started=time.monotonic()
   for tab in [h,g]:tab.evaluate('releaseFrames()')
   h.locator('canvas').focus();h.keyboard.down('x');g.locator('canvas').focus();g.keyboard.down('z')
   for tab in [h,g]:tab.wait_for_function('proof.frameCount>=240',timeout=20000,polling=50)
   for tab in [h,g]:
    tab.evaluate("currentWorker.postMessage({type:'state-export',requestId:900000})");tab.wait_for_function('proof.controllerRam',polling=50);assert tab.evaluate('proof.controllerRam')==[128,64]
   first_active=time.monotonic()-play_started
   h.keyboard.up('x');g.keyboard.up('z')
   if args.fault=='focus':h.evaluate("window.dispatchEvent(new Event('blur'))")
   else:h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   before=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert before[0]==before[1],before
   if args.fault=='focus':
    h.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
    assert h.evaluate('proof.room.game.status')=='paused'
    h.evaluate("window.dispatchEvent(new Event('focus'))")
   for tab in [h,g]:tab.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
   h.get_by_role('button',name='Resume together',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='playing'",timeout=15000,polling=50)
   resumed=time.monotonic()
   if args.fault not in ['none','focus']:
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
   for tab in [h,g]:tab.wait_for_function('n=>proof.frameCount>=n',arg=max(360,args.seconds*60),timeout=(args.seconds+30)*1000,polling=100)
   active_seconds=round(first_active+time.monotonic()-resumed,2)
   h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   final=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert final[0]==final[1],final
   hashes=[tab.evaluate('proof.sentHashes') for tab in [h,g]];assert hashes[0]==hashes[1], 'Every epoch/frame hash must be present and identical on both peers';assert len(hashes[0])>=2
   result={'run_id':run_id,'result':'pass','browsers':{kind:b.version for kind,b in browsers.items()},'pair':args.pair,'injection':args.fault,'target_seconds':args.seconds,'active_seconds':active_seconds,'final':final,'seconds':round(time.monotonic()-started,2),'pause':before,'peers':[tab.evaluate('(({room,...proof})=>proof)(proof)') for tab in [h,g]],'page_errors':errors};assert not errors,errors
   out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','seconds':result['seconds']}));[browser.close() for browser in browsers.values()]
  except Exception:
   failure={'run_id':run_id,'result':'fail','page_errors':errors,'peers':[tab.evaluate("""({proof:(({room,...p})=>p)(proof),status:document.querySelector('[data-testid=game-status]')?.textContent,localStatus:document.querySelector('[data-testid=player-status]')?.textContent,game:proof.room?.game,established:proof.room?.established})""") for tab in [h,g]]}
   out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True);raise

finally:
 if run_id:
  (out.parent/'result-pointer.json').write_text(json.dumps({'run_id':run_id,'output':str(out.resolve())})+'\n')
 service.terminate();service.wait(timeout=5)
