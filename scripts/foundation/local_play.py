"""Enter unified local play and inspect the active browser worker for tests."""
import hashlib


CORE_PROBE = '''() => {
  window.localCoreProbe={records:[]};
  const NativeWorker=Worker;
  window.Worker=class extends NativeWorker {
    constructor(...args){
      super(...args);
      this.probeRecord={core:null,rom:null,ended:false,digest:Promise.resolve()};
      localCoreProbe.records.push(this.probeRecord);
      this.addEventListener('message',event=>{
        if(event.data?.type==='ready')this.probeRecord.core=event.data.coreSha256;
      });
    }
    postMessage(message,...args){
      if(message?.type==='load'&&message.rom instanceof ArrayBuffer){
        const bytes=new Uint8Array(message.rom).slice();
        this.probeRecord.digest=crypto.subtle.digest('SHA-256',bytes).then(value=>{
          this.probeRecord.rom=[...new Uint8Array(value)]
            .map(byte=>byte.toString(16).padStart(2,'0')).join('');
        });
      }
      return super.postMessage(message,...args);
    }
    terminate(){this.probeRecord.ended=true;return super.terminate();}
  };
  localCoreProbe.active=async()=>{
    await Promise.all(localCoreProbe.records.map(record=>record.digest));
    const record=localCoreProbe.records.filter(row=>!row.ended&&row.rom&&row.core).at(-1);
    return record?`${record.rom} ${record.core}`:null;
  };
}'''


def enter_create(page):
    """Start local play, with a test-only record of the active emulator core."""
    page.evaluate(CORE_PROBE)
    page.get_by_role('button', name='Play locally', exact=True).click()
    page.locator('[data-page="local"]').wait_for()


def read_fingerprint(page, expected=None):
    """Read ROM and core hashes from the live worker without showing them in UI."""
    if expected is not None:
        page.wait_for_function(
            'async expected=>(await localCoreProbe.active())?.includes(expected)',
            arg=expected)
    value = page.evaluate('localCoreProbe.active()')
    assert value, 'No loaded local emulator worker was found'
    return value


def start_solo(page, rom, *, require_start=False):
    """Wait for a selected cartridge and explicitly resume its local timeline."""
    expected = hashlib.sha256(rom).hexdigest()
    assert expected in read_fingerprint(page, expected)
    start = page.get_by_role('button', name='Resume', exact=True)
    start.wait_for()
    page.wait_for_function("Number(document.querySelector('canvas')?.dataset.frameCount)===0")
    if require_start:
        frames = page.locator('canvas')
        assert frames.get_attribute('data-frame-count') == '0', 'Game advanced before Resume'
        page.wait_for_timeout(200)
        assert frames.get_attribute('data-frame-count') == '0', 'Loaded game advanced before Resume'
    start.click()
    page.wait_for_function("Number(document.querySelector('canvas').dataset.frameCount)>5")
