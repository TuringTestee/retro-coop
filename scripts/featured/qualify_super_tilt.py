"""Qualify the exact supplied Super Tilt Bro PAL build in the browser worker."""
import argparse,hashlib,http.server,json,platform,threading,time
from pathlib import Path
from playwright.sync_api import sync_playwright

EXPECTED='847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d';ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--wasm',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rom=a.rom.read_bytes();wasm=a.wasm.read_bytes()
 if len(rom)!=524304 or hashlib.sha256(rom).hexdigest()!=EXPECTED:p.error('not the exact supplied Super Tilt Bro PAL artifact')
 a.output.mkdir(parents=True,exist_ok=True);started=time.monotonic()
 class H(http.server.BaseHTTPRequestHandler):
  def log_message(self,*_):pass
  def do_GET(self):
   if self.path=='/':data=b'<canvas width="256" height="240" style="width:512px;height:480px;image-rendering:pixelated"></canvas>';kind='text/html'
   elif self.path=='/demo/worker.js':data=(ROOT/'spikes/d02/demo/worker.js').read_bytes();kind='text/javascript'
   elif self.path=='/target/wasm32-unknown-unknown/release/retro_coop_d02.wasm':data=wasm;kind='application/wasm'
   else:self.send_error(404);return
   self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 with http.server.ThreadingHTTPServer(('127.0.0.1',0),H)as server:
  threading.Thread(target=server.serve_forever,daemon=True).start()
  with sync_playwright()as pw:
   browser=pw.chromium.launch(channel='chrome',ignore_default_args=['--mute-audio']);page=browser.new_page(viewport={'width':528,'height':496});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{server.server_port}/')
   page.evaluate('''()=>{const w=new Worker('/demo/worker.js');window.call=data=>new Promise((ok,no)=>{const t=setTimeout(()=>no(Error('deadline')),15000);w.onmessage=({data})=>{clearTimeout(t);data.type==='error'?no(Error(data.message)):ok(data)};w.onerror=e=>no(Error(e.message));w.postMessage(data)});const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');window.step=async(n,p1=0,p2=0)=>{let last,peak=0,t=[];for(let i=0;i<n;i++){last=await call({type:'frame',p1,p2});for(const v of new Float32Array(last.audio))peak=Math.max(peak,Math.abs(v));t.push(hex(await crypto.subtle.digest('SHA-256',last.pixels)))}document.querySelector('canvas').getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(last.pixels),256,240),0,0);return{peak,timeline:hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(t.join('')))),last:t.at(-1)}}}''')
   page.evaluate('bytes=>call({type:"load",rom:new Uint8Array(bytes).buffer})',list(rom));boot=page.evaluate('step(1500)');assert boot['peak']>0;page.screenshot(path=str(a.output/'boot-menu.png'))
   page.evaluate('call({type:"save"})');neutral=page.evaluate('step(180)');page.evaluate('call({type:"restore"})');start=page.evaluate('step(1,8)');after_start=page.evaluate('step(600)');page.screenshot(path=str(a.output/'after-start.png'));assert neutral['timeline']!=after_start['timeline']
   page.evaluate('call({type:"save"})');idle=page.evaluate('step(180)');page.evaluate('call({type:"restore"})');p1=page.evaluate('step(180,129)');page.evaluate('call({type:"restore"})');p1_repeat=page.evaluate('step(180,129)');page.evaluate('call({type:"restore"})');p2=page.evaluate('step(180,0,129)');assert p1['timeline']==p1_repeat['timeline'];assert not errors
   result={'result':'pass','rom_sha256':EXPECTED,'rom_bytes':len(rom),'wasm_sha256':hashlib.sha256(wasm).hexdigest(),'browser':browser.version,'os':platform.system(),'duration_seconds':round(time.monotonic()-started,2),'boot_menu_rendered':True,'start_input_changed_timeline':True,'audio_nonzero_pcm':boot['peak'],'canonical_save_restore_replay':True,'p1_changed_timeline':p1['timeline']!=idle['timeline'],'p2_changed_timeline':p2['timeline']!=idle['timeline'],'limits':'Browser worker/core qualification with visual screenshots and PCM inspection; no physical controller or audible device capture, matched peer, exhaustive mechanics, or release-version provenance claim.'};(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));browser.close()
  server.shutdown()
if __name__=='__main__':main()
