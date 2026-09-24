"""Actual candidate battery restore, IndexedDB upgrade/recovery and preferences."""
import json
from local_play import enter_create, start_solo


def verify_persistence(browser,url,rom,worker_path,output):
    context=browser.new_context(viewport={'width':1280,'height':1000},accept_downloads=True)
    requests=[];context.on('request',lambda request:requests.append((request.method,request.url)))
    page=context.new_page()
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script('''window.fileEvents=[];const NativeWorker=Worker;window.Worker=class extends NativeWorker{
      postMessage(data,...args){fileEvents.push(data.type);return super.postMessage(data,...args)}
    };''')
    variant=bytearray(rom);variant[6]|=2
    # Read battery at boot into CPU RAM, then write nonzero progress and loop.
    program=bytes([0x78,0xad,0x00,0x60,0x85,0x03,0xa9,0x5a,0x8d,0x00,0x60,0x4c,0x0b,0x80])
    variant[16:16+len(program)]=program
    page.goto(url)
    # Seed a real compatible v1 slot and a synthetic other-identity backup before upgrade.
    legacy=page.evaluate('''async ({rom,workerPath})=>{
      const worker=new Worker(workerPath,{type:'module'}),ask=data=>new Promise((resolve,reject)=>{worker.onmessage=event=>resolve(event.data);worker.onerror=reject;worker.postMessage(data)});
      if((await ask({type:'load',rom:new Uint8Array(rom).buffer})).type!=='ready')throw Error('seed load');
      await ask({type:'frame',p1:0,p2:0});const info=await ask({type:'state-info',requestId:1}),save=await ask({type:'state-export',requestId:2});worker.terminate();
      const other=new Uint8Array(save.bytes.slice(0));other.fill(0xaa,8,40);
      await new Promise((resolve,reject)=>{const request=indexedDB.open('retro-coop-local',1);request.onupgradeneeded=()=>request.result.createObjectStore('saves',{keyPath:['identity','slot']}).createIndex('identity','identity');request.onsuccess=()=>{const db=request.result,tx=db.transaction('saves','readwrite'),store=tx.objectStore('saves');store.put({identity:info.info.identity,slot:3,savedAt:1,bytes:save.bytes});store.put({identity:'aa'.repeat(32),slot:1,savedAt:2,bytes:other.buffer});tx.oncomplete=()=>{db.close();resolve()};tx.onabort=()=>reject(tx.error)}});
      return Array.from(other);
    }''',{'rom':list(variant),'workerPath':worker_path})
    def load(target=page):
        target.get_by_label('NES cartridge file').set_input_files({'name':'battery-private.nes','mimeType':'application/octet-stream','buffer':bytes(variant)})
        start_solo(target,variant)
    def data(target=page):
        return target.evaluate('''()=>new Promise((resolve,reject)=>{const request=indexedDB.open('retro-coop-local');request.onsuccess=()=>{const db=request.result,result={version:db.version},tx=db.transaction(['saves','batteries','preferences','meta']);for(const name of ['saves','batteries','preferences']){const q=tx.objectStore(name).getAll();q.onsuccess=()=>result[name]=q.result.map(row=>({...row,...(row.bytes ? {bytes:Array.from(new Uint8Array(row.bytes))} : {})}))}const epoch=tx.objectStore('meta').get('generation');epoch.onsuccess=()=>result.generation=epoch.result ?? 0;tx.oncomplete=()=>{db.close();resolve(result)};tx.onabort=()=>reject(tx.error)}})''')
    def local_data():
        page.get_by_role('button',name='Settings',exact=True).click()
        page.get_by_role('button',name='Local data',exact=True).click()
        page.get_by_role('button',name='Delete all local data',exact=True).wait_for()
        page.wait_for_function("!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Delete all local data').disabled")
        return page.locator('.local-data.tool-page')
    enter_create(page);load();assert data()['version']==3 and len(data()['saves'])==2
    # The actual ten-second application timer writes nonzero SRAM, without test acceleration.
    page.wait_for_function("fileEvents.includes('battery-export')",timeout=15000)
    page.wait_for_function('''()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction('batteries'),q=tx.objectStore('batteries').count();q.onsuccess=()=>resolve(q.result===1);tx.oncomplete=()=>db.close()}})''')
    assert data()['batteries'][0]['bytes'][76]==0x5a
    page.get_by_role('button',name='Settings',exact=True).click()
    settings=page.locator('.settings.tool-page')
    settings.get_by_label('Display filter').select_option('scanlines');settings.get_by_label('Game volume').fill('37')
    settings.get_by_role('button',name='Change Right',exact=True).click();page.get_by_label('Capture input',exact=True).press('l');settings.get_by_role('button',name='Apply mapping',exact=True).click()
    page.wait_for_function('''()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction('preferences'),q=tx.objectStore('preferences').getAll();q.onsuccess=()=>resolve(q.result[0]?.value.controls.keyboard.right.includes('KeyL'));tx.oncomplete=()=>db.close()}})''')
    page.reload();enter_create(page);load()
    events=page.evaluate('fileEvents');assert events.index('battery-import')<events.index('frame')
    page.wait_for_selector('.screen.scanlines')
    page.get_by_role('button',name='Settings',exact=True).click()
    assert settings.get_by_label('Game volume').input_value()=='37'
    assert settings.get_by_role('button',name='Change Right',exact=True).locator('..').locator('span').nth(1).inner_text()=='L', {'mapping':settings.get_by_role('button',name='Change Right',exact=True).locator('..').inner_text(),'stored':data()['preferences']}
    page.get_by_role('button',name='Back',exact=True).click()
    page.get_by_role('button',name='Saves',exact=True).click()
    with page.expect_download() as download:page.get_by_role('button',name='Export current save',exact=True).click()
    machine=json.loads(open(download.value.path(),'rb').read()[72:]);assert machine['hardware']['wram'][3]==0x5a
    page.get_by_role('button',name='Back',exact=True).click()
    panel=local_data();page.get_by_text('Current game and build',exact=False).first.wait_for()
    other=panel.locator('li').filter(has_text='Other game or build')
    with page.expect_download() as download:other.get_by_role('button',name='Export save').click()
    assert open(download.value.path(),'rb').read()==bytes(legacy)
    assert len(data()['preferences'])==1
    page.screenshot(path=str(output.with_suffix('.local-data-before.png')),full_page=False)
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output.with_suffix('.local-data-mobile-before.png')),full_page=False)
    page.set_viewport_size({'width':1280,'height':1000})
    # Cancellation preserves all current and other-version data.
    before=data()
    for name,fields in [('saves',{'identity','slot','savedAt','bytes'}),('batteries',{'identity','savedAt','bytes'}),('preferences',{'identity','savedAt','value'})]:
        assert before[name] and all(set(row)==fields for row in before[name])
    panel.get_by_role('button',name='Delete all local data',exact=True).click();panel.get_by_role('button',name='Cancel',exact=True).click();assert data()==before
    # Damaged metadata alone must disable automatic replacement, even with valid payload bytes.
    page.evaluate("""()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction('batteries','readwrite'),store=tx.objectStore('batteries'),q=store.getAll();q.onsuccess=()=>{const row=q.result[0];row.savedAt=NaN;store.put(row)};tx.oncomplete=()=>{db.close();resolve()}}})""")
    page.reload();enter_create(page);load()
    assert 'could not be restored' in page.get_by_test_id('persistence-status').inner_text()
    exports=page.evaluate("fileEvents.filter(type=>type==='battery-export').length")
    frames=int(page.get_by_test_id('frames').inner_text().split()[0])
    page.evaluate("window.dispatchEvent(new Event('pagehide'))")
    page.wait_for_function("before=>Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>before+3",arg=frames)
    assert page.evaluate("fileEvents.filter(type=>type==='battery-export').length")==exports
    assert page.evaluate("""()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction('batteries'),q=tx.objectStore('batteries').getAll();q.onsuccess=()=>resolve(Number.isNaN(q.result[0].savedAt));tx.oncomplete=()=>db.close()}})""")
    # Corrupt battery/preferences remain exportable and never block ROM admission.
    page.evaluate('''()=>new Promise((resolve,reject)=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction(['batteries','preferences'],'readwrite');for(const name of ['batteries','preferences']){const store=tx.objectStore(name),q=store.getAll();q.onsuccess=()=>{const row=q.result[0];if(name==='batteries'){new Uint8Array(row.bytes)[44]^=1;row.savedAt=Date.now();}else row.value={controls:null};store.put(row)}}tx.oncomplete=()=>{db.close();resolve()};tx.onabort=()=>reject(tx.error)}})''')
    corrupted=data();page.reload();enter_create(page);load()
    page.get_by_test_id('persistence-status').wait_for()
    assert 'could not be restored' in page.get_by_test_id('persistence-status').inner_text()
    assert page.locator('.screen.scanlines').count()==0
    page.evaluate("window.dispatchEvent(new Event('pagehide'))")
    assert data()['batteries']==corrupted['batteries']
    panel=local_data()
    with page.expect_download() as download:panel.get_by_role('button',name='Export battery',exact=True).click()
    assert open(download.value.path(),'rb').read()==bytes(corrupted['batteries'][0]['bytes'])
    panel.get_by_role('button',name='Delete battery',exact=True).click()
    page.evaluate("""()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction('batteries','readwrite'),store=tx.objectStore('batteries'),q=store.getAll();q.onsuccess=()=>{const row=q.result[0];row.savedAt++;store.put(row)};tx.oncomplete=()=>{db.close();resolve()}}})""")
    newer=data()['batteries'];panel.get_by_role('button',name='Confirm',exact=True).click()
    page.get_by_test_id('local-data-status').filter(has_text='changed in another tab').wait_for()
    assert data()['batteries']==newer
    page.wait_for_function("!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Delete battery').disabled")
    panel.get_by_role('button',name='Delete battery',exact=True).click();panel.get_by_role('button',name='Confirm',exact=True).click()
    page.wait_for_function("!Array.from(document.querySelectorAll('.local-data li')).some(row=>row.textContent.includes('Battery progress'))")
    page.get_by_role('button',name='Back',exact=True).click();page.get_by_role('button',name='Back',exact=True).click()
    page.get_by_role('button',name='Retry battery saving',exact=True).click()
    page.wait_for_function('''()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction('batteries'),q=tx.objectStore('batteries').getAll();q.onsuccess=()=>resolve(q.result[0] && new Uint8Array(q.result[0].bytes)[76]===0x5a);tx.oncomplete=()=>db.close()}})''')
    # An older active tab must not recreate records after clear-all advances the epoch.
    second=page.context.new_page();second.on('pageerror',lambda error:errors.append(str(error)));second.goto(url);enter_create(second);load(second)
    panel=local_data();panel.get_by_role('button',name='Delete all local data',exact=True).click();panel.get_by_role('button',name='Confirm',exact=True).click()
    page.get_by_text('No local data yet.',exact=True).wait_for()
    cleared=data();assert not cleared['saves'] and not cleared['batteries'] and not cleared['preferences'] and cleared['generation']==1
    second.wait_for_function("document.querySelector('[data-testid=persistence-status]')?.textContent.includes('cleared')",timeout=15000)
    assert data()==cleared
    page.screenshot(path=str(output.with_suffix('.local-data-after.png')),full_page=False)
    page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output.with_suffix('.local-data-mobile.png')),full_page=False)
    second.close()
    # Storage denial is a visible recovery state, not a cartridge loading failure.
    denied=browser.new_page(accept_downloads=True);denied.on('pageerror',lambda error:errors.append(str(error)))
    denied.add_init_script("indexedDB.open=()=>{throw new DOMException('denied','SecurityError')}")
    denied.goto(url);enter_create(denied);load(denied)
    assert 'could not be restored' in denied.get_by_test_id('persistence-status').inner_text()
    with denied.expect_download() as download:denied.get_by_role('button',name='Export current battery',exact=True).click()
    assert open(download.value.path(),'rb').read()[:8]==b'RCBAT001'
    denied.close()
    verify_replacement(browser,url,variant)
    verify_damaged_timestamp(browser,url,rom)
    assert not errors,errors
    assert all(method=='GET' and target.startswith(url) for method,target in requests),requests
    result={'v1_slots_preserved_on_upgrade':True,'actual_periodic_nonzero_battery_write':True,'battery_import_before_first_frame':True,'real_cpu_observed_restored_battery_at_boot':True,'preferences_restored_for_exact_game':True,'other_identity_backup_export':True,'corrupt_data_retained_and_play_continues':True,'corrupt_battery_export_delete_and_explicit_retry':True,'stale_battery_delete_preserves_replacement_then_refreshes':True,'clear_confirmation_cancel_preserves_records':True,'cleared_epoch_blocks_other_tab_automatic_write':True,'storage_denial_keeps_play_and_export':True,'damaged_timestamp_blocks_automatic_write':True,'damaged_timestamp_export_delete_preserves_unrelated':True,'changed_damaged_timestamp_refuses_stale_delete':True,'same_rom_replacement_captures_before_candidate_restore':True,'mobile_no_overflow':True,'page_errors':errors}
    context.close();return result


