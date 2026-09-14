"""Exercise the playable page with the project's original diagnostic ROM."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("rom")
parser.add_argument("--url", default="http://127.0.0.1:8765/demo/")
parser.add_argument("--chrome", action="store_true")
parser.add_argument("--output", default="demo-smoke.local.json")
args = parser.parse_args()
muted_url = args.url + ('&' if '?' in args.url else '?') + 'muted=1'
started = time.monotonic()
with sync_playwright() as p:
    browser = p.chromium.launch(ignore_default_args=["--mute-audio"], **({"channel": "chrome"} if args.chrome else {}))
    page = browser.new_page(viewport={"width": 1280, "height": 1000})
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requests.append((request.method, request.url)))
    page.add_init_script("""window.audioProof={buffers:0,peak:0,starts:0};
      // Silence only this page's game output, including explicit unmute checks.
      const connect=AudioNode.prototype.connect, outputs=new WeakMap();
      AudioNode.prototype.connect=function(destination,...args){
        if(destination instanceof AudioDestinationNode){
          let silent=outputs.get(this.context);
          if(!silent){silent=this.context.createGain();silent.gain.value=0;connect.call(silent,destination);outputs.set(this.context,silent);}
          return connect.call(this,silent,...args);
        }
        return connect.call(this,destination,...args);
      };
      const copy=AudioBuffer.prototype.copyToChannel;
      AudioBuffer.prototype.copyToChannel=function(data,...rest){
        window.audioProof.buffers++;for(const x of data)window.audioProof.peak=Math.max(window.audioProof.peak,Math.abs(x));
        return copy.call(this,data,...rest);
      };
      const start=AudioBufferSourceNode.prototype.start;
      AudioBufferSourceNode.prototype.start=function(...args){window.audioProof.starts++;return start.apply(this,args)};
    """)
    page.goto(muted_url)
    page.screenshot(path="demo-before.local.png", full_page=True)
    page.set_input_files("#file", args.rom)
    page.wait_for_function("document.querySelector('#canvas').style.display === 'block'")
    page.wait_for_function("document.querySelector('canvas').getContext('2d').getImageData(0,0,1,1).data[3] === 255")
    before = page.locator("canvas").evaluate("c=>c.toDataURL()")
    page.locator("#screen").focus()
    page.keyboard.down("ArrowRight")
    page.wait_for_function("before=>document.querySelector('canvas').toDataURL()!==before", arg=before)
    page.keyboard.up("ArrowRight")
    page.screenshot(path="demo-after.local.png", full_page=True)
    assert page.locator('#sound').inner_text() == 'Unmute'
    assert page.evaluate('audioProof.starts') == 0
    page.locator("#sound").click()
    page.wait_for_function("audioProof.starts>3 && audioProof.peak>0")
    assert page.locator('#sound').inner_text() == 'Mute'
    page.locator('#sound').click()
    muted_starts = page.evaluate('audioProof.starts')
    page.wait_for_timeout(150)
    assert page.evaluate('audioProof.starts') == muted_starts
    assert page.locator('#sound').inner_text() == 'Unmute'
    page.locator("#pause").click()
    page.wait_for_function("document.querySelector('#screen').dataset.paused === 'true'")
    frozen = page.locator("canvas").evaluate("c=>c.toDataURL()")
    page.wait_for_timeout(200)
    assert frozen == page.locator("canvas").evaluate("c=>c.toDataURL()")
    page.locator("#pause").click()
    page.locator("#save").click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('Saved')")
    page.locator("#restore").click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('restored')")
    title = page.locator("#title").inner_text()
    page.set_input_files("#file", {"name": "invalid.nes", "mimeType": "application/octet-stream", "buffer": b"not a ROM"})
    page.wait_for_function("document.querySelector('#status').classList.contains('error')")
    assert page.locator("#title").inner_text() == title
    assert page.locator("canvas").is_visible()
    assert page.locator('#pause').inner_text() == 'Pause'
    page.set_viewport_size({"width": 700, "height": 900})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    audio_proof = page.evaluate("audioProof")
    # Hold the first file read until the second selection is ready, then await
    # the first digest explicitly. An older selection must never replace it.
    page.goto(muted_url)
    page.evaluate("""() => {
      const read=File.prototype.arrayBuffer, digest=crypto.subtle.digest.bind(crypto.subtle);
      window.loadDigests=[];
      File.prototype.arrayBuffer=async function(){
        if(this.name==='first.nes')await new Promise(resolve=>window.releaseFirstFile=resolve);
        return read.call(this);
      };
      crypto.subtle.digest=(...args)=>{const p=digest(...args);loadDigests.push(p);return p;};
    }""")
    rom = Path(args.rom).read_bytes()
    for name in ['first.nes', 'second.nes']:
        page.set_input_files('#file', {'name': name, 'mimeType': 'application/octet-stream', 'buffer': rom})
    page.wait_for_function("document.querySelector('#title').textContent === 'second'")
    page.evaluate('releaseFirstFile()')
    page.wait_for_function('loadDigests.length === 2')
    page.evaluate('loadDigests[1]')
    assert page.locator('#title').inner_text() == 'second'
    # Exercise non-NROM cartridge admission, NES 2.0, and drop through the actual page.
    # These original diagnostics exercise boot/input/save paths, not every banking feature.
    cartridge_cases = []
    for mapper in [1, 2, 3, 4, 7]:
        fixture = bytearray(rom)
        fixture[4] = 2
        fixture[6] = mapper << 4
        fixture[16+16384:16+16384] = rom[16:16+16384]
        name = f'mapper-{mapper}.nes'
        page.set_input_files('#file', {'name': name, 'mimeType': 'application/octet-stream', 'buffer': bytes(fixture)})
        page.wait_for_function("name=>document.querySelector('#title').textContent===name", arg=name[:-4])
        page.locator('#save').click()
        page.wait_for_function("document.querySelector('#status').textContent.includes('Saved')")
        page.locator('#restore').click()
        page.wait_for_function("document.querySelector('#status').textContent.includes('restored')")
        cartridge_cases.append(mapper)
    fixture[7] = 8  # NES 2.0, mapper 7, same original diagnostic.
    page.evaluate("""bytes=>{
      const transfer=new DataTransfer();
      transfer.items.add(new File([new Uint8Array(bytes)],'nes2-drop.nes'));
      document.querySelector('#screen').dispatchEvent(new DragEvent('drop',{dataTransfer:transfer,bubbles:true,cancelable:true}));
    }""", list(fixture))
    page.wait_for_function("document.querySelector('#title').textContent==='nes2-drop'")
    # The former application size cutoff is gone: a valid core-readable cartridge
    # with trailing bytes is passed to the core even above 8 MiB.
    large = bytes(fixture) + bytes(8*1024*1024)
    page.set_input_files('#file', {'name':'large.nes','mimeType':'application/octet-stream','buffer':large})
    page.wait_for_function("document.querySelector('#title').textContent==='large'")
    assert page.evaluate('audioProof.starts') == 0
    # Normal play starts audio after a user gesture, without an unmute click.
    page.goto(args.url)
    with page.expect_file_chooser() as chooser:
        page.locator('#choose').click()
    chooser.value.set_files(args.rom)
    page.wait_for_function("audioProof.starts>3 && audioProof.peak>0")
    assert page.locator('#sound').inner_text() == 'Mute'
    page.screenshot(path="demo-normal.local.png", full_page=True)
    page.locator('#sound').click()
    assert page.locator('#sound').inner_text() == 'Unmute'
    assert not errors, errors
    assert all(method == "GET" and url.startswith(args.url.split('/demo/')[0]) for method, url in requests), requests
    result = {"browser_version": browser.version, "wall_seconds": time.monotonic()-started,
                      "rom_sha256": hashlib.sha256(Path(args.rom).read_bytes()).hexdigest(),
                      "non_nrom_mappers_loaded_and_saved": cartridge_cases, "nes2_drop": True, "over_8_mib_admitted": True,
                      "test_starts_muted": True, "normal_start_unmuted": True, "mute_stops_scheduling": True,
                      "manual_input_changes_pixels": True, "pause_freezes_pixels": True,
                      "latest_file_selection_wins": True,
                      "save_restore": True, "invalid_rom_preserves_game": True,
                      "narrow_layout_no_overflow": True, "audio": audio_proof,
                      "page_errors": errors, "no_upload_requests": True}
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    browser.close()
