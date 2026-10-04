#!/usr/bin/env python3
"""Exercise the current lobby shell with a real coordinator and built client."""

import argparse
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright
from layout_geometry import browser_zoom, zoom_context, control_visibility, verify_zoom
from ui_helpers import choose_section

ROOT = Path(__file__).resolve().parents[2]



def settings_controls_fit(page):
    return page.locator('.rc-tool-body').evaluate("""body => {
      const edge = body.closest('.rc-mobile-side-panel,.rc-side-panel,.rc-play-tools').getBoundingClientRect().bottom;
      return [...body.querySelectorAll('button,input,select')].filter(node => getComputedStyle(node).display !== 'none')
        .every(node => node.getBoundingClientRect().bottom <= edge + 1);
    }""")


def text_fits(locator):
    """Check glyph bounds through every clipping ancestor, including wrapped text."""
    return locator.evaluate("""node => {
      let clip = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
      for (let parent = node; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent), box = parent.getBoundingClientRect();
        if (style.display === "contents") continue;
        if (/(hidden|clip|auto|scroll)/.test(style.overflowX)) {
          clip.left = Math.max(clip.left, box.left + parent.clientLeft);
          clip.right = Math.min(clip.right, box.left + parent.clientLeft + parent.clientWidth);
        }
        if (/(hidden|clip|auto|scroll)/.test(style.overflowY)) {
          clip.top = Math.max(clip.top, box.top + parent.clientTop);
          clip.bottom = Math.min(clip.bottom, box.top + parent.clientTop + parent.clientHeight);
        }
      }
      for (const child of node.querySelectorAll('*')) {
        const style = getComputedStyle(child);
        if (child.getClientRects().length && /(hidden|clip)/.test(style.overflowX)
          && child.scrollWidth > child.clientWidth + 1) return false;
      }
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
      let text;
      while ((text = walker.nextNode())) {
        if (!text.textContent.trim()) continue;
        const range = document.createRange(); range.selectNodeContents(text);
        for (const box of range.getClientRects()) {
          if (box.width && box.height && (box.left < clip.left - 1 || box.right > clip.right + 1
            || box.top < clip.top - 1 || box.bottom > clip.bottom + 1)) return false;
        }
      }
      return node.scrollWidth <= node.clientWidth + 1 && node.scrollHeight <= node.clientHeight + 1;
    }""")


def names_fit(page):
    for node in page.locator('.rc-header-name').all():
        assert text_fits(node), node.inner_text()


def guide_fits(page):
    nodes = page.locator('.rc-inline-settings .rc-control-line,.rc-inline-settings .rc-shortcuts,.rc-inline-settings .rc-controller-art')
    return nodes.count() == 8 and all(text_fits(node) for node in nodes.all())


def regions(page):
    names = ('.rc-header', '.rc-status', '.rc-players', '.rc-game-toolbar',
             '.rc-game-display', '.rc-chat', '.rc-footer')
    boxes = {name: page.locator(name).bounding_box() for name in names}
    assert all(boxes.values()), boxes
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    for name, box in boxes.items():
        assert box['x'] >= -1 and box['y'] >= -1, (name, box)
        assert box['x'] + box['width'] <= page.evaluate('innerWidth') + 1, (name, box)
        assert box['y'] + box['height'] <= page.evaluate('innerHeight') + 1, (name, box)
    assert text_fits(page.locator('.rc-game-toolbar')), page.locator('.rc-game-toolbar').inner_text()
    assert text_fits(page.locator('.rc-status-copy')), page.locator('.rc-status-copy').inner_text()
    for row in page.locator('.rc-players .slot-row').all():
        assert text_fits(row), row.inner_text()
        assert row.evaluate("""row => {
          const fields = [...row.querySelectorAll('strong,.slot-state,.slot-chevron')].map(node => {
            const range = document.createRange(); range.selectNodeContents(node);
            return [...range.getClientRects()].filter(rect => rect.width && rect.height);
          });
          const bounds = row.getBoundingClientRect();
          return fields.every(rects => rects.every(rect => rect.left>=bounds.left-1
            && rect.right<=bounds.right+1 && rect.top>=bounds.top-1 && rect.bottom<=bounds.bottom+1))
            && fields.every((rects,index) => fields.slice(index+1).every(other =>
            rects.every(a => other.every(b => Math.min(a.right,b.right)-Math.max(a.left,b.left)<=1
              || Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)<=1))));
        }"""), row.inner_text()
    footer_controls = [node for node in page.locator('.rc-footer button').all() if node.is_visible()]
    for control in footer_controls:
        assert text_fits(control), control.inner_text()
        control_visibility(control)
    for index, control in enumerate(footer_controls):
        a = control.bounding_box()
        for other in footer_controls[index + 1:]:
            b = other.bounding_box()
            overlap_x = min(a['x'] + a['width'], b['x'] + b['width']) - max(a['x'], b['x'])
            overlap_y = min(a['y'] + a['height'], b['y'] + b['height']) - max(a['y'], b['y'])
            assert overlap_x <= 1 or overlap_y <= 1, (control.inner_text(), other.inner_text())
    assert page.locator('.rc-chat-history').evaluate('(node) => getComputedStyle(node).overflowY === "auto"')
    return boxes


