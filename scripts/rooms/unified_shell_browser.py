#!/usr/bin/env python3
"""Exercise the current lobby shell with a real coordinator and built client."""

import argparse
import json
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from layout_geometry import browser_zoom, zoom_context, control_visibility, verify_zoom, CLIPPING_BOXES
from ui_helpers import choose_section, choose_panel, choose_audio, capture_binding, open_access

ROOT = Path(__file__).resolve().parents[2]



def control_hit_target(control):
    result = control.evaluate("""node => {
      const box = node.getBoundingClientRect();
      const hit = document.elementFromPoint(box.x + box.width/2, box.y + box.height/2);
      return {reachable: node.contains(hit), control: node.outerHTML,
        box: box.toJSON(), hit: hit?.outerHTML};
    }""")
    assert result['reachable'], result


def game_fits(page):
    canvas = page.locator('.rc-game-display canvas').bounding_box()
    region = page.locator('.rc-game-display').bounding_box()
    assert canvas['x'] >= region['x']-1 and canvas['y'] >= region['y']-1, (canvas, region)
    assert canvas['x']+canvas['width'] <= region['x']+region['width']+1, (canvas, region)
    assert canvas['y']+canvas['height'] <= region['y']+region['height']+1, (canvas, region)
    scale = min(canvas['width']/256, canvas['height']/240)
    rendered = {'width': 256*scale, 'height': 240*scale}
    assert rendered['height'] >= 90, rendered
    return rendered


def settings_controls_fit(page):
    return page.locator('.rc-tool-body').evaluate("""body => {
      const edge = body.closest('.rc-session-settings').getBoundingClientRect().bottom;
      return [...body.querySelectorAll('button,input,select')].filter(node => getComputedStyle(node).display !== 'none')
        .every(node => node.getBoundingClientRect().bottom <= edge + 1);
    }""")


def text_fits(locator):
    """Check glyph bounds through every clipping ancestor, including wrapped text."""
    return locator.evaluate("""node => {
      CLIPPING_BOXES
      let clip = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
      for (const parent of clippingBoxes(node)) {
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
        if (text.parentElement.closest(".rc-game-heading[data-overflow=true] .rc-title-track") && !matchMedia("(prefers-reduced-motion:reduce)").matches) continue;
        const range = document.createRange(); range.selectNodeContents(text);
        for (const box of range.getClientRects()) {
          if (box.width && box.height && (box.left < clip.left - 1 || box.right > clip.right + 1
            || box.top < clip.top - 1 || box.bottom > clip.bottom + 1)) return false;
        }
      }
      return node.scrollWidth <= node.clientWidth + 1 && node.scrollHeight <= node.clientHeight + 1;
    }""".replace('CLIPPING_BOXES', CLIPPING_BOXES))


def title_fits(page):
    heading = page.locator('.rc-game-heading')
    return heading.evaluate("""node => {
      const box=node.getBoundingClientRect(), toolbar=node.closest('.rc-game-toolbar').getBoundingClientRect();
      if(box.left<toolbar.left-1||box.right>toolbar.right+1||box.top<toolbar.top-1||box.bottom>toolbar.bottom+1)return false;
      const track=node.querySelector('.rc-title-track'),text=node.querySelector('.rc-title-text'),clone=track.querySelector('[aria-hidden=true]');
      if(!text||text.textContent!==node.title)return false;
      if(node.dataset.overflow==='true'&&!matchMedia('(prefers-reduced-motion:reduce)').matches){
        const style=getComputedStyle(track),distance=parseFloat(node.style.getPropertyValue('--rc-title-distance'));
        return clone?.textContent===text.textContent && style.animationName==='rc-title-loop'
          && parseFloat(style.animationDuration)>0 && Math.abs(distance-text.getBoundingClientRect().width-32)<1
          && Math.abs(clone.getBoundingClientRect().left-text.getBoundingClientRect().left-distance)<1;
      }
      return !clone||getComputedStyle(clone).display==='none';
    }""") and (page.locator('.rc-game-heading').get_attribute('data-overflow') == 'true'
                and not page.evaluate("matchMedia('(prefers-reduced-motion:reduce)').matches") or text_fits(heading))


def title_motion(page):
    """Observe actual animation progress, fixed controls and reduced-motion wrapping."""
    page.mouse.move(0, 0)
    page.evaluate('document.fonts.ready')
    measured=page.locator('.rc-game-heading').evaluate('node=>({textWidth:node.querySelector(".rc-title-text").getBoundingClientRect().width,viewportWidth:node.clientWidth})')
    overflowing=measured['textWidth']>measured['viewportWidth']+1
    page.wait_for_function('(overflow)=>document.querySelector(".rc-game-heading").dataset.overflow===String(overflow)',arg=overflowing)
    assert title_fits(page)
    print(f'title geometry: {measured}, overflowing={overflowing}',flush=True)
    if not overflowing:
        assert text_fits(page.locator('.rc-game-heading'))
        assert page.locator('.rc-title-track').evaluate('node=>getComputedStyle(node).animationName')=='none'
        return
    before = page.locator('.rc-game-toolbar').bounding_box()
    time = page.locator('.rc-title-track').evaluate('node=>node.getAnimations()[0].currentTime')
    page.wait_for_function('(before)=>document.querySelector(".rc-title-track").getAnimations()[0].currentTime>before+100', arg=time)
    assert page.locator('.rc-game-toolbar').bounding_box() == before
    page.locator('.rc-game-heading').focus()
    assert page.locator('.rc-title-track').evaluate('node=>getComputedStyle(node).animationPlayState') == 'paused'
    page.locator('.rc-game-heading').evaluate('node=>node.blur()')
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function("document.querySelector('.rc-game-heading').dataset.overflow==='false'&&getComputedStyle(document.querySelector('.rc-title-track')).animationName==='none'")
    assert text_fits(page.locator('.rc-game-heading'))
    assert page.locator('.rc-title-track').evaluate('node=>getComputedStyle(node).animationName') == 'none'
    assert page.locator('.rc-game-toolbar').bounding_box() == before
    page.emulate_media(reduced_motion='no-preference')


def names_fit(page):
    for node in page.locator('.rc-header-name').all():
        if not node.is_visible():
            continue
        if text_fits(node):
            continue
        # Compact headers reserve a readable value; its public dialog exposes the full name.
        value=node.locator('.rc-header-edit')
        assert value.count()==1 and value.is_visible()
        assert text_fits(node.locator(':scope > span:first-child')), node.evaluate("""n=>({viewport:[innerWidth,innerHeight],html:n.outerHTML,ancestors:(()=>{const a=[];for(let p=n;p;p=p.parentElement)a.push({class:p.className,rect:p.getBoundingClientRect().toJSON(),display:getComputedStyle(p).display,overflow:getComputedStyle(p).overflow});return a})()})""")
        assert value.evaluate('n=>getComputedStyle(n).textOverflow==="ellipsis"&&n.scrollWidth>n.clientWidth')
        assert value.inner_text().replace('✎','').strip() in value.get_attribute('aria-label')
        control_visibility(value)


def guide_fits(page):
    # NES targets live in the game band; Settings retains non-controller shortcuts.
    nodes = page.locator('.rc-binding-inventory button')
    return nodes.count() == 16 and all(text_fits(node) for node in nodes.all())


def controller_fits(page):
    band = page.locator('.rc-controller-band')
    if not band.is_visible():
        assert page.get_by_role('navigation', name='Lobby sections').is_visible()
        assert page.locator('.rc-game-fullscreen').count() == 0
        choose_section(page, 'Controls')
        edit=page.get_by_role('button', name='Map A:', exact=False)
        assert text_fits(edit)
        control_visibility(edit)
        choose_panel(page, 'Game')
        return
    targets = band.locator('[data-game-input] button')
    assert targets.count() == 5
    for target in targets.all():
        assert text_fits(target), target.get_attribute('aria-label')
        control_visibility(target)
        box = target.bounding_box()
        assert min(box['width'], box['height']) >= 44, box
        if target.get_attribute('aria-disabled') != 'true':
            assert target.evaluate('node=>{const r=node.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return hit===node||node.contains(hit);}'), target.get_attribute('aria-label')
    for action in band.get_by_role('button').all():
        assert text_fits(action), (page.viewport_size, action.inner_text())
        control_visibility(action)
    assert band.evaluate('node=>node.scrollWidth<=node.clientWidth+1'), band.bounding_box()
    assert band.evaluate('node=>node.scrollHeight<=node.clientHeight+1'), band.evaluate('node=>({viewport:[innerWidth,innerHeight],height:node.clientHeight,scroll:node.scrollHeight,text:node.innerText})')


