#!/usr/bin/env python3
"""Exercise protected room creation, directory and invitation admission in Chromium."""
import json,os,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2]
screens=Path(os.environ['RETRO_COOP_ACCESS_OUTPUT']) if 'RETRO_COOP_ACCESS_OUTPUT' in os.environ else None
if screens: screens.mkdir(parents=True,exist_ok=True)
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,env={**os.environ,'COORDINATOR_EMPTY_OFFERS':'super-tilt-bro-pal'},stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url']
 with sync_playwright() as p:
  browser=p.chromium.launch()
  host=browser.new_context(permissions=['clipboard-read','clipboard-write'],viewport={'width':1280,'height':800}).new_page()
  host.goto(url)
  host.get_by_role('button',name='Create game',exact=True).click()
  host.locator('input[type=file]').set_input_files(root/'apps/client/dist/generated/diagnostic.nes')
  host.get_by_label('Room access').select_option('protected')
  host.get_by_label('Room password').fill('blue-sky-room')
  host.get_by_role('button',name='Create room',exact=True).click()
  host.get_by_test_id('room-view').wait_for(state='attached')
  host.get_by_role('button',name='Copy invite',exact=True).click()
  invite=host.evaluate('navigator.clipboard.readText()')
  guest=browser.new_page(viewport={'width':1280,'height':800})
  guest.goto(url)
  if screens: guest.screenshot(path=str(screens/'public-rooms.png'))
  guest.locator('.room-list li').filter(has_text='Password required').get_by_role('button',name='Join',exact=True).first.click()
  if screens: guest.screenshot(path=str(screens/'password-step.png'))
  guest.get_by_label('Room password').fill('wrong-password')
  guest.get_by_role('button',name='Join room',exact=True).click()
  guest.get_by_role('alert').get_by_text("Password didn't work. Try again.",exact=True).wait_for()
  if screens: guest.screenshot(path=str(screens/'wrong-password.png'))
  assert guest.get_by_test_id('room-view').count()==0
  guest.get_by_label('Room password').fill('blue-sky-room')
  guest.get_by_role('button',name='Join room',exact=True).click()
  guest.get_by_test_id('room-view').wait_for(state='attached')
  assert guest.locator('#room-heading').inner_text()==host.locator('#room-heading').inner_text()
  invited=browser.new_page(viewport={'width':390,'height':800})
  invited.goto(invite)
  invited.get_by_role('button',name='Join room',exact=True).click()
  invited.get_by_label('Room password').fill('blue-sky-room')
  invited.locator('.room-password-dialog').get_by_role('button',name='Join room',exact=True).click()
  invited.get_by_test_id('room-view').wait_for(state='attached')
  if screens: invited.screenshot(path=str(screens/'joined-mobile.png'))
  host.get_by_text('Room settings',exact=True).click()
  host.get_by_role('button',name='Change password',exact=True).click()
  host.get_by_label('New room password').fill('green-hill-room')
  host.get_by_role('button',name='Save new password',exact=True).click()
  host.get_by_text('Room access: Password protected',exact=True).wait_for()
  changed=browser.new_page()
  changed.goto(invite)
  changed.get_by_role('button',name='Join room',exact=True).click()
  changed.get_by_label('Room password').fill('blue-sky-room')
  changed.locator('.room-password-dialog').get_by_role('button',name='Join room',exact=True).click()
  changed.locator('.room-password-dialog [role=alert]').get_by_text("Password didn't work. Try again.",exact=True).wait_for()
  changed.get_by_label('Room password').fill('green-hill-room')
  changed.locator('.room-password-dialog').get_by_role('button',name='Join room',exact=True).click()
  try: changed.get_by_test_id('room-view').wait_for(state='attached',timeout=5000)
  except Exception:
   print('changed status:',changed.locator('.room-panel').inner_text());raise
  host.get_by_role('button',name='Make public',exact=True).click()
  host.get_by_role('button',name='Confirm public access',exact=True).click()
  host.get_by_text('Room access: Public',exact=True).wait_for()
  print(json.dumps({'protected_create':True,'listed_locked':True,'wrong_password_denied':True,'correct_password_joined':True,'invite_password_joined':True,'password_change':True,'public_change':True}))
  browser.close()
finally:
 service.terminate();service.wait(timeout=10)