def chat_recovery(page, output, label):
    """Use the actual outbox after a rejected transport send, with keyboard recovery."""
    page.evaluate("""() => {
      window.chatNativeSend = WebSocket.prototype.send;
      WebSocket.prototype.send = function(raw) {
        if (JSON.parse(raw).type === 'chat' && window.rejectNextChat) {
          window.rejectNextChat = false; throw Error('Injected transport send failure');
        }
        return window.chatNativeSend.call(this, raw);
      };
    }""")
    entry = page.get_by_role('textbox', name='Message everyone')
    history = page.get_by_role('log', name='Lobby messages')
    baseline = regions(page)
    try:
        for text, action in (('Retry preserves my message', 'Retry'), ('Discard only my unsent message', 'Discard')):
            entry.fill(text)
            page.evaluate('window.rejectNextChat = true')
            page.get_by_role('button', name='Send', exact=True).click()
            retry = page.get_by_role('button', name='Retry', exact=True)
            retry.wait_for()
            discard = page.get_by_role('button', name='Discard', exact=True)
            for control in (retry, discard):
                assert text_fits(control), control.inner_text()
                control_visibility(control)
            feedback = page.locator('.rc-chat-feedback')
            assert text_fits(feedback), feedback.inner_text()
            assert feedback.evaluate('n => n.parentElement.classList.contains("rc-chat-history")')
            assert entry.input_value() == text and entry.get_attribute('readonly') is not None
            history.focus()
            control_visibility(history, require_focus=True)
            page.keyboard.press('Home')
            page.wait_for_function('document.querySelector(".rc-chat-history").scrollTop <= 1')
            page.keyboard.press('End')
            page.wait_for_function("""() => {const n=document.querySelector('.rc-chat-history');
              return n.scrollHeight-n.clientHeight-n.scrollTop <= 1;}""")
            entry.focus()
            page.keyboard.press('Tab')
            control_visibility(retry, require_focus=True)
            if action == 'Discard':
                page.keyboard.press('Tab')
                control_visibility(discard, require_focus=True)
            page.screenshot(path=str(output / f'chat-{action.lower()}-{label}.png'))
            page.keyboard.press('Enter')
            page.wait_for_function('document.querySelector(".rc-chat input").value === ""')
            assert page.locator('.rc-chat-history li').filter(has_text=text).count() == (1 if action == 'Retry' else 0)
            assert page.get_by_text('(you) Alex: hello', exact=True).count() == 1
            assert regions(page) == baseline
    finally:
        page.evaluate('() => {WebSocket.prototype.send = window.chatNativeSend;}')


def theme_defaults(browser, url):
    for hour, expected in ((10, 'light'), (22, 'dark')):
        context = browser.new_context()
        context.add_init_script(f'const NativeDate=Date;window.Date=class extends NativeDate{{getHours(){{return {hour}}}}};')
        page = context.new_page()
        page.goto(url)
        assert page.evaluate('document.documentElement.dataset.theme') == expected
        assert page.evaluate("localStorage.getItem('retro-coop-theme')") is None
        page.get_by_role('button', name=f'Switch to {"dark" if expected == "light" else "light"} mode').click()
        changed = 'dark' if expected == 'light' else 'light'
        page.reload()
        assert page.evaluate('document.documentElement.dataset.theme') == changed
        context.close()


