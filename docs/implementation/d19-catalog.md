Audience: Agent

# D19 two-game catalog evidence

Retro Coop now opens on live public lobbies with direct actions for Super Tilt Bro, From Below, and any local NES file. Loading a game replaces discovery with the largest fitting game canvas and usable controls; All lobbies returns to discovery while the emulator keeps running.

## Candidate behavior

The ordered catalog manifest owns titles, immutable asset paths, exact sizes and hashes, cartridge identity, instructions, credits, and an honest unverified-license status. Its generic fetch path bounds bytes before hashing, rejects redirects and integrity errors, supports cancellation and retry, and checks current selection and room membership again before the emulator accepts the candidate. Arbitrary local files continue through structural iNES/NES 2.0 admission and do not consult the catalog.

Discovery uses a `100dvh` shell. It has no hero, slogan, About card, catalog tab, or pre-game runtime controls. Directory page size is deterministically selected from viewport height (2, 3, or 4 rows); filtering and live removal clamp the page, and page navigation moves focus to the first result. Single-page directories omit pagination. Playing uses the same LocalPlayer and RoomClient instances. Game help is available only after load and includes instructions, credits, and the supplied build's unverified-license status.

## Journey trace

| Journey | Connected observation |
|---|---|
| UJS-1 | Both ordered Play actions downloaded their pinned files and reached rendered frames without a picker. |
| UJS-2 | Six real public rooms produced two directory pages with game, host, occupancy, status, and Join; the host remains visible at 760 px, paging moved focus, and the directory used no nested scrolling. |
| UJS-3 | An arbitrary generated NES file loaded, rendered, and created a public room; its filename never appeared in the product or wire-facing evidence. Invalid bytes kept discovery and the picker visible with a specific error. |
| UJS-4 | The local post-load canvas measures 660×618 at 1280×800 and 563×528 at 760×680. Established shared play measures 972×911 at 1280×1050, or 65.9% of the viewport, while its closed room drawer measures 417/417 px with no hidden overflow. Pause, Saves, Rewind, Settings, Game help, and Fullscreen are absent before load. Room details use a deliberate header control; waiting-room invitation and Copy invite remain immediately visible inside a no-scroll drawer. All lobbies retained the same runtime and frames advanced from 32 to 50 before returning. |
| UJS-5 | Included download status stays beside launch actions; cancellation, network, size, truncation, excess, and hash failures are tested. Invalid local input preserves a direct retry. |
| UJS-6 | Wide 1280×800, narrow 760×680, 800×600 constrained, large-text, play, pause, error, help, room drawer, and invitation measurements all equal the viewport with no document overflow. Room and invitation panels have no nested overflow. Keyboard paging restores useful row focus. |

## Exact artifacts

| Game | Bytes | SHA-256 |
|---|---:|---|
| Super Tilt Bro supplied PAL build | 524,304 | `847155bb712e474f71554174c9d9ed402bf651b13ff1e4afc9a42ec69cd03d8d` |
| From Below 1.0 | 40,976 | `1a3ac4faf4b35640505344059ae5d91dae07cd47e1fb4d9d2a33c76391f1c555` |

[Packaged artifact output](d19-catalog/packaged-assets.txt) records the configured build. [Configured](d19-catalog/build-configured.txt) and [unconfigured](d19-catalog/build-unconfigured.txt) build logs show that both exact assets ship only when configured.

## Browser evidence

The real built client ran against the real local coordinator in Chrome 145. [Machine-readable measurements](d19-catalog/browser/browser.json) cover both included launches, nonblack From Below output and an input-following pixel change, arbitrary hosting, invalid-file recovery, six-room pagination, focus, progressive disclosure, All lobbies retention, large text, and no-scroll states. Inspectable captures: [wide discovery](d19-catalog/browser/wide-discovery.png), [narrow discovery](d19-catalog/browser/narrow-discovery.png), [multi-page directory](d19-catalog/browser/multi-page-lobbies.png), [Super Tilt play](d19-catalog/browser/super-playing.png), [From Below play](d19-catalog/browser/from-below-playing.png), [wide room drawer](d19-catalog/browser/room-session.png), [narrow room drawer](d19-catalog/browser/narrow-room-session.png), [narrow invitation](d19-catalog/browser/narrow-invitation.png), and [Game help](d19-catalog/browser/game-help.png).

