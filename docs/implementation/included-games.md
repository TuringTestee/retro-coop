Audience: Agent

# Two-game catalog amendment

Implement one small catalog with Super Tilt Bro first and From Below second, reusing the current player, room and peer protocols. Keep arbitrary-file hosting independent of catalog membership. The exact supplied Super Tilt Bro artifact is identified below; runtime qualification is pending, not inferred from its header or source repository.

## Source and approval boundary

Human direction: [Included games and arbitrary NES files](../design/included-games.md), reflecting the user's explicit 2026-09-20 request. Baseline plan approval remains PR #3, reviewed `2e8adfcd3259f5bdffdc9a13ef9b983f78cfb965`, merged `ecf6bd4c7443526f0a163b721a351c854ee90fd4`; this is a bounded content/entry amendment. Independent review and the approved amendment revision must be recorded in the planning PR before executing changed catalog behavior. Unchanged D12/D15 work continues. The issue and Project board hold live assignments, not a second plan.

## Exact artifact inventory

| Order | Catalog entry | Bytes | SHA-256 | Inspected header |
|---|---|---:|---|---|
| 1 | Super Tilt Bro, supplied build; release version unverified | 524,304 | `847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d` | NES 2.0, mapper 2 / submapper 1, PAL; 512 KiB PRG, CHR RAM |
| 2 | From Below, supplied NES 1.0 | 40,976 | `1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555` | iNES, mapper 0 / submapper 0, NTSC |

Original files stay outside Git. Packaging may include verified distributable copies under the user's supplied-game authorization. No arbitrary URL, user ROM, modified header or newer upstream binary may silently replace either identity. The Super Tilt Bro filename also occurs in newer upstream builds with different cartridge hardware: the inspected supplied bytes, not the filename or current master, define this catalog entry. Creator context: [official game](https://super-tilt-bro.com/about.html), [upstream repository](https://github.com/sgadrat/super-tilt-bro). Neither link establishes that the supplied binary was rebuilt from current source.

[From Below's handoff](featured-from-below.md) owns its existing creator credits and scoped controller evidence. Super Tilt Bro's About initially credits its creator sgadrat and retains game-provided credits; verify additional contributors and exact menu wording against the supplied artifact before final presentation. Both display the requested license placeholder. Do not invent SPDX identifiers or replace dependency notices.

## Architecture and reuse

- One bounded, ordered catalog manifest owns IDs, exact byte identity, static asset paths, presentation metadata and license-placeholder status. Build packaging verifies both hashes/lengths and emits immutable versioned assets. Client availability reflects actual configured assets; arbitrary local-file admission does not read the catalog.
- Coordinator directory/invite views derive the known catalog ID from validated file metadata. Do not accept an independently writable catalog ID, identify games by editable host labels, publish arbitrary ROM hashes, or receive ROM bytes. Metadata classification is not proof against a malicious client lying about its file; honest peers still validate exact local bytes and compatibility before shared play.
- Generalize the existing D19 download owner to a selected entry. Keep one bounded fetch/identity/cancel pipeline, one LocalPlayer and existing RoomClient selection/replacement consent. Bind asynchronous completion through native candidate acceptance to the current selection and membership, not just the fetch response. Cache/reuse only exact in-tab identity and never reset a progressed host to simplify joining.
- Keep per-game Browse filtering in DirectoryPanel with existing public visibility, focus and stale-result guards. The first catalog entry supplies default prominence, not special networking or a second implementation path.
- D15 owns separate-controller mapping and shared-P1 consent. D12 owns progressed late join, D13 recovery, D14 shared timeline controls. The catalog does not duplicate these protocols. The application peer connection remains the internet multiplayer transport for both included and arbitrary local games.

## Delivery and acceptance ownership

D19/#23 retains its existing dependencies D03/#7, D09/#13 and D11/#15, which are integrated. Its amended outcome includes both ordered entries, artifact packaging, requested license placeholders, matching-file reuse and all download/room recovery paths. Before advertising Super Tilt Bro as playable, D19 must record an initial actual-worker/browser boot, menu/controller and short matched-peer check for its exact PAL build, including canonical save/restore suitability. Failures return to the core/adapter owner as bounded fixes rather than substituting a different binary. This initial content check is not D20's full qualification.

D20/#24 includes both exact artifacts in the existing local-play versus netplay/save/rewind matrix and preserves broad arbitrary-title/hardware investigation. D21/#25 includes both cold catalog journeys in action-count/startup and independent-network acceptance. No new dependency cycle, hidden external content approval, account system, ROM-sharing service, cartridge Wi-Fi integration or extra emulator is introduced. GKE is the user's separate D24 hosting selection; costs and actual deployment retain their existing gates.

Required evidence: order and zero-room UI; configured and unconfigured builds; Start/Join for each entry without a picker; no fetch on invite preview; exact matching in-tab reuse; wrong size/hash, network failure, timeout, cancel, membership replacement and manual-reselection races; public catalog filtering and host-label spoofing; actual arbitrary noncatalog ROM hosting without ROM upload; keyboard-accessible About/license placeholders; observed native P1/P2 behavior and matching canonical state for the exact Super Tilt Bro build. Retain meaningful current regression checks within the existing 60-second preflight and 30-minute presubmit limits. Final Internet, full browser/hardware and voice acceptance remains explicitly pending until its owning work completes.

## Review snapshot

This proposal changes catalog count/order and license-placeholder presentation, and records the user's repeated arbitrary-NES requirement. It does not change room privacy, peer transport, timing, state bounds, staffing, budget or the approved release acceptance gates. The planning PR records the independent scorecard, reviewed commit and actual user approval; silence is not approval of a reviewed version.
