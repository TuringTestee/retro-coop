"""Real-page transition geometry and Chromium browser-zoom evidence for #158.

Start a recorder before the action, mark observed UI states, and finish after the
outcome. Navigation/resize/zoom starts a new recorder. No helper changes scroll.
"""
import contextlib
import hashlib
import subprocess
import json
import tempfile
from pathlib import Path
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

REGIONS = '[data-layout-region], [data-testid="room-slot"], [data-slot-region]'

INSTALL = r"""({selector, label}) => {
  if (window.layoutProbe) window.layoutProbe.running = false;
  const ids = new WeakMap(); let serial = 0;
  const id = n => { if (!ids.has(n)) ids.set(n, ++serial); return ids.get(n); };
  const rect = n => { const r=n.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; };
  const name = n => n.dataset.layoutRegion || (n.dataset.slotRegion ?
    `${n.closest('[data-slot-id]').dataset.slotId}/${n.dataset.slotRegion}` : n.dataset.slotId) || n.id || n.className || n.tagName;
  const probe = window.layoutProbe = {label, running:true, samples:[], marks:[], intentionalScroll:false, limit:false};
  probe.sample = () => {
    const nodes = [...document.querySelectorAll(selector)].filter(n=>n.getClientRects().length);
    const regions=nodes.map(n=>{
      const ancestors=[]; let p=n.parentElement;
      while(p){ const s=getComputedStyle(p); ancestors.push({id:id(p),tag:p.tagName,name:p.dataset.layoutRegion||p.id||p.className,
        left:p.scrollLeft,top:p.scrollTop,width:p.clientWidth,height:p.clientHeight,
        scrollWidth:p.scrollWidth,scrollHeight:p.scrollHeight,overflowX:s.overflowX,overflowY:s.overflowY,bounds:rect(p)}); p=p.parentElement; }
      return {name:name(n),id:id(n),bounds:rect(n),ancestors};
    });
    probe.samples.push({time:performance.now(),state:probe.state||'armed',intentionalScroll:probe.intentionalScroll,
      viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scale:visualViewport.scale},
      document:{left:scrollX,top:scrollY,width:document.documentElement.scrollWidth},regions});
  };
  const tick=()=>{if(!probe.running)return;if(probe.samples.length>=10000){probe.limit=true;probe.running=false;return;}probe.sample();requestAnimationFrame(tick);};
  probe.sample(); requestAnimationFrame(tick);
}"""


class GeometryRecorder:
    def __init__(self, page, label, selector=REGIONS):
        self.page = page
        page.evaluate(INSTALL, {'selector': selector, 'label': label})

    def mark(self, state):
        self.page.evaluate("state=>{layoutProbe.state=state;layoutProbe.marks.push({state,time:performance.now()});layoutProbe.sample();}", state)

    def allow_user_scroll(self, enabled=True):
        """Bracket actual keyboard/wheel/click input, never asynchronous feedback."""
        self.page.evaluate('enabled=>{layoutProbe.sample();layoutProbe.intentionalScroll=enabled;}', enabled)

    def finish(self, output, required=()):
        self.page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        result = self.page.evaluate('()=>{layoutProbe.sample();layoutProbe.running=false;return {label:layoutProbe.label,samples:layoutProbe.samples,marks:layoutProbe.marks,limit:layoutProbe.limit};}')
        failures, baselines, previous = [], {}, {}
        max_drift = 0
        for sample in result['samples']:
            names = [r['name'] for r in sample['regions']]
            if len(names) != len(set(names)):
                failures.append('duplicate visible region names')
            if sample['document']['width'] > sample['viewport']['width'] + 1:
                failures.append('horizontal document overflow')
            current = {r['name']: r for r in sample['regions']}
            for name in baselines.keys() - current.keys():
                failures.append(f'{name}: stable region disappeared')
            for name, region in current.items():
                base = baselines.setdefault(name, region)
                ancestors = region['ancestors']
                before = previous.get(name, region)
                if region['id'] != base['id']:
                    failures.append(f'{name}: DOM identity changed')
                if [a['id'] for a in ancestors] != [a['id'] for a in base['ancestors']]:
                    failures.append(f'{name}: ancestor identity changed')
                if not sample['intentionalScroll'] and [(a['left'], a['top']) for a in ancestors] != [(a['left'], a['top']) for a in before['ancestors']]:
                    failures.append(f'{name}: scroll changed outside user-input interval')
                for axis in ('x', 'y', 'width', 'height'):
                    actual, expected = region['bounds'][axis], base['bounds'][axis]
                    if axis in ('x', 'y'):
                        scroll = 'left' if axis == 'x' else 'top'
                        actual += sum(a[scroll] for a in ancestors)
                        expected += sum(a[scroll] for a in base['ancestors'])
                    delta = abs(actual - expected)
                    max_drift = max(max_drift, delta)
                    if delta > 1:
                        failures.append(f'{name}.{axis}: {delta:.3f}px drift')
            previous = current
        if not baselines:
            failures.append('no stable owners recorded')
        for name in required:
            if name not in baselines:
                failures.append(f'missing required owner: {name}')
        if result['limit']:
            failures.append('recorder capacity exceeded')
        result.update(max_drift_css_px=max_drift, failures=sorted(set(failures)), regions=list(baselines))
        Path(output).write_text(json.dumps(result, indent=2) + '\n')
        assert not result['failures'], (result['label'], result['failures'])
        return {'label': result['label'], 'samples': len(result['samples']), 'max_drift_css_px': max_drift,
                'regions': list(baselines), 'evidence': str(output)}


