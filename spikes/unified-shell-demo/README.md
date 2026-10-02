The [local demo launcher](current-production.html) shows the running React client and coordinator at `http://127.0.0.1:8765/`. Start the current checkout with:

```sh
RETRO_COOP_SKIP_INSTALL=1 RETRO_COOP_SKIP_PREPARE=1 sh scripts/demo.sh
```

The launcher is a simple iframe, so it always shows the current local code. Open the URL directly if the browser restricts local-file frames.

The current design is [wireframe v6](../../docs/design/unified-lobbies-wireframe-v6.md), with behavior in the [implementation plan](../../docs/implementation/unified-lobbies.md).
