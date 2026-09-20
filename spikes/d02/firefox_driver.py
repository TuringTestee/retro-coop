"""Use the verified official Firefox build consistently in performance probes."""
import hashlib
import json
from pathlib import Path
from prepare_stock_firefox import VERSION, URL, ARCHIVE_SHA256, ARCHIVE_BYTES

DRIVER = 'official Firefox via WebDriver BiDi'


def validate_evidence(evidence, version):
    build = evidence.get('firefox_build', {})
    expected = {'version': VERSION, 'source': URL, 'archive_sha256': ARCHIVE_SHA256,
                'archive_bytes': ARCHIVE_BYTES}
    if evidence.get('firefox_driver') != DRIVER or version != VERSION or any(build.get(k) != v for k, v in expected.items()):
        raise ValueError('Firefox performance proof requires the pinned official build and BiDi driver')
    digest = evidence.get('firefox_executable_sha256')
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest) or digest != build.get('binary_sha256'):
        raise ValueError('Prepared Firefox binary identity differs')


def evidence(executable):
    binary = Path(executable).resolve()
    result = {'firefox_driver': DRIVER,
              'firefox_build': json.loads((binary.parents[1] / 'browser-build.json').read_text()),
              'firefox_executable_sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
    validate_evidence(result, result['firefox_build']['version'])
    return result


def launch_options(executable):
    # No compiler preferences: measure the installed product's default execution mode.
    evidence(executable)
    return {'channel': 'moz-firefox', 'executable_path': str(Path(executable).resolve()), 'headless': True}


def page_options():
    # Firefox 146 BiDi does not implement screen-size emulation.
    return {'no_viewport': True}
