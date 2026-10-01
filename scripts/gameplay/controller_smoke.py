"""Public slot roles, native controller ownership, and held-device release."""
import json,time

def run(host,guest,out,root,errors,source,build_files):
 started=time.monotonic();pages=[host,guest];results=[]
 def native(page):
  return page.evaluate("""()=>new Promise(resolve=>{const requestId=900091;function done({data}){if(data.requestId===requestId){currentWorker.removeEventListener('message',done);resolve(data.info)}}currentWorker.addEventListener('message',done);currentWorker.postMessage({type:'state-hash',requestId})})""")
 def pause():
  host.get_by_role('button',name='Pause',exact=True).click()
  for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
  deadline=time.monotonic()+5
  while True:
   states=[native(page) for page in pages]
   if states[0]==states[1]:return states[0]
   assert time.monotonic()<deadline,states
   time.sleep(.02)
 def assign(slot,role):
  before=native(host);old=host.evaluate('proof.room.game.epoch')
  if host.get_by_test_id('room-slot').count()==0:host.get_by_role('button',name='Players',exact=True).click()
  actions=host.locator(f'[data-slot-id=slot-{slot}] [data-slot-action]')
  actions.select_option(f'role:{role}')
  for page in pages:page.wait_for_function("v=>proof.room.game.status==='playing'&&proof.room.game.epoch!==v",arg=old,polling=20)
  actions.focus()
  host.wait_for_function("document.activeElement?.hasAttribute('data-slot-action')")
  host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
  results.append({'assigned_slot':slot,'role':role,'preserved_boundary':before})
 def sample(expected,label):
  for page in pages:
   count=page.evaluate('proof.frameCount');page.wait_for_function('n=>proof.frameCount>=n+18',arg=count,polling=20)
   page.evaluate("proof.controllerRam=undefined;currentWorker.postMessage({type:'state-export',requestId:900000})");page.wait_for_function('proof.controllerRam',polling=20)
   assert page.evaluate('proof.controllerRam')==expected,(label,page.evaluate('proof.controllerRam'))
  results.append({'mapping':label,'both_native_controller_ram':expected})
 baseline=pause();host.screenshot(path=str(out.with_suffix('.before.png')))
 assign(2,'player1')
 for page,key in [(host,'x'),(guest,'z')]:page.locator('canvas').focus();page.keyboard.up(key);page.keyboard.down(key)
 sample([64,128],'member P1, host P2');pause()
 # A held physical pad must be released when checkpoint/role ownership changes.
 guest.evaluate((root/'scripts/foundation/gamepad_fixture.js').read_text());guest.get_by_role('button',name='Settings',exact=True).click();guest.get_by_label('Input device',exact=True).select_option('0');guest.get_by_role('button',name='Back',exact=True).click();guest.evaluate('padButtons=[0]')
 assign(1,'observer')
 host.locator('canvas').focus();host.evaluate("window.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyX',repeat:true}))")
 sample([0,0],'held pad released and host observer input ignored')
 guest.evaluate('padButtons=[]');guest.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');guest.evaluate('padButtons=[0]');guest.locator('canvas').focus();guest.evaluate("window.gameFault='old-epoch'")
 sample([128,0],'single P1 owner, neutral unassigned P2');assert guest.evaluate('window.gameFault===undefined');pause()
 assign(1,'player1')
 host.locator('canvas').focus();host.keyboard.up('x');host.keyboard.down('x')
 sample([128,0],'host P1, former owner remains observer despite held pad')
 final=pause()
 for page in pages:
  if page.get_by_test_id('room-slot').count()==0:page.get_by_role('button',name='Players',exact=True).click()
  assert page.get_by_test_id('room-slot').count()==5
  page.locator('.room-panel').evaluate('(panel)=>panel.scrollTop=0')
 host.screenshot(path=str(out.with_suffix('.after.png')));guest.screenshot(path=str(out.with_suffix('.member.png')))
 assert not errors,errors
 result={'result':'pass','source':source,'build_files':build_files,'scenarios':results,'initial_native_state':baseline,'final_equal_native_state':final,'cancel_recovery_owner':'five_slots_smoke.py public role cancellation and retry','page_errors':errors,'seconds':round(time.monotonic()-started,2)}
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result
