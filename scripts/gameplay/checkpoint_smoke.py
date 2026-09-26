"""Exercise real paused checkpoint recovery through the production worker and channel."""
import time

def run(host,guest,mode,relay):
 pages=[host,guest]
 def worker(page,command):
  return page.evaluate('''command=>new Promise((resolve,reject)=>{const requestId=window.checkpointProofRequest=(window.checkpointProofRequest??910000)+1;const timer=setTimeout(()=>{currentWorker.removeEventListener('message',receive);reject(Error('Worker proof timed out'))},5000);function receive({data}){if(data.requestId!==requestId)return;clearTimeout(timer);currentWorker.removeEventListener('message',receive);if(data.type==='error')reject(Error(data.message));else resolve(data);}currentWorker.addEventListener('message',receive);currentWorker.postMessage({...command,requestId});})''',command)
 host.get_by_role('button',name='Pause',exact=True).click()
 for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
 original=worker(host,{'type':'state-hash'})['info'];assert original==worker(guest,{'type':'state-hash'})['info']
 # Diagnostic divergence changes only guest worker progress while the shared game is paused.
 guest.evaluate('''frame=>currentWorker.postMessage({type:'frame',epoch:proof.activeEpoch,frame,p1:128,p2:0})''',original['frame'])
 divergent=worker(guest,{'type':'state-hash'})['info'];assert divergent['frame']==original['frame']+1 and divergent['hash']!=original['hash']
 host.evaluate('''mode=>{const send=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(this.label==='retro-coop-checkpoint'&&data instanceof ArrayBuffer){if(mode==='cancel')return;if(mode==='corrupt'){data=data.slice(0);new Uint8Array(data)[data.byteLength-1]^=1;}}return send.call(this,data);}}''',mode)
 for page in pages:page.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
 if mode=='cancel':
  guest.wait_for_function("document.querySelector('[data-testid=game-status]').textContent.includes('Synchronizing')",polling=20)
  guest.evaluate("proof.roomSocket.send(JSON.stringify({type:'gameUnready',requestId:crypto.randomUUID(),peerEpoch:proof.room.peer.epoch}))")
 if mode!='success':
  for page in pages:page.wait_for_function("!proof.room.game.ready?.length&&['failed','paused'].includes(proof.room.game.status)",polling=20)
  assert worker(host,{'type':'state-hash'})['info']==original
  assert worker(guest,{'type':'state-hash'})['info']==divergent
  return {'mode':mode,'result':'pass','host_preserved':original,'guest_preserved':divergent}
 for page in pages:page.wait_for_function("proof.room.game.status==='resume_ready'",polling=20)
 recovered=[worker(page,{'type':'state-hash'})['info'] for page in pages]
 assert all(state['frame']==original['frame'] and state['hash']==original['hash'] for state in recovered),recovered
 host.get_by_role('button',name='Resume together',exact=True).click()
 for page in pages:page.wait_for_function("proof.room.game.status==='playing'",polling=20)
 host.wait_for_function('frame=>proof.frames.at(-1)?.frame>=frame+120',arg=original['frame'],polling=20)
 host.get_by_role('button',name='Pause',exact=True).click()
 for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
 resumed=[worker(page,{'type':'state-hash'})['info'] for page in pages];assert resumed[0]==resumed[1] and resumed[0]['frame']>original['frame']
 routes=[]
 for page in pages:
  route=page.evaluate("""async()=>{const reports=await Promise.all(gamePeers.map(peer=>peer.getStats()));for(const report of reports){const transport=[...report.values()].find(s=>s.type==='transport'&&s.selectedCandidatePairId);const pair=transport&&report.get(transport.selectedCandidatePairId);if(pair)return [report.get(pair.localCandidateId)?.candidateType,report.get(pair.remoteCandidateId)?.candidateType];}return [];}""")
  assert len(route)==2 and (('relay' in route)==relay),route;routes.append(route)
 return {'mode':mode,'result':'pass','host_preserved':original,'guest_before':divergent,'recovered':recovered,'resumed':resumed,'candidate_routes':routes}
