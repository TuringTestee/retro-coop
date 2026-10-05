#!/usr/bin/env python3
"""Build the unmodified pinned libretro core with the pinned Emscripten SDK."""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = '7a542dab1e87679921962a9f056186eca425c0c2'
SDK = '6.0.11'
EXPORTS = ['malloc', 'free', 'retro_init', 'retro_deinit', 'retro_load_game', 'retro_unload_game',
           'retro_run', 'retro_serialize_size', 'retro_serialize', 'retro_unserialize',
           'retro_set_environment', 'retro_set_video_refresh', 'retro_set_audio_sample',
           'retro_set_audio_sample_batch', 'retro_set_input_poll', 'retro_set_input_state',
           'retro_set_controller_port_device', 'retro_get_system_av_info']
COMMON = ['compat/compat_posix_string', 'compat/compat_snprintf', 'compat/compat_strcasestr',
          'compat/compat_strl', 'compat/fopen_utf8', 'encodings/encoding_utf', 'file/file_path',
          'file/file_path_io', 'streams/file_stream', 'streams/file_stream_transforms',
          'string/stdstring', 'time/rtime', 'vfs/vfs_implementation']


def run(*args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Clean checkout at the pinned revision')
    args = parser.parse_args()
    version = subprocess.check_output(['emcc', '--version'], text=True).splitlines()[0]
    if SDK not in version:
        parser.error(f'Activate Emscripten {SDK} before building')
    with tempfile.TemporaryDirectory(prefix='retro-fceumm-') as temporary:
        source = args.source or Path(temporary) / 'source'
        if args.source is None:
            run('git', 'init', str(source))
            run('git', 'fetch', '--depth', '1', 'https://github.com/libretro/libretro-fceumm.git', REVISION, cwd=source)
            run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=source)
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() != REVISION or \
                subprocess.check_output(['git', 'diff', 'HEAD', '--'], cwd=source):
            parser.error('FCEUmm must be the clean, unmodified pinned source')
        common_objects = 'RETROARCH_OBJECTS=' + ' '.join('src/drivers/libretro/libretro-common/' + name + '.o' for name in COMMON)
        run('make', '-f', 'Makefile.libretro', 'clean', 'platform=emscripten', common_objects, cwd=source)
        run('make', '-f', 'Makefile.libretro', '-j4', 'platform=emscripten',
            'CC=emcc', 'AR=emar', 'HAVE_HDPACK=0', 'HAVE_NTSC=0',
            common_objects, cwd=source)
        generated = ROOT / 'apps/client/src/generated'
        notices = ROOT / 'apps/client/public/generated'
        generated.mkdir(parents=True, exist_ok=True)
        notices.mkdir(parents=True, exist_ok=True)
        # Upstream's historical .bc target is an ar archive in current SDKs.
        archive = Path(temporary) / 'fceumm.a'
        shutil.copyfile(source / 'fceumm_libretro_emscripten.bc', archive)
        run('emcc', str(archive), '-O2', '-o', str(generated / 'fceumm.mjs'),
            '-sMODULARIZE=1', '-sEXPORT_ES6=1', '-sENVIRONMENT=worker', '-sALLOW_TABLE_GROWTH=1',
            '-sINITIAL_MEMORY=33554432', '-sMAXIMUM_MEMORY=67108864', '-sALLOW_MEMORY_GROWTH=1',
            '-sSTACK_SIZE=1048576', '-sFORCE_FILESYSTEM=1',
            '-sEXPORTED_FUNCTIONS=' + json.dumps(['_' + name for name in EXPORTS]),
            '-sEXPORTED_RUNTIME_METHODS=' + json.dumps(['addFunction', 'UTF8ToString', 'stringToUTF8', 'lengthBytesUTF8', 'FS', 'HEAPU8', 'HEAP16', 'HEAPU32', 'HEAPF64']),
            '-sINCOMING_MODULE_JS_API=' + json.dumps(['wasmBinary', 'print', 'printErr', 'onAbort']))
        shutil.copyfile(source / 'Copying', notices / 'fceumm-license.txt')
        (notices / 'fceumm-source.txt').write_text(
            f'FCEUmm {REVISION}, GPL-2.0-or-later.\n'
            f'Corresponding source: https://github.com/libretro/libretro-fceumm/tree/{REVISION}\n'
            f'Source archive: https://github.com/libretro/libretro-fceumm/archive/{REVISION}.tar.gz\n'
            f'Build: activate Emscripten {SDK}; python3 scripts/foundation/fceumm_build.py\n'
            'Application adapter and complete build recipe: https://github.com/TuringTestee/retro-coop\n'
            'No upstream source modifications. HD packs and NTSC presentation filters disabled.\n')


if __name__ == '__main__':
    main()
