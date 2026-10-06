Historical critique of the original baseline. [Gameplay controls](gameplay-controls.md) supersedes its Settings, editing and feedback decisions. This retained record does not prescribe the replaced routes.

Audience: Human

# Mobile controller critique v4

Sources: [historical wireframe](mobile-controller-wireframe-v4.md), [direction](mobile-controller-direction.md), [journeys](mobile-controller-journeys.md), [scenarios](mobile-controller-scenarios.md). v1–v3 remain historical proposals.

| Screen | Supports | Missing or unproven | Revision or verification |
|---|---|---|---|
| Desktop preparation/editor | J1: actual key lines, one Edit/Save/Cancel flow, reserved band | Real rendered fit and conflict recovery | Preserve configured bindings; inspect full content and keyboard actions in product. |
| Portrait expanded play | J2–J4: large thumb targets, return to lobby | Physical comfort, safe areas and play-entry/Return state persistence | Expand once when phone play is locally usable; verify Return is preserved through room updates and real touch events use fixed bounds. |
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

The phone composition and automatic entry are approved; merge the independently reviewed governing plan before implementation. The local demo fits maximum accepted content in both minimum orientations; actual panel persistence, safe areas and touch input remain unproven. No new fullscreen gesture decision is required.
