# Internal emulator support

The former D02 public demo was removed after the lobby application replaced it. Use the repository root [play instructions](../../../README.md#play) for the current product.

This directory retains only code with supported internal consumers:

- `runtime/input.js` and `runtime/audio.js` own shared browser input and bounded audio scheduling used by `apps/client`.
- `worker.js` runs exact-artifact qualification from `scripts/featured/qualify.py` and `qualify_super_tilt.py`.

These modules do not define a public page, route, or alternate player. D02 network and browser probes remain under `spikes/d02` and identify themselves as engineering qualification tools.
