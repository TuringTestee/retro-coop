import sys,json,http.server,threading
sys.path.insert(0,'/tmp/retro-d11-gameplay/spikes/d02')
import firefox_driver
from playwright.sync_api import sync_playwright
class H(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<!doctype html><title>Probe</title><p>empty page</p>')
 def log_message(self,*args):pass
with http.server.ThreadingHTTPServer(('127.0.0.1',0),H) as srv:
 threading.Thread(target=srv.serve_forever,daemon=True).start()
 with sync_playwright() as p:
  b=p.firefox.launch(**firefox_driver.launch_options('/tmp/d11-stock-146/firefox/firefox'));pg=b.new_page(**firefox_driver.page_options());errs=[];pg.on('pageerror',lambda e:errs.append({'message':str(e),'stack':e.stack}))
  samples=[]
  for scripts in [0,1,3]:
   if scripts:pg.add_init_script('window.probeValue=42;')
   pg.goto(f'http://127.0.0.1:{srv.server_port}/?scripts={scripts}')
   pg.wait_for_function('document.readyState==="complete"');samples.append({'scripts':scripts,'errors':list(errs)});errs.clear()
  b.close();print(json.dumps(samples));open('/tmp/d11-bidi-minimal.json','w').write(json.dumps(samples,indent=2)+'\n')
 srv.shutdown()
