Put one recognizable, usable NES controller beside the game flow, with current keyboard help when idle and reachable touch controls during play.

Audience: Human

# Mobile controller direction

**Owner-approved direction for [#216](https://github.com/TuringTestee/retro-coop/issues/216).** The phone composition and automatic expanded play entry are approved; the [governing plan PR #233](https://github.com/TuringTestee/retro-coop/pull/233) is independently accepted and merged. Audience: general PG-13 players. [References](mobile-controller-references.md) inform the arrangement and touch mechanics.

The subsequent owner request [#261](https://github.com/TuringTestee/retro-coop/issues/261) replaces Profile placement, separate game/settings sections and live binding feedback through the [gameplay controls revision](gameplay-controls.md). The earlier phone approval below records the original decision; the one-panel layout and automatic expanded play remain current.

## Owner-requested behavior

- Restore the Famicom shape: direction pad left, Select/Start center, B/A right. Actual mouse/touch input uses the full controls, including large square A/B hit areas and simultaneous holds.
- Current-key help appears after five seconds without action; accepted keyboard input highlights the actual controller. Controls shows all mappings together, and each mapped key opens the centered capture dialog with Save/Cancel. This replaces the inline controller editor.
- Phone touch controls use the bottom band specified below; portrait reserves black space and landscape expanded play may use a translucent overlay. A large draggable thumb dot produces one or two direction keys. Keep targets reachable by two thumbs and respect safe areas.
- Preserve the requested canvas-click expansion and return gesture. The top-right Full screen/Return to lobby view control requested in #216 activates that same presentation state. Touching controller targets must never toggle fullscreen. Fade decoration at idle, retaining an identifiable, focusable target; pointer proximity/focus restores contrast.

## Phone touch areas (#272)

The owner’s [#272 request](https://github.com/TuringTestee/retro-coop/issues/272) replaces the earlier fixed-size phone controller geometry. During phone play, keep the controller at the bottom, occupying between one quarter and one half of the usable viewport height. Adapt its height to the space available after browser chrome and safe areas; taller screens can use the smaller share, shorter screens the larger share. Preserve the game and the existing expansion/Return action without page scrolling.

Measure every fraction below against the **whole controller rectangle**, not the screen or the visible button artwork:

| Target | Interactive region | Share of controller area |
|---|---|---|
| Direction pad | Entire left third, full height | 1/3 |
| B and A | Right third, full height, split equally with B left and A right | 1/6 each |
| Select and Start | Center third, lower half, split equally with Select left and Start right | 1/12 each |

The center upper half has no gameplay target. Keep the recognizable NES cross, centered Select/Start pills and circular B/A artwork inside these larger regions. Artwork, labels and decorative gaps must not shrink the hit areas. Regions do not overlap; a touch belongs to exactly one region and cannot activate fullscreen. Keep simultaneous directions and action holds, independent releases and the existing draggable pad behavior. Desktop geometry and keyboard/gamepad behavior are unchanged.

## Existing behavior to preserve

One shared lobby shell; five physical slots and current controller authority; existing Ready/Start gate, late join and role transitions; chat and settings in lobby view; exact configured keyboard/gamepad bindings, rapid A/D, emulator pause versus NES Start, coordinated host quick load, game audio/voice behavior. The controller sends only for a synchronized active controller owner. Spectators see a disabled controller with their current role.

Replace the static guide and inline/paginated editors with one complete Controls inventory and capture dialog; reuse `Settings`, `controls.ts`, preferences and `LocalPlayer`. Retain gamepad and push-to-talk configuration. No new settings page, account or input protocol.

## Historical phone approval

The owner approved the concrete local demo with one reserved phone panel with Game, Players, Settings and Chat tabs. The lobby and your full names move to Settings → Profile, with existing centered edit dialogs. All five slots, moderation, chat, settings and their recovery actions remain in the same session. Desktop retains its full header, Players | Game | Settings and full-width chat below.

On 2026-10-04 the owner approved one phone section at a time and the demonstrated Settings → Profile placement for full names/editing. This supersedes the earlier all-regions-visible phone requirement. Desktop centers the lobby-name and your-name controls side by side in the top header row. Phones keep complete names/editing in Settings → Profile, as confirmed by the owner. ROM titles retain their fixed window. Only overflowing titles move continuously in one direction and loop seamlessly; the complete title remains accessible, hover/focus pauses it, and reduced motion restores readable wrapping. Identity names do not animate. Ordinary desktop labels and values share one line; maximum accepted text may wrap within its reserved control, without clipping or moving unrelated regions.

## Current phone behavior

The earlier Profile placement above is historical. Current names use reserved header values and centered edit dialogs; Settings contains Controls and Audio as specified in [gameplay controls](gameplay-controls.md).

Keep Game as the initial phone panel. The owner selected automatic expanded game view when play starts on a phone. Enter expansion only when the local game is usable; synchronized late join uses the same entry. Do not repeat expansion after Return, pause/resume, reconnect, rotation or snapshot updates within that play session. Desktop expansion remains manual. The already requested canvas-click toggle and top-right Full screen control open the same expanded play presentation with large thumb controls; Return restores the selected lobby panel without ending play. Touching a controller target never toggles presentation. Do not introduce another fullscreen gesture.

The maximum-content demo fits 320×568 portrait and 568×320 landscape without document scrolling or clipped accepted names. It is a layout proposal, not an implemented controller, native gameplay proof or physical-device qualification. The earlier demo’s 152px controller band and image dimensions are historical examples, superseded by the proportional touch areas above. Safe areas constrain the usable viewport; native fullscreen rejection retains in-window expansion.

Physical thumb comfort, device safe areas, assistive input, keyboard editing and actual combined input remain implementation proof obligations. Approval of the composition cannot waive them.
