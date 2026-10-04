Historical critique of v3, superseded by the [v4 critique](mobile-controller-critique-v4.md); its pending phone approval was later resolved.

Audience: Human

# Mobile controller critique v3 — historical

Sources at this revision: [historical v3 wireframe](mobile-controller-wireframe-v3.md), [direction](mobile-controller-direction.md), [journeys](mobile-controller-journeys.md), [scenarios](mobile-controller-scenarios.md). Earlier v2 incorrectly treated replacing canvas-click expansion as necessary; that proposal was withdrawn.

| Screen | Supports | Missing or unproven | Revision or verification |
|---|---|---|---|
| Desktop preparation/editor | J1: actual key lines, one Edit/Save/Cancel flow, reserved band | Real rendered fit and conflict recovery | Preserve configured bindings; inspect full content and keyboard actions in product. |
| Portrait expanded play | J2–J4: large thumb targets, return to lobby | Approval of one-panel lobby; physical comfort and safe areas | Expansion is manual; verify real touch events and usable fixed bounds. |
| Landscape expanded play | J3: low translucent controls, top-right return | Actual overlap and idle discoverability | Preserve canvas-click shortcut; exclude controller contacts; verify rotation and idle return. |
| Watching/recovery/exit | J5–J6: disabled input, lifecycle release, deliberate teardown | Runtime authority and release behavior | Exercise role changes, late synchronization, blur, cancellation and confirmed exit. |

## Seven-rule check

- Complete journeys: specified by J1–J6; independent design review found the canvas-only focus owner could drop a held keyboard direction when clicking a virtual control. The implementation plan now defines one focus boundary; runtime completion remains unproven.
- Feature support: each entry and recovery is mapped in S1–S10; verify actual actions, including the mixed-input focus transition.
- Information just in time: preparation shows mappings; live play hides them while retaining controls.
- One clear forward path: one editor and presentation owner. The requested canvas gesture and top-right control activate that same presentation, with controller input excluded.
- Concise and consistent: NES action names and current bindings derive from the existing controls owner.
- Stable layout: reserved portrait/landscape targets are specified; real fit, safe areas and orientation changes remain unproven.
- Borrow before inventing: retained references explain the Famicom arrangement and bounded thumb origin. Physical usability is not inferred from those references.

At this historical revision, phone composition still awaited approval. The [v4 critique](mobile-controller-critique-v4.md) records that approval; actual panel persistence, safe areas and touch input remain implementation proof obligations. No new fullscreen gesture decision is required.
