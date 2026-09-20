"""Require all three production browser pairs and the same immutable client/core artifact."""
import argparse,json
from pathlib import Path
from verify import require,verify

def verify_matrix(directory):
 observed={}
 for path in directory.rglob('gameplay.json'):
  result=json.loads(path.read_text());pair=result['pair']
  require(pair not in observed,'duplicate production browser pair');verify(result,600);observed[pair]=result
 require(set(observed)=={'Chrome-Chrome','Chrome-Firefox','Firefox-Firefox'},'missing production browser pair')
 first=observed['Chrome-Chrome']
 for result in observed.values():
  require(result['identity']==first['identity'] and result['build_files']==first['build_files'],'production matrix artifact mismatch')
 # Human input and pause timing can differ across runs. Each pair must agree on
 # every actual epoch/frame hash; D02 separately checks a common scripted replay.
 return observed

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);args=parser.parse_args();verify_matrix(args.directory);print('PASS: three production browser pairs, exact artifacts and complete per-pair deterministic proofs')
