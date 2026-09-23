"""Keep a loaded client's emulator stable across a static release and rollback."""
import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


@contextlib.contextmanager
def room_test_server(root, site):
    service = subprocess.Popen(['node', 'scripts/rooms/browser-server.ts'], cwd=root,
                               env={**os.environ, 'RETRO_COOP_STATIC_ROOT': str(site)},
                               stdout=subprocess.PIPE, text=True)
    try:
        yield json.loads(service.stdout.readline())['url']
    finally:
        if service.poll() is None:
            service.terminate()
        service.wait(timeout=5)

parser = argparse.ArgumentParser()
parser.add_argument('--chrome', action='store_true')
parser.add_argument('--output', default='versioned-core.local.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
started = time.monotonic()
with tempfile.TemporaryDirectory(prefix='retro-versioned-core-') as directory:
    scratch = Path(directory)
    for folder in ['apps/client', 'packages/contracts', 'spikes/d02/demo/runtime']:
        shutil.copytree(root / folder, scratch / folder,
                        ignore=shutil.ignore_patterns('node_modules', 'dist'))
    (scratch / 'node_modules').symlink_to(root / 'node_modules', target_is_directory=True)
    source = scratch / 'apps/client/src/generated/retro_coop_d02.wasm'
    source.parent.mkdir(parents=True, exist_ok=True)
    built_cores = list((root / 'apps/client/dist/assets').glob('*.wasm'))
    assert len(built_cores) == 1, 'Build the versioned client first'
    original = built_cores[0].read_bytes()
    shutil.copytree(root / 'apps/client/dist/generated',
                    scratch / 'apps/client/public/generated', dirs_exist_ok=True)
    releases = []
    # A valid, inert WASM custom section changes build identity without changing emulation.
    for index, wasm in enumerate([original, original + b'\x00\x05\x04d24b']):
        source.write_bytes(wasm)
        output = scratch / f'release-{index}'
        subprocess.run(['node', str(root / 'node_modules/vite/bin/vite.js'),
                        'build', '--outDir', str(output)],
                       cwd=scratch / 'apps/client', check=True)
        assets = list((output / 'assets').glob('*.wasm'))
        assert len(assets) == 1
        assert assets[0].read_bytes() == wasm
        assert not (output / 'generated/retro_coop_d02.wasm').exists()
        releases.append((output, assets[0].name, hashlib.sha256(wasm).hexdigest()))
    assert releases[0][1] != releases[1][1], 'Different cores need different immutable URLs'
    site = scratch / 'site'
    shutil.copytree(releases[0][0], site)

    def publish(release):
        # Retain every previous hashed asset; never replace content at an existing URL.
        for path in (release / 'assets').iterdir():
            target = site / 'assets' / path.name
            if target.exists():
                assert target.read_bytes() == path.read_bytes()
            else:
                shutil.copyfile(path, target)
        shutil.copyfile(release / 'index.html', site / 'index.html')

    with room_test_server(root, site) as url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                **({'channel': 'chrome'} if args.chrome else {}),
                ignore_default_args=['--mute-audio'])
            old = browser.new_page()
            old.goto(url)
            rom = (site / 'generated/diagnostic.nes').read_bytes()

            def load(page, expected, *, existing=False):
                page.set_input_files('input[type=file]', {
                    'name': 'private-original.nes', 'mimeType': 'application/octet-stream',
                    'buffer': rom})
                if existing:
                    page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Game loaded. Preparing shared play')")
                    page.get_by_role('button', name='Resume', exact=True).click()
                else:
                    start = page.get_by_role('button', name='Start game', exact=True)
                    start.wait_for()
                    frames = page.get_by_test_id('frames')
                    assert frames.inner_text() == '0 frames', 'Waiting room advanced before Host Start'
                    page.wait_for_timeout(200)
                    assert frames.inner_text() == '0 frames', 'Waiting room advanced before Host Start'
                    start.click()
                page.wait_for_function("document.querySelector('[data-testid=player-status]').textContent.startsWith('Playing locally')")
                page.wait_for_function("Number(document.querySelector('[data-testid=frames]').textContent.split(' ')[0])>10")
                observed = page.get_by_test_id('fingerprint').text_content()
                assert expected in observed, {'expected_core': expected, 'fingerprint': observed}
                # The game is muted through its own setting, never a browser-wide flag.
                assert page.get_by_role('button', name='Unmute', exact=True).count() == 1
                page.get_by_role('button', name='Pause', exact=True).click()

            publish(releases[1][0])
            load(old, releases[0][2])
            current = browser.new_page()
            current.goto(url)
            load(current, releases[1][2])
            publish(releases[0][0])
            rollback = browser.new_page()
            rollback.goto(url)
            load(rollback, releases[0][2])
            load(current, releases[1][2], existing=True)
            browser.close()
    result = {
        'result': 'pass', 'source': 'two builds of the current checkout; second has inert custom section',
        'different_core_bytes_have_different_urls': True,
        'old_loaded_client_uses_original_core_after_publish': True,
        'new_client_uses_new_core': True,
        'rollback_restores_old_client_and_preserves_loaded_new_client': True,
        'core_sha256': [release[2] for release in releases],
        'seconds': round(time.monotonic() - started, 2),
    }
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
