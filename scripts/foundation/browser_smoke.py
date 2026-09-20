"""Prove the built app renders emulator frames, receives input and schedules muted PCM."""
import argparse
import functools
import http.server
import json
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='foundation.local.json')
parser.add_argument('--chrome', action='store_true')
args = parser.parse_args()
started = time.monotonic()
root = Path(__file__).resolve().parents[2]
output = Path(args.output)
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root / 'apps/client/dist'))
with http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler) as server:
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        browser = p.chromium.launch(ignore_default_args=['--mute-audio'], **({'channel': 'chrome'} if args.chrome else {}))
        page = browser.new_page(viewport={'width': 1280, 'height': 1000})
        errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append((request.method, request.url)))
        page.add_init_script('''window.proof={buffers:0,peak:0,starts:0,muted:true};
        const copy=AudioBuffer.prototype.copyToChannel;
        AudioBuffer.prototype.copyToChannel=function(data,...rest){proof.buffers++;for(const x of data)proof.peak=Math.max(proof.peak,Math.abs(x));return copy.call(this,data,...rest)};
        const connect=AudioNode.prototype.connect;
        AudioNode.prototype.connect=function(node,...rest){if(node instanceof GainNode)proof.muted=proof.muted && node.gain.value===0;return connect.call(this,node,...rest)};
        const start=AudioBufferSourceNode.prototype.start;
        AudioBufferSourceNode.prototype.start=function(...args){proof.starts++;return start.apply(this,args)};
        ''')
        page.goto(f'http://127.0.0.1:{server.server_port}/')
        page.screenshot(path=str(output.with_suffix('.before.png')), full_page=True)
        page.get_by_role('button', name='Run diagnostic').click()
        page.wait_for_function("Number(document.querySelector('output').textContent.split(' ')[0])>10")
        page.wait_for_function('proof.starts>3 && proof.peak>0')
        page.locator('canvas').focus()
        before = page.locator('canvas').evaluate('c=>c.toDataURL()')
        page.keyboard.down('ArrowRight')
        page.wait_for_function("before=>document.querySelector('canvas').toDataURL()!==before", arg=before)
        page.keyboard.up('ArrowRight')
        page.screenshot(path=str(output.with_suffix('.after.png')), full_page=True)
        page.get_by_role('button', name='Pause', exact=True).click()
        page.wait_for_function("document.querySelector('[role=status]').textContent.startsWith('Paused')")
        frozen = page.locator('canvas').evaluate('c=>c.toDataURL()')
        page.wait_for_timeout(200)
        assert frozen == page.locator('canvas').evaluate('c=>c.toDataURL()')
        proof = page.evaluate('proof')
        assert proof['muted'] and proof['peak'] > 0 and proof['starts'] > 3
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(output.with_suffix('.mobile.png')), full_page=True)
        assert not errors, errors
        assert all(method == 'GET' and url.startswith(f'http://127.0.0.1:{server.server_port}/') for method, url in requests), requests
        result = {'result':'pass', 'browser':browser.version, 'duration_seconds':round(time.monotonic()-started,2), 'audio':proof, 'input_changed_canvas':True, 'paused_canvas_stable':True, 'mobile_no_overflow':True, 'page_errors':errors, 'requests':requests, 'coordinator_url':page.locator('main').get_attribute('data-coordinator')}
        output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
        browser.close()
    server.shutdown()