def control_visibility(locator, require_focus=False):
    """Check full bounds + focused outline against every clipping ancestor."""
    result = locator.evaluate(r"""n=>{
      const b=n.getBoundingClientRect(),style=getComputedStyle(n),focused=n===document.activeElement;
      const outline=focused ? Math.max(0,parseFloat(style.outlineWidth)||0)+Math.max(0,parseFloat(style.outlineOffset)||0):0;
      let clip={left:0,top:0,right:innerWidth,bottom:innerHeight}; const ancestors=[];
      for(let p=n.parentElement;p;p=p.parentElement){if(p===document.body||p===document.documentElement)continue;
        const s=getComputedStyle(p),r=p.getBoundingClientRect();
        const x=/(auto|scroll|hidden|clip)/.test(s.overflowX),y=/(auto|scroll|hidden|clip)/.test(s.overflowY);
        if(x){clip.left=Math.max(clip.left,r.left+p.clientLeft);clip.right=Math.min(clip.right,r.left+p.clientLeft+p.clientWidth);}
        if(y){clip.top=Math.max(clip.top,r.top+p.clientTop);clip.bottom=Math.min(clip.bottom,r.top+p.clientTop+p.clientHeight);}
        ancestors.push({name:p.dataset.layoutRegion||p.id||p.className,x,y,scrollTop:p.scrollTop,scrollLeft:p.scrollLeft});
      }
      return {text:n.textContent,focused,outline,bounds:{left:b.left,top:b.top,right:b.right,bottom:b.bottom},clip,ancestors,
        visible:b.width>0&&b.height>0&&b.left-outline>=clip.left-1&&b.top-outline>=clip.top-1&&b.right+outline<=clip.right+1&&b.bottom+outline<=clip.bottom+1};
    }""")
    assert result['visible'], result
    assert not require_focus or result['focused'], result
    return result


@contextlib.contextmanager
def zoom_context(playwright, viewport):
    """Chromium extension API changes real browser zoom, including layout DPR."""
    with tempfile.TemporaryDirectory(prefix='layout-zoom-') as directory:
        root = Path(directory)
        ext = root / 'extension'
        ext.mkdir()
        (ext / 'manifest.json').write_text(json.dumps({'manifest_version': 3, 'name': 'Geometry zoom probe',
            'version': '1.0', 'permissions': ['tabs'], 'background': {'service_worker': 'worker.js'}}))
        (ext / 'worker.js').write_text('chrome.runtime.onInstalled.addListener(()=>{});')
        # Under parallel CI browser load, Chromium can start without installing
        # the extension. Restart that disposable profile instead of waiting for
        # an event the failed launch will never emit.
        for attempt in range(3):
            context = playwright.chromium.launch_persistent_context(str(root / f'profile-{attempt}'), channel='chromium',
                headless=True, viewport=viewport, args=[f'--disable-extensions-except={ext}', f'--load-extension={ext}'])
            try:
                worker = next((w for w in context.service_workers if w.url.startswith('chrome-extension://')), None)
                if worker is None:
                    worker = context.wait_for_event('serviceworker',
                        predicate=lambda w: w.url.startswith('chrome-extension://'), timeout=8000)
                break
            except PlaywrightTimeoutError:
                context.close()
                if attempt == 2:
                    raise RuntimeError('Chromium did not load the zoom probe extension after three launches') from None
        try:
            yield context, worker
        finally:
            context.close()


def browser_zoom(page, worker, factor=2):
    read = '({width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scale:visualViewport.scale,outerWidth,outerHeight})'
    before = page.evaluate(read)
    settings = worker.evaluate('''async ({url,factor})=>{
      const matches=(await chrome.tabs.query({})).filter(t=>t.url===url);
      if(matches.length!==1)throw Error('Zoom target must have a unique URL');
      const tab=matches[0];await chrome.tabs.setZoomSettings(tab.id,{mode:'automatic',scope:'per-tab'});
      await chrome.tabs.setZoom(tab.id,factor);
      return {tabId:tab.id,zoom:await chrome.tabs.getZoom(tab.id),settings:await chrome.tabs.getZoomSettings(tab.id)};
    }''', {'url': page.url, 'factor': factor})
    page.wait_for_function('width=>Math.abs(innerWidth-width)<=1', arg=page.viewport_size['width'] / factor)
    assert settings['zoom'] == factor, settings
    return {'backing_viewport': page.viewport_size, 'before': before, 'browser_api': settings, 'after': page.evaluate(read)}


def verify_zoom(worker, receipt):
    actual = worker.evaluate('id=>chrome.tabs.getZoom(id)', receipt['browser_api']['tabId'])
    assert actual == receipt['browser_api']['zoom'], actual
    return actual


def artifact_provenance(root, static):
    return {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
            'tracked_status': subprocess.check_output(['git', 'status', '--short', '--untracked-files=no'], cwd=root, text=True),
            'static_root': str(static),
            'artifacts': {str(path.relative_to(static)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted(Path(static).rglob('*')) if path.is_file() and path.suffix in ('.js', '.css', '.wasm')}}
