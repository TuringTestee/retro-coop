// Trusted local ROM and explicit frame inputs. Only output buffers leave this worker.
let e;
onmessage = async ({ data: d }) => {
  try {
    if (d.kind === "init") {
      const start = performance.now();
      const decode = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
      const module = await WebAssembly.compile(decode(d.wasm64));
      const compiled = performance.now();
      const imports = {};
      for (const x of WebAssembly.Module.imports(module)) {
        if (x.kind !== "function") throw Error("Unexpected import kind");
        (imports[x.module] ??= {})[x.name] = () => {
          throw Error("Forbidden host call");
        };
      }
      e = (await WebAssembly.instantiate(module, imports)).exports;
      const rom = decode(d.rom64),
        ptr = e.input_alloc(rom.length);
      new Uint8Array(e.memory.buffer, ptr, rom.length).set(rom);
      e.initialize(ptr, rom.length);
      postMessage({
        kind: "ready",
        compileMs: compiled - start,
        initializeMs: performance.now() - compiled,
      });
    } else if (d.kind === "step") {
      const start = performance.now();
      e.advance_inputs(d.one, d.two);
      const emulated = performance.now();
      const copy = (kind) => {
        const ptr = e.output(kind);
        return new Uint8Array(e.memory.buffer, ptr, e.output_len()).slice()
          .buffer;
      };
      const audio = copy(2),
        video = copy(5);
      const copied = performance.now();
      let canonical;
      if (d.hash) {
        canonical = Array.from(
          new Uint8Array(await crypto.subtle.digest("SHA-256", copy(4))),
          (x) => x.toString(16).padStart(2, "0"),
        ).join("");
      }
      postMessage(
        {
          kind: "frame",
          frame: d.frame,
          audio,
          video,
          canonical,
          emulateMs: emulated - start,
          copyMs: copied - emulated,
          sentAt: performance.timeOrigin + performance.now(),
        },
        [audio, video],
      );
    } else if (d.kind === "epoch") {
      e.save();
      e.restore();
      e.output(2);
      postMessage({ kind: "epoch", empty: e.output_len() === 0 });
    }
  } catch (error) {
    postMessage({ kind: "error", error: String(error) });
  }
};
