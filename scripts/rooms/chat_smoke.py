#!/usr/bin/env python3
"""Exercise bounded lobby chat, recovery, and play in real browser tabs."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(os.environ.get('RETRO_COOP_STATIC_ROOT', ROOT / 'apps/client/dist'))
ROM = STATIC / 'generated/diagnostic.nes'
parser = argparse.ArgumentParser()
parser.add_argument('--chrome', action='store_true')
parser.add_argument('--output', type=Path, default=Path('chat.local.json'))
args = parser.parse_args()
assert ROM.exists(), 'Build the client and diagnostic NES fixture first.'
started = time.monotonic()
service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                           stdout=subprocess.PIPE, text=True)
try:
    assert service.stdout
    url = json.loads(service.stdout.readline())['url']
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**({'channel': 'chrome'} if args.chrome else {}))
        errors = []

        def page(address):
            tab = browser.new_page(viewport={'width': 1280, 'height': 800})
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.add_init_script('''(() => {
              window.chatProof={room:null,sent:[]};window.chatSockets=[];
              const Native=WebSocket;
              window.WebSocket=class extends Native {
                constructor(...args){super(...args);chatSockets.push(this);
                  this.addEventListener('message',event=>{
                    const value=JSON.parse(event.data);
                    if(value.type==='room')chatProof.room=value.room;
                    if(value.type==='result'&&value.ok&&value.data?.room)
                      chatProof.room=value.data.room;
                    if(window.dropChatReplies&&(value.type==='chat'||value.data?.chatAck))
                      event.stopImmediatePropagation();
                  });
                }
                send(raw){chatProof.sent.push(JSON.parse(raw));return super.send(raw);}
              };
            })()''')
            tab.goto(address)
            return tab

        def chat(tab):
            panel = tab.locator('.rc-chat')
            panel.wait_for(state='visible')
            return panel

        def geometry(tab):
            return chat(tab).evaluate('''panel=>{
              const bounds=node=>{const r=node.getBoundingClientRect();
                return [r.x,r.y,r.width,r.height].map(Math.round)};
              return [panel,panel.querySelector('.rc-chat-history'),
                panel.querySelector('form'),panel.querySelector('input')].map(bounds);
            }''')

        def send(tab, message):
            chat(tab).get_by_role('textbox', name='Message everyone').fill(message)
            chat(tab).get_by_role('button', name='Send', exact=True).click()
            chat(tab).locator('li').filter(has_text=message).wait_for(timeout=10000)

        host = page(url)
        host.get_by_role('button', name='Host a new game').click()
        chat(host)
        before = geometry(host)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        send(host, 'Before anyone joins')
        assert geometry(host) == before, 'The first message moved chat controls.'
        invite = host.evaluate("location.origin+'/#invite='+chatProof.room.invite")
        guest = page(invite)
        guest.get_by_role('button', name='Join lobby').click()
        chat(guest)
        assert guest.locator('.rc-chat-history li').count() == 0
        host.wait_for_function('chatProof.room?.slots[1].member?.id')
        for tab in (host, guest):
            tab.wait_for_function("chatProof.room?.peers[0]?.status==='connected'", timeout=15000)
        send(guest, 'Hello before a game')
        chat(host).locator('li').filter(has_text='Hello before a game').wait_for()
        send(guest, '<img src=x onerror=alert(1)>')
        assert chat(host).locator('img').count() == 0
        assert guest.locator('canvas').get_attribute('data-frame-count') == '0'

        for index in range(3):
            send(guest, f'Bounded {index}')
        guest.set_viewport_size({'width': 390, 'height': 700})
        narrow = geometry(guest)
        assert guest.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert guest.evaluate('document.scrollingElement.scrollHeight <= innerHeight + 1')
        chat(guest).get_by_role('textbox', name='Message everyone').fill('Retry after limit')
        chat(guest).get_by_role('button', name='Send', exact=True).click()
        retry = chat(guest).get_by_role('button', name='Retry', exact=True)
        retry.wait_for(timeout=10000)
        assert retry.is_disabled()
        assert chat(guest).get_by_role('textbox', name='Message everyone').input_value() == 'Retry after limit'
        assert geometry(guest) == narrow, 'Rate limit feedback moved chat controls.'
        expect(retry).to_be_enabled(timeout=15000)
        retry.click()
        chat(host).locator('li').filter(has_text='Retry after limit').wait_for()
        assert chat(host).locator('li').filter(has_text='Retry after limit').count() == 1
        guest.screenshot(path=str(args.output.with_suffix('.narrow.png')))

        guest.evaluate('window.dropChatReplies=true')
        chat(guest).get_by_role('textbox', name='Message everyone').fill('Uncertain delivery')
        chat(guest).get_by_role('button', name='Send', exact=True).click()
        chat(host).locator('li').filter(has_text='Uncertain delivery').wait_for()
        retry = chat(guest).get_by_role('button', name='Retry', exact=True)
        retry.wait_for(timeout=15000)
        guest.evaluate('window.dropChatReplies=false')
        retry.click()
        chat(guest).locator('li').filter(has_text='Uncertain delivery').wait_for()
        assert chat(host).locator('li').filter(has_text='Uncertain delivery').count() == 1
        assert geometry(guest) == narrow, 'Delivery recovery moved chat controls.'

        guest.evaluate('chatSockets.at(-1).close()')
        guest.get_by_role('button', name='Retry connection').wait_for()
        chat(guest).get_by_role('textbox', name='Message everyone').fill('After reconnect')
        assert chat(guest).get_by_role('button', name='Send', exact=True).is_disabled()
        assert chat(host).locator('li').filter(has_text='After reconnect').count() == 0
        guest.get_by_role('button', name='Retry connection').click()
        expect(chat(guest).get_by_role('button', name='Send', exact=True)).to_be_enabled(timeout=15000)
        chat(guest).get_by_role('button', name='Send', exact=True).click()
        chat(host).locator('li').filter(has_text='After reconnect').wait_for()
        assert chat(host).locator('li').filter(has_text='After reconnect').count() == 1

        host.locator('input[aria-label="NES cartridge file"]').set_input_files(ROM)
        expect(host.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
        expect(guest.get_by_role('button', name='Ready', exact=True)).to_be_enabled(timeout=30000)
        host.get_by_role('button', name='Ready', exact=True).click()
        guest.get_by_role('button', name='Ready', exact=True).click()
        expect(host.get_by_role('button', name='Start →')).to_be_enabled(timeout=30000)
        host.get_by_role('button', name='Start →').click()
        for tab in (host, guest):
            tab.locator('[data-page="playing"]').wait_for(timeout=30000)
        playing = geometry(host)
        send(guest, 'Chat while playing')
        chat(host).locator('li').filter(has_text='Chat while playing').wait_for()
        assert geometry(host) == playing, 'Shared play chat moved after a message.'
        assert host.get_by_test_id('room-slot').count() == 5
        host.screenshot(path=str(args.output.with_suffix('.playing.png')))
        assert not errors, errors
        result = {'result': 'pass', 'browser': browser.version,
                  'pre_game_chat_and_no_join_history': True,
                  'plain_text_no_html': True,
                  'rate_limit_explicit_retry': True,
                  'lost_reply_deduplicated': True,
                  'disconnect_requires_reconnect': True,
                  'fixed_chat_in_lobby_and_play': True,
                  'seconds': round(time.monotonic() - started, 2),
                  'page_errors': errors}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=10)