def phone_controller_geometry(page):
    """Measure real phone targets against the whole controller band (#272)."""
    band = page.locator('.rc-controller-band').bounding_box()
    viewport = page.evaluate('({width:innerWidth,height:visualViewport.height})')
    assert viewport['height']/4-1 <= band['height'] <= viewport['height']/2+1, (viewport, band)
    targets = {
        'Direction pad: use arrow keys or drag': (0, 0, 1/3, 1),
        'NES B': (2/3, 0, 1/6, 1), 'NES A': (5/6, 0, 1/6, 1),
        'NES Select': (1/3, 1/2, 1/6, 1/2), 'NES Start': (1/2, 1/2, 1/6, 1/2),
    }
    actual = {}
    for name, (x, y, width, height) in targets.items():
        node = page.get_by_role('button', name=name, exact=True)
        assert node.count() == 1, page.locator('.rc-controller-band').evaluate("n=>({viewport:[innerWidth,innerHeight],ancestors:[...function*(p){while(p){yield [p.className,p.getAttribute('aria-hidden'),p.inert,getComputedStyle(p).visibility];p=p.parentElement;}}(n)]})")
        box = node.bounding_box()
        expected = {'x':band['x']+x*band['width'], 'y':band['y']+y*band['height'],
                    'width':width*band['width'], 'height':height*band['height']}
        assert all(abs(box[k]-expected[k]) <= 1 for k in expected), (name, expected, box)
        actual[name] = box
        # Artwork does not intercept the outer part of the target.
        assert node.evaluate("node=>{const r=node.getBoundingClientRect();return [[r.left+2,r.top+2],[r.right-2,r.bottom-2]].every(([x,y])=>node.contains(document.elementFromPoint(x,y)));}"), name
    result = {'viewport':viewport,'band':band,'targets':actual}
    print('phone controller geometry: '+json.dumps(result), flush=True)
    return result


