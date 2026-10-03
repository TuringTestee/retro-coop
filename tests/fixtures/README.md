# Local game fixture

`battle-city-vs.nes` is the user-requested Battle City (Bootleg) (VS) file, copied unchanged for manual testing. It is not an included game, a default selection, or a CI input.

- Size: 49,168 bytes.
- SHA-256: `8b7106f7dc66ffbfde05aebf3a7b55afa3eeec569e63488fb8146e2fd7d2bde5`.
- Hardware: iNES mapper 99, VS System. The current core does not implement this mapper; this file cannot currently be played.

After building the client, inspect compatibility with the existing probe:

```sh
node scripts/foundation/probe_local_rom.mjs tests/fixtures/battle-city-vs.nes
```

The current result is `unsupported` with `unimplemented mapper 99` (exit 2). For a browser recovery check, create a lobby and upload this file: it should reject the game without closing the lobby. Then select an included game and start normally in the same lobby. Use the generated diagnostic for automated successful-play checks.
