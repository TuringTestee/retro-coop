"""Run bounded production journeys once each and retain every result and failure log."""
import argparse,json,subprocess,sys,time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);args=parser.parse_args();args.directory.mkdir(parents=True,exist_ok=True)
cases=[('operator-remove',['--operator-playing','remove']),('operator-block',['--operator-playing','block']),('kick-playing',['--kick-playing']),('shared',['--screenshots']),('relay',['--relay']),('progressed',['--late-join']),('cancel',['--cancel-barrier']),('ack-timeout',['--barrier-timeout']),('retry-guest-first',['--retry-barrier','guest-first']),('retry-host-first',['--retry-barrier','host-first']),('delayed-start',['--delay-start'])]
cases.extend((fault,['--fault',fault]) for fault in ['drop-input','bad-hash','future-input','duplicate-input','old-epoch','focus','device'])
results=[]
for name,options in cases:
 started=time.monotonic()
 with (args.directory/(name+'.log')).open('w') as log:
  try:
   completed=subprocess.run([sys.executable,str(Path(__file__).with_name('browser_smoke.py')),*options,'--output',str(args.directory/(name+'.json'))],stdout=log,stderr=subprocess.STDOUT,timeout=30)
   code=completed.returncode
  except subprocess.TimeoutExpired:code=124
 results.append({'case':name,'exit_code':code,'seconds':round(time.monotonic()-started,2)})
 (args.directory/'suite.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps(results[-1]),flush=True)
 if code:raise SystemExit(code)
