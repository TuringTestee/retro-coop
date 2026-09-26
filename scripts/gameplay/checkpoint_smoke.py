"""Exercise real paused checkpoint recovery through the production worker and channel."""
import time

def worker(page,command):
 return page.evaluate('''command=>new Promise((resolve,reject)=>{const requestId=window.checkpointProofRequest=(window.checkpointProofRequest??910000)+1;const timer=setTimeout(()=>{currentWorker.removeEventListener('message',receive);reject(Error('Worker proof timed out'))},5000);function receive({data}){if(data.requestId!==requestId)return;clearTimeout(timer);currentWorker.removeEventListener('message',receive);if(data.type==='error')reject(Error(data.message));else resolve(data);}currentWorker.addEventListener('message',receive);currentWorker.postMessage({...command,requestId});})''',command)

def run(host,guest,mode,relay,out):
 pages=[host,guest]
 def membership(page):
  return page.evaluate('({id:proof.room.id,host:proof.room.hostMembership,members:proof.room.slots.filter(slot=>slot.member).map(slot=>({slot:slot.id,role:slot.role,id:slot.member.id})),self:proof.room.chatMembership,established:proof.room.established})')
 members=[membership(page) for page in pages];cancelled=None;cancel_page=host if relay else guest
 host.get_by_role('button',name='Pause',exact=True).click()
 for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
 original=worker(host,{'type':'state-hash'})['info'];assert original==worker(guest,{'type':'state-hash'})['info']
 # Diagnostic divergence changes only guest worker progress while the shared game is paused.
 guest.evaluate('''frame=>currentWorker.postMessage({type:'frame',epoch:proof.activeEpoch,frame,p1:128,p2:0})''',original['frame'])
 divergent=worker(guest,{'type':'state-hash'})['info'];assert divergent['frame']==original['frame']+1 and divergent['hash']!=original['hash']
 host.evaluate('''mode=>{window.checkpointProofMode=mode;const send=RTCDataChannel.prototype.send;RTCDataChannel.prototype.send=function(data){if(this.label==='retro-coop-checkpoint'&&data instanceof ArrayBuffer){if(window.checkpointProofMode==='cancel')return;if(window.checkpointProofMode==='corrupt'){data=data.slice(0);new Uint8Array(data)[data.byteLength-1]^=1;}}return send.call(this,data);}}''',mode)
 for page in pages:page.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
 if mode=='cancel':
  cancel_page.get_by_test_id('game-status').filter(has_text='Synchronizing').wait_for()
  cancel=cancel_page.get_by_role('button',name='Cancel synchronization',exact=True)
  cancel.wait_for();cancel.scroll_into_view_if_needed();cancel_page.screenshot(path=str(out.with_suffix('.cancelling.png')))
  cancel.click()
 if mode!='success':
  for page in pages:page.wait_for_function("!proof.room.game.ready?.length&&['failed','paused'].includes(proof.room.game.status)",polling=20)
  assert worker(host,{'type':'state-hash'})['info']==original
  assert worker(guest,{'type':'state-hash'})['info']==divergent
  assert [membership(page) for page in pages]==members
  if mode=='corrupt':return {'mode':mode,'result':'pass','host_preserved':original,'guest_preserved':divergent}
  for page in pages:page.get_by_test_id('game-status').filter(has_text='Synchronization cancelled. Game progress is preserved.').wait_for()
  cancel_page.get_by_role('button',name='Ready to resume',exact=True).scroll_into_view_if_needed();cancel_page.screenshot(path=str(out.with_suffix('.cancelled.png')))
  cancelled={'actor':'host' if relay else 'guest','host':original,'guest':divergent,'membership_preserved':True,'feedback':guest.get_by_test_id('game-status').inner_text()}
  host.evaluate("window.checkpointProofMode='success'")
  for page in pages:page.locator('.room-panel').get_by_role('button',name='Ready to resume',exact=True).click()
 for page in pages:page.wait_for_function("proof.room.game.status==='resume_ready'",polling=20)
 host.screenshot(path=str(out.with_suffix('.recovered.png')),mask=[host.locator('input[aria-label="Room invitation"]:visible')])
 recovered=[worker(page,{'type':'state-hash'})['info'] for page in pages]
 assert all(state['frame']==original['frame'] and state['hash']==original['hash'] for state in recovered),recovered
 host.get_by_role('button',name='Resume together',exact=True).click()
 for page in pages:page.wait_for_function("proof.room.game.status==='playing'",polling=20)
 host.wait_for_function('frame=>proof.frames.at(-1)?.frame>=frame+120',arg=original['frame'],polling=20)
 host.get_by_role('button',name='Pause',exact=True).click()
 for page in pages:page.wait_for_function("proof.room.game.status==='paused'",polling=20)
 resumed=[worker(page,{'type':'state-hash'})['info'] for page in pages];assert resumed[0]==resumed[1] and resumed[0]['frame']>original['frame']
 assert [membership(page) for page in pages]==members
 routes=[]
 for page in pages:
  route=page.evaluate("""async()=>{const reports=await Promise.all(gamePeers.map(peer=>peer.getStats()));for(const report of reports){const transport=[...report.values()].find(s=>s.type==='transport'&&s.selectedCandidatePairId);const pair=transport&&report.get(transport.selectedCandidatePairId);if(pair)return [report.get(pair.localCandidateId)?.candidateType,report.get(pair.remoteCandidateId)?.candidateType];}return [];}""")
  assert len(route)==2 and (('relay' in route)==relay),route;routes.append(route)
 return {'mode':mode,'result':'pass','host_preserved':original,'guest_before':divergent,'recovered':recovered,'resumed':resumed,'candidate_routes':routes,**({'cancelled':cancelled,'membership_preserved_after_retry':[membership(page) for page in pages]==members} if cancelled else {})}
