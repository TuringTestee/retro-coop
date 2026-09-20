"""Real IndexedDB transactions and visible manual-slot workflows, using actual WASM."""
import json


def verify_saves(browser,url,rom,output):
    page=browser.new_page(viewport={'width':1280,'height':1000},accept_downloads=True)
    errors=[];requests=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('request',lambda request:requests.append((request.method,request.url)))
    page.add_init_script('''window.fileCalls=[];window.fileReplies=[];window.abortNextSave=false;
      const NativeWorker=Worker;window.Worker=class extends NativeWorker{
        constructor(...args){super(...args);this.addEventListener('message',event=>{const data=event.data;if(data.type==='state-info' && window.holdInfo){event.stopImmediatePropagation();window.heldInfo={worker:this,data};return}if('requestId' in data)fileReplies.push(data)})}
        postMessage(data,...args){if('requestId' in data)fileCalls.push(data.type);return super.postMessage(data,...args)}
      };
      const openDb=indexedDB.open.bind(indexedDB);
      indexedDB.open=(...args)=>{const request=openDb(...args);request.addEventListener('success',event=>{if(window.holdDbOpen){window.holdDbOpen=false;event.stopImmediatePropagation();window.heldDbOpen=request;}});return request};
      const put=IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put=function(...args){if(window.throwNextSave){window.throwNextSave=false;throw new DOMException('quota','QuotaExceededError')}const request=put.apply(this,args);if(abortNextSave){abortNextSave=false;const tx=this.transaction;request.addEventListener('success',()=>tx.abort())}return request};
    ''')
    def load():
        page.get_by_label('NES cartridge file').set_input_files({'name':'private-slots.nes','mimeType':'application/octet-stream','buffer':rom})
        page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>5")
    def open_saves(wait_for_slots=True):
        page.get_by_role('button',name='Saves',exact=True).click()
        page.get_by_role('button',name='Save current point',exact=True).wait_for()
        if wait_for_slots: page.wait_for_function("!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Save current point').disabled")
    def saved():
        page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('Saved in Slot')")
    def rows():
        return page.evaluate('''()=>new Promise((resolve,reject)=>{const r=indexedDB.open('retro-coop-local',1);r.onsuccess=()=>{const db=r.result,tx=db.transaction('saves'),q=tx.objectStore('saves').getAll();q.onsuccess=()=>resolve(q.result.map(x=>({...x,bytes:Array.from(new Uint8Array(x.bytes))})));tx.oncomplete=()=>db.close()};r.onerror=()=>reject(r.error)})''')
    page.goto(url);load();open_saves()
    dialog=page.get_by_role('dialog',name='Saves on this device')
    page.screenshot(path=str(output.with_suffix('.saves-before.png')),full_page=False)
    frames_before=page.locator('[data-testid=frames]').inner_text()
    dialog.get_by_role('button',name='Save current point',exact=True).click();saved()
    first=rows();assert len(first)==1 and set(first[0])=={'identity','slot','savedAt','bytes'}
    assert bytes(first[0]['bytes'][:8])==b'RCSTATE1'
    assert page.locator('[data-testid=frames]').inner_text()!=frames_before
    dialog.get_by_role('button',name='Save current point',exact=True).click()
    dialog.get_by_role('button',name='Cancel',exact=True).click();assert rows()==first
    page.wait_for_function("document.activeElement.textContent==='Save current point'")
    # A second tab can create/change the slot after listing: check-and-put is atomic.
    page.evaluate("""()=>new Promise((resolve,reject)=>{const r=indexedDB.open('retro-coop-local',1);r.onsuccess=()=>{const db=r.result,tx=db.transaction('saves','readwrite'),store=tx.objectStore('saves'),q=store.getAll();q.onsuccess=()=>{const row=q.result[0];row.savedAt+=1;store.put(row)};tx.oncomplete=()=>{db.close();resolve()};tx.onabort=()=>reject(tx.error)}})""")
    first=rows()
    dialog.get_by_role('button',name='Save current point',exact=True).click();dialog.get_by_role('button',name='Confirm',exact=True).click()
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('changed in another tab')")
    assert rows()==first
    dialog.get_by_role('button',name='Close saves',exact=True).click();open_saves()
    page.evaluate('throwNextSave=true')
    dialog.get_by_role('button',name='Save current point',exact=True).click();dialog.get_by_role('button',name='Confirm',exact=True).click()
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('quota')")
    assert rows()==first
    # Abort after request success: no false durable success and old row survives.
    page.evaluate('abortNextSave=true')
    dialog.get_by_role('button',name='Save current point',exact=True).click()
    dialog.get_by_role('button',name='Confirm',exact=True).click()
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes(\"Couldn't save on this device\")")
    assert rows()==first
    with page.expect_download() as download:
        dialog.get_by_role('button',name='Export memory backup',exact=True).click()
    assert download.value.suggested_filename.endswith('.rcstate')
    dialog.get_by_role('button',name='Save current point',exact=True).click()
    dialog.get_by_role('button',name='Confirm',exact=True).click();saved()
    updated=rows();assert updated[0]['savedAt']>first[0]['savedAt'];first=updated
    page.evaluate("()=>{window.nativeUrl=URL.createObjectURL;URL.createObjectURL=()=>{throw Error('download blocked')}}")
    dialog.get_by_role('button',name='Export Slot 1',exact=True).click()
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes(\"Couldn't export\")")
    page.evaluate('()=>{URL.createObjectURL=nativeUrl}')
    with page.expect_download() as download:
        dialog.get_by_role('button',name='Retry export',exact=True).click()
    assert open(download.value.path(),'rb').read()==bytes(first[0]['bytes'])
    # Persisted data survives reload, but ROM must be selected again.
    page.reload();assert page.get_by_role('button',name='Choose NES file',exact=True).is_visible()
    load();page.evaluate('holdDbOpen=true');open_saves(False)
    page.wait_for_function('!!window.heldDbOpen')
    assert dialog.get_by_role('button',name='Save current point',exact=True).is_disabled()
    assert dialog.get_by_role('button',name='Import save',exact=True).is_disabled()
    page.evaluate("heldDbOpen.dispatchEvent(new Event('success'))")
    dialog.get_by_role('button',name='Load Slot 1',exact=True).wait_for()
    assert rows()==first
    dialog.get_by_role('button',name='Load Slot 1',exact=True).click();dialog.get_by_role('button',name='Cancel',exact=True).click()
    assert page.evaluate("fileCalls.filter(x=>x==='state-import').length")==0
    dialog.get_by_role('button',name='Load Slot 1',exact=True).click();dialog.get_by_role('button',name='Confirm',exact=True).click()
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('Save loaded')")
    assert page.evaluate("fileReplies.some(x=>x.type==='state-imported')")
    # Import inserts a validated slot without replacing current paused progress.
    dialog.get_by_label('Save slot').select_option('2')
    calls=page.evaluate("fileCalls.filter(x=>x==='state-import').length")
    canvas=page.locator('canvas').evaluate('c=>c.toDataURL()')
    page.get_by_label('Save file',exact=True).set_input_files({'name':'backup.rcstate','mimeType':'application/octet-stream','buffer':bytes(first[0]['bytes'])})
    saved();assert len(rows())==2
    assert page.evaluate("fileCalls.filter(x=>x==='state-import').length")==calls
    assert page.evaluate("fileReplies.some(x=>x.type==='state-validated')")
    assert page.locator('canvas').evaluate('c=>c.toDataURL()')==canvas
    preserved=rows()
    bad=bytearray(first[0]['bytes']);bad[8]^=1
    page.get_by_label('Save file',exact=True).set_input_files({'name':'wrong.rcstate','mimeType':'application/octet-stream','buffer':bytes(bad)})
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('different game')")
    assert rows()==preserved
    page.get_by_label('Save file',exact=True).set_input_files({'name':'broken.rcstate','mimeType':'application/octet-stream','buffer':b'broken'})
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('Invalid local state length')")
    assert rows()==preserved
    validations=page.evaluate("fileCalls.filter(x=>x==='state-validate').length")
    page.get_by_label('Save file',exact=True).set_input_files({'name':'oversized.rcstate','mimeType':'application/octet-stream','buffer':bytes(2*1024*1024+1)})
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('exceeds the supported size')")
    assert page.evaluate("fileCalls.filter(x=>x==='state-validate').length")==validations
    assert rows()==preserved
    dialog.get_by_role('button',name='Delete Slot 2',exact=True).click();dialog.get_by_role('button',name='Cancel',exact=True).click();assert rows()==preserved
    dialog.get_by_role('button',name='Delete Slot 2',exact=True).click();dialog.get_by_role('button',name='Confirm',exact=True).click()
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('Deleted Slot 2')")
    assert len(rows())==1
    page.screenshot(path=str(output.with_suffix('.saves-after.png')),full_page=False)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output.with_suffix('.saves-mobile.png')),full_page=False)
    dialog.press('Escape');assert page.evaluate("document.activeElement.textContent==='Saves'")
    # Storage denial still exposes the in-memory export path; play remains usable.
    page.evaluate("()=>{window.nativeOpen=indexedDB.open.bind(indexedDB);indexedDB.open=()=>{throw new DOMException('denied','SecurityError')}}")
    open_saves(False)
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes(\"Couldn't save on this device\")")
    with page.expect_download() as download:
        dialog.get_by_role('button',name='Export current save',exact=True).click()
    assert download.value.suggested_filename.endswith('.rcstate')
    dialog.get_by_role('button',name='Close saves',exact=True).click()
    page.evaluate('()=>{indexedDB.open=nativeOpen}')
    # A superseded worker's delayed reply cannot populate the replacement game's slots.
    page.evaluate('holdInfo=true');page.get_by_role('button',name='Saves',exact=True).click()
    page.wait_for_function('!!window.heldInfo');page.evaluate('holdInfo=false')
    page.get_by_label('NES cartridge file').set_input_files({'name':'other-game.nes','mimeType':'application/octet-stream','buffer':rom+b'\x01'})
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('No saves for this game')")
    page.evaluate("heldInfo.worker.dispatchEvent(new MessageEvent('message',{data:heldInfo.data}))")
    assert dialog.get_by_role('button',name='Load Slot 1',exact=True).count()==0
    dialog.get_by_role('button',name='Close saves',exact=True).click()
    # An unvalidated profile has an explicit save limitation, not a loading gate.
    variant=bytearray(rom);variant[4]=2;variant[16+16384:16+16384]=rom[16:16+16384];variant[6]=0xd2;variant[7]=0x90
    page.get_by_label('NES cartridge file').set_input_files({'name':'unvalidated.nes','mimeType':'application/octet-stream','buffer':bytes(variant)})
    page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>5")
    page.get_by_role('button',name='Saves',exact=True).click()
    page.wait_for_function("document.querySelector('[data-testid=save-status]')?.textContent.includes('not yet validated')")
    assert dialog.get_by_role('button',name='Save current point',exact=True).is_disabled()
    assert len(rows())==1
    assert not errors,errors
    assert all(method=='GET' and target.startswith(url) for method,target in requests),requests
    result={'quota_failure_keeps_slot_and_backup':True,'concurrent_slot_change_requires_fresh_confirmation':True,'slot_listing_gates_overwrite_decisions':True,'failed_export_keeps_bytes_for_retry':True,'superseded_worker_reply_ignored':True,'storage_denial_keeps_memory_export':True,'oversized_rejected_before_worker':True,'unvalidated_profile_stays_playable':True,'transaction_complete_before_success':True,'aborted_overwrite_preserves_slot':True,'memory_export_after_storage_failure':True,'reload_requires_rom_and_retains_save':True,'confirmed_restore':True,'import_validates_without_changing_timeline':True,'wrong_identity_and_malformed_preserve_slots':True,'confirmed_delete_and_cancel':True,'save_does_not_pause':True,'mobile_no_overflow':True,'escape_restores_focus':True,'no_rom_record_or_upload':True,'stored_file_bytes':len(first[0]['bytes']),'page_errors':errors}
    page.close();return result
