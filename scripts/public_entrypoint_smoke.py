#!/usr/bin/env python3
"""Check that the documented command owns the current lobby-first application."""

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def fetch(url, method="GET"):
    with urlopen(Request(url, method=method), timeout=1) as response:
        return response.status, response.read()


def wait_closed(port):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)):
                return
        time.sleep(.05)
    raise AssertionError(f"port {port} remained open after the launcher exited")


def migrated_default_preferences(browser, url, output):
    """Restore both supported record shapes, then edit and play with distinct Save/B keys."""
    from playwright.sync_api import expect
    from rooms.ui_helpers import choose_section, capture_binding
    rows=[]
    context=browser.new_context(viewport={'width':1280,'height':800})
    context.add_init_script((ROOT/'scripts/gameplay/fixture.js').read_text()+"addEventListener('DOMContentLoaded',()=>releaseFrames());")
    page=context.new_page()
    def load_game():
        page.get_by_role('button',name='Load NES game').click();page.get_by_role('button',name='Add game file').click();page.get_by_label('NES cartridge file').set_input_files(str(ROOT/'spikes/d02/fixture.local.nes'))
        page.get_by_role('button',name='Prepare',exact=True).wait_for()
    try:
        page.goto(url);page.get_by_role('button',name='Host a new game').click();load_game()
        editor,capture=capture_binding(page);capture.press('k')
        editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
        page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click()
        page.locator('.rc-listing').wait_for()
        for count in (15,16):
            page.evaluate("""async count=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('retro-coop-local');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
              await new Promise((resolve,reject)=>{const tx=db.transaction('preferences','readwrite'),store=tx.objectStore('preferences'),r=store.getAll();r.onsuccess=()=>{if(r.result.length!==1){tx.abort();return;}const row=r.result[0],c=row.value.controls;c.keyboard={...c.keyboard,a:['KeyX'],b:['KeyZ'],select:['ShiftLeft','ShiftRight'],start:['Enter'],save:['KeyC']};if(count===15){delete c.keyboard.restart;delete c.gamepad.restart;}store.put(row);};tx.oncomplete=resolve;tx.onabort=()=>reject(tx.error??Error('fixture preferences missing'));});db.close();}""",count)
            for reload in range(2):
                page.reload();page.get_by_role('button',name='Host a new game').click();load_game()
                choose_section(page,'Controls')
                expect(page.get_by_role('button',name='Map B: Z',exact=True)).to_be_visible()
                expect(page.get_by_role('button',name='Map Save: C',exact=True)).to_be_visible()
                assert page.get_by_text('Stored preferences are invalid.',exact=False).count()==0
                if reload==0:
                    page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click();page.locator('.rc-listing').wait_for()
            editor,capture=capture_binding(page,'B');capture.press('b');editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
            editor,capture=capture_binding(page,'B');expect(editor).to_contain_text('Current: B');capture.press('z');editor.get_by_role('button',name='Save',exact=True).click();expect(editor).to_have_count(0)
            rows.append({'record_actions':count,'reloads':2,'b':'Z','save':'C','editable':True})
            if count==15:
                page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click();page.locator('.rc-listing').wait_for()
        page.get_by_role('button',name='Prepare',exact=True).click();page.get_by_role('button',name='Start →').click();page.wait_for_function('proof.frameCount>10')
        def native(key,expected):
            before=page.evaluate('proof.frameCount');page.keyboard.down(key)
            page.wait_for_function('before=>proof.frameCount>before+proof.room.game.delay+3',arg=before)
            page.evaluate("delete proof.controllerRam;currentWorker.postMessage({type:'state-export',requestId:900000})")
            page.wait_for_function('proof.controllerRam!==undefined');ram=page.evaluate('proof.controllerRam');assert ram==[expected,0],(count,key,ram)
            page.keyboard.up(key);return ram
        b=native('z',64);save=native('c',0)
        page.get_by_text('Saved to quick slot 1.',exact=True).wait_for()
        rows[-1].update(native_b_ram=b,native_save_ram=save,save_notice=True)
        page.get_by_role('button',name='Back to Main Page',exact=True).click();page.get_by_role('button',name='Close lobby',exact=True).click();page.locator('.rc-listing').wait_for()
    finally:context.close()
    (output/'migrated-default-preferences.json').write_text(json.dumps(rows,indent=2)+'\n')