def expired_guest_recovers(browser, url):
    expired = 'A' * 43
    context = browser.new_context()
    context.add_init_script("""(() => {const Native=WebSocket;window.WebSocket=class extends Native {
      send(raw) {const command=JSON.parse(raw);if(command.type==='hello'&&!command.token&&sessionStorage.getItem('fail-fresh-hello')==='1') {sessionStorage.removeItem('fail-fresh-hello');this.close();return;}super.send(raw);}
    };})()""")
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(url)
        page.locator('.rc-list-head').get_by_text('0 lobbies', exact=True).wait_for(timeout=15000)
        page.evaluate("""async expired => {
          const db = await new Promise((resolve,reject) => {const request=indexedDB.open('retro-coop-local',3);request.onupgradeneeded=()=>{const db=request.result;db.createObjectStore('saves',{keyPath:['identity','slot']}).createIndex('identity','identity');for(const name of ['batteries','preferences'])db.createObjectStore(name,{keyPath:'identity'});db.createObjectStore('roms',{keyPath:'sha256'});db.createObjectStore('meta');};request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
          await new Promise((resolve,reject) => {const tx=db.transaction('saves','readwrite');tx.objectStore('saves').put({identity:'recovery-test',slot:1,savedAt:Date.now(),bytes:new ArrayBuffer(1)});tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
          db.close();sessionStorage.setItem('retro-coop-guest',expired);
        }""", expired)
        page.reload()
        page.locator('.rc-list-head').get_by_text('0 lobbies', exact=True).wait_for(timeout=15000)
        page.wait_for_function("sessionStorage.getItem('retro-coop-guest') !== '" + expired + "'")
        assert page.evaluate("""async () => {const db=await new Promise((resolve,reject)=>{const request=indexedDB.open('retro-coop-local',3);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});const row=await new Promise((resolve,reject)=>{const tx=db.transaction('saves');const request=tx.objectStore('saves').get(['recovery-test',1]);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});db.close();return row?.bytes?.byteLength===1;}""")
        assert 'Lobbies unavailable' not in page.locator('body').inner_text()
        page.get_by_role('button', name='Host a new game').click()
        page.locator('[data-page=lobby]').wait_for(timeout=10000)
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.get_by_role('button', name='Close lobby').click()
        page.locator('.rc-listing').wait_for()
        page.evaluate("sessionStorage.setItem('retro-coop-guest','B'.repeat(43));sessionStorage.setItem('fail-fresh-hello','1')")
        page.reload()
        page.get_by_role('button', name='Retry', exact=True).wait_for(timeout=15000)
        assert 'Lobbies unavailable' in page.locator('body').inner_text()
        page.get_by_role('button', name='Retry', exact=True).click()
        page.locator('.rc-list-head').get_by_text('0 lobbies', exact=True).wait_for(timeout=15000)
        assert page.evaluate("sessionStorage.getItem('retro-coop-guest') !== 'B'.repeat(43)")
        assert not errors, errors
    finally:
        context.close()


def local_shortcuts(browser, url, output):
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    context.add_init_script("""(() => {const Native=Worker;window.Worker=class extends Native {
      postMessage(message,...rest) {if(message.type==='state-import'&&window.holdQuickLoad){window.releaseQuickLoad=()=>super.postMessage(message,...rest);return;}return super.postMessage(message,...rest);}
    };})()""")
    page = context.new_page()
    try:
        page.goto(url)
        page.locator('input[aria-label="NES cartridge file"]').set_input_files(str(ROOT / 'apps/client/dist/generated/diagnostic.nes'))
        page.locator('[data-page=local]').wait_for(timeout=15000)
        page.keyboard.press('q')
        page.get_by_text('Saved to quick slot 1.', exact=True).wait_for(timeout=10000)
        page.keyboard.press('e')
        page.get_by_role('alertdialog', name='Load quick save?').wait_for()
        page.screenshot(path=str(output / 'local-load-confirmation.png'))
        page.get_by_role('button', name='Keep playing').click()
        assert page.get_by_role('alertdialog', name='Load quick save?').count() == 0
        page.keyboard.press('e')
        page.get_by_role('alertdialog', name='Load quick save?').wait_for()
        page.evaluate("""async () => {const db=await new Promise((resolve,reject)=>{const request=indexedDB.open('retro-coop-local',3);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});await new Promise((resolve,reject)=>{const tx=db.transaction('saves','readwrite');const store=tx.objectStore('saves');const request=store.getAll();request.onsuccess=()=>{const row=request.result.find(value=>value.slot===1);store.put({...row,savedAt:row.savedAt+1});};tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});db.close();}""")
        page.get_by_role('button', name='Load Slot 1').click()
        page.get_by_text('Quick save changed. Press E again to load the current slot.', exact=True).wait_for(timeout=10000)
        assert page.locator('[data-page=local]').count() == 1
        assert page.get_by_role('button', name='Resume', exact=True).count() == 1
        page.keyboard.press('e')
        page.get_by_role('button', name='Load Slot 1').click()
        page.get_by_text('Quick slot 1 loaded. Choose Resume to play.', exact=True).wait_for(timeout=10000)
        page.keyboard.press('p')
        page.get_by_role('button', name='Pause', exact=True).wait_for()
        page.keyboard.press('p')
        page.get_by_role('button', name='Resume', exact=True).wait_for()
        page.evaluate('window.holdQuickLoad=true')
        page.keyboard.press('e')
        page.get_by_role('button', name='Load Slot 1').click()
        page.wait_for_function('typeof window.releaseQuickLoad === "function"')
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.locator('.rc-listing').wait_for(timeout=10000)
        assert 'Quick slot 1 loaded' not in page.locator('body').inner_text()
        page.evaluate('window.releaseQuickLoad()')
        page.wait_for_timeout(100)
        assert 'Quick slot 1 loaded' not in page.locator('body').inner_text()
    finally:
        context.close()


