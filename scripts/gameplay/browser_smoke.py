"""Production worker/barrier proof. The host is held at its genuine power-on state before shared start."""
import argparse,json,os,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--output',default='/tmp/gameplay.json');parser.add_argument('--seconds',type=int,default=8);args=parser.parse_args()
root=Path(__file__).resolve().parents[2];out=Path(args.output);started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,'TURN_URLS':'','TURN_SECRET':''},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
 with sync_playwright() as p:
  browser=p.chromium.launch(ignore_default_args=['--mute-audio']);errors=[]
  def page():
   tab=browser.new_page(viewport={'width':1280,'height':1050});tab.on('pageerror',lambda e:errors.append(str(e)))
   tab.add_init_script('''
    const raf=requestAnimationFrame.bind(window),cancel=cancelAnimationFrame.bind(window),pending=new Map();let held=true,id=0;
    window.requestAnimationFrame=fn=>held?(pending.set(++id,fn),id):raf(fn);
    window.cancelAnimationFrame=n=>held?pending.delete(n):cancel(n);
    window.releaseFrames=()=>{held=false;for(const fn of pending.values())raf(fn);pending.clear()};
    window.proof={hashes:[],rooms:[],frames:[]};
    const W=Worker;window.Worker=class extends W{constructor(...a){super(...a);this.addEventListener('message',({data})=>{if(data.type==='state-hash')proof.hashes.push(data.info);if(data.type==='frame'&&data.epoch)proof.frames.push({epoch:data.epoch,frame:data.frame})})}};
    const S=WebSocket;window.WebSocket=class extends S{constructor(...a){super(...a);this.addEventListener('message',({data})=>{const e=JSON.parse(data);if(e.type==='room'){proof.room=e.room;proof.rooms.push({established:e.room.established,status:e.room.game?.status})}})}};
   ''');tab.goto(url);return tab
  try:
   h=page();g=page()
   h.set_input_files('input[type=file]',{'name':'original.nes','mimeType':'application/octet-stream','buffer':rom});h.get_by_test_id('room-view').wait_for()
   invite=h.get_by_label('Room invitation',exact=True).input_value();g.goto(invite);g.reload();g.get_by_role('button',name='Retry join / Join',exact=True).click();g.get_by_test_id('room-view').wait_for()
   assert h.get_by_test_id('frames').inner_text()=='0 frames'
   g.set_input_files('input[type=file]',{'name':'matching.nes','mimeType':'application/octet-stream','buffer':rom})
   for tab in [h,g]:tab.wait_for_function("proof.room?.established && proof.room.game.status==='playing'",timeout=15000,polling=50)
   for tab in [h,g]:tab.evaluate('releaseFrames()')
   h.locator('canvas').focus();h.keyboard.down('KeyX')
   for tab in [h,g]:tab.wait_for_function('proof.frames.length>=240',timeout=20000,polling=50)
   h.keyboard.up('KeyX');h.get_by_role('button',name='Pause',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='paused'",timeout=15000,polling=50)
   before=[tab.evaluate('proof.hashes.at(-1)') for tab in [h,g]];assert before[0]==before[1],before
   for tab in [h,g]:tab.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
   h.get_by_role('button',name='Resume together',exact=True).click()
   for tab in [h,g]:tab.wait_for_function("proof.room.game.status==='playing'",timeout=15000,polling=50)
   for tab in [h,g]:tab.wait_for_function('proof.frames.length>=360',timeout=15000,polling=50)
   result={'result':'pass','browser':browser.version,'seconds':round(time.monotonic()-started,2),'pause':before,'peers':[tab.evaluate('proof') for tab in [h,g]],'page_errors':errors};assert not errors,errors
   out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':'pass','seconds':result['seconds']}));browser.close()
  except Exception:
   failure={'result':'fail','page_errors':errors,'peers':[tab.evaluate('({proof,status:document.body.innerText})') for tab in [h,g]]}
   out.write_text(json.dumps(failure,indent=2)+'\n');print(json.dumps(failure),flush=True);raise

finally:
 service.terminate();service.wait(timeout=5)