The controller/settings work from merged PR #64 is integrated without restoring the old split-column shared layout. [Established Chrome–Chrome results](d19-catalog/browser/shared-session.json) assert a 972×911 canvas, exact document bounds, a no-overflow room drawer, synchronized frames/hashes, input isolation, pause/resume, and the existing workload budget. The responsive gate requires each canvas to occupy at least 40% of viewport width, 75% of viewport height, and 30% of viewport area; this preserves the approved game-dominant hierarchy without assuming one runner's pixel dimensions. [Firefox–Firefox](d19-catalog/browser/shared-firefox-firefox.json) and [Chrome–Firefox](d19-catalog/browser/shared-chrome-firefox.json) passed the same gate, gameplay, and timing checks on the current merged base. [Established shared-play capture](d19-catalog/browser/shared-session.shared-playing.png) shows the game-first layout and truthful `Close details` control. [Controller handoff results](d19-catalog/browser/controller-handoff.json) and [host](d19-catalog/browser/controller-handoff.after.png) / [guest](d19-catalog/browser/controller-handoff.guest.png) captures cover separate and shared ownership, decline/cancel, two-player consent, held-input suppression, native controller RAM, and drawer/document no-overflow assertions. Connection/session, controller, room chat, voice, and guest settings use one-at-a-time disclosures so the game stays dominant and controls remain reachable.

The exact Super Tilt artifact also ran through the actual browser worker. [Qualification results](d19-catalog/super-tilt/result.json) record boot/menu rendering, a Start-input timeline change, nonzero PCM peak `0.1657758355140686`, and deterministic canonical save/restore replay. [Boot](d19-catalog/super-tilt/boot-menu.png) and [after Start](d19-catalog/super-tilt/after-start.png) are the inspected frames.

Reproduce with:

```sh
npm run build:staging
python3 scripts/featured/catalog_browser.py --output docs/implementation/d19-catalog/browser
python3 scripts/gameplay/browser_smoke.py --pair Chrome-Chrome --seconds 8 --screenshots --output docs/implementation/d19-catalog/browser/shared-session.json
python3 scripts/gameplay/browser_smoke.py --pair Firefox-Firefox --seconds 8 --output docs/implementation/d19-catalog/browser/shared-firefox-firefox.json
python3 scripts/gameplay/browser_smoke.py --pair Chrome-Firefox --seconds 8 --output docs/implementation/d19-catalog/browser/shared-chrome-firefox.json
python3 scripts/gameplay/browser_smoke.py --pair Chrome-Chrome --controllers --seconds 8 --output docs/implementation/d19-catalog/browser/controller-handoff.json
python3 scripts/featured/qualify_super_tilt.py --rom /path/to/exact/Super_Tilt_Bro_\(E\).nes --wasm apps/client/src/generated/retro_coop_d02.wasm --output docs/implementation/d19-catalog/super-tilt
timeout 60s sh scripts/preflight.sh
```

## Honest limits

The browser journey is local same-origin desktop Chrome, not the public Internet route. Super Tilt evidence inspects browser-generated PCM rather than an audible device and does not use a physical controller. Start changed the native input timeline; directional P1/P2 samples at the later sampled menu state did not change pixels. The two-browser shared proof uses the diagnostic ROM rather than either catalog game. Physical-controller play, exhaustive mechanics, exact release-version provenance, Firefox/Safari, assistive-technology sessions, and final D20/D21 qualification remain with their owning issues.
