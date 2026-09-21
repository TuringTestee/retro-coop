"""Exercise temporary chat, explicit retry and input isolation in real browser tabs."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser();parser.add_argument('--chrome',action='store_true');parser.add_argument('--output',default='chat.local.json');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];output=Path(args.output);started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,stdout=subprocess.PIPE,text=True)
try:
    url=json.loads(service.stdout.readline())['url'];rom=(root/'apps/client/dist/generated/diagnostic.nes').read_bytes()
    with sync_playwright() as p:
        browser=p.chromium.launch(ignore_default_args=['--mute-audio'],**({'channel':'chrome'} if args.chrome else {}))
        errors=[]
        def page(address=url):
            page=browser.new_page(viewport={'width':1280,'height':1000});page.on('pageerror',lambda error:errors.append(str(error)))
            page.add_init_script('''window.chatProof={errors:[],requests:{}};window.chatSockets=[];const OriginalSocket=WebSocket;window.WebSocket=class extends OriginalSocket{constructor(...args){super(...args);chatSockets.push(this);this.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.type==='result'&&!data.ok)chatProof.errors.push({type:chatProof.requests[data.requestId],error:data.error,retryAfterMs:data.retryAfterMs});if(window.dropChatReplies && (data.type==='chat' || data.data?.chatAck))event.stopImmediatePropagation()})}};
window.inputProof=[];const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(message,...rest){if(message.type==='frame')inputProof.push(message.p1);return post.call(this,message,...rest)};''')
            page.goto(address);return page
        def open_chat(tab):tab.locator('details.chat-disclosure').evaluate('(node)=>node.open=true')
        host=page();host.set_input_files('input[type=file]',{'name':'private-chat-host.nes','mimeType':'application/octet-stream','buffer':rom});host.get_by_role('button',name='Room',exact=True).click();host.locator('main.session-open').wait_for();host.get_by_test_id('room-view').wait_for(state='attached');host.get_by_test_id('room-status').filter(has_text='Room created').wait_for(state='attached');open_chat(host)
        def send(page,text):
            page.get_by_label('Chat message',exact=True).fill(text);page.get_by_role('button',name='Send message',exact=True).click();page.locator('.chat-panel li p').get_by_text(text,exact=True).wait_for()
        send(host,'only before join')
        invite=host.get_by_label('Room invitation',exact=True).input_value();guest=page(invite);guest.get_by_role('button',name='Retry join / Join',exact=True).click();guest.get_by_test_id('room-view').wait_for(state='attached');open_chat(guest)
        assert guest.get_by_test_id('frames').inner_text()=='0 frames'
        assert guest.locator('.chat-panel li').count()==0
        send(guest,'hello before ROM');host.locator('.chat-panel li p').get_by_text('hello before ROM',exact=True).wait_for()
        send(guest,'<img src=x onerror=alert(1)>');assert host.locator('.chat-panel img').count()==0
        # Keyboard input releases on chat focus, and typing control keys cannot reach emulator frames.
        host.get_by_label('Local game screen',exact=True).focus();host.keyboard.down('ArrowRight');host.wait_for_function('inputProof.includes(128)')
        host.get_by_label('Chat message',exact=True).focus();host.keyboard.up('ArrowRight');host.evaluate('inputProof=[]')
        host.get_by_label('Chat message',exact=True).press('x');host.wait_for_function('inputProof.length>=4')
        assert host.evaluate('inputProof.every(value=>value===0)')
        assert 'Typing in chat' in host.locator('#chat-help').inner_text()
        host.get_by_label('Chat message',exact=True).fill('a'*501);assert host.get_by_role('button',name='Send message',exact=True).is_disabled()
        # Consume five-message budget including earlier messages, then preserve rejected text.
        for i in range(3):send(guest,f'bounded {i}')
        guest.get_by_label('Chat message',exact=True).fill('retry after limit');guest.get_by_role('button',name='Send message',exact=True).click()
        retry=guest.get_by_role('button',name='Retry message',exact=True);retry.wait_for();assert retry.is_disabled()
        assert guest.get_by_label('Chat message',exact=True).input_value()=='retry after limit'
        guest.wait_for_function("[...document.querySelectorAll('button')].some(button=>button.textContent==='Retry message' && !button.disabled)",timeout=15000)
        retry.click();guest.locator('.chat-panel li p').get_by_text('retry after limit',exact=True).wait_for()
        assert host.locator('.chat-panel li p').get_by_text('retry after limit',exact=True).count()==1
        # No automatic reconnect/send. Unsent draft survives actual socket loss until explicit retry.
        guest.evaluate('chatSockets.forEach(socket=>socket.close())');guest.get_by_role('button',name='Reconnect rooms',exact=True).wait_for()
        guest.get_by_label('Chat message',exact=True).fill('after reconnect');guest.get_by_role('button',name='Send message',exact=True).click()
        guest.get_by_role('button',name='Retry message',exact=True).wait_for();assert guest.get_by_role('button',name='Retry message',exact=True).is_disabled()
        guest.get_by_role('button',name='Reconnect rooms',exact=True).click();guest.wait_for_function("[...document.querySelectorAll('button')].some(button=>button.textContent==='Retry message' && !button.disabled)")
        assert host.locator('.chat-panel li p').get_by_text('after reconnect',exact=True).count()==0
        guest.get_by_role('button',name='Retry message',exact=True).click()
        try:host.locator('.chat-panel li p').get_by_text('after reconnect',exact=True).wait_for()
        except Exception:
            print(json.dumps({'failed':'reconnect delivery','hostErrors':host.evaluate('chatProof.errors'),'guestErrors':guest.evaluate('chatProof.errors'),'guestDeliveryStatus':guest.locator('.chat-panel [role=status]').all_text_contents()}),flush=True)
            raise
        assert host.locator('.chat-panel li p').get_by_text('after reconnect',exact=True).count()==1
        guest.locator('.chat-panel li p').get_by_text('after reconnect',exact=True).wait_for()
        guest.wait_for_function("document.querySelector('#chat-message').readOnly===false")
        # The server receives a message but both sender event and acknowledgement are lost.
        guest.evaluate('window.dropChatReplies=true')
        guest.get_by_label('Chat message',exact=True).fill('uncertain delivery')
        guest.get_by_role('button',name='Send message',exact=True).click()
        host.locator('.chat-panel li p').get_by_text('uncertain delivery',exact=True).wait_for()
        guest.get_by_role('button',name='Retry message',exact=True).wait_for(timeout=12000)
        guest.evaluate('window.dropChatReplies=false')
        guest.get_by_role('button',name='Retry message',exact=True).click()
        guest.locator('.chat-panel li p').get_by_text('uncertain delivery',exact=True).wait_for()
        assert host.locator('.chat-panel li p').get_by_text('uncertain delivery',exact=True).count()==1
        guest.screenshot(path=str(output.with_suffix('.chat.png')),full_page=True)
        guest.set_viewport_size({'width':400,'height':900})
        assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
        # Relay service is intentionally absent here; failed peer setup cannot disable text.
        guest.locator('.room-panel').get_by_label('Connection privacy',exact=True).select_option('relay')
        guest.get_by_text('Relay service is unavailable.',exact=False).first.wait_for()
        guest.get_by_label('Chat message',exact=True).fill('text survives peer denial')
        guest.get_by_role('button',name='Send message',exact=True).click()
        host.locator('.chat-panel li p').get_by_text('text survives peer denial',exact=True).wait_for()
        guest.get_by_role('button',name='Cancel join',exact=True).click();guest.locator('.chat-panel').wait_for(state='detached')
        guest.get_by_role('button',name='Retry join / Join',exact=True).click();open_chat(guest);guest.locator('.chat-panel').wait_for();assert guest.locator('.chat-panel li').count()==0
        assert not errors,errors
        result={'pre_rom_chat':True,'no_pre_join_history':True,'plain_text_not_html':True,'typing_releases_game_input':True,'oversize_disabled':True,'rate_limit_retains_text_countdown_and_explicit_retry':True,'socket_loss_no_automatic_duplicate':True,'lost_event_and_ack_retry_has_no_duplicate':True,'narrow_no_overflow':True,'peer_relay_denial_keeps_chat_usable':True,'rejoin_clears_chat':True,'page_errors':errors,'elapsedSeconds':round(time.monotonic()-started,2)}
        output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));browser.close()
finally:service.terminate();service.wait(timeout=5)