def regions(page):
    names = ('.rc-header', '.rc-status', '.rc-players', '.rc-game-toolbar',
             '.rc-game-display', '.rc-game-viewport', '.rc-chat', '.rc-footer')
    navigation = page.get_by_role('navigation', name='Lobby sections')
    selected = navigation.locator('[aria-current=page]').inner_text() if navigation.is_visible() else None
    boxes = {}
    for name in names:
        if selected:
            choose_panel(page, 'Players' if name == '.rc-players' else 'Chat' if name == '.rc-chat' else 'Game')
        boxes[name] = page.locator(name).bounding_box()
    assert all(boxes.values()), boxes
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1 && document.documentElement.scrollHeight <= innerHeight + 1 && scrollY === 0')
    for name, box in boxes.items():
        assert box['x'] >= -1 and box['y'] >= -1, (name, box)
        assert box['x'] + box['width'] <= page.evaluate('innerWidth') + 1, (name, box)
        assert box['y'] + box['height'] <= page.evaluate('innerHeight') + 1, (name, box)
    for preview in page.locator('.rc-preview-media img').all():
        if preview.is_visible():control_visibility(preview)
    assert title_fits(page), page.locator('.rc-game-toolbar').inner_text()
    for action in page.locator('.rc-game-links button').all():
        assert text_fits(action), (page.viewport_size, action.inner_text())
    assert text_fits(page.locator('.rc-status-copy')), page.locator('.rc-status-copy').inner_text()
    if selected:
        choose_panel(page, 'Players')
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
    if selected:
        choose_panel(page, 'Game')
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
    if selected:
        choose_panel(page, selected)
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
    choose_panel(page, 'Chat')
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
          const db = await new Promise((resolve,reject) => {const request=indexedDB.open('retro-coop-local');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
          await new Promise((resolve,reject) => {const tx=db.transaction('saves','readwrite');tx.objectStore('saves').put({identity:'recovery-test',slot:1,savedAt:Date.now(),bytes:new ArrayBuffer(1)});tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
          db.close();sessionStorage.setItem('retro-coop-guest',expired);
        }""", expired)
        page.reload()
        page.locator('.rc-list-head').get_by_text('0 lobbies', exact=True).wait_for(timeout=15000)
        page.wait_for_function("sessionStorage.getItem('retro-coop-guest') !== '" + expired + "'")
        assert page.evaluate("""async () => {const db=await new Promise((resolve,reject)=>{const request=indexedDB.open('retro-coop-local');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});const row=await new Promise((resolve,reject)=>{const tx=db.transaction('saves');const request=tx.objectStore('saves').get(['recovery-test',1]);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});db.close();return row?.bytes?.byteLength===1;}""")
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


def controller_input(browser, url, output):
    """Public Host/Load/Play path, real contacts and exported native controller RAM."""
    context = browser.new_context(viewport={'width': 1280, 'height': 800}, has_touch=True)
    context.add_init_script((ROOT / 'scripts/gameplay/fixture.js').read_text() + """
      addEventListener('DOMContentLoaded',()=>releaseFrames());
      const NativeWorker=Worker;window.Worker=class extends NativeWorker {
        postMessage(message,...args) {
          if(message.type==='frame') {proof.masks??=[];proof.masks.push([message.p1,message.p2]);
            if(proof.masks.length>32)proof.masks.shift();}
          return super.postMessage(message,...args);
        }
      };
    """)
    # Delay delivery of real preference transaction outcomes, including an actual abort.
    context.add_init_script("""
      window.controllerPreferenceGate={hold:false,pending:[],abort:false};
      for(const event of ['oncomplete','onabort']) {
        const descriptor=Object.getOwnPropertyDescriptor(IDBTransaction.prototype,event);
        Object.defineProperty(IDBTransaction.prototype,event,{...descriptor,set(callback) {
          const tx=this;descriptor.set.call(tx,function(...args) {
            const gate=window.controllerPreferenceGate;
            if(tx.mode==='readwrite'&&tx.objectStoreNames.contains('preferences')&&gate.hold) {
              gate.pending.push(()=>callback.apply(tx,args));return;
            }
            callback.apply(tx,args);
          });
        }});
      }
      const put=IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put=function(...args) {
        const request=put.apply(this,args),gate=window.controllerPreferenceGate;
        if(this.name==='preferences'&&gate.abort) {gate.abort=false;this.transaction.abort();}
        return request;
      };
    """)
    page = context.new_page()
    records = []
    def observe(label, expected):
        before = page.evaluate('proof.frameCount')
        page.wait_for_function('({before,mask})=>proof.frameCount>before+proof.room.game.delay+2&&proof.masks.slice(-3).every(value=>value[0]===mask&&value[1]===0)',
                               arg={'before': before, 'mask': expected})
        page.evaluate("delete proof.controllerRam;currentWorker.postMessage({type:'state-export',requestId:900000})")
        page.wait_for_function('proof.controllerRam!==undefined')
        ram = page.evaluate('proof.controllerRam')
        # This diagnostic cartridge uses ROL while reading the NES serial port.
        assert ram == [int(f'{expected:08b}'[::-1], 2), 0], (label, expected, ram)
        records.append({'action': label, 'mask': expected, 'native_ram': ram,
                        'frames': page.evaluate('proof.frameCount')})
        (output / 'controller-native.json').write_text(json.dumps(records, indent=2)+'\n')
        print(f'controller input: {label}', flush=True)
    try:
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='Add game file').click()
        page.get_by_label('NES cartridge file').set_input_files(str(ROOT / 'spikes/d02/fixture.local.nes'))
        page.get_by_role('button', name='Prepare', exact=True).wait_for()
        for width, height in ((1280,800),(1024,600),(900,700),(760,520)):
            page.set_viewport_size({'width':width,'height':height})
            choose_panel(page,'Game')
            reserved=page.locator('.rc-game-display,.rc-game-viewport').evaluate_all('nodes=>nodes.map(node=>node.getBoundingClientRect().toJSON())')
            controller_fits(page)
            editor,capture=capture_binding(page)
            expect(page.locator('.rc-stage')).to_have_attribute('inert','')
            capture.press('NumpadSubtract')
            assert text_fits(editor), (width,height,editor.inner_text())
            for action in editor.get_by_role('button').all():control_visibility(action)
            assert page.locator('.rc-game-display,.rc-game-viewport').evaluate_all('nodes=>nodes.map(node=>node.getBoundingClientRect().toJSON())')==reserved
            editor.get_by_role('button',name='Save',exact=True).click()
            expect(editor).to_have_count(0)
            choose_panel(page,'Game')
            controller_fits(page)
            assert page.locator('.rc-game-display,.rc-game-viewport').evaluate_all('nodes=>nodes.map(node=>node.getBoundingClientRect().toJSON())')==reserved
        page.set_viewport_size({'width':1280,'height':800})
        editor,capture=capture_binding(page)
        capture.press('z');editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
        editor,capture=capture_binding(page)
        capture.press('c')
        expect(editor.get_by_role('status')).to_contain_text('used for B')
        assert editor.get_by_role('button',name='Save',exact=True).is_disabled()
        editor.get_by_role('button',name='Cancel',exact=True).click()
        desktop_navigation=[]
        for pending in (False,True):
            editor,capture=capture_binding(page)
            capture.press('k')
            page.set_viewport_size({'width':320,'height':568})
            page.set_viewport_size({'width':1280,'height':800})
            expect(editor).to_contain_text('Current: Z')
            expect(editor.get_by_role('status')).to_contain_text('New input: K')
            if pending:
                page.evaluate('window.controllerPreferenceGate={hold:true,pending:[],abort:true}')
                editor.get_by_role('button',name='Save',exact=True).click()
                page.wait_for_function('controllerPreferenceGate.pending.length>0')
            # The dialog blocks background navigation; explicit Cancel revokes the draft.
            expect(page.locator('.rc-stage')).to_have_attribute('inert','')
            editor.get_by_role('button',name='Cancel',exact=True).click()
            page.set_viewport_size({'width':320,'height':568})
            choose_panel(page,'Chat');choose_panel(page,'Game')
            editor,capture=capture_binding(page);capture.press('l')
            if pending:
                page.evaluate('async()=>{const gate=controllerPreferenceGate;gate.hold=false;gate.pending.splice(0).forEach(release=>release());await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);}')
            expect(editor).to_contain_text('Current: Z')
            expect(editor.get_by_role('status')).to_contain_text('New input: L')
            assert editor.get_by_role('button',name='Save',exact=True).is_enabled()
            desktop_navigation.append({'pending_save':pending,'cancel_revokes_before_navigation':True,'current':'Z','new_draft':'L','resize_preserved_draft':True})
            editor.get_by_role('button',name='Cancel',exact=True).click()
        (output/'controller-desktop-navigation.json').write_text(json.dumps(desktop_navigation,indent=2)+'\n')
        page.set_viewport_size({'width':1280,'height':800})
        editor,capture=capture_binding(page);capture.press('k');capture.press('Escape');expect(editor).to_have_count(0)
        choose_panel(page,'Game')
        page.get_by_role('button',name='Change game',exact=True).click()
        page.get_by_role('button',name='From Below',exact=True).click()
        page.locator('.rc-game-heading').get_by_text('From Below',exact=True).wait_for()
        expect(page.get_by_role('button',name='Prepare',exact=True)).to_be_enabled()
        editor,capture=capture_binding(page)
        expect(editor.get_by_role('status')).to_have_text('Waiting for input…')
        editor.get_by_role('button',name='Cancel',exact=True).click()
        choose_panel(page,'Game')
        page.get_by_role('button',name='Change game',exact=True).click()
        page.get_by_role('button',name='Add game file',exact=True).click()
        page.get_by_label('NES cartridge file').set_input_files(str(ROOT/'spikes/d02/fixture.local.nes'))
        page.locator('.rc-game-heading').get_by_text('fixture.local',exact=True).wait_for()
        expect(page.get_by_role('button',name='Prepare',exact=True)).to_be_enabled()
        page.set_viewport_size({'width':320,'height':568})
        lifecycle=[]
        for failed in (False,True):
            editor,capture=capture_binding(page);capture.press('k')
            page.evaluate('(abort)=>window.controllerPreferenceGate={hold:true,pending:[],abort}',failed)
            editor.get_by_role('button',name='Save',exact=True).click()
            page.wait_for_function('window.controllerPreferenceGate.pending.length>0')
            editor.get_by_role('button',name='Cancel',exact=True).click()
            choose_audio(page,'Game sound')
            editor,capture=capture_binding(page);capture.press('l')
            page.evaluate('async()=>{const gate=window.controllerPreferenceGate;gate.hold=false;gate.pending.splice(0).forEach(release=>release());await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);}')
            expect(editor).to_contain_text('Current: Z')
            expect(editor.get_by_role('status')).to_contain_text('New input: L')
            assert editor.get_by_role('button',name='Save',exact=True).is_enabled()
            lifecycle.append({'obsolete_outcome':'abort' if failed else 'commit','current':'Z','draft':'L','save_enabled':True})
            editor.get_by_role('button',name='Cancel',exact=True).click()
        (output/'controller-editor-lifecycle.json').write_text(json.dumps({'game_replacement_clears_draft':True,'delayed_outcomes':lifecycle},indent=2)+'\n')
        page.set_viewport_size({'width':568,'height':320})
        # Model the hardware enumeration boundary; editing still uses the
        # public Settings controls, production persistence and capture owner.
        page.evaluate("()=>{window.mappingPad={connected:true,index:0,id:'Mapping fixture',axes:[0,0],buttons:Array.from({length:16},()=>({pressed:false,value:0}))};navigator.getGamepads=()=>[mappingPad];}")
        choose_section(page,'Controls')
        device=page.get_by_role('combobox',name='Input device',exact=True)
        expect(device.locator('option',has_text='Gamepad 1')).to_have_count(1)
        device.select_option(label='Gamepad 1')
        editor,capture=capture_binding(page)
        expect(editor).to_contain_text('Current: Z')
        source=editor.get_by_role('combobox',name='Binding device',exact=True)
        capture.press('Shift+Tab');expect(source).to_be_focused()
        source.select_option(label='Gamepad')
        assert text_fits(editor), 'Gamepad capture must fit the short landscape dialog'
        page.evaluate('mappingPad.buttons[1]={pressed:true,value:1}')
        expect(editor.get_by_role('status')).to_contain_text('used for B')
        assert editor.get_by_role('button',name='Save',exact=True).is_disabled()
        page.evaluate('mappingPad.buttons[1]={pressed:false,value:0}')
        page.wait_for_function('mappingPad.buttons[1].pressed===false')
        source.select_option(label='Keyboard');source.select_option(label='Gamepad')
        page.evaluate('mappingPad.buttons[3]={pressed:true,value:1}')
        expect(editor.get_by_role('status')).to_contain_text('New input: Button 4')
        editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
        page.evaluate('mappingPad.buttons[3]={pressed:false,value:0}')
        editor,capture=capture_binding(page)
        expect(editor).to_contain_text('Current: Z')
        editor.get_by_role('combobox',name='Binding device',exact=True).select_option(label='Gamepad')
        expect(editor).to_contain_text('Current: Button 4')
        editor.get_by_role('button',name='Cancel',exact=True).click()
        reset=page.get_by_role('button',name='Restore defaults',exact=True)
        reset.click();confirmation=page.get_by_role('alertdialog',name='Restore gamepad mappings?',exact=True)
        expect(confirmation.get_by_role('button',name='Cancel',exact=True)).to_be_focused()
        assert text_fits(confirmation)
        confirmation.get_by_role('button',name='Cancel',exact=True).click();expect(reset).to_be_focused()
        reset.click();confirmation.get_by_role('button',name='Restore',exact=True).click();expect(confirmation).to_have_count(0)
        editor,capture=capture_binding(page);expect(editor).to_contain_text('Current: Z')
        editor.get_by_role('combobox',name='Binding device',exact=True).select_option(label='Gamepad')
        expect(editor).to_contain_text('Current: Button 1')
        editor.get_by_role('button',name='Cancel',exact=True).click()
        device.select_option(label='Keyboard')
        page.set_viewport_size({'width':1280,'height':800})
        editor,capture=capture_binding(page)
        expect(editor).to_contain_text('Current: Z')
        capture.press('k');editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
        expect(page.get_by_role('button',name='Map A: K',exact=True)).to_be_visible()
        choose_panel(page,'Game')
        prepare = page.get_by_role('button', name='Prepare', exact=True)
        assert page.locator('.rc-footer').get_by_role('button', name='Prepare', exact=True).count() == 0
        assert prepare.evaluate('node=>{const b=node.getBoundingClientRect(),p=node.closest(".rc-game-viewport").getBoundingClientRect();return Math.abs(b.x+b.width/2-p.x-p.width/2)<1&&Math.abs(b.y+b.height/2-p.y-p.height/2)<1;}')
        control_hit_target(prepare)
        prepare.click()
        page.get_by_role('button', name='Start →').click()
        page.wait_for_function('proof.frameCount>10')
        choose_audio(page, 'Game sound')
        page.get_by_role('button', name='Mute game', exact=True).click()
        choose_panel(page, 'Game')
        page.locator('canvas').focus()
        page.keyboard.down('ArrowRight')
        observe('keyboard right', 128)
        a = page.get_by_role('button', name='NES A', exact=True)
        a.hover(); page.mouse.down()
        observe('keyboard right and mouse A', 129)
        page.mouse.up()
        observe('mouse release retains physical right', 128)
        page.keyboard.up('ArrowRight')
        observe('physical release', 0)
        page.locator('canvas').focus(); page.keyboard.down('Space')
        a.hover(); page.mouse.down()
        observe('physical Start and mouse A', 9)
        page.mouse.up()
        observe('mouse release retains Start', 8)
        page.keyboard.up('Space')
        observe('Start released after controller focus', 0)
        a.focus(); page.keyboard.down('Space')
        observe('semantic A does not also press Start', 1)
        page.keyboard.up('Space')
        observe('semantic release', 0)
        page.keyboard.down('Enter'); page.keyboard.down('Space')
        observe('two semantic contacts on A', 1)
        page.keyboard.up('Enter')
        observe('releasing Enter retains semantic Space', 1)
        page.keyboard.up('Space')
        observe('both semantic contacts released', 0)
        page.locator('canvas').focus(); page.keyboard.down('k')
        observe('saved remapping drives A', 1)
        expect(a).to_have_attribute('aria-pressed','true')
        # Accepted holds prevent false idle; hints appear after actual release.
        page.wait_for_timeout(5100)
        expect(a.locator('.rc-input-hint')).to_have_count(0)
        page.keyboard.up('k')
        observe('remapped key released', 0)
        expect(a).to_have_attribute('aria-pressed','false')
        before_hints=page.locator('.rc-controller-band').bounding_box()
        expect(a.locator('.rc-input-hint')).to_have_text('K',timeout=6000)
        assert page.locator('.rc-controller-band').bounding_box()==before_hints
        page.locator('canvas').focus();page.keyboard.press('ArrowLeft')
        expect(a.locator('.rc-input-hint')).to_have_count(0)
        page.set_viewport_size({'width': 320, 'height': 568})
        choose_panel(page, 'Game')
        page.get_by_role('button', name='Expand game to full screen', exact=True).click()
        controller_fits(page)
        expansion = page.get_by_role('button', name='Return to lobby view', exact=True)
        expansion_box = expansion.bounding_box()
        page.mouse.move(0, 0)
        page.wait_for_function('Number(getComputedStyle(document.querySelector(".rc-expansion-action")).opacity)<.6')
        expansion.focus()
        page.wait_for_function('Number(getComputedStyle(document.querySelector(".rc-expansion-action")).opacity)>.95')
        assert expansion.bounding_box() == expansion_box
        page.locator('canvas').focus()
        geometries = [phone_controller_geometry(page)]
        for width, height in ((320,650),(390,844),(320,1000)):
            page.set_viewport_size({'width':width,'height':height})
            geometries.append(phone_controller_geometry(page))
            assert page.evaluate('document.documentElement.scrollHeight<=innerHeight+1')
            game_fits(page)
        page.set_viewport_size({'width':320,'height':568})
        (output / 'phone-controller-geometry.json').write_text(json.dumps(geometries,indent=2)+'\n')
        cdp = context.new_cdp_session(page)
        pad = page.get_by_role('button', name='Direction pad: use arrow keys or drag').bounding_box()
        ab, bb = a.bounding_box(), page.get_by_role('button', name='NES B', exact=True).bounding_box()
        points = [{'id': 1, 'x': pad['x']+pad['width']/2, 'y': pad['y']+pad['height']/2}]
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': points})
        points[0]['x'] += 30; points[0]['y'] -= 30
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': points})
        observe('touch diagonal', 144)
        for ident, box in ((2, ab), (3, bb)):
            points.append({'id': ident, 'x': box['x']+2, 'y': box['y']+2})
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': points})
        observe('simultaneous diagonal A and B', 147)
        page.screenshot(path=str(output / 'controller-portrait-multitouch.png'))
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchCancel', 'touchPoints': []})
        observe('cancel releases every contact', 0)
        for ident, name, mask in ((6, 'NES Select', 4), (7, 'NES Start', 8)):
            box = page.get_by_role('button', name=name, exact=True).bounding_box()
            page.mouse.move(box['x']+2,box['y']+2); page.mouse.down()
            observe(name+' exact outer pointer area', mask)
            page.mouse.up(); observe(name+' pointer release', 0)
            cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'id':ident,'x':box['x']+box['width']/2,'y':box['y']+10}]})
            observe(name+' outer hit area', mask)
            cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'id':ident,'x':20,'y':20}]})
            cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
            observe(name+' release outside', 0)
        band = page.locator('.rc-controller-band').bounding_box()
        cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'id':8,'x':band['x']+band['width']/2,'y':band['y']+band['height']/4}]})
        observe('center upper area sends no input', 0)
        cdp.send('Input.dispatchTouchEvent', {'type':'touchCancel','touchPoints':[]})
        assert page.locator('.rc-game-fullscreen').count() == 1
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
            {'id': 4, 'x': ab['x']+ab['width']/2, 'y': ab['y']+ab['height']/2}]})
        observe('A held before rotation', 1)
        page.set_viewport_size({'width': 568, 'height': 320})
        observe('rotation releases held A', 0)
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        controller_fits(page)
        phone_controller_geometry(page)
        page.screenshot(path=str(output / 'controller-landscape.png'))
        box = a.bounding_box()
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [
            {'id': 5, 'x': box['x']+box['width']/2, 'y': box['y']+box['height']/2}]})
        observe('fresh A after rotation', 1)
        page.keyboard.press('p')
        page.wait_for_function('proof.room.game.status==="paused"')
        assert a.get_attribute('aria-pressed') == 'false'
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
        choose_section(page, 'Controls')
        expect(page.get_by_role('button',name='Map Mute game: M',exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Save (Q)', exact=True)).to_be_enabled()
        expect(page.get_by_role('button', name='Load (E)', exact=True)).to_be_enabled()
        page.keyboard.press('q')
        page.get_by_text('Saved to quick slot 1.', exact=True).wait_for()
        assert page.locator('.rc-session').get_attribute('data-phone-panel') == 'settings'
        feedback = page.locator('.rc-panel-save-status')
        expect(feedback).to_have_count(1)
        assert feedback.evaluate('n=>!n.closest("[inert],[aria-hidden=true]")')
        page.screenshot(path=str(output / 'save-inactive-phone-game.png'))
        page.evaluate("""() => {window.saveStorePut=IDBObjectStore.prototype.put;window.failSaveStore=true;
          IDBObjectStore.prototype.put=function(...args){if(this.name==='saves'&&window.failSaveStore)throw Error('Storage is full.');return window.saveStorePut.apply(this,args);};} """)
        page.keyboard.press('q')
        expect(feedback).to_contain_text('Save failed: Storage is full.')
        for control in page.locator('.rc-session-settings button:visible,.rc-session-settings select:visible').all():
            control_visibility(control)
            control_hit_target(control)
        page.screenshot(path=str(output / 'save-inactive-phone-retry.png'))
        page.evaluate('window.failSaveStore=false')
        feedback.get_by_role('button', name='Retry Save').click()
        expect(feedback).to_have_text('Saved to quick slot 1.')
        page.set_viewport_size({'width': 320, 'height': 568})
        page.evaluate('window.failSaveStore=true')
        page.get_by_role('button', name='Save (Q)', exact=True).click()
        expect(feedback).to_contain_text('Save failed: Storage is full.')
        for control in page.locator('.rc-session-settings button:visible,.rc-session-settings select:visible').all():
            control_visibility(control)
            control_hit_target(control)
        retry=feedback.get_by_role('button',name='Retry Save',exact=True)
        control_visibility(retry)
        assert retry.evaluate('n=>{const b=n.getBoundingClientRect();return n.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2));}')
        page.screenshot(path=str(output / 'save-inactive-phone-portrait-failure.png'))
        page.evaluate('window.failSaveStore=false')
        tab_stops=page.locator('button:visible,input:visible,select:visible,[tabindex="0"]:visible').count()
        for _ in range(tab_stops+1):
            if retry.evaluate('n=>n===document.activeElement'):break
            page.keyboard.press('Shift+Tab')
        assert retry.evaluate('n=>n===document.activeElement&&n.matches(":focus-visible")')
        page.keyboard.press('Space')
        expect(feedback).to_have_text('Saved to quick slot 1.')
        assert page.locator('.rc-session').get_attribute('data-phone-panel')=='settings'
        page.evaluate('()=>{IDBObjectStore.prototype.put=window.saveStorePut;}')
        print('controller input: portrait failure and keyboard Retry preserve Settings controls',flush=True)
        page.screenshot(path=str(output / 'save-inactive-phone-portrait.png'))
        page.set_viewport_size({'width': 568, 'height': 320})
        page.keyboard.press('m')
        choose_audio(page, 'Game sound')
        page.get_by_role('button', name='Mute game', exact=True).click()
        choose_panel(page, 'Game')
        page.get_by_role('button', name='Prepare to resume', exact=True).click()
        page.get_by_role('button', name='Resume together', exact=True).click()
        observe('resume requires fresh contacts', 0)
        choose_panel(page, 'Chat')
        page.get_by_role('textbox', name='Message everyone').focus()
        page.keyboard.press('k')
        observe('typing A in chat is neutral', 0)
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.get_by_role('button', name='Close lobby', exact=True).click()
        (output / 'controller-native.json').write_text(json.dumps(records, indent=2)+'\n')
    finally:
        context.close()


def canceled_preference_read_restores_saved_controls(browser, url, output):
    # An independent visitor avoids mixing this storage lifecycle with recovery
    # records created by the controller gameplay journey.
    context = browser.new_context(viewport={'width': 320, 'height': 568})
    context.add_init_script("""
      window.holdPreferenceRead=false;window.preferenceReads=[];
      const controllerReads=new WeakSet(),get=IDBObjectStore.prototype.get;
      IDBObjectStore.prototype.get=function(...args){const request=get.apply(this,args),tx=this.transaction;
        request.addEventListener('success',()=>{if(request.result?.value?.controls)controllerReads.add(tx);});return request;};
      const descriptor=Object.getOwnPropertyDescriptor(IDBTransaction.prototype,'oncomplete');
      Object.defineProperty(IDBTransaction.prototype,'oncomplete',{...descriptor,set(callback){
        const tx=this;descriptor.set.call(tx,function(...args){
          if(holdPreferenceRead&&controllerReads.has(tx)&&tx.mode==='readonly'&&tx.objectStoreNames.contains('preferences')){preferenceReads.push(()=>callback.apply(tx,args));return;}
          callback.apply(tx,args);
        });
      }});
    """)
    page = context.new_page()
    def load():
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='From Below', exact=True).click()
        expect(page.get_by_role('button', name='Prepare', exact=True)).to_be_enabled()
        choose_section(page, 'Controls')
        capture_binding(page)
    def close():
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.get_by_role('button', name='Close lobby', exact=True).click()
        page.locator('.rc-listing').wait_for()
    try:
        page.goto(url);load()
        capture = page.get_by_label('Capture input', exact=True)
        editor = page.get_by_role('dialog', name='Map A', exact=True)
        capture.focus();page.keyboard.press('j')
        editor.get_by_role('button', name='Save', exact=True).click()
        expect(editor).not_to_be_visible()
        close();page.reload();page.locator('.rc-listing').wait_for()
        page.evaluate('holdPreferenceRead=true');load()
        page.wait_for_function('preferenceReads.length>0')
        capture.focus();page.keyboard.press('k')
        editor.get_by_role('button', name='Save', exact=True).click()
        expect(editor.get_by_role('button', name='Saving…', exact=True)).to_be_disabled()
        editor.get_by_role('button',name='Cancel',exact=True).click()
        choose_audio(page, 'Game sound');capture_binding(page)
        capture.focus();page.keyboard.press('l')
        page.evaluate('async()=>{holdPreferenceRead=false;preferenceReads.splice(0).forEach(release=>release());await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);}')
        expect(editor).to_contain_text('Current: J')
        expect(editor.get_by_role('status')).to_contain_text('New input: L')
        assert editor.get_by_role('button', name='Save', exact=True).is_enabled()
        (output / 'controller-canceled-preference-read.json').write_text(json.dumps({'restored_current':'J','newer_draft':'L','save_enabled':True})+'\n')
        editor.get_by_role('button', name='Cancel', exact=True).click();close()
    finally:
        context.close()


def save_feedback(browser, url, output):
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    context.add_init_script("""(() => {
      const Native=Worker;window.Worker=class extends Native {
        postMessage(message,...rest) {
          if(message.type==='state-capture'&&window.holdSave){window.releaseSave=()=>super.postMessage(message,...rest);return;}
          return super.postMessage(message,...rest);
        }
      };
      const put=IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put=function(...args) {
        if(this.name==='saves'&&window.failSave)throw new DOMException('Storage is full.','QuotaExceededError');
        return put.apply(this,args);
      };
    })()""")
    page = context.new_page()
    try:
        page.goto(url)
        cartridge = page.locator('input[aria-label="NES cartridge file"]')
        cartridge.set_input_files(str(ROOT / 'spikes/d02/fixture.local.nes'))
        page.get_by_role('button', name='Full screen', exact=True).wait_for()
        page.get_by_role('button', name='Resume', exact=True).click()
        page.wait_for_function('Number(document.querySelector("canvas").dataset.frameCount)>10')
        status = page.locator('.rc-game-save-status')
        for width, height in ((1440, 900), (320, 568), (568, 320), (760, 520)):
            page.set_viewport_size({'width': width, 'height': height})
            for expanded in (False, True):
                if expanded:
                    page.get_by_role('button', name='Full screen', exact=True).click()
                page.locator('canvas').focus()
                before = page.locator('.rc-game-viewport').bounding_box()
                page.evaluate('window.holdSave=true;window.releaseSave=undefined')
                page.keyboard.press('q')
                expect(status).to_have_text('Saving…')
                page.wait_for_function('typeof window.releaseSave === "function"')
                assert page.locator('.rc-game-viewport').bounding_box() == before
                assert status.evaluate("""node => {
                  const box=node.getBoundingClientRect(),game=node.closest('.rc-game-display').getBoundingClientRect();
                  return box.x>=game.x&&box.y>=game.y&&box.right<=game.right&&box.bottom<=game.bottom
                    &&game.right-box.right<=12
                    &&node.contains(document.elementFromPoint(box.x+box.width/2,box.y+box.height/2));
                }""")
                expansion = page.get_by_role('button', name='Return to lobby view' if expanded else 'Full screen', exact=True)
                assert expansion.evaluate('n=>{const b=n.getBoundingClientRect();return n.contains(document.elementFromPoint(b.x+b.width/2,b.y+b.height/2));}')
                if expanded:
                    page.screenshot(path=str(output / f'save-progress-{width}x{height}.png'))
                page.evaluate('window.holdSave=false;window.releaseSave()')
                expect(status).to_have_text('Saved to quick slot 1.')
                if expanded:
                    page.screenshot(path=str(output / f'save-success-{width}x{height}.png'))
                    page.get_by_role('button', name='Return to lobby view', exact=True).click()
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.get_by_role('button', name='Full screen', exact=True).click()
        page.evaluate('window.failSave=true')
        page.locator('canvas').focus()
        page.keyboard.press('q')
        expect(status).to_contain_text('Save failed: Storage is full.')
        expect(status.get_by_role('button', name='Retry Save')).to_be_visible()
        page.screenshot(path=str(output / 'save-failure-retry.png'))
        page.evaluate('window.failSave=false')
        status.get_by_role('button', name='Retry Save').click()
        expect(status).to_have_text('Saved to quick slot 1.')
        page.evaluate('window.holdSave=true;window.releaseSave=undefined')
        page.locator('canvas').focus()
        page.keyboard.press('q')
        page.wait_for_function('typeof window.releaseSave === "function"')
        page.get_by_role('button', name='Return to lobby view', exact=True).click()
        cartridge.set_input_files(str(ROOT / 'spikes/d02/fixture.local.nes'))
        page.get_by_role('button', name='Full screen', exact=True).wait_for()
        page.evaluate('window.holdSave=false;window.releaseSave()')
        expect(status).to_have_count(0)
        page.locator('canvas').focus()
        page.keyboard.press('q')
        expect(status).to_have_text('Saved to quick slot 1.')
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.locator('.rc-listing').wait_for(timeout=10000)
        expect(status).to_have_count(0)
    finally:
        context.close()


def local_shortcuts(browser, url, output):
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    context.add_init_script("""(() => {window.quickProof={workers:[],captures:[],hashes:[]};const Native=Worker;window.Worker=class extends Native {
      constructor(...args){super(...args);this.id=quickProof.workers.length;quickProof.workers.push({id:this.id,terminated:false});this.addEventListener('message',({data})=>{if(data.type==='frame')window.acceptedQuickWorker=this;if(data.type==='state-captured')quickProof.captures.push({id:this.id,frame:data.frame,hash:data.hash});if(data.type==='state-imported')this.postMessage({type:'state-hash',requestId:925333});if(data.type==='state-hash')quickProof.hashes.push({id:this.id,requestId:data.requestId,...data.info});});}
      terminate(){quickProof.workers[this.id].terminated=true;return super.terminate();}
      postMessage(message,...rest) {if(message.type==='load'&&window.failRestartCartridge){window.failRestartCartridge=false;const rom=new ArrayBuffer(1);return super.postMessage({...message,rom},[rom]);}if(message.type==='state-import'&&window.holdQuickLoad){window.releaseQuickLoad=()=>super.postMessage(message,...rest);return;}return super.postMessage(message,...rest);}
    };})()""")
    page = context.new_page()
    try:
        page.goto(url)
        page.locator('input[aria-label="NES cartridge file"]').set_input_files(str(ROOT / 'spikes/d02/fixture.local.nes'))
        page.locator('[data-page=local]').wait_for(timeout=15000)
        page.keyboard.press('q')
        page.get_by_text('Saved to quick slot 1.', exact=True).wait_for(timeout=10000)
        page.keyboard.press('e')
        page.locator('.rc-game-save-status').get_by_text('Saved progress loaded.',exact=True).wait_for(timeout=10000)
        assert page.get_by_role('alertdialog').count()==0
        assert page.locator('[data-page=local]').count()==1
        page.get_by_role('button',name='Resume',exact=True).wait_for()
        page.keyboard.press('n')
        dialog=page.get_by_role('alertdialog',name='Restart this cartridge?')
        expect(dialog).to_be_visible()
        page.get_by_role('button',name='Keep playing',exact=True).click()
        expect(dialog).to_have_count(0)
        assert page.evaluate('quickProof.workers.length')==1
        imports_before = page.evaluate('quickProof.hashes.length')
        page.evaluate('window.failRestartCartridge=true')
        page.keyboard.press('n');page.get_by_role('button',name='Restart cartridge',exact=True).click()
        expect(dialog.get_by_role('alert')).to_contain_text('NES')
        assert page.evaluate('quickProof.workers.at(-1).terminated')
        assert page.evaluate('quickProof.hashes.length') == imports_before
        expect(dialog.get_by_role('button',name='Keep playing',exact=True)).to_be_enabled()
        dialog.get_by_role('button',name='Keep playing',exact=True).click()
        expect(page.get_by_role('button',name='Resume',exact=True)).to_be_visible()
        page.keyboard.press('n');page.get_by_role('button',name='Restart cartridge',exact=True).click()
        expect(dialog).to_have_count(0)
        page.get_by_text('Cartridge restarted.',exact=True).wait_for()
        page.wait_for_function('quickProof.hashes.some(row=>row.requestId===925333&&row.hash===quickProof.captures.at(-1)?.hash)')
        assert page.evaluate('quickProof.captures.at(-1).frame')==0
        assert page.evaluate('quickProof.workers.at(-1).terminated')
        expect(page.get_by_role('button',name='Resume',exact=True)).to_be_visible()
        page.keyboard.press('p')
        page.get_by_role('button',name='Pause',exact=True).wait_for()
        page.get_by_role('button',name='Full screen',exact=True).click()
        page.locator('canvas').focus();page.keyboard.press('e')
        page.locator('.rc-game-save-status').get_by_text('Saved progress loaded.',exact=True).wait_for()
        expect(page.get_by_role('button',name='Return to lobby view',exact=True)).to_be_visible()
        assert page.get_by_role('alertdialog').count()==0
        notice=page.locator('.rc-game-save-status')
        assert notice.evaluate('n=>{const r=n.getBoundingClientRect();return !n.closest("[inert],[aria-hidden=true]")&&r.left>innerWidth/2&&r.top<innerHeight/3&&r.right<=innerWidth;}')
        page.wait_for_function('window.acceptedQuickWorker&&Number(document.querySelector("canvas").dataset.frameCount)>10')
        page.keyboard.down('z');expect(page.get_by_role('button',name='NES A',exact=True)).to_have_attribute('aria-pressed','true');page.keyboard.up('z')
        expect(page.get_by_role('button',name='NES A',exact=True)).to_have_attribute('aria-pressed','false')
        page.get_by_role('button',name='Return to lobby view',exact=True).click()
        page.keyboard.press('p')
        page.get_by_role('button', name='Resume', exact=True).wait_for()
        page.evaluate('window.holdQuickLoad=true')
        page.keyboard.press('e')
        page.wait_for_function('typeof window.releaseQuickLoad === "function"')
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.locator('.rc-listing').wait_for(timeout=10000)
        assert 'Saved progress loaded.' not in page.locator('body').inner_text()
        page.evaluate('window.releaseQuickLoad()')
        assert page.evaluate('quickProof.workers.every(worker=>worker.terminated)')
        assert 'Saved progress loaded.' not in page.locator('body').inner_text()
        (output/'local-shortcuts-result.json').write_text(json.dumps({'direct_load':True,'failed_restart_preserves_game':True,'restart':page.evaluate('quickProof.captures'),'native_imports':page.evaluate('quickProof.hashes'),'fullscreen_notice':True,'keyboard_feedback':True,'exit_cancels_import':True},indent=2))
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
    finally:
        host_context.close()
        guest_context.close()


def restored_battery_preview(browser, url, output=None):
    # The ROM exercises the same preview path as every battery-backed game.
    output = output or ROOT / 'spikes/d02/public-entrypoint.local/unified-shell'
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    context.add_init_script("""window.batteryPreviewProof={imports:0,previews:0};const BatteryWorker=Worker;
      window.Worker=class extends BatteryWorker{constructor(...args){super(...args);window.batteryPreviewWorker=this;this.addEventListener('message',({data})=>{
        if(data.type==='battery-imported')batteryPreviewProof.imports++;
        if(data.type==='state-preview')batteryPreviewProof.previews++;
        if(data.type==='state-hash'&&data.requestId===925801)batteryPreviewProof.native=data.info;
      });}};""")
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def load():
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='Super Tilt Bro', exact=False).click()
        page.get_by_role('button', name='Prepare', exact=True).wait_for(timeout=30000)
        page.locator('.rc-preview img').wait_for()
        assert 'Unable to load' not in page.locator('.rc-status').inner_text()

    try:
        load()
        # Save actual native battery bytes through the public control, without
        # waiting for periodic persistence or starting an unrelated play session.
        choose_section(page, 'Controls')
        page.get_by_role('button', name='Local data', exact=True).click()
        page.get_by_role('button', name='Current', exact=True).click()
        page.get_by_role('button', name='Retry battery saving', exact=True).click()
        page.get_by_text('Local data updated.', exact=True).wait_for()
        page.wait_for_function("async()=>new Promise(resolve=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>{const db=q.result,tx=db.transaction('batteries'),count=tx.objectStore('batteries').count();count.onsuccess=()=>resolve(count.result>0);tx.oncomplete=()=>db.close()}})", timeout=10000)
        stored=page.evaluate("""()=>new Promise(resolve=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>{const db=q.result,tx=db.transaction('batteries'),all=tx.objectStore('batteries').getAll();all.onsuccess=()=>resolve(all.result.map(row=>({bytes:row.bytes.byteLength})));tx.oncomplete=()=>db.close()}})""")
        assert len(stored) == 1 and stored[0]['bytes'] > 0, {'stored': stored, 'status': page.locator('.rc-status').inner_text(), 'native': page.evaluate('batteryPreviewProof')}
        page.get_by_role('button', name='Back', exact=True).click()
        page.get_by_role('button', name='Back to Main Page', exact=True).click()
        page.get_by_role('button', name='Close lobby').click()
        page.locator('.rc-listing').wait_for()
        load()
        assert page.evaluate('batteryPreviewProof.imports') == 1
        assert page.evaluate('batteryPreviewProof.previews') == 1
        page.evaluate("batteryPreviewWorker.postMessage({type:'state-hash',requestId:925801})")
        page.wait_for_function('batteryPreviewProof.native')
        assert page.evaluate('batteryPreviewProof.native.frame === 0 && batteryPreviewProof.native.fresh === true')
        page.get_by_role('button', name='Prepare', exact=True).click()
        expect(page.get_by_role('button', name='Start →', exact=True)).to_be_enabled()
        (output / 'restored-battery-result.json').write_text(json.dumps({'stored':stored,**page.evaluate('batteryPreviewProof')},indent=2))
        page.screenshot(path=str(output / 'restored-battery-preview.png'))
        assert not errors, errors
    except Exception:
        page.screenshot(path=str(output / 'restored-battery-failure.png'))
        (output / 'restored-battery-failure.json').write_text(json.dumps({'body':page.locator('body').inner_text(),'native':page.evaluate('batteryPreviewProof'),'errors':errors},indent=2))
        raise
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
        page.get_by_role('button', name='Prepare', exact=True).wait_for(timeout=30000)
        assert page.evaluate('previewRejected') == 1
        assert 'Unable to load' not in page.locator('.rc-status').inner_text()
    finally:
        context.close()


def saved_game_picker_and_exit(browser, url, output=None):
    label = "界" * 80
    filename = label + ".nes"
    output = output or ROOT / "spikes/d02/public-entrypoint.local/unified-shell"
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    try:
        page = context.new_page()
        page.goto(url)
        page.get_by_role('button', name='Host a new game').click()
        page.get_by_role('button', name='Load NES game').click()
        page.get_by_role('button', name='Add game file').click()
        page.set_input_files('input[aria-label="NES cartridge file"]', {
            'name': filename, 'mimeType': 'application/octet-stream',
            'buffer': (ROOT / 'spikes/d02/fixture.local.nes').read_bytes()})
        page.get_by_role('button', name='Prepare', exact=True).wait_for(timeout=30000)
        page.wait_for_function("async()=>new Promise(resolve=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>{const db=q.result,tx=db.transaction('roms'),count=tx.objectStore('roms').count();count.onsuccess=()=>resolve(count.result>0);tx.oncomplete=()=>db.close()}})")
        # Seed valid cached cartridges at the storage boundary, then exercise
        # the public picker. Distinct harmless padding bytes give distinct hashes.
        page.evaluate("""async()=>{
          const db=await new Promise((resolve,reject)=>{const q=indexedDB.open('retro-coop-local');q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
          const base=await new Promise((resolve,reject)=>{const q=db.transaction('roms').objectStore('roms').getAll();q.onsuccess=()=>resolve(q.result.find(row=>row.source==='import'));q.onerror=()=>reject(q.error)});
          const rows=[];for(let i=1;i<=7;i++){const bytes=base.bytes.slice(0),view=new Uint8Array(bytes);view[view.length-1]=i;
            const sha256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
            rows.push({...base,sha256,bytes,label:`Saved cartridge ${i}`,lastUsedAt:base.lastUsedAt-i});}
          await new Promise((resolve,reject)=>{const tx=db.transaction('roms','readwrite');rows.forEach(row=>tx.objectStore('roms').put(row));tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});db.close();
        }""")
        page.get_by_role('button', name='Change game').click()
        page.get_by_role('button', name='Saved games').click()
        page.get_by_role('button', name=label).wait_for()
        expect(page.locator('.rc-saved-list button')).not_to_have_count(1)
        page.emulate_media(reduced_motion='reduce')
        for width, height in ((1024, 600), (320, 568), (568, 320)):
            page.set_viewport_size({'width': width, 'height': height})
            choose_panel(page, 'Game')
            page.locator('.rc-session').evaluate('async node=>{await document.fonts.ready;node.getBoundingClientRect();await Promise.all(node.getAnimations({subtree:true}).filter(animation=>animation.effect.getTiming().iterations!==Infinity).map(animation=>animation.finished.catch(()=>{})));}')
            picker = page.locator('.rc-game-picker')
            fits = text_fits(picker)
            entries=picker.locator('.rc-saved-list button')
            assert entries.count()>0, 'Saved picker must retain a usable page when space only fits a long title'
            listed=set(entries.all_inner_texts())
            next_page=picker.get_by_role('button',name='Next saved games',exact=True)
            while next_page.is_visible() and next_page.is_enabled():
                next_page.click()
                assert text_fits(picker)
                for button in picker.get_by_role('button').all():control_visibility(button)
                batch=entries.all_inner_texts();assert not listed.intersection(batch)
                listed.update(batch)
            assert listed=={label,*[f'Saved cartridge {i}' for i in range(1,8)]}
            previous_page=picker.get_by_role('button',name='Previous saved games',exact=True)
            while previous_page.is_visible() and previous_page.is_enabled():previous_page.click()
            page.screenshot(path=str(output / f'saved-picker-{width}x{height}.png'))
            if not fits:
                geometry = picker.evaluate("""node=>{
                  const box=n=>({tag:n.tagName,class:n.className,rect:n.getBoundingClientRect().toJSON(),client:[n.clientWidth,n.clientHeight],scroll:[n.scrollWidth,n.scrollHeight],font:getComputedStyle(n).font,overflow:[getComputedStyle(n).overflowX,getComputedStyle(n).overflowY]});
                  const ancestors=[];for(let n=node;n;n=n.parentElement)ancestors.push(box(n));
                  const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),glyphs=[];let text;
                  while(text=walker.nextNode()){if(!text.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(text);glyphs.push({text:text.textContent,owner:box(text.parentElement),rects:[...range.getClientRects()].map(rect=>rect.toJSON())});}
                  return {viewport:[innerWidth,innerHeight],reducedMotion:matchMedia('(prefers-reduced-motion:reduce)').matches,ancestors,glyphs,animations:node.getAnimations({subtree:true}).map(animation=>({state:animation.playState,timing:animation.effect.getComputedTiming()}))};
                }""")
                (output / f'saved-picker-{width}x{height}-failure.json').write_text(json.dumps(geometry, indent=2)+'\n')
            assert fits, (width, height)
            for button in picker.get_by_role('button').all():
                control_visibility(button)
            assert page.locator('.rc-controller-band').get_attribute('inert') is not None
        page.emulate_media(reduced_motion='no-preference')
        display = page.locator('.rc-game-display').bounding_box()
        preview_before_cancel = page.locator('.rc-preview img').get_attribute('src')
        page.get_by_role('button', name='Back to games', exact=True).click()
        page.get_by_role('button', name='Cancel', exact=True).click()
        assert page.locator('.rc-game-display').bounding_box() == display
        assert page.locator('.rc-preview img').get_attribute('src') == preview_before_cancel
        page.get_by_role('button', name='Change game').click()
        page.get_by_role('button', name='Saved games').click()
        choose_section(page, 'Controls')
        capture_binding(page)
        page.get_by_role('dialog',name='Map A',exact=True).wait_for()
        expect(page.locator('.rc-game-picker')).to_have_count(0)
        page.get_by_role('dialog',name='Map A',exact=True).get_by_role('button', name='Cancel', exact=True).click()
        choose_panel(page, 'Game')
        page.get_by_role('button', name='Change game').click()
        page.get_by_role('button', name='Saved games').click()
        page.get_by_role('button', name=label).click()
        page.get_by_role('button', name='Prepare', exact=True).wait_for()
        page.locator('.rc-game-picker').wait_for(state='hidden')
        assert page.locator('.rc-game-heading').get_attribute('title') == label
        page.get_by_role('button', name='Back to Main Page').click()
        page.get_by_role('button', name='Close lobby').click()
        page.locator('.rc-listing').wait_for()
        assert page.locator('main').get_attribute('data-page') == 'main'
        assert page.locator('.rc-session-holder').is_hidden()
        assert page.get_by_role('button', name='Resume', exact=True).count() == 0
    finally:
        context.close()


def host(page):
    page.get_by_role('button', name='Host a new game').click()
    page.get_by_role('button', name='Back to Main Page', exact=True).wait_for()
    assert page.locator('main').get_attribute('data-page') == 'lobby'
    assert page.get_by_role('heading', name='Create a lobby').count() == 0
    assert page.locator('.rc-players .slot-row').count() == 5
    assert page.get_by_role('button', name='Start →').count() == 0
    assert page.get_by_role('button', name='Load NES game').count() == 1
    assert page.get_by_role('button', name='Copy invite').count() == 1
    choose_panel(page, 'Settings')
    assert page.get_by_role('button', name='Audio', exact=True).count() == 1 or page.get_by_role('combobox', name='Settings section').is_visible()
    assert page.get_by_role('button', name='Settings', exact=True).count() == int(page.get_by_role('navigation', name='Lobby sections').is_visible())
    assert page.get_by_role('region', name='Game settings').is_visible()
    assert page.locator('.rc-side-panel button', has_text='×').count() == 0
    if page.get_by_role('navigation', name='Lobby sections').is_visible():
        choose_section(page, 'Controls')
    return page.get_by_role('button', name='Edit lobby name:', exact=False).inner_text().replace('✎', '').strip()


def exercise(page, size, output, play=False, invitation_recovery=False, uploaded_title=False, responsive_sizes=()):
    responsive_results = []
    assert page.evaluate('[innerWidth, innerHeight]') == list(size)
    name = host(page)
    assert name
    before = page.locator('.rc-identity').bounding_box()
    names_fit(page)
    header_boxes = {selector: page.locator(selector).bounding_box() for selector in ('.rc-header', '.rc-trail', '.rc-identity')}
    name_boxes = page.locator('.rc-header-name').evaluate_all('nodes => nodes.filter(node=>node.getClientRects().length).map(node => node.getBoundingClientRect().toJSON())')
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
    for profile in responsive_sizes:
        page.set_viewport_size({'width': profile[0], 'height': profile[1]})
        choose_section(page, 'Controls')
        names_fit(page)
        regions(page)
        choose_panel(page, 'Game')
        controller_fits(page)
        page.screenshot(path=str(output / f'maximum-names-{profile[0]}x{profile[1]}.png'))
    if responsive_sizes:
        page.set_viewport_size({'width': size[0], 'height': size[1]})
        choose_section(page, 'Controls')
    assert header_boxes == {selector: page.locator(selector).bounding_box() for selector in header_boxes}
    assert name_boxes == page.locator('.rc-header-name').evaluate_all('nodes => nodes.filter(node=>node.getClientRects().length).map(node => node.getBoundingClientRect().toJSON())')
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
    choose_panel(page, 'Players')
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
    choose_audio(page, 'Voice')
    assert page.locator('main').get_attribute('data-page') == 'lobby'
    if not page.get_by_role('navigation', name='Lobby sections').is_visible():
        page.locator('.rc-game-toolbar').click(position={'x': 2, 'y': 2})
    page.keyboard.press('Escape')
    assert page.get_by_role('region', name='Game settings').is_visible()
    if page.get_by_role('combobox', name='Settings section').is_visible():
        assert page.get_by_role('combobox', name='Settings section').input_value() == 'audio'
    else:
        assert page.get_by_role('button', name='Audio', exact=True).get_attribute('aria-current') == 'page'
    open_access(page)
    access=page.get_by_role('dialog',name='Lobby access',exact=True)
    expect(page.locator('.rc-header')).to_have_attribute('inert','')
    assert page.get_by_text('Who can join?',exact=True).is_visible()
    assert text_fits(access)
    for control in access.locator('button:visible,input:visible').all():control_visibility(control)
    access.get_by_role('button',name='Done',exact=True).click()
    page.get_by_role('button',name='Copy invite').click()
    page.wait_for_function("document.querySelector('.rc-dialog-card') || document.querySelector('.rc-status-copy')?.textContent?.includes('Invitation copied.')")
    if page.get_by_role('dialog',name='Invitation link').count():page.get_by_role('dialog',name='Invitation link').get_by_role('button',name='Done').click()
    for section in ('Controls','Audio'):
        choose_section(page,section)
        assert settings_controls_fit(page), (size,section)
    choose_audio(page,'Voice')
    voice_setting=page.get_by_role('combobox',name='Voice setting')
    if voice_setting.is_visible():
        for option in ('Other players','Devices'):
            voice_setting.select_option(label=option)
            assert settings_controls_fit(page), (size,option)
    choose_section(page,'Controls')
    base = regions(page)
    page.screenshot(path=str(output / f'lobby-{size[0]}x{size[1]}.png'))
    if play:
        choose_panel(page, 'Game')
        page.get_by_role('button', name='Load NES game').click()
        if uploaded_title:
            expected_title = '界' * 80
            page.get_by_role('button', name='Add game file', exact=True).click()
            page.locator('input[aria-label="NES cartridge file"]').set_input_files({'name': expected_title + '.nes', 'mimeType': 'application/octet-stream', 'buffer': (ROOT / 'spikes/d02/fixture.local.nes').read_bytes()})
        else:
            expected_title = 'From Below'
            page.get_by_role('button', name='From Below', exact=True).click()
        page.get_by_role('button', name='Prepare', exact=True).wait_for(timeout=30000)
        assert regions(page) == base
        if uploaded_title:
            expect(page.locator('.rc-title-text')).to_have_text(expected_title)
            title_motion(page)
        assert page.get_by_role('button', name='Change game').count() == 1
        assert page.locator('.rc-preview-actions').count() == 0
        assert page.locator('.rc-game-display button', has_text='Change game').count() == 0
        choose_panel(page, 'Chat')
        page.get_by_role('textbox', name='Message everyone').fill('hello')
        page.get_by_role('button', name='Send').click()
        page.get_by_text('(you) Alex: hello', exact=True).wait_for()
        assert text_fits(page.get_by_text('(you) Alex: hello', exact=True))
        chat_recovery(page, output, f'{size[0]}x{size[1]}')
        choose_panel(page, 'Game')
        page.get_by_role('button', name='Prepare', exact=True).click()
        page.get_by_role('button', name='Start →').click(timeout=30000)
        page.get_by_text('Playing together.', exact=True).wait_for(timeout=15000)
        phone = page.get_by_role('navigation', name='Lobby sections').is_visible()
        assert bool(page.locator('.rc-game-fullscreen').count()) == phone
        if phone:
            page.wait_for_function('Number(document.querySelector("canvas").dataset.frameCount)>=60')
            page.screenshot(path=str(output / f'automatic-play-{size[0]}x{size[1]}.png'))
            page.get_by_role('button', name='Return to lobby view', exact=True).click()
            assert page.get_by_role('navigation', name='Lobby sections').locator('[aria-current=page]').inner_text() == 'Game'
        assert page.locator('.rc-game-heading').get_attribute('title') == expected_title
        choose_audio(page, 'Game sound')
        assert page.get_by_role('button', name='Mute game').count() == 1
        page.get_by_role('button', name='Mute game', exact=True).click()
        page.get_by_role('button', name='Unmute game', exact=True).wait_for()
        choose_section(page, 'Controls')
        assert page.get_by_label('Current bindings').is_visible()
        assert guide_fits(page), f'Controller guide overflowed at {size}'
        expect(page.get_by_role('button',name='Map Rapid A: A',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='Map Rapid B: D',exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Save (Q)', exact=True)).to_be_enabled()
        expect(page.get_by_role('button', name='Load (E)', exact=True)).to_be_enabled()
        choose_panel(page, 'Game')
        page.wait_for_function('Number(document.querySelector(".rc-game-display canvas")?.dataset.frameCount) >= 60')
        controller_fits(page)
        rendered_game = game_fits(page)
        page.screenshot(path=str(output / f'active-game-{size[0]}x{size[1]}.png'))
        page.keyboard.press('q')
        page.get_by_text('Saved to quick slot 1.', exact=True).wait_for(timeout=10000)
        for profile in responsive_sizes:
            page.set_viewport_size({'width': profile[0], 'height': profile[1]})
            choose_section(page, 'Controls')
            assert guide_fits(page), profile
            assert settings_controls_fit(page), profile
            regions(page)
            choose_panel(page, 'Game')
            frames = int(page.locator('canvas').get_attribute('data-frame-count'))
            page.wait_for_function('(before)=>Number(document.querySelector("canvas").dataset.frameCount)>before', arg=frames)
            controller_fits(page)
            responsive_results.append({'size': profile, 'rendered_game': game_fits(page), 'frames_advanced': True})
            page.screenshot(path=str(output / f'active-game-{profile[0]}x{profile[1]}.png'))
        if responsive_sizes:
            page.set_viewport_size({'width': size[0], 'height': size[1]})
        choose_panel(page, 'Game')
        playing_regions = regions(page)
        expect(page.get_by_role('button',name='Pause',exact=True)).to_be_enabled()
        page.locator('canvas').focus()
        page.keyboard.press('p')
        choose_panel(page, 'Game')
        page.get_by_role('button', name='Prepare to resume').wait_for(timeout=10000)
        choose_section(page, 'Controls')
        assert guide_fits(page), f'Paused guide overflowed at {size}'
        expect(page.get_by_role('button',name='Map Pause / resume: P',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='Map Mute game: M',exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Save (Q)', exact=True)).to_be_enabled()
        expect(page.get_by_role('button', name='Load (E)', exact=True)).to_be_enabled()
        assert regions(page) == playing_regions
        page.screenshot(path=str(output / f'playing-{size[0]}x{size[1]}.png'))
        page.keyboard.press('p')
        choose_panel(page, 'Game')
        page.get_by_role('button', name='Resume together').wait_for(timeout=10000)
        page.keyboard.press('p')
        page.get_by_role('button', name='Pause', exact=True).wait_for(timeout=15000)
        choose_panel(page, 'Game')
        assert page.locator('.rc-game-fullscreen').count() == 0
        page.get_by_role('button', name='Expand game to full screen', exact=True).click()
        expanded = page.locator('.rc-game-fullscreen').bounding_box()
        assert expanded['width'] == size[0] and expanded['height'] == size[1]
        page.get_by_role('button', name='Return game to lobby').click()
        assert page.locator('.rc-game-fullscreen').count() == 0
    if invitation_recovery:
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
    if invitation_recovery:
        page.evaluate("window.heldInvites[1].reject(Error('clipboard unavailable'))")
        page.wait_for_timeout(100)
        assert page.get_by_role('dialog', name='Invitation link').count() == 0
        assert page.locator('main').get_attribute('data-page') == 'main'
    assert page.evaluate('[innerWidth, innerHeight]') == list(size)
    return {'size': size, 'lobby': name, 'regions': list(base), 'played': play, 'rendered_game': rendered_game if play else None, 'responsive_play': responsive_results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', choices=('firefox', 'chromium'), default='chromium')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--serve', action='store_true')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--zoom', action='store_true')
    mode.add_argument('--controls-only', action='store_true')
    mode.add_argument('--layout-only', action='store_true')
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
                rows,zooms=[],[]
                for backing in ({'width':640,'height':1136},{'width':1520,'height':1040}):
                    with zoom_context(playwright, backing) as (context, worker):
                        page = context.new_page()
                        page.goto(url, wait_until='domcontentloaded')
                        zoom = browser_zoom(page, worker, 2)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        size = tuple(page.evaluate('[innerWidth, innerHeight]'))
                        rows.append(exercise(page, size, output, play=True, uploaded_title=True))
                        verify_zoom(worker, zoom)
                        zoom['after_journey'] = page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scale:visualViewport.scale})')
                        assert all(zoom['after_journey'][key] == zoom['after'][key] for key in ('width', 'height', 'dpr', 'scale'))
                        zooms.append(zoom)
                        page.close()
                assert not errors, errors
                print(json.dumps({'result':'pass','zoom':zooms,'checks':rows}),flush=True)
                return
            browser = getattr(playwright, args.browser).launch(headless=True, ignore_default_args=['--mute-audio'], **({'args': ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']} if args.browser == 'chromium' else {}))
            try:
                if args.controls_only:
                    controller_input(browser,url,output)
                    canceled_preference_read_restores_saved_controls(browser,url,output)
                    print(json.dumps({'result':'pass','controller_input':True,'canceled_preference_read':True}),flush=True)
                    return
                rows = []
                scenarios = (
                    {'size': (1280, 800), 'play': True, 'invitation_recovery': True, 'responsive_sizes': ((900,700),(760,520),(899,700),(1280,520),(844,390),(320,650))},
                    {'size': (1024, 600), 'play': True, 'uploaded_title': True},
                    {'size': (568, 320), 'play': True, 'uploaded_title': True},
                    {'size': (650, 760)},
                    {'size': (401, 760)},
                    {'size': (320, 568), 'play': True, 'uploaded_title': True},
                )
                for scenario in scenarios:
                    size = scenario['size']
                    # Each layout journey is an independent visitor, including
                    # local ROMs and recovery captures from a played scenario.
                    context = browser.new_context(viewport={'width': size[0], 'height': size[1]})
                    try:
                        page = context.new_page()
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(url, wait_until='domcontentloaded')
                        print(f'shell profile: {size}', flush=True)
                        rows.append(exercise(page, output=output, **scenario))
                    finally:
                        context.close()
                theme_defaults(browser, url)
                if args.browser == 'chromium':
                    print('shell check: expired_guest_recovers', flush=True)
                    expired_guest_recovers(browser, url)
                    print('shell check: local_shortcuts', flush=True)
                    local_shortcuts(browser, url, output)
                    if not args.layout_only:
                        print('shell check: controller_input', flush=True)
                        controller_input(browser, url, output)
                        canceled_preference_read_restores_saved_controls(browser,url,output)
                    print('shell check: automatic_voice', flush=True)
                    automatic_voice(browser, url)
                    print('shell check: restored_battery_preview', flush=True)
                    restored_battery_preview(browser, url, output)
                    print('shell check: unavailable_preview_keeps_game', flush=True)
                    unavailable_preview_keeps_game(browser, url)
                    print('shell check: saved_game_picker_and_exit', flush=True)
                    saved_game_picker_and_exit(browser, url, output)
                    print('shell check: saved_game_picker_and_exit completed', flush=True)
                assert not errors, errors
                print(json.dumps({'result': 'pass', 'checks': rows, 'theme_defaults': True, 'expired_guest_recovery': args.browser == 'chromium', 'local_shortcuts': args.browser == 'chromium', 'automatic_voice': args.browser == 'chromium', 'restored_battery_preview': args.browser == 'chromium', 'preview_recovery': args.browser == 'chromium', 'saved_game_picker_and_exit': args.browser == 'chromium'}), flush=True)
            finally:
                browser.close()
    finally:
        service.terminate()
        service.wait(timeout=10)


if __name__ == '__main__':
    main()
