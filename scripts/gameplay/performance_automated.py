"""Run the same bounded worker oracle through patched Firefox automation.

ORACLE_FIREFOX=/path/to/bundled/firefox python3 scripts/gameplay/performance_automated.py result.json
This preserves the driver used for the rejected compiler experiments.
"""
import argparse,sys,json,time,hashlib,os
from pathlib import Path
from playwright.sync_api import sync_playwright
import subprocess
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'scripts/foundation'))
from worker_probe import prepare_worker_probe,finish_worker_probe
parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(service.stdout.readline())['url'];dist=root/'apps/client/dist';worker='/assets/'+next((dist/'assets').glob('worker-*.js')).name
 prefix=(root/'scripts/gameplay/performance-worker.js').read_text()
 with sync_playwright() as p:
  browser=p.firefox.launch(executable_path=os.environ['ORACLE_FIREFOX'])
  page,requests=prepare_worker_probe(browser,url)
  page.unroute('**/worker-*.js')
  def profile(route):
   response=route.fetch();route.fulfill(response=response,body=prefix+response.text())
  page.route('**/worker-*.js',profile)
  started=time.monotonic()
  result=page.evaluate((root/'scripts/gameplay/performance-workload.js').read_text(),worker)
  result.update(seconds=time.monotonic()-started,browser=browser.version,wasm_bytes=next((dist/'assets').glob('*.wasm')).stat().st_size,source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip())
  finish_worker_probe(page,requests,url,result);browser.close()
 Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
finally:service.terminate();service.wait(timeout=5)
