# Relay route status: v2 page critique

The revised screen set has one status area in the fixed room panel and one recovery path for each connection failure. No further wireframe change is needed before implementation proof.

| Page | Supports | Missing | Remove | Result |
| --- | --- | --- | --- | --- |
| P1 Standard relay | J1, R02/R08/R10 | Runtime route detection and real narrow-screen fit are unproven. | No inert heading or extra control remains. | Message appears only after selected relay, then yields to interruption. |
| P2 Relay only | J2, R05/R10 | Runtime policy/route pairing is unproven. | No firewall claim or extra heading remains. | Message states the deliberate choice beside play. |
| P3 Failure | J1/J2/J3, R06/R08/R09/R10 | Exact control availability needs browser proof. | No extra recovery route added. | Existing specific error and conditional controls remain. |

| Rule | P1 | P2 | P3 | Evidence |
| --- | --- | --- | --- | --- |
| Complete journeys | Met | Met | Met | J1/J2 connect to play and P3 recovery; J3 exits. |
| Feature support | Met | Met | Met | Scenario table maps entry, state, feedback and failure; P3 names exact variants. |
| Information just in time | Met | Met | Met | A selected route triggers success text; failure replaces it immediately. |
| One clear forward path | Met | Met | Met | Normal play continues; Retry is the primary recovery, Stay/Leave are distinct outcomes. |
| Concise and consistent | Met | Met | Met | One area, short sentences, existing room controls and exact errors. |
| Borrow before inventing | Met | Met | Met | Active route distinction follows Tailscale; no diagnostic metrics or modal copied. |

Implementation must verify that the `role=status` update is announced once per actual state change, does not steal focus, survives 400 px width, appears in shared play, and clears on reconnect, solo play or leave. The design itself does not prove those behaviors.
