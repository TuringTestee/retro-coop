The five-member room, recovery controls, and exit path were exercised in the integrated browser on candidate `f6037fd`.

## Visible journey

| State | Evidence |
| --- | --- |
| Five occupants, each awaiting Ready | [Desktop](lobby-desktop.png), [mobile slots](lobby-mobile.png), [mobile actions](lobby-mobile-actions.png) |
| Everyone Ready; host can Start | [Ready lobby](everyone-ready.png) |
| Five-member play and later observer recovery | [Shared play](five-member-play.png), [observer recovery](observer-recovery.png) |
| Failed host close and failed member leave retain the session for retry | [Host retry](host-close-retry.png), [member retry](member-leave-retry.png) |
| Successful close returns to Public rooms | [Exited room](public-rooms-after-exit.png) |

## Reproduction

- `python3 scripts/gameplay/five_slots_smoke.py --output /tmp/retro-172-f603-five.json` passed in 28.42 seconds with five members, four connected peers per member, identical native game states after pause/recovery, and no page errors. The screenshots above come from that run's desktop and mobile viewports.
- `RETRO_EXIT_SCREENSHOT_DIR=/tmp/retro-172-f603-exit python3 scripts/rooms/exit_browser.py` passed. It observed failed host and member exits retaining the room, then verified successful exit stopped worker input, queued game audio, and microphone tracks before the directory appeared. A separate browser confirmed the hosted room disappeared.
- `sh scripts/demo.sh` launched the documented entry point. In Chromium, Copy invite supplied a visible link; four new browser contexts used Join room, all five occupants chose Ready, and the host started shared play.

The browser used Chromium 145.0.7632.6 on Linux. The game image is the repository's original diagnostic NES fixture; its grey canvas is expected in these state and layout captures.
