"""Verify production shared frames and the existing uniquely bound packet impairment proof."""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'spikes/d02'))
from verify_realtime import require,verify_network_evidence,digest,number
import firefox_driver

def normalized_periodic_hashes(hashes,pause,final):
 """Validate absolute checkpoint order; omit only acknowledged optional endpoints."""
 groups={}
 for packet in hashes:
  require(packet['kind']=='hash' and digest(packet['hash']),'invalid checkpoint record')
  groups.setdefault(packet['epoch'],[]).append(packet['frame'])
 require(len(groups)==2,'missing initial or resumed checkpoint epoch')
 pause_frame,final_frame=pause['frame'],final['frame']
 require(type(pause_frame) is int and type(final_frame) is int and 0<pause_frame<final_frame,'invalid epoch frame boundaries')
 # Both epochs share one absolute frame count. Every interior interval is
 # mandatory. A hash already sent at the freeze boundary must match its ack.
 boundaries=((0,pause_frame,pause['hash']),(pause_frame,final_frame,final['hash']))
 expected=[]
 for epoch,(start,end,boundary_hash) in zip(groups,boundaries):
  expected.extend((epoch,frame) for frame in range((start//120+1)*120,end,120))
  endpoints=[packet for packet in hashes if packet['epoch']==epoch and packet['frame']==end]
  if endpoints:
   require(end%120==0 and len(endpoints)==1 and endpoints[0]['hash']==boundary_hash,'invalid periodic boundary checkpoint')
   expected.append((epoch,end))
 require([(packet['epoch'],packet['frame']) for packet in hashes]==expected,'missing or reordered periodic checkpoint')
 return [packet for packet in hashes if packet['frame'] not in (pause_frame,final_frame)]

def verify(result,seconds):
 require(not result.get('controlled_worker_delivery_floor_ms'), 'controlled diagnostic is not qualification')
 require(result['result']=='pass' and not result['page_errors'],'browser failure')
 require(result['target_seconds']==seconds,'wrong workload')
 if seconds==600 and 'Firefox' in result['pair']:
  firefox_driver.validate_evidence(result,result['browsers'].get('Firefox'))
  instances=result.get('browser_instances',[])
  require([b.get('kind') for b in instances]==result['pair'].split('-'),'missing separate browser instances')
  for browser in instances:
   if browser['kind']=='Firefox':firefox_driver.validate_evidence(result,browser.get('version'))
 require(number(result['active_seconds']) and seconds<=result['active_seconds']<=seconds+2,'shared execution did not sustain the real-time workload')
 require(digest(result['identity']['romSha256']) and result['identity']['coreSha256'] in {value for name,value in result['build_files'].items() if name.endswith('.wasm')},'missing actual ROM/core artifact identity')
 peers=result['peers'];require(len(peers)==2,'missing peer')
 fps=peers[0]['fps'];require(number(fps) and 45<=fps<=65 and fps==peers[1]['fps'],'missing or unequal reported region rates')
 frames=math.ceil(seconds*fps);require(result['target_frames']==frames,'workload is not bound to reported region rate')
 require(result['pause'][0]==result['pause'][1] and result['final'][0]==result['final'][1],'pause divergence')
 require(result['final'][0]['frame']>=frames,'short committed workload')
 normalized=[normalized_periodic_hashes(peer['sentHashes'],result['pause'][i],result['final'][i]) for i,peer in enumerate(peers)]
 require(normalized[0]==normalized[1],'missing or divergent epoch/frame hash')
 require(peers[0]['hashes'][0]==peers[1]['hashes'][0],'initial machine hashes differ')
 for peer in peers:
  require(peer.get('scriptedInputs',0)>=max(1,(frames-300)//60),'missing sustained controller transitions')
  require(peer['controllerRam']==[128,64],'both controller ports were not observed by the CPU')
  require(peer['frameCount']>=frames and peer['frameCount']==result['final'][0]['frame'],'short or unaccounted peer execution')
  require(peer['hashes'][0]['fresh'] and peer['hashes'][0]['frame']==0,'not genuine initial state')
  require(all(3<=delay<=8 for delay in peer['timing']['delays']) and len(peer['timing']['delays'])==2,'invalid negotiated epochs')
 verify_network_evidence(result,seconds)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('result',type=Path);parser.add_argument('--seconds',type=int,choices=[30,600]);args=parser.parse_args()
 result=json.loads(args.result.read_text());verify(result,args.seconds or result['target_seconds']);print('PASS: production shared frames, controller inputs, matching hashes and actual impaired packets')
