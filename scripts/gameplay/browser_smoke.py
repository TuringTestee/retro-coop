"""Production worker/barrier proof. The host is held at its genuine power-on state before shared start."""
import argparse,json,os,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--output',default='/tmp/gameplay.json');parser.add_argument('--seconds',type=int,choices=[8,30,600],default=8);parser.add_argument('--pair',choices=['Chrome-Chrome','Firefox-Firefox','Chrome-Firefox'],default='Chrome-Chrome');parser.add_argument('--firefox-executable');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];out=Path(args.output);run_id=os.environ.get('GAMEPLAY_RUN_ID');started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,'TURN_URLS':'','TURN_SECRET':''},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
 with sync_playwright() as p:
  browsers={kind:(p.chromium.launch(ignore_default_args=['--mute-audio']) if kind=='Chrome' else p.firefox.launch(**({'executable_path':args.firefox_executable} if args.firefox_executable else {}))) for kind in set(args.pair.split('-'))};errors=[];kinds=iter(args.pair.split('-'))
  def page():
   tab=browsers[next(kinds)].new_page(viewport={'width':1280,'height':1050});tab.on('pageerror',lambda e:errors.append(str(e)))
   tab.add_init_script('''
    const raf=requestAnimationFrame.bind(window),cancel=cancelAnimationFrame.bind(window),pending=new Map();let held=true,id=0;
    window.requestAnimationFrame=fn=>held?(pending.set(++id,fn),id):raf(fn);
    window.cancelAnimationFrame=n=>held?pending.delete(n):cancel(n);
    window.releaseFrames=()=>{held=false;for(const fn of pending.values())raf(fn);pending.clear()};
    window.proof={hashes:[],rooms:[],frames:[],frameCount:0,sentHashes:[],timing:{workerMs:0,workerMax:0,frameGaps:[],waitMs:0,waitCount:0,delays:[]}};
    const ds=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(typeof data==='string'){const d=JSON.parse(data);if(d.kind==='hash')proof.sentHashes.push(d);}return ds.call(this,data)};
    let waitStart=0,lastFrame=0,workerStart=0;
    new MutationObserver(()=>{const waiting=document.querySelector('[data-testid=game-status]')?.textContent.includes('Waiting for the other player’s input');if(waiting&&!waitStart){waitStart=performance.now();proof.timing.waitCount++}else if(!waiting&&waitStart){proof.timing.waitMs+=performance.now()-waitStart;waitStart=0}}).observe(document,{subtree:true,childList:true,characterData:true});
    const W=Worker;window.Worker=class extends W{postMessage(data,...rest){if(data.type==='frame'&&data.epoch)workerStart=performance.now();return super.postMessage(data,...rest)}constructor(...a){super(...a);window.currentWorker=this;this.addEventListener('message',({data})=>{if(data.type==='state-exported'&&data.requestId===900000)proof.controllerRam=JSON.parse(new TextDecoder().decode(data.bytes.slice(72))).hardware.wram.slice(0,2);if(data.type==='state-hash')proof.hashes.push(data.info);if(data.type==='frame'&&data.epoch){const now=performance.now(),elapsed=now-workerStart;proof.timing.workerMs+=elapsed;proof.timing.workerMax=Math.max(proof.timing.workerMax,elapsed);if(lastFrame){const bucket=Math.min(200,Math.round(now-lastFrame));proof.timing.frameGaps[bucket]=(proof.timing.frameGaps[bucket]||0)+1}lastFrame=now;proof.frameCount++;proof.frames.push({epoch:data.epoch,frame:data.frame});if(proof.frames.length>12)proof.frames.shift()}})}};
    const S=WebSocket;window.WebSocket=class extends S{constructor(...a){super(...a);this.addEventListener('message',({data})=>{const e=JSON.parse(data);if(e.type==='gameStart'){proof.timing.delays.push(e.delay);lastFrame=0;}if(e.type==='room'){proof.room=e.room;proof.rooms.push({established:e.room.established,status:e.room.game?.status})}})}};
   ''');tab.goto(url);return tab
  try:
   h=page();g=page()
   h.set_input_files('input[type=file]',{'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});h.get_by_test_id('room-view').wait_for()
   invite=h.get_by_label('Room invitation',exact=True).input_value();g.goto(invite);g.reload();g.get_by_role('button',name='Retry join / Join',exact=True).click();g.get_by_test_id('room-view').wait_for()
   assert h.get_by_test_id('frames').inner_text()=='0 frames'
   g.set_input_files('input[type=file]',{'name':'matching.nes','mimeType':'application/octet-stream','buffer':rom})
   for tab in [h,g]:tab.wait_for_function("proof.room?.established && proof.room.game.status==='playing'",timeout=15000,polling=50)
   play_started=time.monotonic()
   for tab in [h,g]:tab.evaluate('releaseFrames()')
   h.locator('canvas').focus();h.keyboard.down('x');g.locator('canvas').focus();g.keyboard.down('z')
   for tab in [h,g]:tab.wait_for_function('proof.frameCount>=240',timeout=20000,polling=50)
   for tab in [h,g]:
    tab.evaluate("currentWorker.postMessage({type:'state-export',requestId:900000})");tab.wait_for_function('proof.controllerRam',polling=50);assert tab.evaluate('proof.controllerRam')==[128,64]
   first_active=time.monotonic()-play_started
   h.keyboard.up('x');g.keyboard.up('z');h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   before=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert before[0]==before[1],before
   for tab in [h,g]:tab.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
   h.get_by_role('button',name='Resume together',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='playing'",timeout=15000,polling=50)
   resumed=time.monotonic()
   for tab in [h,g]:tab.wait_for_function('n=>proof.frameCount>=n',arg=max(360,args.seconds*60),timeout=(args.seconds+30)*1000,polling=100)
   active_seconds=round(first_active+time.monotonic()-resumed,2)
   h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   final=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert final[0]==final[1],final
   hashes=[tab.evaluate('proof.sentHashes') for tab in [h,g]];assert hashes[0]==hashes[1], 'Every epoch/frame hash must be present and identical on both peers';assert len(hashes[0])>=2
   result={'run_id':run_id,'result':'pass','browsers':{kind:b.version for kind,b in browsers.items()},'pair':args.pair,'target_seconds':args.seconds,'active_seconds':active_seconds,'final':final,'seconds':round(time.monotonic()-started,2),'pause':before,'peers':[tab.evaluate('(({room,...proof})=>proof)(proof)') for tab in [h,g]],'page_errors':errors};assert not errors,errors
   out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','seconds':result['seconds']}));[browser.close() for browser in browsers.values()]
  except Exception:
   failure={'run_id':run_id,'result':'fail','page_errors':errors,'peers':[tab.evaluate("""({proof:(({room,...p})=>p)(proof),status:document.querySelector('[data-testid=game-status]')?.textContent,localStatus:document.querySelector('[data-testid=player-status]')?.textContent,game:proof.room?.game,established:proof.room?.established})""") for tab in [h,g]]}
   out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True);raise

finally:
 if run_id:
  (out.parent/'result-pointer.json').write_text(json.dumps({'run_id':run_id,'output':str(out.resolve())})+'\n')
 service.terminate();service.wait(timeout=5)
