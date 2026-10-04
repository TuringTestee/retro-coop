Put one recognizable, usable NES controller beside the game flow, with keyboard help before play and reachable touch controls during play.

Audience: Human

# Mobile controller direction

**Proposal for [#216](https://github.com/TuringTestee/retro-coop/issues/216); not approved for implementation.** Audience: general PG-13 players. [References](mobile-controller-references.md) inform the arrangement and touch mechanics.

## Owner-requested behavior

- Restore the Famicom shape: direction pad left, Select/Start center, B/A right. Actual mouse/touch input uses the full controls, including large square A/B hit areas and simultaneous holds.
- Desktop preparation shows current configured keyboard keys connected to their buttons, with one inline Edit → Save/Cancel path. Default live play hides mappings while retaining the controller. Selecting Controls deliberately reveals the same editor during play; it does not create another editor.
- Portrait touch controls sit low in reserved black space; landscape expanded-play controls overlay the lower corners translucently. A large draggable thumb dot produces one or two direction keys. Keep targets reachable by two thumbs and respect safe areas.
- Preserve the requested canvas-click expansion and return gesture. The top-right Full screen/Return to lobby view control requested in #216 activates that same presentation state. Touching controller targets must never toggle fullscreen. Fade decoration at idle, retaining an identifiable, focusable target; pointer proximity/focus restores contrast.

## Existing behavior to preserve

One shared lobby shell; five physical slots and current controller authority; existing Ready/Start gate, late join and role transitions; chat and settings in lobby view; exact configured keyboard/gamepad bindings, rapid A/D, emulator pause versus NES Start, local-only quick load, game audio/voice behavior. The controller sends only for a synchronized active controller owner. Spectators see a disabled controller with their current role.

`PlayingTools` already supplies the static guide in started Game settings. Replace that display and the duplicated NES keyboard rows with one controller/editor; reuse `Settings`, `controls.ts`, preferences and `LocalPlayer`. Retain gamepad and push-to-talk configuration. No new settings page, account or input protocol.

## Required owner choices

The inspected 320×568 five-member/CJK layout has only 96px for game/settings after its 224px player rail. A 96px direction pad, two 64px A/B targets and two 44px Select/Start targets need 312px in one row before spacing, and another 100–140px vertically. Full slots, chat, settings and these targets cannot coexist at usable sizes. Do not clip them, hide names, shrink fonts or add scrolling to claim a fit.

**Recommend:** after play begins on a touch layout, use the existing expanded game presentation automatically; keep one Return to lobby view action. Portrait reserves a 152px bottom controller band and 44px top controls; a 320×300 NES image fits in the remaining 372px. Landscape uses a lower translucent overlay. Lobby view remains the same session with all five slots, chat, moderation and settings; returning must not end play.

**Alternative requiring explicit scope choice:** keep lobby view as the mobile default and use Full screen to reach the large thumb controls. This narrows “buttons always on screen” on the smallest screens until expanded play is entered. It is not silently equivalent to the request.

**Fullscreen interaction is already specified:** preserve canvas-click expansion and the requested top-right control, both calling the same presentation owner, with controller events excluded. Do not replace the requested gesture or ask the owner to approve it again.

No orientation lock or native-browser fullscreen guarantee is proposed. Existing expanded presentation can work when browser fullscreen is unavailable. Physical thumb comfort, device safe areas and assistive input remain implementation proof obligations.
