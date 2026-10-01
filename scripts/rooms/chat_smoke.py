"""Exercise temporary chat, explicit retry and input isolation in real browser tabs."""
import argparse
import os
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from layout_geometry import browser_zoom, control_visibility, verify_zoom, zoom_context

parser=argparse.ArgumentParser();parser.add_argument('--chrome',action='store_true');parser.add_argument('--output',default='chat.local.json');args=parser.parse_args()
root=Path(__file__).resolve().parents[2];output=Path(args.output);started=time.monotonic()
service=subprocess.Popen(['node','scripts/rooms/browser-server.ts'],cwd=root,stdout=subprocess.PIPE,text=True)
try:
    url=json.loads(service.stdout.readline())['url'];rom=(Path(os.environ.get('RETRO_COOP_STATIC_ROOT', root/'apps/client/dist'))/'generated/diagnostic.nes').read_bytes()
    with sync_playwright() as p:
        browser=p.chromium.launch(ignore_default_args=['--mute-audio'],**({'channel':'chrome'} if args.chrome else {}))
        errors=[]
        def page(address=url):
            page=browser.new_page(viewport={'width':1280,'height':1000});page.on('pageerror',lambda error:errors.append(str(error)))
            page.context.grant_permissions(['clipboard-read','clipboard-write'])
            page.add_init_script('''window.chatProof={errors:[],requests:{},events:[],sent:[]};window.chatSockets=[];const OriginalSocket=WebSocket;window.WebSocket=class extends OriginalSocket{constructor(...args){super(...args);chatSockets.push(this);this.addEventListener('message',event=>{const data=JSON.parse(event.data);if(data.type==='room')chatProof.room=data.room;chatProof.events.push(data.type==='result'&&data.data?.chatAck?'chatAck':data.type);if(data.type==='result'&&!data.ok)chatProof.errors.push({type:chatProof.requests[data.requestId],error:data.error,retryAfterMs:data.retryAfterMs});if(window.dropChatReplies && (data.type==='chat' || data.data?.chatAck))event.stopImmediatePropagation()})}send(raw){const data=JSON.parse(raw);chatProof.sent.push(data.type);chatProof.requests[data.requestId]=data.type;return super.send(raw)}};
    window.chatPcs=[];window.failPeerSetup=false;const NativePeer=RTCPeerConnection;window.RTCPeerConnection=class extends NativePeer{constructor(config){if(window.failPeerSetup)throw Error('Peer setup blocked by test');super(config);chatPcs.push(this)}};
window.inputProof=[];const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(message,...rest){if(message.type==='frame')inputProof.push(message.p1);return post.call(this,message,...rest)};''')
            page.goto(address);return page
        def open_room(tab):
            panel=tab.locator('.room-panel')
            panel.wait_for(state='visible');return panel
        def open_chat(tab):
            panel=open_room(tab)
            disclosure=panel.locator('details.chat-disclosure')
            if disclosure.count() and not disclosure.evaluate('(node)=>node.open'):
                disclosure.locator('summary').click()
            panel.locator('.chat-panel').wait_for();return panel
        def geometry(tab):
            return tab.locator('.chat-panel').evaluate('''panel=>{
              const bounds=node=>{const r=node.getBoundingClientRect();let x=r.x+scrollX,y=r.y+scrollY;
                for(let p=node.parentElement;p;p=p.parentElement){x+=p.scrollLeft;y+=p.scrollTop}
                return {x,y,width:r.width,height:r.height}};
              return {panel:bounds(panel),list:bounds(panel.querySelector('.chat-log-region')),
                form:bounds(panel.querySelector('form')),textarea:bounds(panel.querySelector('textarea')),
                actions:bounds(panel.querySelector('.chat-action-slot')),
                feedback:bounds(panel.querySelector('.chat-feedback-slot')),
                connection:bounds(panel.querySelector('.chat-connection-slot'))};
            }''')
        host=page();host.get_by_role('button',name='Create game',exact=True).click();host.set_input_files('input[type=file]',{'name':'private-chat-host.nes','mimeType':'application/octet-stream','buffer':rom});host.get_by_role('button',name='Create room',exact=True).click();host.get_by_test_id('room-view').wait_for(state='attached');open_chat(host)
        empty_geometry=geometry(host)
        host.locator('.chat-panel').screenshot(path=str(output.with_suffix('.empty.png')))
        def send(page,text):
            open_chat(page);message=page.get_by_label('Chat message',exact=True);message.fill(text);assert message.input_value()==text
            button=page.get_by_role('button',name='Send message',exact=True);button.wait_for();assert button.is_enabled();sent=page.evaluate("chatProof.sent.filter(type=>type==='chat').length");button.click()
            try:page.wait_for_function("count=>chatProof.sent.filter(type=>type==='chat').length>count",arg=sent,timeout=2000)
            except Exception:
                print(json.dumps({'failed':'send action','value':message.input_value(),'buttons':page.get_by_role('button').all_text_contents(),'panelVisible':page.locator('.room-panel').is_visible(),'chatVisible':page.locator('.chat-panel').is_visible(),'mainClass':page.locator('main').get_attribute('class'),'statuses':page.locator('[role=status]').all_text_contents(),'sent':page.evaluate('chatProof.sent')}),flush=True);raise
            page.locator('.chat-panel li p').filter(has_text=text).wait_for(state='attached')
        send(host,'only before join')
        assert geometry(host)==empty_geometry,(empty_geometry,geometry(host))
        host.locator('.chat-panel').screenshot(path=str(output.with_suffix('.first-message.png')))

        host.get_by_role('button',name='Copy invite',exact=True).click();invite=host.evaluate('navigator.clipboard.readText()');guest=page(invite);guest.get_by_role('button',name='Join room',exact=True).click();guest.get_by_test_id('room-view').wait_for(state='attached');host.wait_for_function("chatProof.room?.slots[1].member?.id&&document.querySelectorAll('[data-testid=room-slot]').length===5")
        for tab in [host,guest]:tab.wait_for_function("chatProof.room?.peers[0]?.status==='connected'")
        open_chat(guest)
        assert guest.locator('canvas').get_attribute('data-frame-count')=='0'
        assert guest.locator('.chat-panel li').count()==0
        send(guest,'hello before ROM')
        try:host.locator('.chat-panel').get_by_text('hello before ROM',exact=True).wait_for(state='attached',timeout=5000)
        except Exception:
            print(json.dumps({'failed':'pre-ROM delivery','hostMessages':host.locator('.chat-panel li').all_text_contents(),'guestMessages':guest.locator('.chat-panel li').all_text_contents(),'hostEvents':host.evaluate('chatProof.events'),'guestEvents':guest.evaluate('chatProof.events'),'hostSent':host.evaluate('chatProof.sent'),'guestSent':guest.evaluate('chatProof.sent'),'hostErrors':host.evaluate('chatProof.errors'),'guestErrors':guest.evaluate('chatProof.errors')}),flush=True)
            raise
        send(guest,'<img src=x onerror=alert(1)>');assert host.locator('.chat-panel img').count()==0
        # The waiting room hides gameplay input; typing in chat must not send controller frames.
        assert not host.get_by_label('Local game screen',exact=True).is_visible()
        host.get_by_label('Chat message',exact=True).focus();host.evaluate('inputProof=[]')
        host.get_by_label('Chat message',exact=True).press('x')
        assert host.evaluate('inputProof.every(value=>value===0)')
        assert 'Typing in chat' in host.locator('#chat-help').inner_text()
        host.get_by_label('Chat message',exact=True).fill('a'*501);assert host.get_by_role('button',name='Send message',exact=True).is_disabled()
        # Consume five-message budget including earlier messages, then preserve rejected text.
        for i in range(3):send(guest,f'bounded {i}')
        log=host.locator('.chat-log-region ol')
        assert log.evaluate('node=>node.scrollHeight>node.clientHeight')
        log.evaluate('node=>{node.scrollTop=0;node.dispatchEvent(new Event("scroll"))}')
        host_before_unread=geometry(host)
        guest.set_viewport_size({'width':400,'height':900})
        guest_before_rejection=geometry(guest)
        guest.get_by_label('Chat message',exact=True).fill('retry after limit');guest.get_by_role('button',name='Send message',exact=True).click()
        retry=guest.get_by_role('button',name='Retry message',exact=True);retry.wait_for();assert retry.is_disabled()
        assert geometry(guest)==guest_before_rejection,(guest_before_rejection,geometry(guest))
        control_visibility(retry)
        guest.locator('.chat-panel').screenshot(path=str(output.with_suffix('.retry-mobile.png')))
        assert guest.get_by_label('Chat message',exact=True).input_value()=='retry after limit'
        guest.wait_for_function("[...document.querySelectorAll('button')].some(button=>button.textContent==='Retry message' && !button.disabled)",timeout=15000)
        retry.click();guest.locator('.chat-panel').get_by_text('retry after limit',exact=True).wait_for(state='attached')
        host.get_by_role('button',name='New messages · Jump to latest',exact=True).wait_for()
        assert geometry(host)==host_before_unread,(host_before_unread,geometry(host))
        host.locator('.chat-panel').screenshot(path=str(output.with_suffix('.unread.png')))
        host.get_by_role('button',name='New messages · Jump to latest',exact=True).click()
        assert geometry(host)==host_before_unread,(host_before_unread,geometry(host))
        guest.wait_for_function("document.querySelector('#chat-message').readOnly===false")
        assert host.locator('.chat-panel').get_by_text('retry after limit',exact=True).count()==1
        # No automatic reconnect/send. Unsent draft survives actual socket loss until explicit retry.
        guest.evaluate('chatSockets.forEach(socket=>socket.close())');guest.get_by_role('button',name='Reconnect rooms',exact=True).wait_for()
        guest.get_by_label('Chat message',exact=True).fill('after reconnect');guest.get_by_role('button',name='Send message',exact=True).click()
        guest.get_by_role('button',name='Retry message',exact=True).wait_for();assert guest.get_by_role('button',name='Retry message',exact=True).is_disabled()
        guest.get_by_role('button',name='Reconnect rooms',exact=True).click();guest.wait_for_function("[...document.querySelectorAll('button')].some(button=>button.textContent==='Retry message' && !button.disabled)")
        assert host.locator('.chat-panel').get_by_text('after reconnect',exact=True).count()==0
        guest.get_by_role('button',name='Retry message',exact=True).click()
        try:host.locator('.chat-panel').get_by_text('after reconnect',exact=True).wait_for(state='attached')
        except Exception:
            print(json.dumps({'failed':'reconnect delivery','hostErrors':host.evaluate('chatProof.errors'),'guestErrors':guest.evaluate('chatProof.errors'),'guestDeliveryStatus':guest.locator('.chat-panel [role=status]').all_text_contents()}),flush=True)
            raise
        assert host.locator('.chat-panel').get_by_text('after reconnect',exact=True).count()==1
        guest.locator('.chat-panel').get_by_text('after reconnect',exact=True).wait_for(state='attached')
        guest.wait_for_function("document.querySelector('#chat-message').readOnly===false")
        # The server receives a message but both sender event and acknowledgement are lost.
        guest.evaluate('window.dropChatReplies=true')
        guest.get_by_label('Chat message',exact=True).fill('uncertain delivery')
        guest.get_by_role('button',name='Send message',exact=True).click()
        host.locator('.chat-panel').get_by_text('uncertain delivery',exact=True).wait_for(state='attached')
        guest.get_by_role('button',name='Retry message',exact=True).wait_for(timeout=12000)
        guest.evaluate('window.dropChatReplies=false')
        guest.get_by_role('button',name='Retry message',exact=True).click()
        guest.locator('.chat-panel').get_by_text('uncertain delivery',exact=True).wait_for(state='attached')
        assert host.locator('.chat-panel').get_by_text('uncertain delivery',exact=True).count()==1
        guest.screenshot(path=str(output.with_suffix('.chat.png')),full_page=True)
        guest.set_viewport_size({'width':400,'height':900})
        assert guest.evaluate('document.documentElement.scrollWidth<=innerWidth')
        # Test-owned peer failure cannot disable text or release room membership.
        guest.evaluate('window.failPeerSetup=true;chatPcs.at(-1).close()')
        guest.wait_for_function("chatProof.room?.peers[0]?.status==='failed'",timeout=10000)
        open_room(guest).get_by_role('button',name='Retry connection',exact=True).click()
        guest.wait_for_function("chatProof.room?.peers[0]?.status==='failed'",timeout=10000)
        open_chat(guest)
        guest.get_by_label('Chat message',exact=True).fill('text survives peer denial')
        guest.get_by_role('button',name='Send message',exact=True).click()
        host.locator('.chat-panel').get_by_text('text survives peer denial',exact=True).wait_for(state='attached')
        open_room(guest).get_by_role('button',name='Leave room',exact=True).click();guest.locator('.chat-panel').wait_for(state='detached')
        guest.goto(invite);guest.get_by_role('button',name='Join room',exact=True).click();guest.get_by_test_id('room-view').wait_for(state='attached');open_chat(guest);guest.locator('.chat-panel').wait_for();assert guest.locator('.chat-panel li').count()==0
        play_host=page();play_host.get_by_role('button',name='Create game',exact=True).click()
        play_host.set_input_files('input[type=file]',{'name':'playing-chat.nes','mimeType':'application/octet-stream','buffer':rom})
        play_host.get_by_role('button',name='Create room',exact=True).click()
        play_host.get_by_role('button',name='Copy invite',exact=True).click()
        play_invite=play_host.evaluate('navigator.clipboard.readText()')
        play_guest=page(play_invite);play_guest.get_by_role('button',name='Join room',exact=True).click()
        for tab in (play_host,play_guest):tab.wait_for_function("chatProof.room?.peers[0]?.status==='connected'")
        play_guest.get_by_role('button',name='Ready',exact=True).click()
        play_host.get_by_role('button',name='Ready',exact=True).click()
        play_host.get_by_role('button',name='Start game',exact=True).click()
        for tab in (play_host,play_guest):
            try:tab.locator('main.playing.with-room').wait_for(timeout=10000)
            except Exception:
                print(json.dumps({'playing_chat_setup':[
                    {'main':peer.locator('main').get_attribute('class'),
                     'game':peer.evaluate('chatProof.room?.game'),
                     'status':peer.locator('[data-testid=game-status]').all_text_contents(),
                     'room_text':peer.locator('.room-panel').inner_text()[:500]}
                    for peer in (play_host,play_guest)],'errors':errors}),flush=True)
                raise
        open_chat(play_host);open_chat(play_guest)
        playing_geometry=geometry(play_host)
        send(play_guest,'chat during shared play')
        play_host.locator('.chat-panel').get_by_text('chat during shared play',exact=True).wait_for(state='attached')
        assert geometry(play_host)==playing_geometry,(playing_geometry,geometry(play_host))
        def check_profile(tab,label,zoom=None,zoom_worker=None):
            tab.get_by_role('button',name='Create game',exact=True).click()
            tab.set_input_files('input[type=file]',{'name':f'{label}-chat.nes','mimeType':'application/octet-stream','buffer':rom})
            tab.get_by_role('button',name='Create room',exact=True).click()
            open_chat(tab)
            editor=tab.get_by_label('Chat message',exact=True)
            editor.fill('profile message')
            editor.focus();tab.keyboard.press('Tab')
            send_button=tab.get_by_role('button',name='Send message',exact=True)
            send_visibility=control_visibility(send_button,require_focus=True)
            tab.keyboard.press('Shift+Tab')
            editor_visibility=control_visibility(editor,require_focus=True)
            before=geometry(tab)
            tab.screenshot(path=str(output.with_suffix(f'.{label}-before.png')))
            send_button.click();tab.locator('.chat-panel').get_by_text('profile message',exact=True).wait_for(state='attached')
            assert geometry(tab)==before,(label,'first message',before,geometry(tab))
            tab.evaluate('chatSockets.at(-1).close()')
            tab.get_by_role('button',name='Reconnect rooms',exact=True).wait_for()
            open_chat(tab);editor.fill('profile retry');send_button.click()
            retry=tab.get_by_role('button',name='Retry message',exact=True);retry.wait_for()
            assert geometry(tab)==before,(label,'recovery',before,geometry(tab))
            tab.get_by_role('button',name='Reconnect rooms',exact=True).click()
            tab.wait_for_function("[...document.querySelectorAll('button')].some(button=>button.textContent==='Retry message' && !button.disabled)")
            retry.focus();retry_visibility=control_visibility(retry,require_focus=True)
            tab.keyboard.press('Tab')
            discard_visibility=control_visibility(tab.get_by_role('button',name='Discard message',exact=True),require_focus=True)
            tab.keyboard.press('Shift+Tab');control_visibility(retry,require_focus=True)
            tab.screenshot(path=str(output.with_suffix(f'.{label}-recovery.png')))
            retry.click();tab.locator('.chat-panel').get_by_text('profile retry',exact=True).wait_for(state='attached')
            assert geometry(tab)==before,(label,'retried',before,geometry(tab))
            if zoom_worker:assert verify_zoom(zoom_worker,zoom)==2
            return {'label':label,'viewport':tab.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})'),
                'geometry':before,'send_visible':send_visibility['visible'],'editor_visible':editor_visibility['visible'],
                'retry_visible':retry_visibility['visible'],'discard_visible':discard_visibility['visible'],
                'keyboard_forward_reverse':True,'first_message_recovery_and_retry_fixed':True,'zoom':zoom}
        short=page();short.set_viewport_size({'width':1024,'height':600})
        profiles=[check_profile(short,'short')]
        with zoom_context(p,{'width':1280,'height':800}) as (zoom_browser,worker):
            zoom_tab=zoom_browser.new_page()
            zoom_browser.grant_permissions(['clipboard-read','clipboard-write'])
            zoom_tab.add_init_script("window.chatSockets=[];const OriginalSocket=WebSocket;window.WebSocket=class extends OriginalSocket{constructor(...args){super(...args);chatSockets.push(this)}}")
            zoom_tab.goto(url)
            zoom=browser_zoom(zoom_tab,worker)
            profiles.append(check_profile(zoom_tab,'zoom-200',zoom,worker))
        assert not errors,errors
        result={'pre_rom_chat':True,'no_pre_join_history':True,'plain_text_not_html':True,'typing_releases_game_input':True,'oversize_disabled':True,'rate_limit_retains_text_countdown_and_explicit_retry':True,'socket_loss_no_automatic_duplicate':True,'lost_event_and_ack_retry_has_no_duplicate':True,'narrow_no_overflow':True,'peer_failure_keeps_chat_usable':True,'rejoin_clears_chat':True,'fixed_chat_through_play':True,'layout_profiles':profiles,'page_errors':errors,'elapsedSeconds':round(time.monotonic()-started,2)}
        output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));browser.close()
finally:service.terminate();service.wait(timeout=5)
