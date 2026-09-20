import json,os,subprocess,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(sys.argv[1]);out=Path(sys.argv[2]);voice=len(sys.argv)>3
server=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,'TURN_URLS':'','TURN_SECRET':''},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(server.stdout.readline())['url']
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',ignore_default_args=['--mute-audio'],args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
  h=browser.new_page(viewport={'width':1280,'height':900});h.goto(url)
  h.set_input_files('input[type=file]',{'name':'fixture.nes','mimeType':'application/octet-stream','buffer':(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()});h.get_by_test_id('room-view').wait_for()
  g=browser.new_page();g.goto(h.get_by_label('Room invitation',exact=True).input_value());g.get_by_role('button',name='Retry join / Join',exact=True).click()
  for t in [h,g]:t.wait_for_function("document.querySelector('[data-testid=connection-status]')?.textContent.includes('Route: direct')",timeout=25000)
  if voice:
   for t in [h,g]:
    t.locator('.room-panel').get_by_label('Remote voice volume',exact=False).fill('0');t.get_by_role('button',name='Enable voice',exact=True).click();t.locator('.room-panel').get_by_text('Transmitting microphone audio',exact=True).wait_for()
  if h.get_by_role('button',name='Pause',exact=True).count():h.get_by_role('button',name='Pause',exact=True).click()
  h.screenshot(path=str(out.with_suffix('.desktop.png')),full_page=True)
  h.get_by_role('button',name='Settings',exact=True).click();h.screenshot(path=str(out.with_suffix('.settings.png')),full_page=True);
  if voice:
   h.locator('dialog .voice-panel').scroll_into_view_if_needed();h.screenshot(path=str(out.with_suffix('.settings-voice.png')),full_page=True)
  h.get_by_role('button',name='Close settings',exact=True).click()
  h.set_viewport_size({'width':400,'height':1000});h.screenshot(path=str(out.with_suffix('.mobile.png')),full_page=True)
  browser.close()
finally:server.terminate();server.wait(timeout=5)
