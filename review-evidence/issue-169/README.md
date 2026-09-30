This evidence shows the public and password-protected room journey, including recovery, on product revision `1e6e542620ca55a737ad48b2e0707029bfeac6e5`. Screenshots come from Chromium at 1280×800 for the directory and dialog, 390×800 for the joined mobile view, and 800×600 for download recovery. Test content is the generated diagnostic NES file.

## Visible states

- [Public rooms](public-rooms.png): public and locked rows before joining.
- [Password step](password-step.png): one plain-language access prompt.
- [Wrong password](wrong-password.png): denial with an actionable retry.
- [Joined mobile](joined-mobile.png): protected admission at 390×800.
- [Download failed](download-failed.png) and [download ready](download-ready.png): preparation recovery with stable slot rows at 800×600.

## Reproduction

From the repository root after `npm run build:staging`:

```sh
RETRO_COOP_ACCESS_OUTPUT=/tmp/access python3 scripts/rooms/access_browser.py
python3 scripts/rooms/integrated_transfer_browser.py --output /tmp/transfer
python3 scripts/rooms/layout_current_browser.py --output /tmp/layout
```

The access check holds each Join WebSocket request until the visitor closes the dialog with Back or Escape, then releases it and verifies that no membership appears. It also checks wrong passwords, directory and invite admission, password change, and public conversion. The transfer check covers download failure and retry, cache reuse, and reservation expiry.

## Fixed bounds

The recorder samples animation frames during room updates and actual browser zoom. Values are CSS pixels; zero means the measured region did not move or resize at a fixed viewport and zoom. The complete frame records are generated at `/tmp/layout`; the [compact machine-readable summary](geometry-summary.json) is committed here.

| Region | CSS viewport | Samples | Max drift | Failures |
|---|---:|---:|---:|---:|
| desktop-directory | 1280×800 | 34 | 0 | 0 |
| desktop-password | 1280×800 | 13 | 0 | 0 |
| desktop-slots | 1280×800 | 63 | 0 | 0 |
| desktop-zoom-200-directory | 640×400 | 6 | 0 | 0 |
| mobile-password | 390×700 | 13 | 0 | 0 |
| mobile-slots | 390×700 | 43 | 0 | 0 |
| mobile-zoom-200-directory | 390×700 | 6 | 0 | 0 |

The 200% zoom checks use actual browser zoom: 1280×800 backing viewport becomes 640×400 CSS pixels, and 780×1400 becomes 390×700 CSS pixels. The recovery browser also asserts the guest preparation region and first slot keep identical position and size through a failed download and successful retry.

## Five occupied slots

The [five-member browser result](five-slots.json) passed in 23.86 seconds at the same product revision. It used three browser processes, reached five occupied slots, checked shared state and recovery, and reported no page errors. The release gate separately exercises forced relay and the cross-browser matrix in CI.
