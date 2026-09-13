// Developer-only experiment. No peer or ROM-upload endpoint.
async function run({rom64, wasm64}) {
                const bytes = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
                const module = await WebAssembly.compile(bytes(wasm64));
                const imports = WebAssembly.Module.imports(module);
                const blockedImports = {};
                for(const {module, name, kind} of imports) {
                    if(kind !== 'function') throw Error('Unsupported import type: '+kind);
                    (blockedImports[module] ??= {})[name] = () => { throw Error('Forbidden host call: '+name); };
                }
                const e = (await WebAssembly.instantiate(module, blockedImports)).exports;
                const rom = bytes(rom64), ptr = e.input_alloc(rom.length);
                new Uint8Array(e.memory.buffer, ptr, rom.length).set(rom);
                e.initialize(ptr, rom.length);
                const hash = async kind => {
                    const ptr = e.output(kind), len = e.output_len();
                    const data = new Uint8Array(e.memory.buffer, ptr, len).slice();
                    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', data)))
                        .map(x => x.toString(16).padStart(2, '0')).join('');
                };
                const hashes = [];
                const start = performance.now();
                for(let f = 0; f < 36000; f += 600) {
                    e.advance(f, 600);
                    postMessage({kind:"progress",frame:f+600});
                    hashes.push({frame:f + 600, state:await hash(0), canonical:await hash(4), video:await hash(1), audio:await hash(2)});
                }
                const tenMinuteReplayMs = performance.now() - start;
                const snapshotBytes = e.save();
                const restoreStart = performance.now();
                e.advance(36000, 600);
                const expected = [await hash(0), await hash(1), await hash(2), await hash(4)];
                e.restore();
                e.advance(36000, 600);
                const actual = [await hash(0), await hash(1), await hash(2), await hash(4)];
                e.advance(36600, 137);
                e.restore();
                const audioQueueEmpty = (()=>{ e.output(2); return e.output_len() === 0; })();
                e.advance(36000, 600);
                const alternateHistory = [await hash(0), await hash(1), await hash(2), await hash(4)];
                const lastAudioSamples = (()=>{e.output(2);return e.output_len()/4;})();
                const rewindStart = performance.now();
                const rewindPtr = e.rewind_probe(36600);
                const rewind = JSON.parse(new TextDecoder().decode(new Uint8Array(e.memory.buffer, rewindPtr, e.output_len())));
                rewind.probe_ms = performance.now() - rewindStart;
                rewind.wasm_linear_memory_bytes_after = e.memory.buffer.byteLength;
                return {hashes, rewind, checkpointBytes:snapshotBytes, audioQueueEmpty, lastAudioSamples,
                    newEpochEqual:actual.map((h,i)=>h===alternateHistory[i]),
                    tenMinuteReplayMs, replayAndRestoreMs:performance.now()-restoreStart,
                    restoreExpected:expected, restoreActual:actual,
                    restoreEqual:expected.map((h,i)=>h===actual[i])};

}
onmessage = async ({data}) => {
    try { postMessage({kind:"result",result:await run(data)}); }
    catch(error) { postMessage({kind:"result",result:{error:String(error),stack:error.stack}}); }
};
