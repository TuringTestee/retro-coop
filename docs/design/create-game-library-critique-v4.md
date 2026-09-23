The current ASCII design gives each main action a page region and removes floating UI. The real browser build must still prove layout, admission races and accessible focus.

Audience: Human

# Page critique of wireframe v4

M=met in the sketch; U=requires implementation proof. Rules: J complete journeys, F feature support, I information timing, O one path, C concise/consistent, B borrowed pattern.

| Page | Supported journeys and evidence | Missing / remove / revision | J | F | I | O | C | B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 Public rooms | J1–J3,J9: distinct 0/2 offer, Open, Closed and Occupied rows; one Create and eligible Join. | No further control needed. Live updates and no horizontal overlap remain to test. | M | M | M | M | M | M |
| P2 Create wide | J2–J4,J6: list selection updates in-place preview; one Add and Create. | Verify real frame and byte recheck in build. | M | U | M | M | M | M |
| P3 Create narrow/errors | J2–J4: status and one Add; access appears after verified choice. | Verify focus and no horizontal scroll at 200% zoom. | M | U | M | M | M | M |
| P4 Publishing | J2,J3: progress, Cancel, Retry and Back in their states. | Verify abort removes provisional room. | M | U | M | M | M | M |
| P5 Host waiting | J7,J8: slot control changes by state, inline removal/leave, one Start. | Test exact Close/Join race and confirm disabled/hidden action after Start. | M | U | M | M | M | M |
| P6 Guest/invite | J1,J4,J9: open invitation Join, closed/full status, download and Prepare. | Verify stale invitation updates and download Retry. | M | U | M | M | M | M |
| P7 Playing | J10: canvas, status and room details have their own regions; no redundant drawer action. | Verify controls do not cover canvas on desktop/mobile. | M | U | M | M | M | M |
| P8 Settings | J10: focused setting controls and Local data entry, one Back. | Verify only supported controls render in build; the sketch is not a mandate for new settings. | M | U | M | M | M | M |
| P9 Local data | J5,J10: saved rows and inline confirmation with failure. | Verify delete and clear generations across tabs. | M | U | M | M | M | M |
| P10 Saves/Rewind/Help | J10: distinct full-page states, Back, task controls and inline destructive confirmation. | Verify shared-play policy hides unavailable entry controls and focus returns. | M | U | M | M | M | M |

The design passes all six rules at sketch fidelity. Acceptance needs the actual UI and a current two-browser adversarial review. Keep only the four wireframe versions and their critiques currently present; when v6 is saved, prune v1 and its critique.
