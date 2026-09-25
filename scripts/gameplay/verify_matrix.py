"""Require all three production browser pairs and the same immutable client/core artifact."""
import argparse,json
from pathlib import Path
from verify import require,verify

def verify_matrix(directory, seconds=30):
 observed={}
 for path in directory.rglob('gameplay.json'):
  result=json.loads(path.read_text());pair=result['pair']
  require(pair not in observed,'duplicate production browser pair');verify(result,seconds);observed[pair]=result
 require(set(observed)=={'Chrome-Chrome','Chrome-Firefox','Firefox-Firefox'},'missing production browser pair')
 first=observed['Chrome-Chrome']
 require(set(first['source'])=={'commit','tree'} and all(len(value)==40 for value in first['source'].values()),'missing source provenance')
 for result in observed.values():
  require(result['source']==first['source'],'production matrix source mismatch')
  require(result['identity']==first['identity'] and result['build_files']==first['build_files'],'production matrix artifact mismatch')
 if seconds==30:
  relays={}
  for path in directory.rglob('relay-*.local.json'):
   result=json.loads(path.read_text());pair=result['pair']
   require(pair not in relays,'duplicate forced-relay browser pair')
   require(result['result']=='pass' and not result['page_errors'],'forced-relay browser failure')
   require(result['route']=='relay' and result['target_seconds']==8 and 8<=result['active_seconds']<=10,'missing measured forced-relay play')
   require(result['source']==first['source'] and result['identity']==first['identity'] and result['build_files']==first['build_files'],'forced-relay source or artifact mismatch')
   require(result['final'][0]==result['final'][1] and result['peers'][0]['sentHashes']==result['peers'][1]['sentHashes'],'forced-relay peer divergence')
   relays[pair]=result
  require(set(relays)==set(observed),'missing forced-relay browser pair')
 # Human input and pause timing can differ across runs. Each pair must agree on
 # every actual epoch/frame hash; D02 separately checks a common scripted replay.
 return observed

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--seconds',type=int,choices=[30,600],default=30);args=parser.parse_args();verify_matrix(args.directory,args.seconds);print(f'PASS: three {args.seconds}-second direct browser pairs, exact artifacts and matching peer hashes'+(' plus three forced-relay proofs' if args.seconds==30 else ''))
