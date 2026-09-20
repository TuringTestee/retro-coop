import argparse,json,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--chrome',action='store_true');parser.add_argument('--output',default='voice.local.json');args=parser.parse_args();started=time.monotonic()
root=Path(__file__).resolve().parents[2];server=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,stdout=subprocess.PIPE,text=True)
try:
 url=json.loads(server.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
 with sync_playwright() as p:
  browser=p.chromium.launch(**({'channel':'chrome'} if args.chrome else {}),ignore_default_args=['--mute-audio'],args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']);errors=[]
  def page(url):
   tab=browser.new_page();tab.on('pageerror',lambda e:errors.append(str(e)));tab.add_init_script('''window.pcs=[];window.captures=[];const replace=RTCRtpSender.prototype.replaceTrack;RTCRtpSender.prototype.replaceTrack=function(track){if(window.rejectAttachment&&track)return Promise.reject(new DOMException('fixture attach failure','InvalidModificationError'));return replace.call(this,track)};window.voiceAudio=[];const NativeAudio=Audio;window.Audio=class extends NativeAudio{constructor(...args){super(...args);voiceAudio.push(this)}play(){if(window.blockPlayback)return Promise.reject(Error('fixture playback denial'));return super.play()}};const Native=RTCPeerConnection;window.RTCPeerConnection=class extends Native{constructor(...args){super(...args);pcs.push(this)}};const capture=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{if(window.denyCapture)throw new DOMException('fixture denial','NotAllowedError');if(window.missingDevice)throw new DOMException('fixture device missing','NotFoundError');if(window.holdCapture)await new Promise(resolve=>window.releaseCapture=resolve);const s=await capture(c);captures.push(s);return s};''');tab.goto(url);return tab
  host=page(url);host.set_input_files('input[type=file]',{'name':'fixture.nes','mimeType':'application/octet-stream','buffer':rom});host.get_by_test_id('room-view').wait_for()
  guest=page(host.get_by_label('Room invitation',exact=True).input_value());guest.get_by_role('button',name='Retry join / Join',exact=True).click();guest.get_by_test_id('room-view').wait_for()
  for tab in [host,guest]:
   tab.wait_for_function("document.querySelector('[data-testid=connection-status]').textContent.includes('Route: direct')")
   assert tab.evaluate('captures.length')==0
   tab.locator('.room-panel').get_by_label('Remote voice volume',exact=False).fill('0')
   tab.get_by_role('button',name='Enable voice',exact=True).click()
   tab.locator('.room-panel').get_by_text('Transmitting microphone audio',exact=True).wait_for()
  for tab in [host,guest]:
   tab.wait_for_function('''async()=>{const stats=await pcs.at(-1).getStats();return [...stats.values()].some(s=>s.type==='inbound-rtp'&&s.kind==='audio'&&s.totalAudioEnergy>0&&s.packetsReceived>0)}''')
  panel=host.locator('.room-panel')
  frame_before=host.get_by_test_id('frames').inner_text()
  panel.get_by_label('Voice mode',exact=True).select_option('push')
  host.get_by_label('Local game screen',exact=True).focus();host.keyboard.down('KeyV')
  host.wait_for_function('captures.at(-1).getAudioTracks().every(t=>t.enabled)');host.keyboard.up('KeyV')
  host.wait_for_function('captures.at(-1).getAudioTracks().every(t=>!t.enabled)')
  panel.get_by_role('button',name='Hold to talk',exact=True).focus();host.keyboard.down('Space')
  host.wait_for_function('captures.at(-1).getAudioTracks().every(t=>t.enabled)');host.keyboard.up('Space')
  host.wait_for_function('captures.at(-1).getAudioTracks().every(t=>!t.enabled)')
  host.get_by_label('Room invitation',exact=True).focus();host.keyboard.down('KeyV');host.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');assert host.evaluate('captures.at(-1).getAudioTracks().every(t=>!t.enabled)');host.keyboard.up('KeyV')
  panel.get_by_label('Voice mode',exact=True).select_option('open')
  panel.get_by_role('button',name='Mute remote voice',exact=True).click();assert host.evaluate('voiceAudio.at(-1).muted')
  panel.get_by_role('button',name='Unmute remote voice',exact=True).click();assert not host.evaluate('voiceAudio.at(-1).muted')
  # Permission and device failures do not replace the peer or reset local emulation.
  pc_count=host.evaluate('pcs.length');panel.get_by_role('button',name='Disable microphone',exact=True).click()
  host.evaluate('window.denyCapture=true');panel.get_by_role('button',name='Enable voice',exact=True).click()
  panel.get_by_text('Microphone access was denied.',exact=False).wait_for()
  host.evaluate('window.denyCapture=false;window.missingDevice=true');panel.get_by_role('button',name='Try microphone again',exact=True).click()
  panel.get_by_text('Microphone unavailable. Choose another device',exact=False).wait_for()
  host.evaluate('window.missingDevice=false;window.rejectAttachment=true');panel.get_by_role('button',name='Try microphone again',exact=True).click()
  panel.get_by_text('Voice could not start.',exact=False).wait_for();assert host.evaluate('pcs.length')==pc_count
  host.evaluate('window.rejectAttachment=false;window.blockPlayback=true');panel.get_by_role('button',name='Try microphone again',exact=True).click()
  panel.get_by_role('button',name='Enable voice sound',exact=True).wait_for()
  host.evaluate('window.blockPlayback=false');panel.get_by_role('button',name='Enable voice sound',exact=True).click()
  panel.get_by_text('Transmitting microphone audio',exact=True).wait_for();assert host.evaluate('pcs.length')==pc_count
  assert int(host.get_by_test_id('frames').inner_text().split()[0])>=int(frame_before.split()[0])
  # Select another actual fake-device input after permission; replacement starts muted.
  devices=panel.get_by_label('Microphone device',exact=True).locator('option').evaluate_all("options=>options.map(o=>o.value).filter(v=>v!=='default')")
  assert devices
  panel.get_by_label('Microphone device',exact=True).select_option(devices[0])
  panel.get_by_text('Microphone muted',exact=True).wait_for();assert host.evaluate("captures.slice(0,-1).every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
  panel.get_by_role('button',name='Unmute microphone',exact=True).click()
  # Pending permission can be cancelled; a later result must stop all its tracks.
  panel.get_by_role('button',name='Disable microphone',exact=True).click();host.evaluate('window.holdCapture=true')
  panel.get_by_role('button',name='Enable voice',exact=True).click();host.wait_for_function('!!window.releaseCapture')
  panel.get_by_role('button',name='Cancel microphone request',exact=True).click();count=host.evaluate('captures.length');host.evaluate('releaseCapture();window.holdCapture=false')
  host.wait_for_function('(count)=>captures.length>count',arg=count)
  host.wait_for_function("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
  panel.get_by_role('button',name='Enable voice',exact=True).click();panel.get_by_text('Transmitting microphone audio',exact=True).wait_for()
  host.screenshot(path=str(Path(args.output).with_suffix('.voice.png')),full_page=True)
  host.set_viewport_size({'width':400,'height':1000});assert host.evaluate('document.documentElement.scrollWidth<=innerWidth')
  host.screenshot(path=str(Path(args.output).with_suffix('.mobile.png')),full_page=True)
  host.evaluate("window.dispatchEvent(new Event('blur'))");host.locator('.room-panel').get_by_text('Microphone muted',exact=True).wait_for();assert host.evaluate('captures.at(-1).getAudioTracks().every(t=>!t.enabled)')
  host.evaluate("window.dispatchEvent(new Event('focus'))");assert host.evaluate('captures.at(-1).getAudioTracks().every(t=>!t.enabled)')
  guest.get_by_role('button',name='Cancel join',exact=True).click();guest.get_by_test_id('room-view').wait_for(state='detached')
  for tab in [host,guest]:tab.wait_for_function("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
  assert not errors,errors
  result={'two_way_decoded_audio_energy':True,'no_capture_before_enable':True,'blur_mutes_focus_does_not_unmute':True,'leave_stops_both_tracks':True,'remote_volume_zero_via_setting':True,'page_errors':errors,'push_to_talk_key_button_and_typing_isolation':True,'permission_device_and_playback_retry_preserve_peer_and_frames':True,'late_cancelled_capture_stops':True,'device_replacement_muted_until_deliberate_unmute':True,'failed_sender_attachment_retries_without_peer_reset':True,'mobile_no_overflow':True,'seconds':round(time.monotonic()-started,2)}
  Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
  browser.close()
finally:server.terminate();server.wait(timeout=5)
