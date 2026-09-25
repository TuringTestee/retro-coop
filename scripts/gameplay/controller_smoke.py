"""Actual production controller mapping, consent, frame/hash and held-device proof."""
import json,time

def run(host,guest,out,root,errors,source,build_files):
 started=time.monotonic();pages=[host,guest];results=[]
 def status(value):
  for page in pages:page.wait_for_function('s=>proof.room.game.status===s',arg=value,polling=20)
 def pause():
  host.get_by_role('button',name='Pause',exact=True).click();status('paused')
  hashes=[page.evaluate('proof.hashes.at(-1)') for page in pages];assert hashes[0]==hashes[1],hashes
  return hashes[0]
 def settings():
  for page in pages:
   page.locator('.room-panel').wait_for(state='visible')
   page.locator('details.session-settings').evaluate('(node)=>node.open=false')
   page.locator('details.controller-disclosure').evaluate('(node)=>node.open=true')
   layout=page.evaluate("""()=>{const panel=document.querySelector('.room-panel');return {documentHeight:document.documentElement.scrollHeight,viewportHeight:innerHeight,panelHeight:panel.clientHeight,panelScrollHeight:panel.scrollHeight}}""")
   assert layout['documentHeight']<=layout['viewportHeight'] and layout['panelHeight']<=layout['viewportHeight'],layout
 def propose(mode,p1):
  host.get_by_label('Controller mode',exact=True).select_option(mode);host.get_by_label('P1 owner',exact=True).select_option(p1)
  host.get_by_role('button',name='Request assignment',exact=True).click()
  for page in pages:page.get_by_role('button',name='Accept assignment',exact=True).wait_for()
 def consent(mode,p1):
  before=[page.evaluate('proof.frameCount') for page in pages]
  host.get_by_role('button',name='Accept assignment',exact=True).focus();host.keyboard.press('Enter');host.wait_for_function("document.activeElement?.dataset.testid==='controller-mode'")
  assert host.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).is_disabled()
  assert host.evaluate('proof.room.game.controllers.mode')!=mode or host.evaluate('proof.room.game.controllers.p1')!=p1
  guest.get_by_role('button',name='Accept assignment',exact=True).focus();guest.keyboard.press('Enter');guest.wait_for_function("document.activeElement?.dataset.testid==='controller-mode'")
  for page in pages:page.wait_for_function('v=>!proof.room.game.controllerProposal&&proof.room.game.controllers.mode===v[0]&&proof.room.game.controllers.p1===v[1]',arg=[mode,p1],polling=20)
  assert before==[page.evaluate('proof.frameCount') for page in pages]
  for page,role in [(host,'host'),(guest,'guest')]:
   card=page.locator('.play-controls')
   if mode=='shared':
    assert 'Shared P1' in card.inner_text()
    assert ('Your input is idle.' in card.inner_text()) == (role!=p1)
    assert card.locator('.play-bindings').count() == (1 if role==p1 else 0)
   else:
    assert ('Player 1' if role==p1 else 'Player 2') in card.inner_text()
  for page in pages:page.locator('.room-panel').evaluate('(panel)=>panel.scrollTop=0')
  host.screenshot(path=str(out.with_suffix(f'.sidebar-{mode}-{p1}-host.png')))
  guest.screenshot(path=str(out.with_suffix(f'.sidebar-{mode}-{p1}-guest.png')))
 def resume():
  old=host.evaluate('proof.room.game.epoch')
  for page in pages:page.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
  host.get_by_role('button',name='Resume together',exact=True).click();status('playing')
  assert host.evaluate('proof.room.game.epoch')!=old
 def sample(expected,label):
  for page in pages:
   count=page.evaluate('proof.frameCount');page.wait_for_function('n=>proof.frameCount>=n+18',arg=count,polling=20)
   page.evaluate("proof.controllerRam=undefined;currentWorker.postMessage({type:'state-export',requestId:900000})");page.wait_for_function('proof.controllerRam',polling=20)
   assert page.evaluate('proof.controllerRam')==expected,(label,page.evaluate('proof.controllerRam'))
  results.append({'mapping':label,'both_native_controller_ram':expected})
 # Native diagnostic independently reads the two controller ports into machine RAM.
 baseline=pause();settings();host.screenshot(path=str(out.with_suffix('.before.png')),mask=[host.get_by_label('Room invitation',exact=True)])
 previous=host.evaluate('proof.room.game.controllers')
 propose('shared','guest');guest.get_by_role('button',name='Decline assignment',exact=True).click()
 host.wait_for_function('!proof.room.game.controllerProposal');assert host.evaluate('proof.room.game.controllers.p1')==previous['p1'];assert host.evaluate('proof.hashes.at(-1)')==baseline
 propose('shared','guest');host.get_by_role('button',name='Cancel assignment request',exact=True).click();host.wait_for_function('!proof.room.game.controllerProposal')
 assert host.evaluate('proof.room.game.controllers.p1')==previous['p1'];assert host.evaluate('proof.hashes.at(-1)')==baseline
 propose('separate','guest');consent('separate','guest');resume()
 for page,key in [(host,'x'),(guest,'z')]:page.locator('canvas').focus();page.keyboard.up(key);page.keyboard.down(key)
 sample([64,128],'separate swapped: guest P1, host P2');pause()
 # A continuously polled selected pad remains held across the assignment change.
 guest.evaluate((root/'scripts/foundation/gamepad_fixture.js').read_text());guest.get_by_role('button',name='Settings',exact=True).click();guest.get_by_label('Input device',exact=True).select_option('0');guest.get_by_role('button',name='Back',exact=True).click();guest.evaluate('padButtons=[0]')
 propose('shared','guest');consent('shared','guest');resume();host.evaluate("window.gameFault='old-epoch'")
 host.locator('canvas').focus();host.evaluate("window.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyX',repeat:true}))")
 sample([0,0],'held keyboard repeat and gamepad suppressed after acceptance');assert host.evaluate('window.gameFault===undefined')
 guest.evaluate('padButtons=[]');guest.wait_for_function("proof.frames.at(-1).frame>20",polling=20)
 # Observe release on an animation tick before pressing again.
 guest.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
 guest.evaluate('padButtons=[0]');host.keyboard.up('x');host.keyboard.down('x')
 sample([128,0],'shared guest owner: host input cannot write P1 or P2');pause()
 host.get_by_role('button',name='Pass controller',exact=True).click();consent('shared','host');resume()
 # Guest keeps its pad physically held; only the new named host owner can write.
 host.locator('canvas').focus();host.keyboard.up('x');host.keyboard.down('x');sample([128,0],'shared host owner after accepted pass')
 final=pause();settings()
 host.screenshot(path=str(out.with_suffix('.after.png')),mask=[host.get_by_label('Room invitation',exact=True)])
 guest.screenshot(path=str(out.with_suffix('.guest.png')),mask=[guest.get_by_label('Room invitation',exact=True)])
 assert not errors,errors
 result={'result':'pass','live_sidebar_assignment_and_idle_states':True,'source':source,'build_files':build_files,'scenarios':results,'decline_cancel_preserved_hash':baseline,'final_equal_native_hash':final,'page_errors':errors,'seconds':round(time.monotonic()-started,2)}
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return result
