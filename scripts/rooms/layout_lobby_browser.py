"""Five real lobby members: fixed regions, recovery, browser zoom and keyboard access."""
import argparse,contextlib,json,os,subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import GeometryRecorder,control_visibility,zoom_context,browser_zoom,verify_zoom,artifact_provenance
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/peer'))
from fixture import LocalTurn
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--relay',action='store_true');parser.add_argument('--turnserver',default='turnserver');args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
static=Path(os.environ.get('RETRO_COOP_STATIC_ROOT',ROOT/'apps/client/dist'));started=time.monotonic();provenance=artifact_provenance(ROOT,static);results=[];errors=[]
with contextlib.ExitStack() as stack:
 turn=stack.enter_context(LocalTurn(args.turnserver)) if args.relay else None
 env={**os.environ,**(turn.environment() if turn else {'TURN_URLS':'','TURN_SECRET':''}),'TURN_PAIR_LIMIT':'10'}
 server=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=ROOT,env=env,stdout=subprocess.PIPE,text=True);stack.callback(server.wait);stack.callback(server.terminate);url=json.loads(server.stdout.readline())['url']
 p=stack.enter_context(sync_playwright());context,zoom_worker=stack.enter_context(zoom_context(p,{'width':1366,'height':682},['--use-fake-device-for-media-stream']));browser=p.chromium.launch();stack.callback(browser.close);other=browser.new_context(viewport={'width':1366,'height':682});pages=[context.new_page() for _ in range(2)]+[other.new_page() for _ in range(3)];host,guest=pages[:2]
 for page in pages:
  page.set_default_timeout(20000);page.add_init_script(path=ROOT/'scripts/gameplay/fixture.js');page.add_init_script("const originalSend=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(window.holdCheckpoint&&this.label==='retro-coop-checkpoint'&&typeof data!=='string')return;return originalSend.call(this,data)}")
  if args.relay:page.add_init_script("sessionStorage.setItem('retro-coop-connection-policy','relay')")
  page.on('pageerror',lambda error:errors.append(str(error)))
 def finish(record,label,required=()):
  results.append(record.finish(args.output/(label+'.json'),required=required))
 def action(record,fn,predicate=None):
  record.allow_user_scroll();fn()
  if predicate:host.wait_for_function(predicate)
  host.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');record.allow_user_scroll(False)
 def paused():
  for page in pages:page.wait_for_function("proof.room.game.status==='paused'")
 try:
  host.goto(url);host.evaluate("releaseFrames()");host.get_by_role('button',name='Create game',exact=True).click();host.set_input_files('input[type=file]',static/'generated/diagnostic.nes');host.get_by_role('button',name='Create room',exact=True).click();host.get_by_role('button',name='Copy invite',exact=True).wait_for();invite=host.get_by_label('Room invitation',exact=True).input_value()
  record=GeometryRecorder(host,'waiting-close-reopen')
  slot=host.locator('[data-slot-id="slot-5"]');action(record,lambda:slot.get_by_role('button',name='Close slot',exact=True).click(),"proof.room.slots[4].open===false");record.mark('closed');action(record,lambda:slot.get_by_role('button',name='Open slot',exact=True).click(),"proof.room.slots[4].open===true");record.mark('reopened');finish(record,'waiting-close-reopen')
  record=GeometryRecorder(host,'waiting-five-acquisition')
  for page in pages[1:]:
   page.goto(invite);page.evaluate("releaseFrames()");page.get_by_role('button',name='Join room',exact=True).click();page.wait_for_function("proof.room?.matches&&proof.room.slots.find(s=>s.member?.id===proof.room.chatMembership)?.member.acquisition==='loaded'");record.mark('member-loaded')
  for page in pages:page.wait_for_function("proof.room.occupancy===5&&proof.room.peers.every(p=>p.status==='connected')")
  finish(record,'waiting-five-acquisition',required=['slot-1','slot-5','slot-5/status'])
  record=GeometryRecorder(host,'remove-cancel')
  slot=host.locator('[data-slot-id="slot-5"]');action(record,lambda:slot.get_by_role('button',name='Remove member',exact=True).click(),"document.activeElement?.hasAttribute('data-confirm-remove')");record.mark('confirm');host.screenshot(path=str(args.output/'remove-confirm.png'));action(record,lambda:slot.get_by_role('button',name='Cancel removal',exact=True).click(),"document.activeElement?.hasAttribute('data-remove-member')");record.mark('cancel');finish(record,'remove-cancel')
  guest.get_by_role('button',name='Prepare to play',exact=True).click();guest.wait_for_function('proof.room.game.ready.includes(proof.room.chatMembership)');host.get_by_role('button',name='Start game',exact=True).click()
  for page in pages:page.evaluate('releaseFrames()')
  host.wait_for_function("proof.room.game.status==='playing'&&proof.frames.at(-1)?.frame>60")
  record=GeometryRecorder(host,'pause')
  action(record,lambda:host.get_by_role('button',name='Pause',exact=True).click());paused();record.mark('paused');finish(record,'pause')
  for index,page in enumerate(pages[:2]):
   label='host' if index==0 else 'guest'
   if args.relay:page.get_by_test_id('connection-status').filter(has_text='Relay').wait_for()
   leave=page.get_by_role('button',name='Leave room',exact=True);leave.focus();control_visibility(leave,require_focus=True)
   page.screenshot(path=str(args.output/(label+'-paused-1366x682.png')))
   record=GeometryRecorder(page,label+'-leave-confirm')
   record.allow_user_scroll();leave.press('Enter');page.wait_for_function("document.activeElement?.matches('.room-confirm button')");record.allow_user_scroll(False);record.mark('confirmation');page.screenshot(path=str(args.output/(label+'-leave-confirm.png')))
   record.allow_user_scroll();page.get_by_role('button',name='Stay in room',exact=True).click();page.wait_for_function("document.activeElement?.hasAttribute('data-leave-room')");record.allow_user_scroll(False);record.mark('cancel');finish(record,label+'-leave-confirm');control_visibility(leave,require_focus=True)
  record=GeometryRecorder(host,'voice-denied');action(record,lambda:host.get_by_role('button',name='Enable voice',exact=True).click());host.get_by_role('button',name='Try microphone again',exact=True).wait_for();record.mark('microphone-denied');finish(record,'voice-denied')
  context.grant_permissions(['microphone']);host.get_by_role('button',name='Try microphone again',exact=True).click();host.get_by_role('button',name='Mute microphone',exact=True).wait_for()
  mic=host.get_by_role('button',name='Mute microphone',exact=True);settings=host.get_by_role('button',name='Voice settings',exact=True);voice_before={'microphone':mic.bounding_box(),'settings':settings.bounding_box()}
  settings.click();host.get_by_label('Voice mode',exact=True).select_option('push');host.get_by_role('button',name='Back',exact=True).click();host.get_by_role('button',name='Hold to talk',exact=True).wait_for();host.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
  # No click/focus/scroll operation before these checks: all immediate actions
  # must be discoverable together on the normal desktop rail.
  immediate=[control_visibility(target) for target in [mic,host.get_by_role('button',name='Hold to talk',exact=True),settings]]
  for name,target in [('microphone',mic),('settings',settings)]:
   assert all(abs(target.bounding_box()[axis]-voice_before[name][axis])<=1 for axis in ['x','y','width','height']), (name,voice_before,target.bounding_box())
  host.screenshot(path=str(args.output/'voice-push-actions.png'))
  host.evaluate('window.holdCheckpoint=true');record=GeometryRecorder(host,'pending-role-cancel');action(record,lambda:host.get_by_label('Slot 3 role',exact=True).select_option('player2'),"proof.room.game.pending?.status==='synchronizing'");record.mark('synchronizing');host.wait_for_function("proof.room.game.pending?.status==='failed'",timeout=25000);record.mark('role-failed');action(record,lambda:host.get_by_role('button',name='Retry role change',exact=True).click(),"proof.room.game.pending?.status==='synchronizing'");record.mark('retrying');host.screenshot(path=str(args.output/'role-pending.png'));action(record,lambda:host.get_by_role('button',name='Cancel role change',exact=True).click(),"!proof.room.game.pending&&proof.room.game.status==='paused'");record.mark('cancelled');finish(record,'pending-role-cancel');host.evaluate('window.holdCheckpoint=false')
  # Each profile retains all five physical rows; controls are reached by keyboard,
  # and their full focus outlines must fit every declared scroll viewport.
  profiles=[('wide',1440,900,1),('regression',1366,682,1),('short',1024,600,1),('narrow',390,700,1),('zoom200',1280,720,2),('effective320',640,720,2)]
  profile_results=[]
  for label,width,height,zoom in profiles:
   host.set_viewport_size({'width':width,'height':height});receipt=browser_zoom(host,zoom_worker,zoom);verify_zoom(zoom_worker,receipt)
   record=GeometryRecorder(host,label+'-keyboard');record.allow_user_scroll();host.get_by_role('button',name='Leave room',exact=True).focus();checked=[]
   # Focus the exact target, then traverse actual keyboard input into the next
   # control. Focus itself is an intentional navigation and may scroll owners.
   for target in [host.get_by_role('button',name='Leave room',exact=True),host.get_by_role('button',name='Mute microphone',exact=True),host.get_by_role('button',name='Hold to talk',exact=True),host.get_by_role('button',name='Voice settings',exact=True),host.get_by_label('Slot 5 role',exact=True),host.get_by_role('button',name='Remove member',exact=True).last]:
    target.focus();target.press('Tab');host.keyboard.press('Shift+Tab');host.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');checked.append(control_visibility(target,require_focus=True))
   host.get_by_role('button',name='Leave room',exact=True).focus();host.keyboard.press('Enter');host.wait_for_function("document.activeElement?.matches('.room-confirm button')");checked.append(control_visibility(host.get_by_role('button',name='Confirm leave',exact=True),require_focus=True));host.keyboard.press('Tab');host.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');checked.append(control_visibility(host.get_by_role('button',name='Stay in room',exact=True),require_focus=True));host.keyboard.press('Enter');host.wait_for_function("document.activeElement?.hasAttribute('data-leave-room')");checked.append(control_visibility(host.get_by_role('button',name='Leave room',exact=True),require_focus=True))
   record.mark('keyboard-endpoints');record.allow_user_scroll(False);finish(record,label+'-keyboard');host.screenshot(path=str(args.output/(label+'-slots.png')));profile_results.append({'label':label,'zoom':receipt,'focus':checked})
  assert not errors,errors
  assert artifact_provenance(ROOT,static)==provenance,'Static build changed during proof'
  result={'result':'pass','source':provenance,'relay':args.relay,'members':5,'geometry':results,'profiles':profile_results,'immediateVoiceActions':immediate,'errors':errors,'elapsed':round(time.monotonic()-started,2)};(args.output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({'result':'pass','transitions':len(results),'elapsed':result['elapsed']}))
 except Exception:
  for index,page in enumerate(pages):
   with contextlib.suppress(Exception):page.screenshot(path=str(args.output/f'failure-{index}.png'))
  raise
