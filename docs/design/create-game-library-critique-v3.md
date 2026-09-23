The v3 pages cover the main routes, but some controls still repeat actions or appear in the wrong state. Revise those before implementation.

Audience: Human

# Page critique of wireframe v3

Rules: complete journeys (J), feature support (F), information just in time (I), one clear forward path (O), concise and consistent (C), borrow before inventing (B). M=met, F=failed, U=unproven from static wireframe.

| Page | Supports | Missing / remove / exact revision | J | F | I | O | C | B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1 Public rooms | J1,J2,J3,J9; Open/Closed/Occupied visible. | “Super Tilt Bro / —” needs explicit **0/2 Waiting for host** rather than Guest place Open; directory must distinguish an unclaimed included offer from a hosted empty room. Keep Closed row status, with no Join. Search result empty needs distinct copy from no rooms. | M | M | F | M | F | M |
| P2 Create Game wide | J2,J3,J4,J6, selection and preview. | The word “Recent” on a list row is redundant when sorting already puts last-used first; drop it. The preview needs an explicit label for *selected* game, not “recent” if user changed selection. Show “Checking game…” beside Create while bytes verify. | M | U | F | M | F | M |
| P3 Create Game states | J2–J4 errors/storage/narrow. | “Saved copy unavailable [Add NES file]” duplicates the always visible Add action; use the single Add control in the game list. When nothing selected, access/connection options are premature; reveal after verified selection. | M | F | F | F | F | M |
| P4 Publishing | J2,J3 upload/failure. | Failure shows both Retry and Back as competing forward actions; present Retry as primary, Back as exit in header. After Cancel, navigate to Create with one status line. | M | M | M | F | F | M |
| P5 Host waiting | J7,J8, host Start. | Copy invite when Closed is misleading because Join is blocked; show invite only while Open or occupied (occupied invite itself must state full). Remove duplicate Start lines in the state sketch. Inline Leave confirmation needs its exact text and location. If guest is preparing, show clear Start-alone consequence directly by Start. | F | F | F | F | F | M |
| P6 Guest room/invitation | J1,J4,J9. | Public guest download has no Leave while in progress; add it. An open unlisted invitation before joining needs Join and connection choice; current sketch skips that state. Show Retry only on failed download. | F | F | F | U | M | M |
| P7 Playing | J10 play/room status. | Room details control duplicates the visible side region. Remove on wide screens; on narrow screen place details below canvas and scroll to them by ordinary page flow, with no second action. Separate local player tools from room status using consistent fixed regions. | M | F | M | F | F | U |
| P8 Settings/tools | J5,J10 and inline confirmation. | A combined sample does not prove each secondary page has a direct Back action, actual task controls or result. Split Settings, Local data, Saves, Rewind, Help into concrete state sketches. Rewind confirmation must not obscure play and should warn at action time. | F | F | F | U | U | U |

No page may use a fixed or absolute overlay; selected screen areas can use normal grid placement and page scroll. The slot's server-authoritative mutation and narrow layout remain implementation proof tasks, not facts established by ASCII.
