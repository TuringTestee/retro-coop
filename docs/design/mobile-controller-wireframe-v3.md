The revised sketch reserves usable thumb targets in expanded play; it does not pretend those targets fit the crowded mobile lobby.

Audience: Human

# Mobile controller wireframe v3 — current proposal

Revision: preserves the owner-requested canvas-click toggle and the top-right control from #216. Only the mobile entry policy remains undecided. Earlier v2 and its critique remain historical proposals.

Sources: [direction/owner choices](mobile-controller-direction.md), [references](mobile-controller-references.md), [journeys](mobile-controller-journeys.md), [scenarios](mobile-controller-scenarios.md), [current critique](mobile-controller-critique-v3.md). Planning only: no implemented layout, touch usability or input proof.

## Desktop preparation and inline editing / J1

Keep v1's players | NES preview | settings, fixed chat and footer. The controller sits in a reserved band below the game, inside its center column. Select/Start are centered; connected key lines surround their actual targets:

```text
 Arrow keys ── [ + ]   Alt ─ [Select][Start] ─ Space   [ B ] ─ C
                                                    [ A ] ─ Z
                                                        [Edit]
```

Edit → choose NES action in the same band → key capture with current/draft line → [Save][Cancel]. Conflict: “Z is used for A. Choose another.” Save stays blocked until valid. Keep the band position/size and configured colors in empty/loading/error states. Live play hides mapping lines and Edit by default, retaining buttons; selecting Controls reveals the same editor. Remove the old duplicated NES keyboard rows/static Game guide after this replacement is verified.

## Portrait expanded play,320×568 / J2–J4

```text
┌───────────────────────────[Return to lobby view]┐ 44px top region
│                                                │
│                 NES game                       │ 372px game region
│               320×300 maximum                  │ (black letterbox)
│                                                │
├────────── reserved black controller band ───────┤ 152px + safe-area
│                                           [ A ]│
│ [ 96px pad / 44px drag dot ] [Select][Start]    │
│                                   [ B ]        │
└────────────────────────────────────────────────┘
```

Concrete horizontal targets at 320px before safe-area accommodation: pad x 8..104 (96px); Select x 108..152 and Start x 156..200 (44px each); A x 240..304/y 8..72 and B x 208..272/y 80..144 within the controller band (64px square each). A/B are diagonally staggered and never overlap; Select/Start stay central rather than above them. Safe areas reduce the game area first; maintain target sizes, with full fit still requiring actual-device verification. This is fixed geometry within an explicit play presentation, not a viewport-specific test exception.

Full slots/chat/settings remain in the unchanged lobby view reached by the top-right action. The same session continues; host kick, role changes and chat are still reachable. Automatic versus manual entry is unresolved and must be chosen before implementation.

## Landscape expanded play,568×320 / J3

```text
┌ NES game ─────────────────────[Return to lobby view]┐
│                 main game region                  │
│                                                   │
│ [96px pad / dot]     [Select][Start]    [64px B][A] │
└────────── lower translucent band / safe area ──────┘
```

Reserve 44px fullscreen target at top-right and lower 104px target bounds from initial presentation. The NES aspect is preserved; translucent targets may cover lower corners as requested, not the central game. Idle opacity must not make the exit target undiscoverable; focus/proximity restores contrast and the first activation works. Orientation/presentation changes clear held input before relayout. Native fullscreen rejection does not prevent the existing expanded-window presentation.

## Watching, recovery and exit

Spectator/preparing: existing role/preparation state remains authoritative; no virtual input is admitted. No additional role picker or auto-Ready. Release on interruption gives visibly unpressed controls; a fresh hold is required. Return → current lobby → existing Back to Main Page → centered confirmation → teardown remains the only session-exit path. Mapping conflict/cancel returns to unchanged mappings in the same controller band.

## Final design check

Complete journeys, feature support, just-in-time information, one forward path and concise names are specified in J1–J6/S1–S10 and the above action/result labels; mobile entry remains an owner decision; the requested canvas-click toggle and top-right control use one presentation state. Stable geometry is proposed with explicit target bounds; rendered fit, idle visibility, physical reach, screen readers and simultaneous game input remain unproven. Borrowed arrangement/origin mechanics are sourced, with limits explicit. No production build is authorized by this sketch alone.
