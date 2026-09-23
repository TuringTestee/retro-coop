The first wireframe separates browsing from creating, but two duplicate controls and one unclear return path make setup less direct. This critique names the exact page changes before revision.

Audience: Human

# Create Game page critique v1

Rules: CJ complete journeys, FS feature support, JT information just in time, OP one clear forward path, CC concise and consistent, BI borrow before inventing. These abbreviations assess the [shared principles](../../.agents/skills/ui-ux-reviewer/principles.md), not a second rule definition.

| Page | Supports | Missing / remove / exact revision | CJ / FS / JT / OP / CC / BI |
| --- | --- | --- | --- |
| P1 Public rooms | J1 join, J2/J3 Create entry; live/stale/empty states. | Empty state repeats **Create game** already in header, creating two routes. Remove its button; leave only “No public rooms right now.” Directory errors retain Retry. Restore the existing Standard/Relay-only choice beside Join. | CJ met; FS failed (connection choice missing); JT failed (privacy choice missing before Join); OP failed (duplicate Create); CC failed (duplicate); BI met (DST browse/host split). |
| P2 Create Game | J2 saved host, J4 reuse download, C02/C03/C05/C07. | A radio choice should state which game will be uploaded; show **Selected game** near Create. The recent preview is display only; do not turn it into a second selection route. If preview absent, show text without an empty image box. Show source and local-only status next to selected game, not as a broad warning. Place Standard/Relay-only beside Create and require a saved candidate to load into the host browser before Create. | CJ unproven until P4 return; FS failed (selection and connection feedback weak); JT failed (selection identity and privacy choice missing by Create); OP met; CC met; BI met (War3/AoE choice then create). |
| P3 Add/empty/error | J3 new file and C04/C08. | **Choose another file** duplicates **Add NES file** after validation error. Keep the same Add control and place the error beside it. Since bundled games are always available when packaged, a totally empty library means bundled assets are unavailable; label that state honestly rather than “No saved games” alone. | CJ met; FS met; JT met; OP failed (duplicate picker); CC failed (inconsistent label); BI unproven for preview, documented inference. |
| P4 Upload | J2/J3 upload and C06. | **Back to Create Game** during error is a recovery exit; specify selection preservation and that Cancel aborts the upload before return. Error text should state a concrete cause when known. The pending state has only Cancel. | CJ failed (unclear Cancel outcome); FS failed (abort feedback); JT met; OP met; CC met; BI met (create before lobby). |
| P5 Waiting room | J2/J3 outcome, host Start and Leave. | No new control needed. Make sure a guest's loading/prepared status replaces the open-slot text and “Start alone” line at the right time; follow existing room design. | CJ met with existing room states; FS met; JT met; OP met; CC met; BI met (host-controlled Start). |

Highest-risk rewalk: Add file → local save denied → current tab still selected → Create → upload fails → Retry or Cancel → back with selected bytes, no ghost row. P4 lacks explicit Cancel feedback; v2 must add it. A deleted or corrupt saved entry must never remain selected; P2 needs an unavailable state and one Add action.
