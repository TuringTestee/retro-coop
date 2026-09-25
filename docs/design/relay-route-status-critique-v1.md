# Relay route status: v1 page critique

The first wireframe puts route feedback in the right place. It still needs shorter narrow-screen copy and a precise failure state before implementation.

| Page | Supports | Missing or ambiguous | Remove | Exact revision |
| --- | --- | --- | --- | --- |
| P1 Standard relay | J1 success, R02/R03/R07/R08 | Long four-line sentence competes with controls at the narrow desktop width; direct and unknown variants are only in prose. | The `Connection` heading repeats the meaning of the status on an already dense panel. | Shorten to `Direct path unavailable. Relay keeps you connected.`; show direct/unknown variants in one compact state table beneath the page. |
| P2 Relay only | J2 success, R05 | Four-line message is longer than the fact the player needs. | Repeated `Connection` heading. | Use `Relay only is on. You're connected.`; keep `Relay` in the fixed status so the chosen route is clear. |
| P3 Failure | J1/J2 recovery, R06/R08 | Generic `Relay unavailable` could conceal `capacity full`; Retry may be temporarily blocked and Stay in room may be needed. | No extra control; Retry, Stay and Leave have different outcomes. | Show unavailable/full/interrupted as exact existing error variants and keep the existing Retry/Stay/Leave conditions. |

| Rule | P1 | P2 | P3 | Evidence and repair |
| --- | --- | --- | --- | --- |
| Complete journeys | Met | Met | Met | P1/P2 lead to play and P3 recovery; J3 covers leave/reconnect. |
| Feature support | Met | Met | Failed | P3 lacks capacity and interrupted variants; add the exact error mapping. |
| Information just in time | Met | Met | Met | Route is shown only after selected relay; P3 appears on failure. |
| One clear forward path | Met | Met | Met | Play continues; Retry is primary recovery; Stay/Leave are distinct recovery/exit choices. |
| Concise and consistent | Failed | Failed | Failed | P1/P2 wrap and repeat `Connection`; P3 uses generic error text. Revise all three. |
| Borrow before inventing | Met | Met | Met | [Tailscale reference](relay-route-status-references.md) supports active-route distinction; no novel modal or network metric. |

Rewalk after revision: the connected route appears beside play, does not steal focus, and clears before any reconnect/failure message. The current `Route: relay` string and the hidden-during-play conditional must be replaced in implementation, not layered underneath the new text.