def automatic_voice(browser, url):
    def participant():
        context = browser.new_context(permissions=['microphone'])
        context.add_init_script("window.captures=[];const nativeCapture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async options=>{const stream=await nativeCapture(options);captures.push(stream);return stream;};")
        page = context.new_page()
        page.goto(url)
        return context, page
    host_context, host = participant()
    guest_context, guest = participant()
    try:
        host.get_by_role('button', name='Host a new game').click()
        guest.locator('.rc-lobby-card').first.click()
        guest.locator('[data-page=lobby]').wait_for()
        for page in (host, guest):
            page.wait_for_function('captures.length === 1 && captures[0].getAudioTracks()[0].readyState === "live"', timeout=15000)
            assert not page.evaluate('captures[0].getAudioTracks()[0].enabled'), 'Voice must wait for push to talk.'
        host.get_by_role('button', name='Back to Main Page').focus()
        host.keyboard.down('v')
        host.wait_for_function('captures[0].getAudioTracks()[0].enabled')
        host.keyboard.up('v')
        host.wait_for_function('!captures[0].getAudioTracks()[0].enabled')
    finally:
        host_context.close()
        guest_context.close()


def restored_battery_preview(browser, url):
    # The ROM exercises the same preview path as every battery-backed game.
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def load():
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='Super Tilt Bro', exact=False).click()
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        page.locator('.rc-preview img').wait_for()
        assert 'Unable to load' not in page.locator('.rc-status').inner_text()

    try:
        load()
        page.get_by_role('button', name='Ready', exact=True).click()
        page.get_by_role('button', name='Start →').click()
        page.get_by_text('Playing together.', exact=True).wait_for(timeout=15000)
        page.wait_for_function("async()=>new Promise(resolve=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>{const db=q.result,tx=db.transaction('batteries'),count=tx.objectStore('batteries').count();count.onsuccess=()=>resolve(count.result>0);tx.oncomplete=()=>db.close()}})", timeout=20000)
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.get_by_role('button', name='Close lobby').click()
        page.locator('.rc-listing').wait_for()
        load()
        assert not errors, errors
    finally:
        context.close()


def unavailable_preview_keeps_game(browser, url):
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    context.add_init_script("""window.previewRejected=0;const NativeWorker=Worker;
      window.Worker=class extends NativeWorker{postMessage(data,...rest){
        if(data.type==='state-preview'){previewRejected++;queueMicrotask(()=>this.onmessage?.({data:{type:'state-error',requestId:data.requestId,message:'Preview unavailable'}}));return;}
        return super.postMessage(data,...rest);
      }};""")
    try:
        page = context.new_page()
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='From Below', exact=True).click()
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        assert page.evaluate('previewRejected') == 1
        assert 'Unable to load' not in page.locator('.rc-status').inner_text()
    finally:
        context.close()


