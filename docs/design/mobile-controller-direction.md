Put one recognizable, usable NES controller beside the game flow, with keyboard help before play and reachable touch controls during play.

Audience: Human

# Mobile controller direction

**Owner-approved direction for [#216](https://github.com/TuringTestee/retro-coop/issues/216).** The phone composition and automatic expanded play entry are approved; implementation waits for independent review, passing checks and merge of the [governing plan PR #233](https://github.com/TuringTestee/retro-coop/pull/233). Audience: general PG-13 players. [References](mobile-controller-references.md) inform the arrangement and touch mechanics.

## Owner-requested behavior

- Restore the Famicom shape: direction pad left, Select/Start center, B/A right. Actual mouse/touch input uses the full controls, including large square A/B hit areas and simultaneous holds.
- Desktop preparation shows current configured keyboard keys connected to their buttons, with one inline Edit → Save/Cancel path. Default live play hides mappings while retaining the controller. Selecting Controls deliberately reveals the same editor during play; it does not create another editor.
- Portrait touch controls sit low in reserved black space; landscape expanded-play controls overlay the lower corners translucently. A large draggable thumb dot produces one or two direction keys. Keep targets reachable by two thumbs and respect safe areas.
- Preserve the requested canvas-click expansion and return gesture. The top-right Full screen/Return to lobby view control requested in #216 activates that same presentation state. Touching controller targets must never toggle fullscreen. Fade decoration at idle, retaining an identifiable, focusable target; pointer proximity/focus restores contrast.

## Existing behavior to preserve

One shared lobby shell; five physical slots and current controller authority; existing Ready/Start gate, late join and role transitions; chat and settings in lobby view; exact configured keyboard/gamepad bindings, rapid A/D, emulator pause versus NES Start, local-only quick load, game audio/voice behavior. The controller sends only for a synchronized active controller owner. Spectators see a disabled controller with their current role.

`PlayingTools` already supplies the static guide in started Game settings. Replace that display and the duplicated NES keyboard rows with one controller/editor; reuse `Settings`, `controls.ts`, preferences and `LocalPlayer`. Retain gamepad and push-to-talk configuration. No new settings page, account or input protocol.

## Approved phone layout

The owner approved the concrete local demo with one reserved phone panel with Game, Players, Settings and Chat tabs. The lobby and your full names move to Settings → Profile, with existing centered edit dialogs. All five slots, moderation, chat, settings and their recovery actions remain in the same session. Desktop retains its full header, Players | Game | Settings and full-width chat below.

On 2026-10-04 the owner approved one phone section at a time and the demonstrated Settings → Profile placement for full names/editing. This supersedes the earlier all-regions-visible phone requirement. Desktop centers the lobby-name and your-name controls side by side in the top header row. Phones keep complete names/editing in Settings → Profile, as confirmed by the owner. Ordinary desktop labels and values share one line; maximum accepted text may wrap within its reserved control, without clipping or moving unrelated regions.

Keep Game as the initial phone panel. The owner selected automatic expanded game view when play starts on a phone. Enter expansion only when the local game is usable; synchronized late join uses the same entry. Do not repeat expansion after Return, pause/resume, reconnect, rotation or snapshot updates within that play session. Desktop expansion remains manual. The already requested canvas-click toggle and top-right Full screen control open the same expanded play presentation with large thumb controls; Return restores the selected lobby panel without ending play. Touching a controller target never toggles presentation. Do not introduce another fullscreen gesture.

The maximum-content demo fits 320×568 portrait and 568×320 landscape without document scrolling or clipped accepted names. It is a layout proposal, not an implemented controller, native gameplay proof or physical-device qualification. The proposed portrait expanded view reserves a 152px controller band and 44px top controls, leaving room for a 320×300 NES image. Landscape uses lower translucent controls. Safe areas reduce the game first; native fullscreen rejection retains in-window expansion.

Physical thumb comfort, device safe areas, assistive input, keyboard editing and actual combined input remain implementation proof obligations. Approval of the composition cannot waive them.