def cartridge_replacement(browser,url,output):
    """Replace through public controls; reject a real staged native commit and restore the old game."""
    from playwright.sync_api import expect
    start=time.monotonic();pages=[];contexts=[];page_errors=[]
    native_hook="const NativeCartridgeWorker=Worker;proof.native=[];window.Worker=class extends NativeCartridgeWorker{postMessage(data,...rest){if(data.type==='frame'&&data.epoch){(proof.cartridgeInputs??=[]).push({epoch:data.epoch,frame:data.frame,p1:data.p1,p2:data.p2});if(proof.cartridgeInputs.length>32)proof.cartridgeInputs.shift();}if(data.type==='peer-checkpoint-prepare'&&data.initial)this.cartridgeOperation=data.operationId;if(data.type.startsWith('peer-checkpoint-'))proof.native.push({kind:'request',type:data.type,requestId:data.requestId,phase:proof.room?.game.load?.phase,initial:data.initial});if(data.type==='peer-checkpoint-prepare'&&data.initial&&proof.rejectCandidatePrepare){proof.rejectCandidatePrepare=false;const bytes=data.bytes.slice(0),original=new Uint8Array(bytes)[0];new Uint8Array(bytes)[0]^=255;proof.native.push({kind:'request',type:data.type,requestId:data.requestId,fault:'native candidate bytes corrupted',originalHeader:original,sentHeader:new Uint8Array(bytes)[0],bytes:bytes.byteLength});data={...data,bytes};}if(data.type==='peer-checkpoint-commit'&&proof.rejectCandidateCommit&&data.operationId===this.cartridgeOperation){proof.rejectCandidateCommit=false;proof.native.push({kind:'request',type:data.type,requestId:data.requestId,phase:proof.room?.game.load?.phase,fault:'actual stale operation sent after preparation'});data={...data,operationId:data.operationId+'_stale'};}return super.postMessage(data,...rest);}constructor(...args){super(...args);this.addEventListener('message',({data})=>{if(data.type==='frame'&&data.epoch)proof.acceptedCartridgeWorker=this;if(data.type.startsWith('peer-checkpoint-'))proof.native.push({kind:'response',type:data.type,requestId:data.requestId,frame:data.frame,hash:data.hash,message:data.message});});}};"
    observer_hook="""
      const ObserverPeer=RTCPeerConnection;
      const holdObserverChannel=channel=>channel.addEventListener('message',event=>{
        if(!proof.holdObserverFrames||typeof event.data!=='string')return;
        let packet;try{packet=JSON.parse(event.data)}catch{return}
        if(packet.kind==='frame'){
          proof.heldObserverFrames=(proof.heldObserverFrames??0)+1;
          event.stopImmediatePropagation();
        }
      },true);
      // Either member can create the channel; membership IDs determine the offerer.
      window.RTCPeerConnection=class extends ObserverPeer{
        constructor(...args){super(...args);this.addEventListener('datachannel',({channel})=>holdObserverChannel(channel));}
        createDataChannel(...args){const channel=super.createDataChannel(...args);holdObserverChannel(channel);return channel;}
      };
    """
    boundary_hook="const boundarySend=WebSocket.prototype.send;WebSocket.prototype.send=function(raw){let value;try{value=JSON.parse(raw)}catch{}if(value?.type==='gameLoadBoundary'||value?.type==='gameLoadRolledBack')(proof.loadBoundaries??=[]).push({type:value.type,transactionId:value.transactionId,frame:value.frame,hash:value.hash});return boundarySend.call(this,raw);};"
    try:
        for i in range(3):
         ctx=browser.new_context(viewport={'width':1280,'height':800},permissions=['clipboard-read','clipboard-write']);contexts.append(ctx);ctx.add_init_script((ROOT/'scripts/gameplay/fixture.js').read_text());ctx.add_init_script(native_hook);ctx.add_init_script(observer_hook);ctx.add_init_script(boundary_hook);p=ctx.new_page();p.set_default_timeout(15000);p.on('pageerror',lambda e:page_errors.append(str(e)));p.goto(url);p.evaluate('releaseFrames()');pages.append(p)
        h,g,o=pages
        h.get_by_role('button',name='Host a new game',exact=True).click();h.get_by_role('button',name='Load NES game').click();h.get_by_role('button',name='Super Tilt Bro',exact=True).click();h.get_by_role('button',name='Prepare',exact=True).wait_for()
        invite=h.evaluate('proof.room.invite')
        for p in (g,o):
         p.goto(url+'/#invite='+invite);p.evaluate('releaseFrames()');p.get_by_role('button',name='Join lobby',exact=True).click();p.wait_for_function('proof.room?.matches')
        for p in (h,g):p.get_by_role('button',name='Prepare',exact=True).click()
        h.get_by_role('button',name='Start →',exact=True).click()
        for p in (h,g):p.wait_for_function('proof.room?.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
        roster=h.evaluate('proof.room.slots.map(s=>({id:s.id,open:s.open,member:s.member?.id}))');invite=h.evaluate('proof.room.invite')
        h.set_viewport_size({'width':320,'height':700});h.get_by_role('button',name='Expand game to full screen',exact=True).click()
        assert h.get_by_role('button',name='Change game',exact=True).count()==1
        expanded=h.locator('.rc-game-fullscreen').evaluate('node=>({width:innerWidth,buttons:[...node.querySelectorAll(".rc-expanded-change,.rc-expansion-action")].map(n=>{const r=n.getBoundingClientRect();return {text:n.textContent,x:r.x,y:r.y,width:r.width,height:r.height,hit:n.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)),fits:n.scrollWidth<=n.clientWidth};})})')
        print(json.dumps({'expanded_controls':expanded}),flush=True)
        assert all(row['hit'] and row['fits'] and row['x']>=0 and row['x']+row['width']<=expanded['width'] for row in expanded['buttons']),expanded
        assert expanded['buttons'][0]['x']+expanded['buttons'][0]['width']<=expanded['buttons'][1]['x'],expanded
        h.screenshot(path=str(output/'replacement-expanded-action-phone.png'))
        h.get_by_role('button',name='Change game',exact=True).focus();h.keyboard.press('Enter');h.get_by_role('button',name='Cancel',exact=True).focus();h.keyboard.press('Enter')
        h.get_by_role('button',name='Expand game to full screen',exact=True).focus();h.keyboard.press('Enter');h.get_by_role('button',name='Return to lobby view',exact=True).focus();h.keyboard.press('Enter')
        h.get_by_label('NES game screen',exact=True).focus();expect(h.get_by_label('NES game screen',exact=True)).to_be_focused()
        h.set_viewport_size({'width':390,'height':700})
        assert h.evaluate('proof.room.catalogId')=='super-tilt-bro-pal'
        h.evaluate('proof.rejectCandidatePrepare=true')
        h.get_by_role('button',name='Change game',exact=True).click();h.get_by_role('button',name='From Below',exact=True).click()
        h.wait_for_function('proof.native.some(x=>x.type==="peer-checkpoint-error")')
        for page in (h,g):page.wait_for_function('proof.room.game.status==="paused"&&!proof.room.game.load')
        prepare_fault=h.evaluate('proof.native.filter(x=>x.fault||x.type==="peer-checkpoint-error")')
        injected_prepare=next(row for row in prepare_fault if row.get('fault'))
        assert injected_prepare['originalHeader']!=injected_prepare['sentHeader']
        assert any(row['type']=='peer-checkpoint-error' and row['requestId']==injected_prepare['requestId'] and 'State belongs' in row['message'] for row in prepare_fault),prepare_fault
        assert h.evaluate('proof.room.catalogId')=='super-tilt-bro-pal'
        for page in (h,g):page.get_by_role('button',name='Prepare to resume',exact=True).click()
        h.get_by_role('button',name='Resume together',exact=True).click()
        h.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
        print(json.dumps({'actual_native_preparation_rejection':prepare_fault}),flush=True)
        h.get_by_role('button',name='Change game',exact=True).click();h.get_by_role('button',name='From Below',exact=True).click()
        h.wait_for_function('proof.room?.catalogId==="from-below-1.0"&&!proof.room.started',timeout=35000)
        for p in pages:p.wait_for_function('proof.room?.catalogId==="from-below-1.0"&&proof.room.matches',timeout=15000)
        assert h.evaluate('proof.room.slots.map(s=>({id:s.id,open:s.open,member:s.member?.id}))')==roster
        assert h.get_by_text('Saved progress loaded.',exact=True).count()==0
        h.screenshot(path=str(output/'replacement-one-controller-prepare.png'))
        h.get_by_role('button',name='Prepare',exact=True).click();h.get_by_role('button',name='Start →',exact=True).click();h.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
        g.wait_for_function('proof.frames.at(-1)?.epoch===proof.room.game.epoch&&proof.frames.at(-1).frame>=3')
        observer_frame=g.evaluate('proof.frames.at(-1).frame');held_frames=g.evaluate('proof.heldObserverFrames??0');g.evaluate('proof.holdObserverFrames=true')
        h.wait_for_function('frame=>proof.frames.at(-1)?.epoch===proof.room.game.epoch&&proof.frames.at(-1).frame>=frame+30',arg=observer_frame)
        g.wait_for_function('before=>proof.heldObserverFrames>before',arg=held_frames)
        native_boundary="()=>new Promise(resolve=>{const worker=currentWorker;const done=({data})=>{if(data.type==='state-hash'&&data.requestId===900009){worker.removeEventListener('message',done);resolve(data.info);}};worker.addEventListener('message',done);worker.postMessage({type:'state-hash',requestId:900009});})"
        observer_before=g.evaluate(native_boundary)
        assert observer_before['frame']!=h.evaluate('proof.frames.at(-1).frame'),observer_before
        print(json.dumps({'independent_observer_before':observer_before}),flush=True)
        g.evaluate('proof.rejectCandidateCommit=true')
        h.get_by_role('button',name='Change game',exact=True).click();h.get_by_role('button',name='Super Tilt Bro',exact=True).click()
        for p in (h,g):p.wait_for_function('proof.native.some(x=>x.type==="peer-checkpoint-error"&&x.message==="Checkpoint commit is stale")||proof.room.game.load?.phase==="rolling_back"',timeout=15000) if p==g else None
        for p in (h,g):p.wait_for_function('proof.room.game.status==="paused"&&!proof.room.game.load',timeout=15000)
        observer_after=g.evaluate(native_boundary)
        assert g.evaluate('proof.heldObserverFrames>0')
        g.evaluate('proof.holdObserverFrames=false')
        assert observer_after==observer_before,{'before':observer_before,'after':observer_after}
        boundaries=g.evaluate('proof.loadBoundaries')
        assert any(row['type']=='gameLoadBoundary' and row['frame']==observer_before['frame'] and row['hash']==observer_before['hash'] for row in boundaries),boundaries
        assert any(row['type']=='gameLoadRolledBack' and row['frame']==observer_before['frame'] and row['hash']==observer_before['hash'] for row in boundaries),boundaries
        print(json.dumps({'independent_observer_rollback':observer_after,'actual_boundary_receipts':boundaries}),flush=True)
        assert h.evaluate('proof.room.catalogId')=='from-below-1.0'
        assert h.evaluate('proof.room.slots[1].role')=='observer'
        native_fault=g.evaluate('proof.native.filter(x=>x.fault||x.type==="peer-checkpoint-error"||x.type==="peer-checkpoint-prepared")')
        injected=next(row for row in native_fault if row.get('fault'))
        assert any(row['type']=='peer-checkpoint-error' and row['requestId']==injected['requestId'] and row['message']=='Checkpoint commit is stale' for row in native_fault),native_fault
        print(json.dumps({'actual_native_commit_rejection_rollback':native_fault}),flush=True)
        assert h.get_by_role('button',name='Retry Load',exact=True).count()==0
        assert 'Game change failed. Progress kept.' in h.locator('.rc-status').inner_text()
        assert h.locator('.rc-status-copy').evaluate('node=>node.scrollWidth<=node.clientWidth&&node.scrollHeight<=node.clientHeight')
        h.screenshot(path=str(output/'replacement-rollback-prepare-resume.png'))
        h.get_by_role('button',name='Prepare to resume',exact=True).click();h.get_by_role('button',name='Resume together',exact=True).click()
        h.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
        g.wait_for_function('proof.frames.at(-1)?.epoch===proof.room.game.epoch')
        retry_frame=g.evaluate('proof.frames.at(-1).frame');held_frames=g.evaluate('proof.heldObserverFrames??0');g.evaluate('proof.holdObserverFrames=true')
        h.wait_for_function('frame=>proof.frames.at(-1)?.epoch===proof.room.game.epoch&&proof.frames.at(-1).frame>=frame+30',arg=retry_frame)
        g.wait_for_function('before=>proof.heldObserverFrames>before',arg=held_frames)
        observer_retry=g.evaluate(native_boundary)
        assert observer_retry['frame']!=h.evaluate('proof.frames.at(-1).frame'),observer_retry
        print(json.dumps({'independent_observer_retry':observer_retry}),flush=True)
        h.get_by_role('button',name='Change game',exact=True).click();h.get_by_role('button',name='Super Tilt Bro',exact=True).click()
        h.wait_for_function('proof.room?.catalogId==="super-tilt-bro-pal"&&!proof.room.started',timeout=35000)
        for p in pages:p.wait_for_function('proof.room?.catalogId==="super-tilt-bro-pal"&&proof.room.matches',timeout=15000)
        g.evaluate('proof.holdObserverFrames=false')
        for p in (h,g):p.get_by_role('button',name='Prepare',exact=True).click()
        h.get_by_role('button',name='Start →',exact=True).click()
        for p in (h,g):p.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
        assert h.evaluate('proof.room.slots[1].role')=='player2'
        h.get_by_label('NES game screen',exact=True).focus();h.keyboard.press('p');h.wait_for_function('proof.room.game.status==="paused"')
        import zipfile
        archive=output/'replacement.zip'
        with zipfile.ZipFile(archive,'w') as zipped:zipped.write(ROOT/'spikes/d02/fixture.local.nes','game.nes')
        h.get_by_role('button',name='Change game',exact=True).click();h.get_by_role('button',name='Add game file',exact=True).click();h.get_by_label('NES cartridge file').set_input_files(str(archive))
        for p in pages:p.wait_for_function('!proof.room?.catalogId&&proof.room.matches&&!proof.room.started',timeout=35000)
        for p in (h,g):p.get_by_role('button',name='Prepare',exact=True).click()
        h.get_by_role('button',name='Start →',exact=True).click()
        for p in (h,g):p.wait_for_function('proof.room.game.status==="playing"&&proof.frames.at(-1)?.epoch===proof.room.game.epoch')
        print('custom_cartridge_all_members_matched',flush=True)
        h.screenshot(path=str(output/'replacement-playing-phone.png'))
        assert h.evaluate('proof.room.slots.map(s=>({id:s.id,open:s.open,member:s.member?.id}))')==roster
        assert h.evaluate('proof.room.invite')==invite
        input_receipts=[]
        def completed_input(page,mask):
            epoch=page.evaluate('proof.room.game.epoch')
            page.wait_for_function('wanted=>proof.cartridgeInputs?.some(row=>row.epoch===wanted.epoch&&row.p1===wanted.mask[0]&&row.p2===wanted.mask[1])',arg={'epoch':epoch,'mask':mask})
            frame=page.evaluate('wanted=>proof.cartridgeInputs.find(row=>row.epoch===wanted.epoch&&row.p1===wanted.mask[0]&&row.p2===wanted.mask[1]).frame',{'epoch':epoch,'mask':mask})
            page.wait_for_function('wanted=>proof.frames.at(-1)?.epoch===wanted.epoch&&proof.frames.at(-1).frame>=wanted.frame',arg={'epoch':epoch,'frame':frame})
            return {'epoch':epoch,'input_frame':frame,'completed_frame':page.evaluate('proof.frames.at(-1).frame')}
        for page,key,mask,native_mask in ((h,'z',[128,0],[1,0]),(g,'c',[0,64],[0,2])):
            page.get_by_label('NES game screen',exact=True).focus();expect(page.get_by_label('NES game screen',exact=True)).to_be_focused()
            page.evaluate('proof.cartridgeInputs=[]');page.keyboard.down(key)
            receipt=completed_input(page,native_mask)
            page.evaluate("delete proof.controllerRam;proof.acceptedCartridgeWorker.postMessage({type:'state-export',requestId:900000})")
            page.wait_for_function('proof.controllerRam!==undefined');actual=page.evaluate('proof.controllerRam')
            receipt.update(key=key,native_mask=native_mask,expected_ram=mask,actual_ram=actual);print(json.dumps({'cartridge_native_input':receipt}),flush=True)
            assert actual==mask,receipt;input_receipts.append(receipt)
            page.evaluate('proof.cartridgeInputs=[]');page.keyboard.up(key);completed_input(page,[0,0])
        h.get_by_label('NES game screen',exact=True).focus();h.keyboard.press('q');h.get_by_text('Saved to quick slot 1.',exact=True).wait_for()
        epoch=h.evaluate('proof.room.game.epoch');h.keyboard.press('e')
        for page in (h,g):page.wait_for_function('epoch=>proof.room.game.status==="playing"&&proof.room.game.epoch!==epoch&&proof.frames.at(-1)?.epoch===proof.room.game.epoch',arg=epoch)
        h.get_by_label('NES game screen',exact=True).focus();epoch=h.evaluate('proof.room.game.epoch');h.keyboard.press('n');h.get_by_role('button',name='Restart cartridge',exact=True).click()
        for page in (h,g):page.wait_for_function('epoch=>proof.room.game.status==="playing"&&proof.room.game.epoch!==epoch&&proof.frames.at(-1)?.epoch===proof.room.game.epoch',arg=epoch)
        assert not page_errors,page_errors
        result={'result':'pass','seconds':round(time.monotonic()-start,3),'two_one_two_roles':True,'independent_observer_exact_rollback_retry':True,'minimum_width_keyboard_picker':expanded,'same_group_slots_invite':True,'native_prepare_rejection':True,'native_commit_rejection_rollback_retry':True,'phone_expanded_picker_cancel':True,'uploaded_candidate_all_members':True,'native_p1_p2_input':True,'same_cartridge_direct_load_restart':True,'input_receipts':input_receipts}
        (output/'cartridge-replacement.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'cartridge_replacement':result}),flush=True)
    except Exception:
        for index,page in enumerate(pages):
            print(json.dumps({'cartridge_failure_member':index,'state':page.evaluate("({status:document.querySelector('.rc-status')?.textContent,catalog:proof.room?.catalogId,matches:proof.room?.matches,game:proof.room?.game,native:proof.native,inputs:proof.cartridgeInputs,actualRam:proof.controllerRam,events:proof.events})")}),flush=True)
        raise
    finally:
        for context in contexts:context.close()


def browser_check(screenshot_dir=None, url="http://127.0.0.1:8765/"):
    """Exercise the public lobby journey in the built application."""
    from playwright.sync_api import sync_playwright, expect
    from rooms.ui_helpers import choose_panel, choose_audio

    def fits(page):
        result = page.evaluate("""() => {
          const names = ['.rc-shell', '.rc-stage', '.rc-footer', '.rc-main-page',
            '.rc-listing', '.rc-create', '.rc-session', '.rc-players',
            '.rc-game-zone', '.rc-chat'];
          const regions = Object.fromEntries(names.map(name => {
            const node = document.querySelector(name);
            if (!node || node.getClientRects().length === 0) return [name, true];
            return [name, node.scrollWidth <= node.clientWidth && node.scrollHeight <= node.clientHeight];
          }));
          const chat = document.querySelector('.rc-chat-history');
          return {document: document.documentElement.scrollWidth <= innerWidth &&
              document.documentElement.scrollHeight <= innerHeight,
              ...regions,
              chat: !chat || getComputedStyle(chat).overflowY === 'auto'};
        }""")
        assert all(result.values()), result

    sizes = ({"width": 1440, "height": 900}, {"width": 1024, "height": 600},
             {"width": 390, "height": 700}, {"width": 320, "height": 568})

    def responsive(page):
        for size in sizes:
            page.set_viewport_size(size)
            fits(page)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(ignore_default_args=["--mute-audio"])
        host_context = browser.new_context(viewport={"width": 1280, "height": 800})
        guest_context = browser.new_context(viewport={"width": 1024, "height": 600})
        host = host_context.new_page()
        host.add_init_script("""(() => {
          window.__startProof={hold:true,pending:null,replies:[],sent:[]};
          const send=WebSocket.prototype.send;
          WebSocket.prototype.send=function(payload){
            let command;try{command=JSON.parse(payload);}catch{}
            if(command?.type==='prepareHost'&&__startProof.hold){
              __startProof.pending={socket:this,command};
              this.addEventListener('message',event=>{let response;try{response=JSON.parse(event.data);}catch{}if(response?.requestId===command.requestId)__startProof.replies.push(response);});
              return;
            }
            return send.call(this,payload);
          };
          window.__releaseStart=reject=>{
            const {socket,command}=__startProof.pending;
            const sent={...command,...(reject?{membership:command.membership+'_stale'}:{})};
            __startProof.sent.push({original:command,sent});__startProof.pending=null;__startProof.hold=false;
            send.call(socket,JSON.stringify(sent));
          };
          window.__terminatedWorkers = 0;
          const terminate = Worker.prototype.terminate;
          Worker.prototype.terminate = function() {
            window.__terminatedWorkers++;
            return terminate.call(this);
          };
        })()""")
        guest = guest_context.new_page()
        host.goto(url)
        responsive(host)
        host.get_by_role("button", name="Host a new game").click()
        responsive(host)
        host.get_by_role("button", name="Load NES game").wait_for(timeout=15000)
        assert host.get_by_role("button", name="Start →").count() == 0
        assert host.get_by_test_id("room-slot").count() == 5
        responsive(host)
        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            host.screenshot(path=str(screenshot_dir / "empty-lobby.png"))
        guest.goto(url)
        guest.locator('.rc-lobby-card').first.click()
        guest.get_by_text("Waiting for the host to load a NES game").wait_for(timeout=15000)
        guest.get_by_role("button",name="Edit your name:",exact=False).click()
        guest.get_by_label("Your name",exact=True).fill("P"*32)
        guest.get_by_role("button",name="Save name",exact=True).click()
        spectator=browser.new_page(viewport={"width":1024,"height":600})
        spectator.goto(url)
        spectator.locator('.rc-lobby-card').first.click()
        spectator.get_by_text("Waiting for the host to load a NES game").wait_for(timeout=15000)
        for sender, receiver, text in ((guest, host, "Ready when you are"),
                                       (host, guest, "Hosting and chatting")):
            choose_panel(sender, "Chat")
            choose_panel(receiver, "Chat")
            field = sender.get_by_label("Message everyone")
            field.press_sequentially(text)
            expect(field).to_have_value(text)
            field.press("Enter")
            expect(receiver.get_by_role("log", name="Lobby messages")).to_contain_text(text)
            expect(field).to_have_value("")
        assert host.get_by_role("button", name="Start →").count() == 0
        choose_panel(host, "Game")
        host.get_by_role("button", name="Load NES game").click()
        host.get_by_role("button", name="Super Tilt Bro", exact=False).click()
        host.get_by_role("button", name="Prepare", exact=True).wait_for(timeout=30000)
        guest.get_by_role("button", name="Prepare", exact=True).wait_for(timeout=30000)
        for page in (host, guest):
            choose_audio(page, "Game sound")
            page.get_by_role("button", name="Mute game", exact=True).click()
        choose_panel(host, "Game")
        choose_panel(guest, "Game")
        primary_region=host.locator(".rc-prepare-action-region").bounding_box()
        prepare_box=host.get_by_role("button",name="Prepare",exact=True).bounding_box()
        host.get_by_role("button", name="Prepare", exact=True).click()
        expect(host.get_by_role("button", name="Start →")).to_be_disabled()
        expect(host.locator(".rc-prepare-cover")).to_contain_text("not ready")
        assert host.locator(".rc-primary-action-reason").evaluate("node=>{const r=node.getBoundingClientRect(),p=node.closest('.rc-prepare-feedback').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right&&r.top>=p.top&&r.bottom<=p.bottom&&node.scrollHeight<=node.clientHeight;}")
        assert host.locator(".rc-prepare-action-region").bounding_box()==primary_region
        start_box=host.get_by_role("button",name="Start →").bounding_box()
        for axis,length in [("x","width"),("y","height")]:
            assert abs((start_box[axis]+start_box[length]/2)-(prepare_box[axis]+prepare_box[length]/2))<1
        assert host.locator(".rc-footer").get_by_role("button",name="Start →").count()==0
        assert guest.get_by_role("button",name="Start →").count()==0
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "centered-start-waiting.png"))
        guest.get_by_role("button", name="Prepare", exact=True).click()
        expect(host.locator(".rc-prepare-cover").get_by_role("button",name="Start →")).to_be_enabled()
        assert host.locator(".rc-prepare-action-region").bounding_box()==primary_region
        assert spectator.get_by_role("button",name="Prepare",exact=True).count()==0
        assert spectator.get_by_role("button",name="Start →").count()==0
        for size in sizes:
            host.set_viewport_size(size)
            choose_panel(host, "Game")
            fits(host)
            assert host.get_by_role("button",name="Start →").count()==1
            assert host.locator(".rc-footer").get_by_role("button",name="Start →").count()==0
            assert host.locator(".rc-prepare-cover").get_by_role("button",name="Start →").evaluate("node => {const r=node.getBoundingClientRect(), p=node.closest('.rc-game-viewport').getBoundingClientRect();return r.left>=p.left&&r.right<=p.right&&r.top>=p.top&&r.bottom<=p.bottom;}")
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "centered-start-ready-phone.png"))
        start_button=host.get_by_role("button",name="Start →")
        roster=host.locator(".rc-players").inner_text()
        lobby_name=host.locator(".rc-lobby-heading").inner_text()
        start_button.focus();expect(start_button).to_be_focused();start_button.press("Enter")
        host.wait_for_function("__startProof.pending!==null")
        expect(start_button).to_be_disabled()
        pending={"header":host.locator('.rc-status-copy').inner_text(),"overlay":host.locator('.rc-primary-action-reason').inner_text()}
        if screenshot_dir:host.screenshot(path=str(screenshot_dir/"centered-start-pending.png"))
        host.evaluate("__releaseStart(true)")
        host.wait_for_function("__startProof.replies.some(reply=>reply.ok===false)")
        expect(start_button).to_be_enabled()
        assert host.locator("main").get_attribute("data-page")=="lobby"
        assert host.locator(".rc-players").inner_text()==roster
        assert host.locator(".rc-lobby-heading").inner_text()==lobby_name
        rejected={"header":host.locator('.rc-status-copy').inner_text(),"overlay":host.locator('.rc-prepare-cover').inner_text(),"reply":host.evaluate("__startProof.replies.at(-1)")}
        if screenshot_dir:host.screenshot(path=str(screenshot_dir/"centered-start-rejected.png"))
        host.evaluate("__startProof.hold=true")
        start_button.focus();expect(start_button).to_be_focused();start_button.press("Enter")
        host.wait_for_function("__startProof.pending!==null")
        choose_panel(host,"Players")
        host.locator('[data-slot-id="slot-5"] .slot-row').click()
        host.get_by_role('menuitem',name='Close slot',exact=True).click()
        expect(host.locator('[data-slot-id="slot-5"] .slot-row')).to_contain_text('Closed')
        host.evaluate("__releaseStart(true)")
        host.wait_for_function("__startProof.replies.filter(reply=>reply.ok===false).length===2")
        choose_panel(host,"Game")
        context_state={"header":host.locator('.rc-status-copy').inner_text(),"host_prepare":host.get_by_role('button',name='Prepare',exact=True).count(),"guest_prepare":guest.get_by_role('button',name='Prepare',exact=True).count()}
        print(json.dumps({"start_context_after_rejection":context_state}),flush=True)
        expect(host.get_by_role('button',name='Prepare',exact=True)).to_be_enabled()
        host.get_by_role('button',name='Prepare',exact=True).click()
        expect(guest.get_by_role('button',name='Prepare',exact=True)).to_be_enabled()
        guest.get_by_role('button',name='Prepare',exact=True).click()
        expect(start_button).to_be_enabled()
        assert 'Could not start' not in host.locator('.rc-status-copy').inner_text()
        context_rejection={"revision_changed_through_public_slot_action":True,"fresh_preparation_required":True,"old_failure_not_shown_after_preparing":True}
        host.evaluate("__startProof.hold=true")
        start_button.focus();expect(start_button).to_be_focused();start_button.press("Enter")
        host.wait_for_function("__startProof.pending!==null")
        expect(start_button).to_be_disabled()
        host.evaluate("__releaseStart(false)")
        host.get_by_text("Game starts in", exact=False).wait_for(timeout=15000)
        host.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount) > 5", timeout=30000)
        guest.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount) > 5", timeout=30000)
        expect(host.get_by_label("NES game screen",exact=True)).to_be_focused()
        start_proof={"pending":pending,"rejected":rejected,"requests":host.evaluate("__startProof.sent.map(row=>({type:row.sent.type,requestId:row.sent.requestId,staleMembershipInjected:row.sent.membership!==row.original.membership}))"),"keyboard_retry_native_play":True,"canvas_focused":True,"same_lobby_roster_after_rejection":True,"context_rejection":context_rejection}
        print(json.dumps({"start_transition":start_proof}),flush=True)
        if screenshot_dir:(screenshot_dir/'start-transition.json').write_text(json.dumps(start_proof,indent=2)+'\n')
        assert pending['header']=='Starting lobby…' and pending['overlay']=='Starting lobby…',pending
        assert 'Could not start' in rejected['header'] and 'Retry' in rejected['header'],rejected
        choose_panel(host, "Chat")
        choose_panel(guest, "Chat")
        field = guest.get_by_label("Message everyone")
        field.press_sequentially("Chat while playing Z C A D P Q E")
        expect(field).to_have_value("Chat while playing Z C A D P Q E")
        field.press("Enter")
        expect(host.get_by_role("log", name="Lobby messages")).to_contain_text("Chat while playing Z C A D P Q E")
        expect(field).to_have_value("")
        for page, size in ((host, {"width": 390, "height": 700}), (guest, {"width": 320, "height": 568})):
            page.set_viewport_size(size)
            fits(page)
        choose_panel(host, "Game")
        if screenshot_dir:
            host.screenshot(path=str(screenshot_dir / "playing-mobile.png"))
        host.get_by_role("button", name="Back to Main Page").click()
        host.get_by_role("button", name="Close lobby").click()
        host.locator('.rc-listing').wait_for(timeout=15000)
        assert host.evaluate("window.__terminatedWorkers >= 1"), 'The emulator worker survived the lobby exit.'
        assert host.locator('canvas[aria-label="NES game screen"]').get_attribute('data-frame-count') == '0'
        assert host.locator('canvas[aria-label="NES game screen"]').evaluate("""canvas =>
          [...canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data]
            .every(value => value === 0)"""), 'The previous game frame survived the lobby exit.'
        fits(host)
        migration_output=screenshot_dir or ROOT / "spikes/d02/public-entrypoint.local/preferences"
        migration_output.mkdir(parents=True,exist_ok=True)
        migrated_default_preferences(browser,url,migration_output)
        cartridge_replacement(browser,url,migration_output)
        browser.close()
    return {"empty_lobby_before_game": True, "guest_chat_and_readiness": True, "incremental_chat_and_enter": True,
            "synchronized_start": True, "centered_start_same_region": True, "spectator_nonblocking": True, "mobile_shell": True, "exit_to_main": True,
            "game_worker_and_frame_cleared": True, "migrated_preferences_reload_and_play": True, "same_lobby_cartridge_replacement": True}