def abandoned_saved_game_cannot_reopen(browser, url):
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    try:
        page = context.new_page()
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='Add NES file').click()
        page.set_input_files('input[aria-label="NES cartridge file"]', {
            'name': 'saved-fixture.nes', 'mimeType': 'application/octet-stream',
            'buffer': (ROOT / 'spikes/d02/fixture.local.nes').read_bytes()})
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        page.wait_for_function("async()=>new Promise(resolve=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>{const db=q.result,tx=db.transaction('roms'),count=tx.objectStore('roms').count();count.onsuccess=()=>resolve(count.result>0);tx.oncomplete=()=>db.close()}})")
        page.get_by_role('button', name='Change game').click()
        page.get_by_role('button', name='Saved games').click()
        page.get_by_role('button', name='saved-fixture.nes').wait_for()
        page.evaluate("""() => {
          const digest=crypto.subtle.digest.bind(crypto.subtle);
          window.digestHeld=0;
          crypto.subtle.digest=(...args)=>new Promise(resolve=>{
            window.digestHeld++;
            window.releaseDigest=()=>resolve(digest(...args));
          });
        }""")
        page.get_by_role('button', name='saved-fixture.nes').click()
        page.wait_for_function('window.digestHeld === 1')
        page.get_by_role('button', name='Back to Main Page').click()
        page.get_by_role('button', name='Close lobby').click()
        page.locator('.rc-listing').wait_for()
        page.evaluate('window.releaseDigest()')
        page.wait_for_timeout(200)
        assert page.locator('main').get_attribute('data-page') == 'main'
        assert page.locator('.rc-session-holder').is_hidden()
        assert page.get_by_role('button', name='Resume', exact=True).count() == 0
    finally:
        context.close()


def host(page, url):
    page.goto(url, wait_until='domcontentloaded')
    page.get_by_role('button', name='Host a new game').click()
    page.get_by_role('button', name='Back to Main Page', exact=True).wait_for()
    assert page.locator('main').get_attribute('data-page') == 'lobby'
    assert page.get_by_role('heading', name='Create a lobby').count() == 0
    assert page.locator('.rc-players .slot-row').count() == 5
    assert page.get_by_role('button', name='Start →').count() == 0
    assert page.get_by_role('button', name='Load NES game').count() == 1
    assert page.get_by_role('button', name='Copy invite').count() == 1
    assert page.get_by_role('button', name='Voice', exact=True).count() == 1 or page.get_by_role('combobox', name='Settings section').is_visible()
    assert page.get_by_role('button', name='Settings', exact=True).count() == 0
    assert page.get_by_role('heading', name='Settings').is_visible()
    assert page.locator('.rc-side-panel button', has_text='×').count() == 0
    return page.locator('.rc-trail .rc-header-edit').inner_text().replace('✎', '').strip()


