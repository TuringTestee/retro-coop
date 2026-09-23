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
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='retro-cg1-preview-') as directory:
    rom = Path(directory) / 'original-preview.nes'
    rom.write_bytes(fixture())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.goto(args.url)
        page.get_by_role('button', name='Create game', exact=True).click()
        page.set_input_files('input[type=file]', str(rom))
        page.get_by_role('button', name='Play locally', exact=True).click()
        page.get_by_role('button', name='Resume', exact=True).click()
        page.wait_for_function("Number(document.querySelector('[data-testid=frames]')?.textContent?.match(/\\d+/)?.[0]||0)>=90", timeout=30000)
        if args.screenshot: page.screenshot(path=str(args.screenshot), full_page=True)
        proof = page.evaluate('''async()=>{
          const db=await new Promise((resolve,reject)=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});
          const rows=await new Promise((resolve,reject)=>{const q=db.transaction('roms').objectStore('roms').getAll();q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error)});db.close();
          const preview=rows[0]?.preview;const image=new Image();image.src=preview;await image.decode();
          const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;const context=canvas.getContext('2d');context.drawImage(image,0,0);
          const pixels=context.getImageData(0,0,canvas.width,canvas.height).data;let min=255,max=0;
          for(let i=0;i<pixels.length;i+=4){const y=Math.round((pixels[i]+pixels[i+1]+pixels[i+2])/3);min=Math.min(min,y);max=Math.max(max,y)}
          const thumbnail=[];for(let row=0;row<12;row++){let line='';for(let col=0;col<32;col++){const i=(row*canvas.width+col)*4;line+=(pixels[i]+pixels[i+1]+pixels[i+2])/3>68?'#':'.'}thumbnail.push(line)}
          const {previewDisplay,validPreview}=await import('/src/rom-library.ts');
          const fake=new Uint8Array(30);fake.set(new TextEncoder().encode('RIFF'),0);fake[4]=22;fake.set(new TextEncoder().encode('WEBPVP8X'),8);fake[24]=127;fake[27]=119;
          const fakeUrl='data:image/webp;base64,'+btoa(String.fromCharCode(...fake));
          const fakeImage=new Image();fakeImage.src=fakeUrl;try{await fakeImage.decode()}catch{}
          return {recordCount:rows.length,sha256:rows[0]?.sha256,size:rows[0]?.size,previewLength:preview?.length??0,previewWidth:image.naturalWidth,previewHeight:image.naturalHeight,previewMin:min,previewMax:max,thumbnail,syntheticHeaderAccepted:validPreview(fakeUrl),syntheticNaturalWidth:fakeImage.naturalWidth,syntheticFallback:await previewDisplay({label:'Broken',preview:fakeUrl})};
        }''')
        assert proof['recordCount'] == 1 and proof['size'] == len(fixture()), proof
        assert proof['previewLength'] < 32000 and proof['previewWidth'] == 128 and proof['previewHeight'] == 120, proof
        assert proof['previewMax'] - proof['previewMin'] >= 12, proof
        assert proof['syntheticHeaderAccepted'] and proof['syntheticNaturalWidth'] == 0, proof
        assert proof['syntheticFallback'] == {'text': 'No preview yet.'}, proof
        page.reload()
        count = page.evaluate('''async()=>{const db=await new Promise(r=>{const q=indexedDB.open('retro-coop-local',3);q.onsuccess=()=>r(q.result)});const q=await new Promise(r=>{const q=db.transaction('roms').objectStore('roms').getAll();q.onsuccess=()=>r(q.result)});db.close();return q.length}''')
        assert count == 1
        print(json.dumps({'result': 'pass', **proof, 'afterReloadRows': count}))
        browser.close()
