# Internal emulator support

The former D02 public demo was removed after the lobby application replaced it. Use the repository root [play instructions](../../../README.md#play) for the current product.

This directory retains only code with supported internal consumers:

- `runtime/input.js` and `runtime/audio.js` own shared browser input and bounded audio scheduling used by `apps/client`.
The retired canvas worker and its standalone featured-game probes are available in [Git history](https://github.com/TuringTestee/retro-coop/blob/fe5cf26dc52b258826a0491be5d099bf21a97074/spikes/d02/demo/worker.js).

These modules do not define a public page, route, or alternate player. D02 network and browser probes remain under `spikes/d02` and identify themselves as engineering qualification tools.