def exercise(page, url, size, output, play=False):
    name = host(page, url)
    assert page.evaluate('[innerWidth, innerHeight]') == list(size)
    assert name
    before = page.locator('.rc-identity').bounding_box()
    names_fit(page)
    header_boxes = {selector: page.locator(selector).bounding_box() for selector in ('.rc-header', '.rc-trail', '.rc-identity')}
    name_boxes = page.locator('.rc-header-name').evaluate_all('nodes => nodes.map(node => node.getBoundingClientRect().toJSON())')
    original_identity = page.locator('.rc-identity').inner_text()
    page.get_by_role('button', name='Edit your name:', exact=False).click()
    dialog = page.get_by_role('dialog', name='Change your name')
    assert dialog.is_visible()
    box = dialog.bounding_box()
    assert abs(box['x'] + box['width'] / 2 - size[0] / 2) <= 1
    assert abs(box['y'] + box['height'] / 2 - size[1] / 2) <= 1
    assert page.locator('.rc-identity').bounding_box() == before
    field = dialog.get_by_role('textbox', name='Your name')
    assert field.bounding_box()['width'] >= 200
    field.fill('漢' * 32)
    dialog.get_by_role('button', name='Cancel').click()
    assert page.locator('.rc-identity').inner_text() == original_identity
    page.get_by_role('button', name='Edit your name:', exact=False).click()
    page.get_by_role('dialog', name='Change your name').get_by_role('textbox', name='Your name').fill('Alex')
    page.get_by_role('dialog', name='Change your name').get_by_role('button', name='Save name').click()
    page.get_by_role('button', name='Edit your name: Alex').wait_for()
    page.get_by_role('button', name='Edit lobby name:', exact=False).click()
    assert page.get_by_role('dialog', name='Change lobby name').is_visible()
    page.get_by_role('textbox', name='Lobby name').fill('Test Lobby')
    page.get_by_role('textbox', name='Lobby name').press('Enter')
    page.get_by_role('button', name='Edit lobby name: Test Lobby').wait_for()
    assert page.locator('.rc-identity').bounding_box() == before
    long_name = '漢' * 80
    page.get_by_role('button', name='Edit lobby name: Test Lobby').click()
    page.get_by_role('textbox', name='Lobby name').fill(long_name)
    page.get_by_role('button', name='Save name').click()
    page.get_by_role('button', name=f'Edit lobby name: {long_name}').wait_for()
    page.get_by_role('button', name='Edit your name: Alex').click()
    page.get_by_role('textbox', name='Your name', exact=True).fill('漢' * 32)
    page.get_by_role('button', name='Save name', exact=True).click()
    page.get_by_role('button', name='Edit your name: ' + '漢' * 32).wait_for()
    names_fit(page)
    assert header_boxes == {selector: page.locator(selector).bounding_box() for selector in header_boxes}
    assert name_boxes == page.locator('.rc-header-name').evaluate_all('nodes => nodes.map(node => node.getBoundingClientRect().toJSON())')
    page.screenshot(path=str(output / f'maximum-names-{size[0]}x{size[1]}.png'))
    page.get_by_role('button', name='Edit your name: ' + '漢' * 32).click()
    page.get_by_role('textbox', name='Your name', exact=True).fill('Alex')
    page.get_by_role('button', name='Save name', exact=True).click()
    assert page.locator('.rc-identity').bounding_box() == before
    page.get_by_role('button', name=f'Edit lobby name: {long_name}').click()
    page.get_by_role('textbox', name='Lobby name').fill('Test Lobby')
    page.get_by_role('button', name='Save name').click()
    page.get_by_role('button', name='Edit lobby name: Test Lobby').wait_for()
    invite = page.get_by_role('button', name='Copy invite')
    assert invite.count() == 1 and invite.bounding_box()['y'] < page.locator('.rc-game-toolbar').bounding_box()['y']
    for slot_id in ('slot-3', 'slot-5'):
        slot = page.locator(f'[data-slot-id="{slot_id}"] .slot-row')
        slot.focus()
        slot.press('ArrowDown')
        menu = page.locator(f'[data-slot-id="{slot_id}"] .slot-menu')
        assert menu.get_by_role('menuitem').all_text_contents() == ['Close slot']
        page.wait_for_function('document.activeElement?.matches(".slot-menu button")')
        control_visibility(menu.get_by_role('menuitem'), require_focus=True)
        slot.click()
        assert menu.count() == 0
    assert page.locator('.slot-index').count() == 0
    choose_section(page, 'Voice')
    assert page.locator('main').get_attribute('data-page') == 'lobby'
    page.locator('.rc-game-toolbar').click(position={'x': 2, 'y': 2})
    page.keyboard.press('Escape')
    assert page.get_by_role('heading', name='Settings').is_visible()
    if page.get_by_role('combobox', name='Settings section').is_visible():
        assert page.get_by_role('combobox', name='Settings section').input_value() == 'voice'
    else:
        assert page.get_by_role('button', name='Voice', exact=True).get_attribute('aria-current') == 'page'
    choose_section(page, 'Lobby')
    assert page.get_by_text('Who can join?', exact=True).is_visible()
    assert page.locator('.rc-lobby-access button').evaluate("node => { const button = node.getBoundingClientRect(), panel = node.closest('.rc-tool-body').getBoundingClientRect(); return button.bottom <= panel.bottom + 1 && button.top >= panel.top - 1; }")
    page.get_by_role('button', name='Copy invite').click()
    page.wait_for_function("document.querySelector('.rc-dialog-card') || document.querySelector('.rc-status-copy')?.textContent?.includes('Invitation copied.')")
    if page.get_by_role('dialog', name='Invitation link').count():
        page.get_by_role('button', name='Done').click()
    assert page.get_by_role('heading', name='Settings').is_visible()
    assert page.get_by_text('Who can join?', exact=True).is_visible()
    for section in ('Controls', 'Sound', 'Voice', 'Profile'):
        choose_section(page, section)
        assert settings_controls_fit(page), (size, section)
    voice_setting = page.get_by_role('combobox', name='Voice setting')
    choose_section(page, 'Voice')
    if voice_setting.is_visible():
        for option in ('Other players', 'Devices'):
            voice_setting.select_option(label=option)
            assert settings_controls_fit(page), (size, option)
    choose_section(page, 'Lobby')
    base = regions(page)
    page.screenshot(path=str(output / f'lobby-{size[0]}x{size[1]}.png'))
    if play:
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='From Below', exact=True).click()
        page.get_by_role('button', name='Ready', exact=True).wait_for(timeout=30000)
        assert regions(page) == base
        assert page.get_by_role('button', name='Change game').count() == 1
        assert page.locator('.rc-preview-actions').count() == 0
        assert page.locator('.rc-game-display button', has_text='Change game').count() == 0
        page.get_by_role('textbox', name='Message everyone').fill('hello')
        page.get_by_role('button', name='Send').click()
        page.get_by_text('(you) Alex: hello', exact=True).wait_for()
        assert text_fits(page.get_by_text('(you) Alex: hello', exact=True))
        chat_recovery(page, output, f'{size[0]}x{size[1]}')
        page.get_by_role('button', name='Ready', exact=True).click()
        page.get_by_role('button', name='Start →').click(timeout=30000)
        page.get_by_text('Playing together.', exact=True).wait_for(timeout=15000)
        assert page.locator('.rc-game-heading').inner_text() == 'From Below'
        assert page.get_by_role('button', name='Mute game').count() == 0
        choose_section(page, 'Sound')
        assert page.get_by_role('button', name='Mute game').count() == 1
        choose_section(page, 'Game')
        assert page.locator('.rc-controller-art').is_visible()
        assert guide_fits(page), f'Controller guide overflowed at {size}'
        assert page.locator('.rc-control-a').inner_text().endswith('Z · A rapid')
        assert page.locator('.rc-control-b').inner_text().endswith('C · D rapid')
        assert page.locator('.rc-shortcuts').inner_text().find('Q Save') >= 0
        page.wait_for_function('Number(document.querySelector(".rc-game-display canvas")?.dataset.frameCount) >= 60')
        canvas = page.locator('.rc-game-display canvas').bounding_box()
        game_region = page.locator('.rc-game-display').bounding_box()
        assert canvas['x'] >= game_region['x'] - 1 and canvas['y'] >= game_region['y'] - 1, (canvas, game_region)
        assert canvas['x'] + canvas['width'] <= game_region['x'] + game_region['width'] + 1, (canvas, game_region)
        assert canvas['y'] + canvas['height'] <= game_region['y'] + game_region['height'] + 1, (canvas, game_region)
        scale = min(canvas['width'] / 256, canvas['height'] / 240)
        rendered_game = {'width': 256 * scale, 'height': 240 * scale}
        assert rendered_game['height'] >= 90, rendered_game
        page.screenshot(path=str(output / f'active-game-{size[0]}x{size[1]}.png'))
        page.keyboard.press('q')
        page.get_by_text('Saved to quick slot 1.', exact=True).wait_for(timeout=10000)
        playing_regions = regions(page)
        page.keyboard.press('p')
        page.get_by_role('button', name='Prepare to resume').wait_for(timeout=10000)
        assert guide_fits(page), f'Paused guide overflowed at {size}'
        assert 'P Prepare to resume' in page.locator('.rc-shortcuts').inner_text()
        assert regions(page) == playing_regions
        page.screenshot(path=str(output / f'playing-{size[0]}x{size[1]}.png'))
        page.keyboard.press('p')
        page.get_by_role('button', name='Resume together').wait_for(timeout=10000)
        page.keyboard.press('p')
        page.get_by_role('button', name='Pause', exact=True).wait_for(timeout=15000)
        page.get_by_role('button', name='Expand game to full screen').click()
        expanded = page.locator('.rc-game-fullscreen').bounding_box()
        assert expanded['width'] == size[0] and expanded['height'] == size[1]
        page.get_by_role('button', name='Return game to lobby').click()
        assert page.locator('.rc-game-fullscreen').count() == 0
    page.evaluate("""() => {
      window.heldInvites=[];
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:()=>new Promise((resolve,reject)=>window.heldInvites.push({resolve,reject}))}});
    }""")
    page.get_by_role('button', name='Copy invite').click()
    page.wait_for_function('window.heldInvites.length === 1')
    page.get_by_role('button', name='Back to Main Page', exact=True).click()
    assert page.get_by_role('alertdialog', name='Close this lobby?').is_visible()
    page.evaluate('window.heldInvites[0].resolve()')
    page.wait_for_timeout(100)
    assert 'Invitation copied.' not in page.locator('.rc-status').inner_text()
    page.get_by_role('button', name='Stay').click()
    page.get_by_role('button', name='Copy invite').click()
    page.wait_for_function('window.heldInvites.length === 2')
    page.locator('.rc-logo').click()
    assert page.get_by_role('alertdialog', name='Close this lobby?').is_visible()
    exit_box = page.get_by_role('alertdialog', name='Close this lobby?').bounding_box()
    assert abs(exit_box['x'] + exit_box['width'] / 2 - size[0] / 2) <= 1
    assert abs(exit_box['y'] + exit_box['height'] / 2 - size[1] / 2) <= 1
    page.get_by_role('button', name='Close lobby').click()
    page.locator('.rc-listing').wait_for(timeout=10000)
    page.evaluate("window.heldInvites[1].reject(Error('clipboard unavailable'))")
    page.wait_for_timeout(100)
    assert page.get_by_role('dialog', name='Invitation link').count() == 0
    assert page.locator('main').get_attribute('data-page') == 'main'
    assert page.evaluate('[innerWidth, innerHeight]') == list(size)
    return {'size': size, 'lobby': name, 'regions': list(base), 'played': play, 'rendered_game': rendered_game if play else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=('firefox', 'chromium'), default='chromium')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--zoom', action='store_true')
    parser.add_argument('--local-fast-exit', action='store_true')
    args = parser.parse_args()
    if args.zoom and args.browser != 'chromium':
        parser.error('--zoom needs Chromium')
    output = args.output or ROOT / 'spikes/d02/public-entrypoint.local/unified-shell'
    output.mkdir(parents=True, exist_ok=True)
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=ROOT,
                               stdout=subprocess.PIPE, text=True)
    try:
        assert service.stdout
        url = json.loads(service.stdout.readline())['url']
        with sync_playwright() as playwright:
            errors = []
            if args.zoom:
                with zoom_context(playwright, {'width': 640, 'height': 1136}) as (context, worker):
                    page = context.new_page()
                    page.goto(url, wait_until='domcontentloaded')
                    zoom = browser_zoom(page, worker, 2)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    actual_size = tuple(page.evaluate('[innerWidth, innerHeight]'))
                    verify_zoom(worker, zoom)
                    rows = [exercise(page, url, actual_size, output, play=True)]
                    verify_zoom(worker, zoom)
                    zoom['after_journey'] = page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scale:visualViewport.scale})')
                    assert all(zoom['after_journey'][key] == zoom['after'][key] for key in ('width', 'height', 'dpr', 'scale'))
                    page.close()
                assert not errors, errors
                print(json.dumps({'result': 'pass', 'zoom': zoom, 'checks': rows}), flush=True)
                return
            browser = getattr(playwright, args.browser).launch(headless=True, **({'args': ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']} if args.browser == 'chromium' else {}))
            try:
                rows = []
                profile_context = browser.new_context()
                for size in ((1440, 900), (1366, 682), (1024, 600), (401, 760), (320, 568)):
                    # Each page has a fresh visitor token; shared storage keeps
                    # repeated asset acquisition inside the browser gate budget.
                    page = profile_context.new_page()
                    page.set_viewport_size({'width': size[0], 'height': size[1]})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    try:
                        rows.append(exercise(page, url, size, output, play=True))
                    finally:
                        page.close()
                profile_context.close()
                theme_defaults(browser, url)
                if args.browser == 'chromium':
                    expired_guest_recovers(browser, url)
                    local_shortcuts(browser, url, output)
                    automatic_voice(browser, url)
                    restored_battery_preview(browser, url)
                    unavailable_preview_keeps_game(browser, url)
                    abandoned_saved_game_cannot_reopen(browser, url)
                assert not errors, errors
                print(json.dumps({'result': 'pass', 'checks': rows, 'theme_defaults': True, 'expired_guest_recovery': args.browser == 'chromium', 'local_shortcuts': args.browser == 'chromium', 'automatic_voice': args.browser == 'chromium', 'restored_battery_preview': args.browser == 'chromium', 'preview_recovery': args.browser == 'chromium', 'abandoned_saved_game': args.browser == 'chromium'}), flush=True)
            finally:
                browser.close()
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
