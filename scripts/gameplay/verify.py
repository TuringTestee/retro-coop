"""Verify production shared frames and the existing uniquely bound packet impairment proof."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'spikes/d02'))
from verify_realtime import require,verify_network_evidence,digest,number

def verify(result,seconds):
 require(result['result']=='pass' and not result['page_errors'],'browser failure')
 require(result['target_seconds']==seconds,'wrong workload')
 require(number(result['active_seconds']) and seconds-1<=result['active_seconds']<=seconds+2,'shared execution did not sustain the real-time workload')
 require(digest(result['identity']['romSha256']) and result['identity']['coreSha256'] in result['build_files'].values(),'missing actual ROM/core artifact identity')
 peers=result['peers'];require(len(peers)==2,'missing peer')
 require(result['pause'][0]==result['pause'][1] and result['final'][0]==result['final'][1],'pause divergence')
 require(result['final'][0]['frame']>=seconds*60,'short committed workload')
 require(peers[0]['sentHashes']==peers[1]['sentHashes'],'missing or divergent epoch/frame hash')
 hashes=peers[0]['sentHashes'];require(len(hashes)>=seconds*60//120-1,'missing periodic hashes')
 for peer in peers:
  require(peer.get('scriptedInputs',0)>=max(1,seconds-5),'missing sustained controller transitions')
  require(peer['controllerRam']==[128,64],'both controller ports were not observed by the CPU')
  require(peer['frameCount']>=seconds*60,'short peer execution')
  require(peer['hashes'][0]['fresh'] and peer['hashes'][0]['frame']==0,'not genuine initial state')
  require(all(3<=delay<=8 for delay in peer['timing']['delays']) and len(peer['timing']['delays'])==2,'invalid negotiated epochs')
 verify_network_evidence(result,seconds)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('result',type=Path);parser.add_argument('--seconds',type=int,choices=[30,600]);args=parser.parse_args()
 result=json.loads(args.result.read_text());verify(result,args.seconds or result['target_seconds']);print('PASS: production shared frames, controller inputs, matching hashes and actual impaired packets')
