The second wireframe got the room list right but added a needless file-hosting form and hid two existing needs: connection privacy before Join and chat while players wait. The user also deferred later join. This critique names the exact v3 changes.

Audience: Human

# Page-by-page critique of lobby wireframe v2

This reviews [v2](lobby-wireframe-v2.md) against the six [design rules](lobby-refactor.md#design-rules), the approved baseline, and the user's essential-first direction. The independent planning review of PR #72 supplied the baseline contradictions; this document records the design repairs. It is not a product usability test.

| Page | Supports | Missing or unnecessary | V3 repair |
|---|---|---|---|
| 1 Public rooms | One list, roles, separate rows. | Codes show four characters instead of the approved eight. Standard/Relay-only privacy is hidden in Settings before a Join that may expose peer addresses. A playing 1/2 row promises later Join, now deferred. The 0/2 row lacks explicit Waiting-for-host status, and an occupied From Below row hides its shared-controller mode. | Use eight-character codes, one compact inline privacy choice beside room actions, 0/2 status, and From Below mode in both empty and occupied rows. Playing says Join unavailable. |
| 2 Host file | Local selection and public/unlisted choice. | Required name and separate Create step conflict with direct drop/picker hosting and one forward action. Privacy is only in Settings. | Make Page 2 a compact inline host action on Page 1: choose Public/Unlisted and privacy, then drop/pick a file. Validate and create automatically with a generated label; rename later. |
| 3 Room | Host/P1, guest/P2, Start, invite. | Waiting-room chat is absent before the guest chooses a ROM, although pre-ROM text is an approved feature. If the host starts while P2 is preparing, the guest needs an honest unavailable/exit result. | Show Chat as soon as two people share the room, even before file match. Explain Start's effect and release/redirect a guest who cannot join after Start. Keep voice opt-in where both are present. |
| 4 Playing | Canvas is dominant and help/save controls are contextual. | Later-join transfer controls are now out of scope; an open-looking P2 slot suggests guests can join after Start. | Show Playing · 1/2 · Join unavailable, with the reason in room details. Remove pending-guest transfer choices from the essential screen. |
| 5 Recovery | Errors stay near actions. | Late-join retry is no longer an essential recovery path; capacity should disable a predictable failed claim before clicking. | Keep first-claim race, mismatch, host loss and capacity variants; mark later join deferred. |

## Six-rule score

M = met in v2; F = failed for essential v3. The reference study remains valid. Detailed journeys need the new deferral and direct-host path; feature support fails on waiting chat; information timing fails on privacy and From Below mode; one route fails on the extra Create/name gate; consistency fails on code length and playing admission.

| Page | Journeys | Features | Just in time | One route | Concise/consistent | Comparable pattern |
|---|---|---|---|---|---|---|
| 1 | F | M | F | M | F | M |
| 2 | F | M | F | F | F | M |
| 3 | M | F | F | M | M | M |
| 4 | F | M | F | M | F | M |
| 5 | F | M | M | M | M | M |

The [v3 wireframe](lobby-wireframe-v3.md) must repair every F at design fidelity. Real-browser and network proof remains separate.
