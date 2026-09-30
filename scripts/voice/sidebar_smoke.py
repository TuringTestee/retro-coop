"""Exercise the compact cards through the public room, Settings and controller paths."""
from pathlib import Path
from background_smoke import audio_arrives
from playwright.sync_api import expect


def run(host, guest, output):
    output = Path(output)
    guest.get_by_test_id('room-view').wait_for(state='detached')
    guest.goto(host.evaluate("location.origin + '/#invite=' + document.querySelector('[data-testid=room-view]').dataset.invite"))
    guest.get_by_role('button', name='Join room', exact=True).click()
    guest.get_by_role('button', name='Ready', exact=True).click()
    host.locator('[data-slot-id="slot-2"] [data-slot-region="status"]').get_by_text('Ready', exact=True).wait_for(timeout=30000)
    host.get_by_role('button', name='Ready', exact=True).click()
    host.get_by_role('button', name='Start game', exact=True).click()
    for tab in [host, guest]:
        tab.locator('.voice-card').wait_for()
        tab.get_by_role('button', name='Pause', exact=True).wait_for()
        tab.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount)>30")
        assert tab.evaluate("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
        assert tab.locator('.voice-disclosure').count() == 0
    host.set_viewport_size({'width':1280,'height':900})
    guest.set_viewport_size({'width':1280,'height':900})
    assert 'Player 1' in host.locator('.play-controls').inner_text()
    assert 'Player 2' in guest.locator('.play-controls').inner_text()
    host.screenshot(path=str(output.with_suffix('.sidebar-off.png')), full_page=True)
    # One editor owns the mapping; the readout updates on return.
    host.get_by_role('button', name='Edit controls', exact=True).click()
    host.get_by_role('button', name='Change A', exact=True).click()
    host.get_by_label('Capture input', exact=True).press('q')
    host.get_by_role('button', name='Apply mapping', exact=True).click()
    host.get_by_role('button', name='Back', exact=True).click()
    assert host.locator('.play-bindings > div').filter(has=host.locator('dt', has_text='A')).first.locator('dd').inner_text() == 'Q'
    host.get_by_role('button', name='Game help', exact=True).click()
    assert 'Arrows move' not in host.locator('.game-help').inner_text()
    host.get_by_role('button', name='Back', exact=True).click()
    # Voice settings reaches the existing owner, with focus on its heading.
    host.get_by_role('button', name='Voice settings', exact=True).click()
    assert host.evaluate("document.activeElement.textContent") == 'Voice'
    host.get_by_label('Voice mode', exact=True).select_option('open')
    host.get_by_role('button', name='Back', exact=True).click()
    assert host.evaluate('document.activeElement.textContent') == 'Voice settings'
    card=host.locator('.voice-card')
    host.evaluate('window.holdCapture=true;window.blockPlayback=true')
    card.get_by_role('button', name='Enable voice', exact=True).click()
    host.wait_for_function('!!window.releaseCapture')
    card.get_by_role('button', name='Cancel microphone request', exact=True).wait_for()
    card.get_by_role('button', name='Enable voice sound', exact=True).wait_for()
    assert 'Requesting microphone' in card.inner_text()
    host.screenshot(path=str(output.with_suffix('.sidebar-pending.png')), full_page=True)
    card.get_by_role('button', name='Cancel microphone request', exact=True).click()
    count=host.evaluate('captures.length')
    host.evaluate('releaseCapture();window.holdCapture=false')
    host.wait_for_function('n=>captures.length>n&&captures.at(-1).getTracks().every(t=>t.readyState==="ended")', arg=count)
    host.evaluate('window.denyCapture=true;window.blockPlayback=true')
    card.get_by_role('button', name='Enable voice', exact=True).click()
    card.get_by_text('Microphone access was denied.', exact=False).wait_for()
    card.get_by_role('button', name='Try microphone again', exact=True).wait_for()
    card.get_by_role('button', name='Enable voice sound', exact=True).wait_for()
    host.screenshot(path=str(output.with_suffix('.sidebar-error.png')), full_page=True)
    card.get_by_role('button', name='Voice settings', exact=True).click()
    host.get_by_role('button', name='Back', exact=True).click()
    assert host.evaluate('document.activeElement.textContent') == 'Voice settings'
    # Microphone recovery and privacy controls stay usable while playback is blocked.
    host.evaluate('window.denyCapture=false')
    card.get_by_role('button', name='Try microphone again', exact=True).click()
    card.get_by_role('button', name='Mute microphone', exact=True).click()
    card.get_by_role('button', name='Unmute microphone', exact=True).click()
    assert card.get_by_role('button', name='Enable voice sound', exact=True).is_visible()
    host.evaluate('window.blockPlayback=false')
    card.get_by_role('button', name='Enable voice sound', exact=True).click()
    card.get_by_role('button', name='Enable voice sound', exact=True).wait_for(state='detached')
    card.get_by_role('button', name='Mute microphone', exact=True).wait_for()
    guest.locator('.voice-card').get_by_role('button', name='Enable voice', exact=True).click()
    for tab in [host,guest]:
        audio_arrives(tab)
    host.screenshot(path=str(output.with_suffix('.sidebar-live.png')), full_page=True)
    host.evaluate("dispatchEvent(new Event('blur'))")
    assert host.evaluate("captures.at(-1).getTracks().every(t=>t.readyState==='live'&&t.enabled)")
    card.get_by_role('button', name='Mute microphone', exact=True).click()
    card.get_by_role('button', name='Unmute microphone', exact=True).wait_for()
    assert host.evaluate("captures.at(-1).getTracks().every(t=>t.readyState==='live'&&!t.enabled)")
    host.screenshot(path=str(output.with_suffix('.sidebar-muted.png')), full_page=True)
    card.get_by_role('button', name='Unmute microphone', exact=True).click()
    host.get_by_role('button', name='Voice settings', exact=True).click()
    host.get_by_label('Voice mode', exact=True).select_option('push')
    host.get_by_role('button', name='Back', exact=True).click()
    assert 'Push to talk · V' in card.inner_text()
    assert card.get_by_role('button', name='Mute microphone', exact=True).is_visible()
    assert card.get_by_role('button', name='Hold to talk', exact=True).is_visible()
    card.get_by_role('button', name='Hold to talk', exact=True).focus()
    host.keyboard.down('Space')
    host.wait_for_function('captures.at(-1).getAudioTracks().every(t=>t.enabled)')
    host.keyboard.up('Space')
    host.wait_for_function('captures.at(-1).getAudioTracks().every(t=>!t.enabled)')
    card.get_by_role('button', name='Mute microphone', exact=True).click()
    expect(card.get_by_role('button', name='Hold to talk', exact=True)).to_be_disabled()
    card.get_by_role('button', name='Unmute microphone', exact=True).click()
    assert not host.evaluate('captures.at(-1).getAudioTracks()[0].enabled')
    host.set_viewport_size({'width':800,'height':900})
    assert host.locator('canvas').evaluate("c=>{const a=c.getBoundingClientRect(),b=c.closest('.panel').getBoundingClientRect();return a.left>=b.left&&a.right<=b.right}")
    host.screenshot(path=str(output.with_suffix('.sidebar-small-desktop.png')),full_page=True)
    host.set_viewport_size({'width':400,'height':900})
    assert host.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert host.locator('canvas').evaluate("c=>!!(c.compareDocumentPosition(document.querySelector('.play-controls'))&Node.DOCUMENT_POSITION_FOLLOWING)")
    host.screenshot(path=str(output.with_suffix('.sidebar-narrow.png')), full_page=True)
    guest.get_by_role('button', name='Leave room', exact=True).click()
    guest.get_by_role('button', name='Confirm leave', exact=True).click()
    guest.wait_for_function("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
    assert host.evaluate("captures.at(-1).getTracks().every(t=>t.readyState==='live'&&!t.enabled)")
    host.get_by_role('button', name='Leave room', exact=True).click()
    host.get_by_role('button', name='Confirm leave', exact=True).click()
    host.wait_for_function("captures.every(s=>s.getTracks().every(t=>t.readyState==='ended'))")
    return {'started_shared_play':True,'live_remap_and_help':True,'visible_pending_error_retry_live_mute_push':True,'simultaneous_microphone_and_playback_recovery':True,'pending_cancel_survives_playback_failure':True,'two_way_audio_during_game':True,'focus_preserves_mute_and_open_track':True,'departing_member_releases_tracks':True,'remaining_member_keeps_capture_and_push_mute':True,'host_leave_releases_tracks':True,'wide_and_narrow_no_overlay':True}


def solo(browser, url, rom, output, root):
    """Persisted unbound/long pad mappings, sole Settings editor and unplug recovery."""
    import sys
    sys.path.insert(0, str(root / 'scripts/foundation'))
    from local_play import start_solo
    tab=browser.new_page(viewport={'width':1280,'height':900})
    tab.add_init_script(path=root/'scripts/foundation/gamepad_fixture.js')
    def load():
        tab.goto(url)
        tab.get_by_role('button',name='Create game',exact=True).click()
        tab.set_input_files('input[type=file]', {'name':'controls.nes','mimeType':'application/octet-stream','buffer':rom})
        start_solo(tab,rom)
    load()
    assert tab.locator('.play-controls').is_visible()
    assert tab.locator('.voice-card').count()==0
    tab.get_by_role('button',name='Edit controls',exact=True).click()
    tab.get_by_label('Input device',exact=True).select_option('0')
    tab.get_by_role('button',name='Back',exact=True).click()
    assert tab.evaluate('document.activeElement.textContent')=='Edit controls'
    # A valid saved mapping can have no input or multiple long alternatives.
    tab.evaluate('''()=>new Promise((resolve,reject)=>{const request=indexedDB.open('retro-coop-local',3);request.onsuccess=()=>{const db=request.result;const tx=db.transaction('preferences','readwrite');const store=tx.objectStore('preferences');const rows=store.getAll();rows.onsuccess=()=>{for(const row of rows.result){row.value.controls.gamepad.select=[];row.value.controls.gamepad.up=['axis:10:-1','axis:11:-1','axis:12:-1'];store.put(row)}};tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error)}})''')
    load()
    card=tab.locator('.play-controls')
    assert 'Gamepad' in card.inner_text() and 'Unbound' in card.inner_text() and 'Axis 13 −' in card.inner_text()
    tab.screenshot(path=str(Path(output).with_suffix('.sidebar-solo-pad.png')),full_page=True)
    tab.set_viewport_size({'width':400,'height':900})
    assert tab.evaluate('document.documentElement.scrollWidth<=innerWidth')
    tab.screenshot(path=str(Path(output).with_suffix('.sidebar-solo-narrow.png')),full_page=True)
    tab.evaluate('padConnected=false')
    tab.get_by_role('button',name='Use keyboard',exact=True).click()
    assert 'Keyboard' in card.inner_text() and 'Gamepad' not in card.inner_text()
    tab.close()
    return {'solo_readout_no_voice':True,'saved_unbound_and_long_pad_mappings':True,'lost_pad_keyboard_recovery':True,'edit_controls_return_focus':True}
