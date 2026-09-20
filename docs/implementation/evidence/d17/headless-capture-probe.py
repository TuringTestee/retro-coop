import json,subprocess,os
from playwright.sync_api import sync_playwright
server=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],stdout=subprocess.PIPE,text=True,env={**os.environ,'TURN_URLS':'','TURN_SECRET':''})
try:
 url=json.loads(server.stdout.readline())['url']
 with sync_playwright() as p:
  for channel in [None,'chromium','chrome']:
   b=p.chromium.launch(**({'channel':channel} if channel else {}),ignore_default_args=['--mute-audio'],args=['--use-fake-device-for-media-stream'])
   tab=b.new_page();tab.context.grant_permissions(['microphone']);tab.goto(url)
   print(channel,b.version,tab.evaluate("""async()=>{try{const s=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});const n=s.getAudioTracks().length;s.getTracks().forEach(t=>t.stop());return {tracks:n}}catch(e){return {name:e.name,message:e.message}}}"""),flush=True);b.close()
finally:server.terminate();server.wait()
