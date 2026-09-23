#!/usr/bin/env python3
"""Check CG1 preview capture and decode fallback with an original patterned NES file."""
import argparse
import json
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright


def fixture():
    code = bytearray()
    def emit(*values): code.extend(values)
    def store(value, low): emit(0xa9, value, 0x8d, low, 0x20)
    emit(0x78, 0xd8, 0xa2, 0xff, 0x9a)  # SEI, CLD, LDX, TXS
    store(0, 0); store(0, 1)  # Disable rendering during palette setup.
    for _ in range(2): emit(0x2c, 2, 0x20, 0x10, 0xfb)  # Wait for vblank.
    store(0x3f, 6); store(0, 6); store(0x0f, 7); store(0x30, 7)
    store(0, 0); store(0x08, 1)  # Show a background of tile zero.
    loop = len(code); emit(0x4c, loop & 255, 0x80 + (loop >> 8))
    prg = code + bytearray([0xea]) * (16384 - len(code))
    for offset in (0x3ffa, 0x3ffc, 0x3ffe):
        prg[offset:offset + 2] = (0x8000).to_bytes(2, 'little')
    chr_rom = bytearray(8192)
    for row in range(8): chr_rom[row] = 0xaa if row % 2 == 0 else 0x55
    return b'NES\x1a' + bytes([1, 1]) + bytes(10) + prg + chr_rom


parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--screenshot', type=Path)
parser.add_argument('--narrow-screenshot', type=Path)
parser.add_argument('--narrow-preview-screenshot', type=Path)
parser.add_argument('--narrow-bottom-screenshot', type=Path)
parser.add_argument('--keyboard-screenshot', type=Path)
parser.add_argument('--fallback-screenshot', type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='retro-cg1-preview-') as directory:
    rom = Path(directory) / 'original-preview.nes'
    rom.write_bytes(fixture())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 1050})
        page.goto(args.url)
        page.get_by_role('button', name='Create game', exact=True).click()
        page.set_input_files('input[type=file]', str(rom))
        page.get_by_role('button', name='Play locally', exact=True).click()
        page.get_by_role('button', name='Resume', exact=True).click()
        page.wait_for_function("Number(document.querySelector('[data-testid=frames]')?.textContent?.match(/\\d+/)?.[0]||0)>=90", timeout=30000)
        diagnostic = page.evaluate('''async()=>{
          const db=await new Promise((resolve,reject)=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
          const rows=await new Promise((resolve,reject)=>{const q=db.transaction('roms').objectStore('roms').getAll();q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});db.close();
          const {capturePreview,previewDisplay,validPreview}=await import('/src/rom-library.ts');
          const checker=document.createElement('canvas');checker.width=256;checker.height=240;const context=checker.getContext('2d');
          for(let y=0;y<240;y++)for(let x=0;x<256;x++){context.fillStyle=(x+y)%2?'#000':'#fff';context.fillRect(x,y,1,1)}
          const averaged=await capturePreview(checker);
          const nearUniform=document.createElement('canvas');nearUniform.width=128;nearUniform.height=120;const flat=nearUniform.getContext('2d');flat.fillStyle='#818181';flat.fillRect(0,0,128,120);flat.fillStyle='#fff';flat.fillRect(0,0,1,1);
          const nearUniformUrl=nearUniform.toDataURL('image/webp',0.5);
          const fake=new Uint8Array(30);fake.set(new TextEncoder().encode('RIFF'),0);fake[4]=22;fake.set(new TextEncoder().encode('WEBPVP8X'),8);fake[24]=127;fake[27]=119;
          const fakeUrl='data:image/webp;base64,'+btoa(String.fromCharCode(...fake));
          const fakeImage=new Image();fakeImage.src=fakeUrl;try{await fakeImage.decode()}catch{}
          return {recordCount:rows.length,size:rows[0]?.size,diagnosticPreview:rows[0]?.preview??null,sourceCheckerRejected:averaged===undefined,nearUniformHeaderAccepted:validPreview(nearUniformUrl),nearUniformFallback:await previewDisplay({label:'Near uniform',preview:nearUniformUrl}),syntheticHeaderAccepted:validPreview(fakeUrl),syntheticNaturalWidth:fakeImage.naturalWidth,syntheticFallback:await previewDisplay({label:'Broken',preview:fakeUrl})};
        }''')
        assert diagnostic['recordCount'] == 1 and diagnostic['size'] == len(fixture()), diagnostic
        assert diagnostic['diagnosticPreview'] is None and diagnostic['sourceCheckerRejected'], diagnostic
        assert diagnostic['nearUniformHeaderAccepted'] and diagnostic['nearUniformFallback'] == {'text':'No preview yet.'}, diagnostic
        assert diagnostic['syntheticHeaderAccepted'] and diagnostic['syntheticNaturalWidth'] == 0 and diagnostic['syntheticFallback'] == {'text':'No preview yet.'}, diagnostic
        page.get_by_role('button',name='Public rooms',exact=True).click()
        page.get_by_role('button',name='Create game',exact=True).click()
        page.get_by_text('No preview yet.',exact=True).wait_for()
        if args.fallback_screenshot: page.screenshot(path=str(args.fallback_screenshot),full_page=True)
        page.locator('.create-library li').filter(has_text='Super Tilt Bro').get_by_role('button').click()
        page.get_by_role('button',name='Play locally',exact=True).click()
        page.get_by_role('button',name='Resume',exact=True).click()
        page.wait_for_function("Number(document.querySelector('[data-testid=frames]')?.textContent?.match(/\\d+/)?.[0]||0)>=180", timeout=30000)
        page.wait_for_function('''async()=>{const db=await new Promise(r=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>r(q.result)});const rows=await new Promise(r=>{const q=db.transaction('roms').objectStore('roms').getAll();q.onsuccess=()=>r(q.result)});db.close();return rows.some(row=>row.label==='Super Tilt Bro'&&row.preview)}''', timeout=30000)
        page.evaluate('''async()=>{const canvas=document.createElement('canvas');canvas.width=128;canvas.height=120;const context=canvas.getContext('2d');context.fillStyle='#818181';context.fillRect(0,0,128,120);context.fillStyle='#fff';context.fillRect(0,0,1,1);const preview=canvas.toDataURL('image/webp',0.5);const db=await new Promise(r=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>r(q.result)});const tx=db.transaction('roms','readwrite'),store=tx.objectStore('roms');const rows=await new Promise(r=>{const q=store.getAll();q.onsuccess=()=>r(q.result)});const diagnostic=rows.find(row=>row.label==='original-preview.nes');store.put({...diagnostic,preview,lastUsedAt:Date.now()+10000});await new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});db.close()}''')
        page.get_by_role('button',name='Public rooms',exact=True).click()
        page.get_by_role('button',name='Create game',exact=True).click()
        page.wait_for_function("document.querySelector('.create-preview img')?.naturalWidth===128",timeout=15000)
        page.locator('.create-library li').filter(has_text='Super Tilt Bro').get_by_role('button').click()
        page.wait_for_function("!document.querySelector('.create-actions button')?.disabled",timeout=15000)
        if args.screenshot: page.screenshot(path=str(args.screenshot),full_page=True)
        result=page.evaluate('''async()=>{const image=document.querySelector('.create-preview img');const db=await new Promise(r=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>r(q.result)});const rows=await new Promise(r=>{const q=db.transaction('roms').objectStore('roms').getAll();q.onsuccess=()=>r(q.result)});db.close();return {previewWidth:image.naturalWidth,previewHeight:image.naturalHeight,previewAlt:image.alt,storedRows:rows.length,storedPreviewLength:rows.find(row=>row.preview===image.src)?.preview?.length??0,selected:document.querySelector('.create-options strong')?.textContent,noRoom:!document.querySelector('[data-testid=room-view]')}}''')
        assert result['previewWidth']==128 and result['previewHeight']==120 and result['storedPreviewLength']>0 and result['selected']=='Super Tilt Bro' and result['noRoom'],result
        if args.narrow_screenshot:
            page.set_viewport_size({'width':390,'height':700})
            page.locator('.create-game').evaluate('(node)=>node.scrollTop=0')
            page.screenshot(path=str(args.narrow_screenshot),full_page=True)
            result['narrowNoOverflow']=page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert result['narrowNoOverflow'],result
            if args.narrow_preview_screenshot:
                page.locator('.create-preview').scroll_into_view_if_needed()
                page.screenshot(path=str(args.narrow_preview_screenshot),full_page=True)
            if args.narrow_bottom_screenshot:
                page.locator('.create-game').evaluate('(node)=>node.scrollTop=node.scrollHeight')
                page.screenshot(path=str(args.narrow_bottom_screenshot),full_page=True)
            page.set_viewport_size({'width':1280,'height':1050})
        if args.keyboard_screenshot:
            page.get_by_role('button',name='Create room',exact=True).focus()
            page.keyboard.press('Shift+Tab')
            page.keyboard.press('Tab')
            result['keyboardFocus']=page.evaluate("document.activeElement?.textContent?.trim()==='Create room'")
            assert result['keyboardFocus'],result
            page.screenshot(path=str(args.keyboard_screenshot),full_page=True)
        print(json.dumps({'result':'pass','diagnostic':diagnostic,'meaningful':result}))
        browser.close()
