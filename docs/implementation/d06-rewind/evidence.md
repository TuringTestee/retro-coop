Audience: Agent

# Local rewind evidence

The initial native and browser runs restore the expected frame after ten actual emulated seconds and keep measured history below 32 MiB. These diagnostic fixtures do not establish banked PRG-RAM or full cartridge qualification.

## Initial candidate, before versioned assets

The application/native implementation is commit `0578946`, integrated with voice main in `1952e767384efa974290cf4c045c0beb7e3c61aa`. Commit `f67d1dfc63d34ce7708d1f3c154c2bcacba0e068` adds the maximum-capacity test, the explicit browser budget assertion and implementation documentation; its full preflight passed. The browser run predates that assertion, but its raw measurements expose the same budget and actual capacity values. Later native test naming clarifies changed PRG-ROM banks versus unqualified PRG-RAM banks without changing test behavior.

- [Native regional replay](native-regions.txt): mapper 0/1/4 × NTSC/PAL/Dendy, actual cycles, exact canonical state/pixels and discarded-future replay.
- [Native wrap and endpoint](native-wrap.txt): u32 CPU-cycle wrap, invalid target invariance and checkpoint pixels without replay.
- [Maximum actual capacity](native-capacity.txt): 28,214,120 history bytes; 30,557,032 including accounted restore buffers, below 33,554,432 bytes.
- [Actual worker measurements](worker-before-assets.json): CPU-executed MMC1 changes, partial serial writes and RAM contents across three regions.
- [Full browser result](browser-before-assets.json) and [raw output](browser-before-assets.txt): 72.27 seconds; includes local rewind and existing foundation checks.
- [Committed-source preflight](preflight-before-assets.txt): passed in 26.36 seconds; this initial run is not the later final evidence-committed gate.

The inspected [confirmation](rewind-before-before-assets.png), [restored state](rewind-after-before-assets.png) and [mobile dialog](rewind-mobile-before-assets.png) show readable controls and no horizontal overflow. The game moves from frame 653 to 52 after confirmation and stays paused until Resume. Audio evidence observes finite, nonzero PCM after Resume while muting only application gain; it does not claim bit-exact filter history.

The guide [defines the measured allocation boundary and remaining D06 work](../d06-rewind.md). CI remains pending until the branch is published. No independent review verdict is claimed by this author evidence.

## Asset-integrated candidate

The [candidate metadata](candidate.json) pins source/base and the rebuilt WASM digest after merging PR #57. The [current full browser result](browser.json) and [raw output](browser.txt) passed in 72.54 seconds, including the explicit 32 MiB assertion. [Confirmation](rewind-before.png), [restored state](rewind-after.png) and [mobile](rewind-mobile.png) were inspected: controls and status are readable, confirmation is explicit, and the mobile dialog fits without overflow. The same 653→52 frame transition and separately observed resumed PCM passed. The static browser harness intentionally has no coordinator; its room connection failure is unrelated to local rewind.

The immutable [issue snapshot](issue-10.json) and [epic snapshot](epic-2.json) preserve the assigned scope and approval lineage. Native timing and capacity proof above remains applicable; only native test naming changed since those runs. Final full preflight output is linked after the evidence commit.

The first final preflight stopped at Rust formatting after the qualification test name was lengthened ([raw failure](preflight-format-failure.txt), 0.31 seconds). Shortening that test name repairs formatting without changing runtime or test behavior. The repeated complete gate below verifies the repaired candidate.

The complete [final preflight](preflight.txt) passed in **26.52 seconds** at `b9bfe33` with all implementation and browser evidence committed. The final evidence-only commit adds this output; `git diff origin/main...HEAD --check` also passes. No check was skipped or timeout budget increased. Presubmit CI and fresh independent review remain pending.