def verify_replacement(browser,url,rom):
    page=browser.new_page(accept_downloads=True)
    page.add_init_script("window.exports=0;const Base=Worker;window.Worker=class extends Base{postMessage(data,...args){if(data.type==='battery-export')exports++;return super.postMessage(data,...args)}}")
    page.goto(url)
    enter_create(page)
    def select():
        page.get_by_label('NES cartridge file').set_input_files({'name':'replacement.nes','mimeType':'application/octet-stream','buffer':bytes(rom)})
        start_solo(page,rom)
    select()
    assert page.evaluate('exports')==0, 'Regression must precede the first periodic/lifecycle capture'
    select()
    page.get_by_role('button',name='Saves',exact=True).click()
    with page.expect_download() as download:page.get_by_role('button',name='Export current save',exact=True).click()
    machine=json.loads(open(download.value.path(),'rb').read()[72:])
    assert machine['hardware']['wram'][3]==0x5a, {'restored_boot_byte':machine['hardware']['wram'][3],'expected':0x5a}
    page.close()


def verify_damaged_timestamp(browser,url,rom):
    page=browser.new_page(accept_downloads=True);page.goto(url);enter_create(page);page.set_input_files('input[type=file]',{'name':'local-data-setup.nes','mimeType':'application/octet-stream','buffer':rom});page.get_by_role('button',name='Settings',exact=True).wait_for()
    def panel():
        page.get_by_role('button',name='Settings',exact=True).click()
        page.get_by_role('button',name='Local data',exact=True).click()
        page.wait_for_function("!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Delete all local data').disabled")
        return page.locator('.local-data.tool-page')
    dialog=panel();page.get_by_role('button',name='Back',exact=True).click();page.get_by_role('button',name='Back',exact=True).click()
    page.evaluate("""()=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction(['batteries','saves'],'readwrite');tx.objectStore('batteries').put({identity:'damaged-record',savedAt:NaN,bytes:new Uint8Array([1,2,3]).buffer});tx.objectStore('saves').put({identity:'unrelated',slot:1,savedAt:1,bytes:new Uint8Array([4,5,6]).buffer});tx.oncomplete=()=>{db.close();resolve()}}})""")
    dialog=panel();dialog.get_by_text('Unknown time',exact=False).wait_for()
    with page.expect_download() as download:dialog.get_by_role('button',name='Export battery',exact=True).click()
    assert open(download.value.path(),'rb').read()==bytes([1,2,3])
    dialog.get_by_role('button',name='Delete battery',exact=True).click();dialog.get_by_role('button',name='Confirm',exact=True).click()
    page.wait_for_function("!Array.from(document.querySelectorAll('.local-data li')).some(row=>row.textContent.includes('Battery progress'))",timeout=2000)
    with page.expect_download() as download:dialog.get_by_role('button',name='Export save',exact=True).click()
    assert open(download.value.path(),'rb').read()==bytes([4,5,6])
    for store,kind in [('batteries','battery'),('preferences','preferences')]:
        page.get_by_role('button',name='Back',exact=True).click();page.get_by_role('button',name='Back',exact=True).click()
        page.evaluate("""name=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction(name,'readwrite');tx.objectStore(name).put({identity:'damaged-record',savedAt:NaN,...(name==='batteries'?{bytes:new Uint8Array([7,8]).buffer}:{value:{invalid:true}})});tx.oncomplete=()=>{db.close();resolve()}}})""",store)
        dialog=panel();dialog.get_by_role('button',name='Delete '+kind,exact=True).click()
        page.evaluate("""name=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction(name,'readwrite'),store=tx.objectStore(name),q=store.get('damaged-record');q.onsuccess=()=>{const row=q.result;row.savedAt=null;store.put(row)};tx.oncomplete=()=>{db.close();resolve()}}})""",store)
        dialog.get_by_role('button',name='Confirm',exact=True).click()
        page.get_by_test_id('local-data-status').filter(has_text='changed in another tab').wait_for()
        assert page.evaluate("""name=>new Promise(resolve=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>{const db=r.result,tx=db.transaction(name),q=tx.objectStore(name).get('damaged-record');q.onsuccess=()=>resolve(q.result?.savedAt===null);tx.oncomplete=()=>db.close()}})""",store)
    page.close()
