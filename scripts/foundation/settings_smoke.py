"""Real-browser controls/presentation checks on the same built client as file-to-play."""
import hashlib


def verify_settings(browser, url, rom, output):
    page = browser.new_page(viewport={'width':1280,'height':1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script('''window.createdWorkers=0;const NativeWorker=Worker;window.Worker=class extends NativeWorker{constructor(...args){super(...args);createdWorkers++}};
      window.padButtons=[];window.padAxes=[0,0];window.padConnected=true;
      navigator.getGamepads=()=>padConnected ? [{id:'Diagnostic controller',index:0,connected:true,
        buttons:Array.from({length:16},(_,i)=>({pressed:padButtons.includes(i),touched:false,value:padButtons.includes(i)?1:0})),axes:padAxes}] : [];
      window.gameGains=[]; const gain=AudioContext.prototype.createGain;
      AudioContext.prototype.createGain=function(){const node=gain.call(this);gameGains.push(node);return node};
    ''')
    page.goto(url)
    page.set_input_files('input[type=file]', {'name':'controls-fixture.nes','mimeType':'application/octet-stream','buffer':rom})
    count = "Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])"
    page.wait_for_function(count+'>10')
    page.get_by_role('button',name='Settings',exact=True).click()
    dialog = page.get_by_role('dialog',name='Local settings')
    assert dialog.is_visible()
    page.screenshot(path=str(output.with_suffix('.settings-before.png')),full_page=True)
    assert dialog.get_by_role('button',name='Change ',exact=False).count() == 9
    # Capture conflict includes future voice input; cancelled capture never changes mappings.
    dialog.get_by_role('button',name='Change Right',exact=True).click()
    page.get_by_label('Capture input',exact=True).press('v')
    assert dialog.get_by_role('button',name='Apply mapping').is_disabled()
    assert 'Push to talk' in dialog.locator('[role=status]').inner_text()
    page.get_by_label('Capture input',exact=True).press('l')
    dialog.get_by_role('button',name='Cancel mapping').click()
    assert page.evaluate('document.activeElement.textContent') == 'Change Right'
    right = dialog.locator('.mapping').filter(has=page.get_by_role('button',name='Change Right',exact=True))
    assert 'Arrow Right' in right.inner_text()
    right.get_by_role('button').click();page.get_by_label('Capture input',exact=True).press('l')
    dialog.get_by_role('button',name='Apply mapping').click()
    assert 'L' in right.inner_text()
    test = page.get_by_label('Test mapped input',exact=True);test.focus();page.keyboard.down('l')
    page.wait_for_function("document.querySelector('[data-testid=input-test]').textContent==='Right'")
    page.keyboard.up('l')
    page.wait_for_function("document.querySelector('[data-testid=input-test]').textContent==='None'")
    # Presentation settings don't restart the game or rewrite its file fingerprint.
    old_frames = page.evaluate(count)
    dialog.get_by_label('Display filter').select_option('scanlines')
    dialog.get_by_label('Game volume').fill('35')
    assert page.locator('.screen').evaluate("e=>getComputedStyle(e,'::after').backgroundImage.includes('repeating-linear-gradient')")
    assert page.evaluate('gameGains[0].gain.value') == 0  # App remains muted throughout.
    page.screenshot(path=str(output.with_suffix('.settings-after.png')),full_page=True)
    dialog.get_by_label('Game volume').fill('0')
    dialog.get_by_role('button',name='Done',exact=True).click()
    assert page.get_by_role('button',name='Settings',exact=True).evaluate('e=>e===document.activeElement')
    page.get_by_role('button',name='Unmute',exact=True).click()
    assert page.evaluate('gameGains[0].gain.value') == 0  # Zero local volume remains silent when unmuted.
    page.get_by_role('button',name='Mute',exact=True).click()
    canvas = page.locator('canvas');canvas.focus();baseline = canvas.evaluate('c=>c.toDataURL()')
    page.keyboard.down('l')
    page.wait_for_function('before=>document.querySelector("canvas").toDataURL()!==before',arg=baseline)
    page.keyboard.up('l')
    assert page.evaluate(count)>old_frames
    # Restore confirms exactly one mapping set; cancellation leaves remap intact.
    page.get_by_role('button',name='Settings',exact=True).click()
    dialog.get_by_role('button',name='Restore keyboard defaults').click()
    dialog.get_by_role('button',name='Keep mappings').click()
    assert 'L' in right.inner_text()
    dialog.get_by_role('button',name='Restore keyboard defaults').click()
    dialog.get_by_role('button',name='Confirm restore').click()
    assert 'Arrow Right' in right.inner_text()
    # A selected gamepad is required for capture; held/default buttons can't bypass conflicts.
    dialog.get_by_label('Input device',exact=True).select_option('0')
    dialog.get_by_role('button',name='Change Right',exact=True).click()
    page.evaluate('padButtons=[10]')
    page.wait_for_function("document.querySelector('.capture [role=status]').textContent.includes('already used')")
    assert dialog.get_by_role('button',name='Apply mapping').is_disabled()
    page.evaluate('padButtons=[];padAxes=[0,0]')
    # Let a released observation pass before issuing the new edge.
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    dialog.get_by_role('button',name='Cancel mapping').click()
    dialog.get_by_role('button',name='Change Right',exact=True).click()
    page.evaluate('padButtons=[3]')
    page.wait_for_function("document.querySelector('.capture [role=status]').textContent.includes('Button 4')")
    dialog.get_by_role('button',name='Apply mapping').click()
    page.get_by_label('Test mapped input',exact=True).focus()
    page.wait_for_function("document.querySelector('[data-testid=input-test]').textContent==='Right'")
    page.evaluate('padButtons=[]')
    dialog.get_by_role('button',name='Change Up',exact=True).click()
    page.evaluate('padAxes=[0,0,-0.75]')
    page.wait_for_function("document.querySelector('.capture [role=status]').textContent.includes('Axis 3')")
    dialog.get_by_role('button',name='Apply mapping').click()
    page.evaluate('padAxes=[0,0,0]')
    dialog.get_by_role('button',name='Done',exact=True).click()
    canvas.focus();baseline=canvas.evaluate('c=>c.toDataURL()')
    page.evaluate('padButtons=[3]')
    page.wait_for_function('before=>document.querySelector("canvas").toDataURL()!==before',arg=baseline)
    page.get_by_role('button',name='Settings',exact=True).focus()
    page.wait_for_function('before=>document.querySelector("canvas").toDataURL()===before',arg=baseline)
    # Disconnect pauses; keyboard fallback must not silently resume or reset.
    page.evaluate('padConnected=false')
    page.get_by_role('button',name='Use keyboard',exact=True).wait_for()
    page.evaluate('padConnected=true;padButtons=[]')
    page.get_by_role('button',name='Use keyboard',exact=True).wait_for(state='detached')
    assert page.get_by_role('button',name='Resume',exact=True).is_enabled()
    page.evaluate('padConnected=false')
    page.get_by_role('button',name='Use keyboard',exact=True).click()
    assert page.get_by_role('button',name='Resume',exact=True).is_enabled()
    frozen = page.evaluate(count)
    page.get_by_role('button',name='Resume',exact=True).click()
    page.wait_for_function('minimum=>Number(document.querySelector("[data-testid=frames]").textContent.split(" ")[0])>minimum',arg=frozen+5)
    # Browser refusal never blocks normal play, and normal fullscreen has an exit.
    page.evaluate('()=>{window.fullscreenRequest=Element.prototype.requestFullscreen;Element.prototype.requestFullscreen=()=>Promise.reject(new Error("Denied"));}')
    page.get_by_role('button',name='Fullscreen',exact=True).click()
    page.get_by_text('Fullscreen was declined.',exact=False).wait_for()
    page.evaluate('()=>{Element.prototype.requestFullscreen=fullscreenRequest;}')
    page.get_by_role('button',name='Fullscreen',exact=True).click()
    page.get_by_role('button',name='Exit fullscreen',exact=True).wait_for()
    assert page.evaluate('!!document.fullscreenElement')
    page.get_by_role('button',name='Exit fullscreen',exact=True).click()
    page.wait_for_function('!document.fullscreenElement')
    page.set_viewport_size({'width':390,'height':844})
    page.get_by_role('button',name='Settings',exact=True).click()
    assert dialog.evaluate('e=>e.scrollWidth<=e.clientWidth')
    dialog.evaluate('e=>e.scrollTop=0')
    page.screenshot(path=str(output.with_suffix('.settings-mobile.png')),full_page=True)
    page.keyboard.press('Escape');assert not dialog.is_visible()
    page.locator('summary').click()
    assert hashlib.sha256(rom).hexdigest() in page.locator('[data-testid=fingerprint]').inner_text()
    assert page.evaluate('createdWorkers') == 1
    assert not errors,errors
    result={'keyboard_remap_input_pixels':True,'reserved_binding_conflict':True,'cancel_and_defaults_confirmation':True,
            'gamepad_remap_input_pixels':True,'gamepad_axis_capture':True,'volume_applies_under_mute':True,'reconnect_does_not_resume':True,'focus_releases_gamepad':True,'unplug_pauses_and_keyboard_resumes':True,
            'presentation_preserves_progress_and_fingerprint':True,'single_worker_through_settings':True,'fullscreen_denial_and_exit':True,
            'dialog_focus_restore_and_escape':True,'mobile_no_overflow':True,'game_only_muted':True,'page_errors':errors}
    page.close()
    return result
