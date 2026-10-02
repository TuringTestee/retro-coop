"""Real-browser controls and presentation checks on the built client."""
import hashlib
from pathlib import Path
from local_play import enter_create, read_fingerprint, start_solo


def verify_settings(browser, url, rom, output):
    page = browser.new_page(viewport={'width':1280,'height':1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script(path=Path(__file__).with_name('gamepad_fixture.js'))
    page.add_init_script('''window.createdWorkers=0;const NativeWorker=Worker;
      window.Worker=class extends NativeWorker{constructor(...args){super(...args);createdWorkers++}};
      window.gameGains=[];const gain=AudioContext.prototype.createGain;
      AudioContext.prototype.createGain=function(){const node=gain.call(this);gameGains.push(node);return node};''')
    page.goto(url)
    enter_create(page)
    page.get_by_label('NES cartridge file').set_input_files({
        'name':'controls-fixture.nes','mimeType':'application/octet-stream','buffer':rom})
    start_solo(page,rom)
    count="Number(document.querySelector('canvas').dataset.frameCount)"
    page.wait_for_function(count+'>10')

    def open_settings():
        action=page.locator('.rc-side-content:visible').get_by_role('button',name='Controls',exact=True)
        if not action.is_visible():
            page.locator('.rc-game-links').get_by_role('button',name='Settings',exact=True).click()
        action.click()
        panel=page.locator('.rc-settings')
        panel.wait_for()
        return panel

    def mapping(panel,action):
        return panel.locator('.rc-mapping').filter(has=page.get_by_text(action,exact=True))

    def set_range(control,value):
        control.evaluate('''(node,value)=>{
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,String(value));
          node.dispatchEvent(new Event('input',{bubbles:true}));
          node.dispatchEvent(new Event('change',{bubbles:true}));
        }''',value)

    panel=open_settings()
    page.screenshot(path=str(output.with_suffix('.settings-before.png')),full_page=False)
    for _ in range(2):
        panel.get_by_role('button',name='Next',exact=True).click()
    right=mapping(panel,'Right')
    right.get_by_role('button',name='Change',exact=True).click()
    page.get_by_label('Capture input',exact=True).press('v')
    assert panel.get_by_role('button',name='Apply mapping').is_disabled()
    panel.get_by_role('status').filter(has_text='used for Push to talk').wait_for()
    page.get_by_label('Capture input',exact=True).press('l')
    panel.get_by_role('button',name='Cancel',exact=True).click()
    assert 'Arrow Right' in right.inner_text()
    right.get_by_role('button',name='Change',exact=True).click()
    page.get_by_label('Capture input',exact=True).press('l')
    panel.get_by_role('button',name='Apply mapping').click()
    assert 'L' in right.inner_text()
    test=page.get_by_label('Test mapped input',exact=True)
    test.focus();page.keyboard.down('l')
    page.wait_for_function("document.querySelector('.rc-input-test')?.textContent?.includes('Right')")
    page.keyboard.up('l')
    page.wait_for_function("document.querySelector('.rc-input-test')?.textContent?.includes('None')")

    old_frames=page.evaluate(count)
    panel.get_by_role('button',name='Sound',exact=True).click()
    panel.get_by_label('Display filter').select_option('scanlines')
    set_range(panel.get_by_label('Game volume',exact=False),35)
    panel.get_by_text('Game volume 35%',exact=True).wait_for()
    assert page.locator('.rc-game-display.rc-scanlines').count()==1
    assert page.evaluate('gameGains[0].gain.value')==0
    page.screenshot(path=str(output.with_suffix('.settings-after.png')),full_page=False)
    set_range(panel.get_by_label('Game volume',exact=False),0)
    panel.get_by_text('Game volume 0%',exact=True).wait_for()
    page.locator('.rc-tool-back').click()
    page.locator('.rc-game-links').get_by_role('button',name='Settings',exact=True).click()
    quick=page.locator('.rc-side-content:visible')
    quick.get_by_role('button',name='Unmute game').click()
    assert page.evaluate('gameGains[0].gain.value')==0
    quick.get_by_role('button',name='Mute game').click()
    canvas=page.locator('canvas');canvas.focus();baseline=canvas.evaluate('c=>c.toDataURL()')
    page.keyboard.down('l')
    page.wait_for_function('before=>document.querySelector("canvas").toDataURL()!==before',arg=baseline)
    page.keyboard.up('l')
    assert page.evaluate(count)>old_frames

    panel=open_settings()
    for _ in range(2):
        panel.get_by_role('button',name='Next',exact=True).click()
    right=mapping(panel,'Right')
    panel.get_by_role('button',name='Restore defaults').click()
    panel.get_by_role('button',name='Keep mappings').click()
    assert 'L' in right.inner_text()
    panel.get_by_role('button',name='Restore defaults').click()
    panel.get_by_role('button',name='Restore',exact=True).click()
    assert 'Arrow Right' in right.inner_text()

    panel.get_by_label('Input device',exact=True).select_option('0')
    right=mapping(panel,'Right')
    right.get_by_role('button',name='Change',exact=True).click()
    page.evaluate('padButtons=[10]')
    panel.get_by_role('status').filter(has_text='used for Push to talk').wait_for()
    assert panel.get_by_role('button',name='Apply mapping').is_disabled()
    page.evaluate('padButtons=[];padAxes=[0,0]')
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    page.evaluate('padButtons=[3]')
    panel.get_by_role('status').filter(has_text='Button 4').wait_for()
    panel.get_by_role('button',name='Apply mapping').click()
    page.get_by_label('Test mapped input',exact=True).focus()
    page.wait_for_function("document.querySelector('.rc-input-test')?.textContent?.includes('Right')")
    page.evaluate('padButtons=[]')
    panel.get_by_role('button',name='Previous').click()
    mapping(panel,'Up').get_by_role('button',name='Change',exact=True).click()
    page.evaluate('padAxes=[0,0,-0.75]')
    panel.get_by_role('status').filter(has_text='Axis 3').wait_for()
    panel.get_by_role('button',name='Apply mapping').click()
    page.evaluate('padAxes=[0,0,0]')
    page.locator('.rc-tool-back').click()
    canvas.focus();baseline=canvas.evaluate('c=>c.toDataURL()')
    page.evaluate('padButtons=[3]')
    page.wait_for_function('before=>document.querySelector("canvas").toDataURL()!==before',arg=baseline)
    page.evaluate('padButtons=[]')

    page.evaluate('padConnected=false')
    page.locator('.rc-status').get_by_role('button',name='Use keyboard').wait_for()
    assert page.get_by_role('button',name='Resume',exact=True).is_enabled()
    frozen=page.evaluate(count)
    page.evaluate('padConnected=true')
    page.locator('.rc-status').get_by_role('button',name='Use keyboard').wait_for(state='detached')
    assert page.evaluate(count)==frozen
    page.evaluate('padConnected=false')
    page.locator('.rc-status').get_by_role('button',name='Use keyboard').click()
    assert page.evaluate(count)==frozen
    page.get_by_role('button',name='Resume',exact=True).click()
    page.wait_for_function('minimum=>Number(document.querySelector("canvas").dataset.frameCount)>minimum',arg=frozen+5)

    page.set_viewport_size({'width':390,'height':700})
    panel=open_settings()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth && document.scrollingElement.scrollHeight<=innerHeight+1')
    page.screenshot(path=str(output.with_suffix('.settings-mobile.png')),full_page=False)
    page.keyboard.press('Escape')
    panel.wait_for(state='detached')
    assert hashlib.sha256(rom).hexdigest() in read_fingerprint(page)
    assert page.evaluate('createdWorkers')==1
    assert not errors,errors
    result={'keyboard_remap_input_pixels':True,'reserved_binding_conflict':True,
            'gamepad_conflict_replaced_without_reopening':True,'cancel_and_defaults_confirmation':True,
            'gamepad_remap_input_pixels':True,'gamepad_axis_capture':True,
            'volume_applies_under_mute':True,'focus_releases_gamepad':True,
            'unplug_pauses_and_keyboard_resumes':True,
            'presentation_preserves_progress_and_fingerprint':True,
            'single_worker_through_settings':True,'escape_and_mobile_no_overflow':True,
            'game_only_muted':True,'page_errors':errors}
    page.close()
    return result


def verify_disconnected_load(browser, url, rom):
    page = browser.new_page()
    page.add_init_script("""window.connected=true;
      navigator.getGamepads=()=>connected ? [{id:'Startup controller',index:0,connected:true,buttons:[],axes:[0,0]}] : [];
    """)
    page.goto(url)
    enter_create(page)
    page.get_by_label('NES cartridge file').set_input_files({'name':'setup.nes','mimeType':'application/octet-stream','buffer':rom})
    start_solo(page,rom)
    page.get_by_role('button',name='Pause',exact=True).wait_for()
    page.get_by_role('button',name='Pause',exact=True).click()
    page.locator('.rc-game-links').get_by_role('button',name='Settings',exact=True).click()
    page.locator('.rc-side-content:visible').get_by_role('button',name='Controls').click()
    tool_page=page.locator('.rc-settings')
    tool_page.get_by_label('Input device',exact=True).select_option('0')
    page.locator('.rc-tool-back').click()
    page.evaluate('connected=false')
    page.locator('.rc-status').get_by_text('Controller disconnected',exact=False).wait_for()
    count="Number(document.querySelector('canvas').dataset.frameCount)"
    for attempt in range(2):
        candidate=rom+(b'first replacement' if attempt==0 else b'second replacement')
        page.get_by_label('NES cartridge file').set_input_files({'name':'disconnected.nes','mimeType':'application/octet-stream','buffer':candidate})
        expected=hashlib.sha256(candidate).hexdigest()
        assert expected in read_fingerprint(page, expected)
        assert page.get_by_role('button',name='Resume',exact=True).is_enabled(), 'Disconnected load must remain paused'
        assert page.evaluate(count)==0, 'Disconnected load must not schedule any frame'
        page.get_by_role('button',name='Resume',exact=True).click()
        assert page.get_by_role('button',name='Resume',exact=True).is_enabled()
        assert page.evaluate(count)==0
        if attempt==0:
            page.evaluate('connected=true')
        else:
            page.locator('.rc-status').get_by_role('button',name='Use keyboard').click()
        assert page.evaluate(count)==0, 'Input recovery must not resume the timeline'
        page.get_by_role('button',name='Resume',exact=True).click()
        page.wait_for_function(count+'>5')
        if attempt==0:
            page.evaluate('connected=false')
            page.locator('.rc-status').get_by_text('Controller disconnected',exact=False).wait_for()
    page.close()
    return {'first_and_replacement_load_wait_for_valid_input':True,'resume_requires_current_device':True,
            'reconnect_and_keyboard_fallback_require_explicit_resume':True}
