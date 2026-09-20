"""One-off diagnostic reproduction: python probe.py REPO OUTPUT [--prevent-enter].

The injected mode deliberately cancels Enter; it does not reproduce the unknown CI cause.
Only this diagnostic fixture shortens the chooser timeout. Production remains unchanged.
"""
from pathlib import Path
import sys

path = Path(sys.argv[1]).resolve() / 'scripts/foundation/browser_smoke.py'
output = sys.argv[2]
inject = '--prevent-enter' in sys.argv[3:]
sys.path.insert(0, str(path.parent))
sys.argv = [str(path), '--output', output]
source = path.read_text().split('        chooser.value.set_files')[0]
if inject:
    navigate = "        page.goto(f'http://127.0.0.1:{server.server_port}/')"
    source = source.replace(navigate, "        page.add_init_script(\"document.addEventListener('keydown',event=>{if(event.key==='Enter')event.preventDefault();});\")\n" + navigate)
    source = source.replace('page.expect_file_chooser()', 'page.expect_file_chooser(timeout=1000)')
exec(compile(source, str(path), 'exec'), {'__file__':str(path), '__name__':'__main__'})