def occupied_port_check(environment):
    blockers = []
    for port in (8765, 8787):
        blocker = socket.socket()
        blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        blocker.bind(("127.0.0.1", port))
        blocker.listen()
        blockers.append(blocker)
    log_path = Path("/tmp/retro-coop-occupied-ports.log")
    service, log = start_launcher(environment, log_path)
    try:
        wait_ready(service, log_path, 8766)
        assert fetch("http://127.0.0.1:8788/health")[0] == 200
        assert "Open http://127.0.0.1:8766/" in log_path.read_text()
        stop_launcher(service, signal.SIGTERM, 8766, 8788)
    finally:
        log.close()
        if service.poll() is None:
            os.killpg(service.pid, signal.SIGKILL)
            service.wait()
        for blocker in blockers:
            blocker.close()
    return {"client": 8766, "coordinator": 8788}


def start_launcher(environment, log_path):
    log = log_path.open("w")
    service = subprocess.Popen(
        ["sh", "scripts/demo.sh"], cwd=ROOT, env=environment,
        stdout=log, stderr=subprocess.STDOUT, text=True, start_new_session=True,
    )
    return service, log


def wait_ready(service, log_path, client_port=8765):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if service.poll() is not None:
            raise AssertionError("Documented launcher exited early: " + log_path.read_text())
        try:
            if fetch(f"http://127.0.0.1:{client_port}/")[0] == 200 and f"Open http://127.0.0.1:{client_port}/" in log_path.read_text():
                return
        except OSError:
            time.sleep(.1)
    raise AssertionError("Documented application URL did not become ready: " + log_path.read_text())


