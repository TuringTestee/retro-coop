#!/usr/bin/env python3
"""A delayed Kick must not remove a new member in the same lobby slot."""

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path('moderation.local.json'))
args = parser.parse_args()
started = time.monotonic()
service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                           env={**os.environ, 'TURN_URLS': '', 'TURN_SECRET': ''},
                           stdout=subprocess.PIPE, text=True)
try:
    assert service.stdout
    url = json.loads(service.stdout.readline())['url']
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            channel='chromium', ignore_default_args=['--mute-audio'],
            args=['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'])
        errors = []

        def page(address):
            tab = browser.new_page(viewport={'width': 1280, 'height': 800})
            tab.context.grant_permissions(['microphone'])
            tab.on('pageerror', lambda error: errors.append(str(error)))
            tab.add_init_script((ROOT / 'scripts/voice/fixtures.js').read_text())
            tab.add_init_script('''(() => {
              const Native = WebSocket;
              window.WebSocket = class extends Native {
                constructor(...args) {
                  super(...args);
                  this.addEventListener('message', ({data}) => {
                    const event=JSON.parse(data);
                    if(event.type==='room')window.moderationRoom=event.room;
                    if(event.type==='result'&&event.ok&&event.data?.room)
                      window.moderationRoom=event.data.room;
                  });
                }
                send(raw) {
                  const command=JSON.parse(raw);
                  if(window.holdRemoval&&command.type==='memberRemove') {
                    window.delayedMembership=command.membership;
                    window.releaseRemoval=()=>super.send(raw);
                    return;
                  }
                  return super.send(raw);
                }
              };
            })()''')
            tab.goto(address)
            return tab

        def join(address):
            tab = page(address)
            tab.get_by_role('button', name='Join lobby', exact=True).click()
            tab.locator('[data-page="lobby"]').wait_for(timeout=15000)
            return tab

        def kick(tab):
            row = tab.locator('[data-slot-id="slot-2"] .slot-row')
            row.click()
            tab.locator('[data-slot-id="slot-2"] .slot-menu').get_by_role(
                'menuitem', name=re.compile('^Kick ')).click()
            tab.get_by_role('alertdialog').get_by_role('button', name='Kick player').click()

        def voice(tab):
            tab.get_by_role('button', name='Voice', exact=True).click()
            tab.get_by_role('button', name='Enable voice').click()
            tab.wait_for_function("captures.length>0 && captures.at(-1).getAudioTracks().some(t=>t.enabled&&t.readyState==='live')")

        host = page(url)
        host.get_by_role('button', name='Host a new game').click()
        host.get_by_role('button', name='Load NES game').wait_for(timeout=15000)
        assert host.get_by_test_id('room-slot').count() == 5
        invitation = host.evaluate("location.origin+'/#invite='+moderationRoom.invite")
        first = join(invitation)
        host.wait_for_function('window.moderationRoom?.slots[1].member?.id')
        first_member = host.evaluate('moderationRoom.slots[1].member.id')

        voice(host)
        host.evaluate('window.holdRemoval=true')
        kick(host)
        host.wait_for_function('typeof releaseRemoval === "function"')
        first.get_by_role('button', name='Back to Main Page').click()
        first.get_by_role('button', name='Leave lobby').click()
        first.locator('.rc-listing').wait_for(timeout=15000)
        replacement = join(invitation)
        host.wait_for_function('id => !!window.moderationRoom?.slots[1].member?.id && window.moderationRoom.slots[1].member.id !== id',
                               arg=first_member)
        replacement_member = host.evaluate('moderationRoom.slots[1].member.id')
        assert replacement_member != first_member
        voice(replacement)
        for tab in (host, replacement):
            tab.wait_for_function("pcs.some(pc=>pc.connectionState==='connected')")
        host.evaluate('window.releaseRemoval();window.holdRemoval=false')
        host.get_by_role('alertdialog').get_by_text('Could not kick', exact=False).wait_for(timeout=15000)
        host.get_by_role('button', name='Cancel', exact=True).click()
        assert host.evaluate('moderationRoom.slots[1].member.id') == replacement_member
        assert replacement.locator('[data-page="lobby"]').count() == 1
        assert host.evaluate("captures.at(-1).getAudioTracks().some(t=>t.readyState==='live')")
        assert replacement.evaluate("captures.at(-1).getAudioTracks().some(t=>t.readyState==='live')")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        host.screenshot(path=str(args.output.with_suffix('.stale-kick.png')))

        writes = host.evaluate('timelineWrites')
        kick(host)
        replacement.locator('.rc-listing').wait_for(timeout=15000)
        replacement.locator('.rc-status').get_by_text(
            'The host removed you from this lobby.', exact=True).wait_for()
        assert host.locator('[data-slot-id="slot-2"] .slot-row').get_attribute(
            'aria-label').startswith('Open Slot 2')
        for tab in (host, replacement):
            tab.wait_for_function("pcs.every(pc=>pc.connectionState==='closed')")
        replacement.wait_for_function("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
        assert host.evaluate("captures.at(-1).getAudioTracks().some(t=>t.readyState==='live'&&t.enabled)")
        first.goto(invitation)
        first.get_by_role('button', name='Join lobby', exact=True).click()
        first.locator('[data-page="lobby"]').wait_for(timeout=15000)
        assert host.get_by_test_id('room-slot').count() == 5
        assert host.evaluate('timelineWrites') == writes
        assert not errors, errors
        result = {'result': 'pass', 'stale_kick_preserves_new_member': True,
                  'current_kick_removes_only_current_member': True,
                  'former_guest_can_rejoin': True,
                  'empty_lobby_moderation': True,
                  'removed_voice_is_closed': True,
                  'host_voice_survives_removal': True,
                  'host_worker_timeline_unchanged': writes,
                  'seconds': round(time.monotonic() - started, 2),
                  'page_errors': errors}
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        browser.close()
finally:
    service.terminate()
    service.wait(timeout=10)
