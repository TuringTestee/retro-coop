"""Compare exact worker outputs and phase costs in an unmodified standalone browser.

ORACLE_FIREFOX=/path/to/firefox python3 scripts/gameplay/performance_probe.py result.json
This bounded 600-frame diagnostic is not the 600-second network qualification.
"""
import os,ast,json,threading,http.server,functools,subprocess,tempfile,time,hashlib,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];dist=root/'apps/client/dist'
sys.path.insert(0,str(root/'scripts/foundation'))
from worker_probe import WORKER_PROBE_SCRIPT
setup=WORKER_PROBE_SCRIPT
action=(root/'scripts/gameplay/performance-workload.js').read_text()
worker='/assets/'+next((dist/'assets').glob('worker-*.js')).name
prefix=(root/'scripts/gameplay/performance-worker.js').read_text()
html='<script>'+setup+'\nconst start=performance.now();('+action+')('+json.dumps(worker)+').then(result=>fetch("/result",{method:"POST",body:JSON.stringify({...result,seconds:(performance.now()-start)/1000,userAgent:navigator.userAgent})})).catch(error=>fetch("/result",{method:"POST",body:JSON.stringify({error:String(error),stack:error.stack})}));</script>'
done=threading.Event(); result={}
class Handler(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if self.path=='/probe.html': data=html.encode()
  elif self.path==worker:data=(prefix+(dist/worker.lstrip('/')).read_text()).encode()
  else:return super().do_GET()
  self.send_response(200);self.send_header('Content-Type','text/html' if self.path=='/probe.html' else 'text/javascript');self.end_headers();self.wfile.write(data)
 def do_POST(self):
  result.update(json.loads(self.rfile.read(int(self.headers['Content-Length']))));self.send_response(200);self.end_headers();done.set()
with tempfile.TemporaryDirectory(prefix='d11-standalone-profile-') as profile:
 with http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(dist))) as server:
  threading.Thread(target=server.serve_forever,daemon=True).start()
  with open(str(sys.argv[1])+'.stderr.log','w') as log:
   binary=os.environ['ORACLE_FIREFOX']
   command=[binary,'--headless','--no-remote','--profile',profile,f'http://127.0.0.1:{server.server_port}/probe.html']
   browser=subprocess.Popen(command,stdout=log,stderr=log)
   try:
    if not done.wait(60):raise RuntimeError('standalone oracle deadline')
   finally:
    browser.terminate();browser.wait(timeout=10);server.shutdown()
result.update(driver='standalone Firefox, no Juggler or WebDriver connection',binary=binary,binary_sha256=hashlib.sha256(Path(binary).read_bytes()).hexdigest(),wasm_bytes=next((dist/'assets').glob('*.wasm')).stat().st_size)
Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