def stop_launcher(service, signum, client_port=8765, coordinator_port=8787):
    service.send_signal(signum)
    try:
        return_code = service.wait(timeout=5)
    except subprocess.TimeoutExpired as error:
        os.killpg(service.pid, signal.SIGKILL)
        service.wait()
        raise AssertionError(f"launcher ignored signal {signum}") from error
    assert return_code in (-signum, 128 + signum), return_code
    wait_closed(client_port)
    wait_closed(coordinator_port)


def signal_lifecycle_check(environment):
    results = {}
    for name, signum in (("sigterm", signal.SIGTERM), ("ctrl_c", signal.SIGINT)):
        log_path = Path(f"/tmp/retro-coop-{name}.log")
        service, log = start_launcher(environment, log_path)
        try:
            wait_ready(service, log_path)
            stop_launcher(service, signum)
            results[name] = "ports released; immediate next launch allowed"
        finally:
            log.close()
            if service.poll() is None:
                os.killpg(service.pid, signal.SIGKILL)
                service.wait()
    return results


def runtime_check(with_browser=False, screenshot_dir=None):
    environment = dict(os.environ, RETRO_COOP_SKIP_INSTALL="1", RETRO_COOP_SKIP_PREPARE="1")
    fallback = occupied_port_check(environment)
    lifecycle = signal_lifecycle_check(environment)
    log_path = Path("/tmp/retro-coop-public-entrypoint.log")
    service, log = start_launcher(environment, log_path)
    result = None
    try:
        wait_ready(service, log_path)
        try:
            status, home = fetch("http://127.0.0.1:8765/")
            old_status, old_route = fetch("http://127.0.0.1:8765/demo/")
            coordinator_status, health = fetch("http://127.0.0.1:8787/health")
            catalog = {
                "super_tilt_bro": fetch("http://127.0.0.1:8765/catalog/super-tilt-bro-e-847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d.nes", "HEAD")[0],
                "from_below": fetch("http://127.0.0.1:8765/catalog/from-below-1.0-1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555.nes", "HEAD")[0],
            }
            assert old_status == coordinator_status == 200
            assert home == old_route
            assert catalog == {"super_tilt_bro": 200, "from_below": 200}
            assert json.loads(health)["status"] == "ok"
            subprocess.run([
                "node", "--input-type=module", "-e",
                "import{WebSocket}from'ws';const w=new WebSocket('ws://127.0.0.1:8787/ws',{headers:{origin:'http://127.0.0.1:8765'}});w.on('open',()=>{w.close();process.exit(0)});w.on('error',e=>{console.error(e.message);process.exit(1)});setTimeout(()=>process.exit(2),3000)",
            ], cwd=ROOT, check=True, timeout=5)
            assert status == 200
            result = {"result": "pass", "url": "http://127.0.0.1:8765/",
                      "legacy_url_serves_current_app": True, "coordinator": "websocket accepted",
                      "catalog": catalog, "occupied_ports_select_next_available": fallback,
                      "launcher_signals": lifecycle}
            if with_browser:
                result["browser"] = browser_check(screenshot_dir)
        finally:
            if service.poll() is None:
                stop_launcher(service, signal.SIGTERM)
    finally:
        log.close()
        if service.poll() is None:
            os.killpg(service.pid, signal.SIGKILL)
            service.wait()
    assert result is not None
    return result


def main():
    global ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--screenshot-dir", type=Path)
    args = parser.parse_args()
    ROOT = args.runtime_root.resolve()
    result = runtime_check(args.browser, args.screenshot_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
