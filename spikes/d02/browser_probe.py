"""Run trusted-local WASM replay; output hashes and timings, never ROM/state bytes."""
import argparse
import asyncio
import base64
import hashlib
import json
import platform
import time
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rom", type=Path)
    parser.add_argument("--wasm", type=Path, default=Path("target/wasm32-unknown-unknown/release/retro_coop_d02.wasm"))
    parser.add_argument("--output", type=Path, default=Path("results.local.json"))
    parser.add_argument("--bundled-chromium", action="store_true")
    parser.add_argument("--browser", choices=["all","Chrome","Firefox"], default="all")
    parser.add_argument("--url", default="http://127.0.0.1:8765/")
    args = parser.parse_args()
    rom, wasm = args.rom.read_bytes(), args.wasm.read_bytes()
    results = {"platform": platform.platform(), "rom_sha256": hashlib.sha256(rom).hexdigest(),
               "wasm_sha256": hashlib.sha256(wasm).hexdigest(), "runs": []}
    async with async_playwright() as p:
        for name, browser_type, options in [
            ("Chrome", p.chromium, {} if args.bundled_chromium else {"channel": "chrome"}),
            ("Firefox", p.firefox, {})]:
            if args.browser not in ("all",name): continue
            browser = await browser_type.launch(headless=True, **options)
            page = await browser.new_page()
            await page.goto(args.url)
            started = time.monotonic()
            result = await page.evaluate("""args => new Promise(resolve => {
                const worker = new Worker('/probe-worker.js');
                let lastFrame = 0;
                const timer = setTimeout(() => {
                    worker.terminate();
                    resolve({error:'900-second browser deadline',lastFrame});
                }, 900000);
                worker.onmessage = ({data}) => {
                    if(data.kind === 'progress') { lastFrame=data.frame; console.log('frame '+lastFrame); }
                    if(data.kind === 'result') {clearTimeout(timer);worker.terminate();resolve(data.result);}
                };
                worker.onerror = e => {clearTimeout(timer);worker.terminate();resolve({error:e.message,lastFrame});};
                worker.postMessage(args);
            })""", {"rom64": base64.b64encode(rom).decode(), "wasm64": base64.b64encode(wasm).decode()})
            results["runs"].append({"browser": "Chromium" if name=="Chrome" and args.bundled_chromium else name, "version": browser.version,
                                     "wall_seconds": time.monotonic() - started, **result})
            args.output.write_text(json.dumps(results, indent=2) + "\n")
            print(name, browser.version, {k: v for k, v in result.items() if k != "hashes"}, flush=True)
            await browser.close()
    if len(results["runs"]) == 2 and all("hashes" in r for r in results["runs"]):
        results["cross_browser_hashes_equal"] = results["runs"][0]["hashes"] == results["runs"][1]["hashes"]
    args.output.write_text(json.dumps(results, indent=2) + "\n")

asyncio.run(main())
