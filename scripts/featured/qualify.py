"""Qualify the pinned featured binary through the existing local-player worker.

The caller supplies the ROM; neither this script nor CI downloads or publishes it.
This is accelerated core/worker evidence, not real-time or multiplayer acceptance.
"""
import argparse
import hashlib
import http.server
import json
from pathlib import Path
import platform
import threading
import time
from playwright.sync_api import sync_playwright

ROM_SHA256 = '1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555'
ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--wasm', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rom, wasm = args.rom.read_bytes(), args.wasm.read_bytes()
    if len(rom) != 40976 or hashlib.sha256(rom).hexdigest() != ROM_SHA256:
        parser.error('This is not the selected exact From Below NES 1.0 artifact')
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            if self.path == '/':
                data = b'<canvas width="256" height="240" style="width:512px;height:480px;image-rendering:pixelated"></canvas>'
                content_type = 'text/html'
            elif self.path == '/demo/worker.js':
                data = (ROOT / 'spikes/d02/demo/worker.js').read_bytes()
                content_type = 'text/javascript'
            elif self.path == '/target/wasm32-unknown-unknown/release/retro_coop_d02.wasm':
                data, content_type = wasm, 'application/wasm'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    records, requests, errors = [], [], []
    with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='chrome', ignore_default_args=['--mute-audio'])
            page = browser.new_page(viewport={'width': 528, 'height': 496})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append({'method': request.method, 'path': request.url.split(f':{server.server_port}', 1)[-1]}))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.evaluate('''() => {
              const worker = new Worker('/demo/worker.js');
              window.call = data => new Promise((resolve,reject) => {
                const timer = setTimeout(()=>reject(Error('Worker response deadline exceeded')),10000);
                worker.onmessage = ({data}) => {clearTimeout(timer);data.type==='error'?reject(Error(data.message)):resolve(data);};
                worker.onerror = event => {clearTimeout(timer);reject(Error(event.message));};
                worker.postMessage(data);
              });
              const hex = bytes => [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');
              window.step = async (frames,p1=0,p2=0) => {
                let peak=0,last; const samples=[];
                for(let frame=0;frame<frames;frame++) {
                  last=await call({type:'frame',p1,p2});
                  for(const value of new Float32Array(last.audio)) peak=Math.max(peak,Math.abs(value));
                  // Video is canonical here; the core intentionally retains session audio history across restore.
                  samples.push(hex(await crypto.subtle.digest('SHA-256',last.pixels)));
                }
                document.querySelector('canvas').getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(last.pixels),256,240),0,0);
                return {frames,peak,pixel_sha256:hex(await crypto.subtle.digest('SHA-256',last.pixels)),audio_sha256:hex(await crypto.subtle.digest('SHA-256',last.audio)),video_timeline_sha256:hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(samples.join(''))))};
              };
            }''')

            def step(frames, p1=0, p2=0):
                return page.evaluate('([n,p1,p2])=>step(n,p1,p2)', [frames, p1, p2])

            def press(mask):
                step(1, mask)
                step(30)

            for name, label, direction in [('timed', 'TIMED', 0), ('classic', 'CLASSIC', 128), ('fixed', 'FIXED', 64)]:
                page.evaluate('bytes=>call({type:"load",rom:new Uint8Array(bytes).buffer})', list(rom))
                boot = step(600)
                assert boot['peak'] > 0, 'Expected game PCM after boot'
                if name == 'timed':
                    page.screenshot(path=str(args.output / 'title.png'))
                    page.evaluate('call({type:"save"})')
                    page.evaluate('call({type:"restore"})')
                    title_idle = step(60)
                    page.evaluate('call({type:"restore"})')
                    title_p2 = step(60, p2=255)
                    assert title_idle['video_timeline_sha256'] == title_p2['video_timeline_sha256']
                press(8)  # P1 Start opens the game's own options.
                if direction:
                    press(32)  # Select the MODE row, then move from its TIMED default.
                    press(direction)
                page.screenshot(path=str(args.output / f'{name}-options.png'))
                page.evaluate('call({type:"save"})')
                page.evaluate('call({type:"restore"})')
                menu_idle = step(60)
                page.evaluate('call({type:"restore"})')
                menu_p2 = step(60, p2=255)
                assert menu_idle['video_timeline_sha256'] == menu_p2['video_timeline_sha256']
                press(8)
                playing = step(120)
                assert playing['peak'] > 0
                page.evaluate('call({type:"save"})')
                page.evaluate('call({type:"restore"})')
                idle = step(120)
                page.evaluate('call({type:"restore"})')
                p2 = step(120, p2=255)
                assert idle['video_timeline_sha256'] == p2['video_timeline_sha256'], name
                page.evaluate('call({type:"restore"})')
                p1 = step(120, p1=128)
                assert idle['video_timeline_sha256'] != p1['video_timeline_sha256'], name
                page.screenshot(path=str(args.output / f'{name}-playing.png'))
                page.evaluate('call({type:"restore"})')
                replay = step(120, p1=128)
                assert p1['video_timeline_sha256'] == replay['video_timeline_sha256'], name
                records.append({'mode': name, 'expected_menu_label': label, 'boot': boot, 'playing': playing,
                                'menu_p2_video_matches_idle': True, 'idle': idle, 'p2': p2, 'p1': p1,
                                'restored_p1_replay': replay})
            assert not errors, errors
            assert all(request['method'] == 'GET' for request in requests), requests
            assert all(request['path'] in ('/', '/demo/worker.js', '/target/wasm32-unknown-unknown/release/retro_coop_d02.wasm') for request in requests), requests
            result = {'result': 'pass', 'rom_sha256': ROM_SHA256, 'rom_bytes': len(rom),
                      'wasm_sha256': hashlib.sha256(wasm).hexdigest(), 'browser': browser.version,
                      'os': platform.system(), 'duration_seconds': round(time.monotonic()-started, 2),
                      'title_p2_video_matches_idle': True, 'modes': records, 'requests': requests, 'page_errors': errors,
                      'audio': 'Nonzero PCM inspected; no AudioContext/device output created. PCM identity across restore is not asserted because upstream preserves running session synth/filter history.',
                      'scope': 'Accelerated local core/worker checks; screenshots require visual inspection; not real-time, network, exhaustive mechanics or final release qualification'}
            (args.output / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(result, indent=2))
            browser.close()
        server.shutdown()


if __name__ == '__main__':
    main()
