Put one recognizable, usable NES controller beside the game flow, with current keyboard help when idle and reachable touch controls during play.

Audience: Human

# Mobile controller direction

**Owner-approved direction for [#216](https://github.com/TuringTestee/retro-coop/issues/216).** The phone composition and automatic expanded play entry are approved; the [governing plan PR #233](https://github.com/TuringTestee/retro-coop/pull/233) is independently accepted and merged. Audience: general PG-13 players. [References](mobile-controller-references.md) inform the arrangement and touch mechanics.

The subsequent owner request [#261](https://github.com/TuringTestee/retro-coop/issues/261) replaces Profile placement, separate game/settings sections and live binding feedback through the [gameplay controls revision](gameplay-controls.md). The earlier phone approval below records the original decision; the one-panel layout and automatic expanded play remain current.

## Owner-requested behavior

- Restore the Famicom shape: direction pad left, Select/Start center, B/A right. Actual mouse/touch input uses the full controls, including large square A/B hit areas and simultaneous holds.
- Current-key help appears after five seconds without action; accepted keyboard input highlights the actual controller. Controls shows all mappings together, and each mapped key opens the centered capture dialog with Save/Cancel. This replaces the inline controller editor.
- Portrait touch controls sit low in reserved black space; landscape expanded-play controls overlay the lower corners translucently. A large draggable thumb dot produces one or two direction keys. Keep targets reachable by two thumbs and respect safe areas.
- Preserve the requested canvas-click expansion and return gesture. The top-right Full screen/Return to lobby view control requested in #216 activates that same presentation state. Touching controller targets must never toggle fullscreen. Fade decoration at idle, retaining an identifiable, focusable target; pointer proximity/focus restores contrast.

## Existing behavior to preserve

One shared lobby shell; five physical slots and current controller authority; existing Ready/Start gate, late join and role transitions; chat and settings in lobby view; exact configured keyboard/gamepad bindings, rapid A/D, emulator pause versus NES Start, coordinated host quick load, game audio/voice behavior. The controller sends only for a synchronized active controller owner. Spectators see a disabled controller with their current role.

Replace the static guide and inline/paginated editors with one complete Controls inventory and capture dialog; reuse `Settings`, `controls.ts`, preferences and `LocalPlayer`. Retain gamepad and push-to-talk configuration. No new settings page, account or input protocol.

## Historical phone approval

The owner approved the concrete local demo with one reserved phone panel with Game, Players, Settings and Chat tabs. The lobby and your full names move to Settings → Profile, with existing centered edit dialogs. All five slots, moderation, chat, settings and their recovery actions remain in the same session. Desktop retains its full header, Players | Game | Settings and full-width chat below.

On 2026-10-04 the owner approved one phone section at a time and the demonstrated Settings → Profile placement for full names/editing. This supersedes the earlier all-regions-visible phone requirement. Desktop centers the lobby-name and your-name controls side by side in the top header row. Phones keep complete names/editing in Settings → Profile, as confirmed by the owner. ROM titles retain their fixed window. Only overflowing titles move continuously in one direction and loop seamlessly; the complete title remains accessible, hover/focus pauses it, and reduced motion restores readable wrapping. Identity names do not animate. Ordinary desktop labels and values share one line; maximum accepted text may wrap within its reserved control, without clipping or moving unrelated regions.

## Current phone behavior

The earlier Profile placement above is historical. Current names use reserved header values and centered edit dialogs; Settings contains Controls and Audio as specified in [gameplay controls](gameplay-controls.md).

Keep Game as the initial phone panel. The owner selected automatic expanded game view when play starts on a phone. Enter expansion only when the local game is usable; synchronized late join uses the same entry. Do not repeat expansion after Return, pause/resume, reconnect, rotation or snapshot updates within that play session. Desktop expansion remains manual. The already requested canvas-click toggle and top-right Full screen control open the same expanded play presentation with large thumb controls; Return restores the selected lobby panel without ending play. Touching a controller target never toggles presentation. Do not introduce another fullscreen gesture.

The maximum-content demo fits 320×568 portrait and 568×320 landscape without document scrolling or clipped accepted names. It is a layout proposal, not an implemented controller, native gameplay proof or physical-device qualification. The proposed portrait expanded view reserves a 152px controller band and 44px top controls, leaving room for a 320×300 NES image. Landscape uses lower translucent controls. Safe areas reduce the game first; native fullscreen rejection retains in-window expansion.

Physical thumb comfort, device safe areas, assistive input, keyboard editing and actual combined input remain implementation proof obligations. Approval of the composition cannot waive them.
