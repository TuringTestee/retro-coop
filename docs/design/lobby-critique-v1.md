The first wireframe has the right one-list structure, but several labels hide who becomes host and whether a playing room can accept a guest. The next version should make those states explicit and remove controls that compete with the current task.

Audience: Human

# Page-by-page critique of lobby wireframe v1

This is an author walkthrough of [wireframe v1](lobby-wireframe-v1.md) against [journeys J1–J7](lobby-journeys-v2.md) and [scenarios N01–N34](lobby-scenarios-v2.md). It is design reasoning, not user testing or browser evidence. This artifact does not silently change v1.

| Page | Supports | Missing: scenario → player consequence | Remove or reduce | Exact v2 revision |
|---|---|---|---|---|
| 1: Public rooms | J1/J2/J5/J6; one list and distinct codes. | N03–N04: **Join** on 0/2 does not reveal that the visitor becomes Host/P1. N09/N24: no Playing 1/2 example or clear late-join state. N06: capacity message could be mistaken for a broken room. | Remove the top-level Connection selector from the list; show the applicable privacy choice immediately before peer contact, where it has meaning. Avoid a separate status column when state and action fit together. | Use **Join as host** for 0/2 and **Join** for waiting 1/2. Add a Playing 1/2 row with **Join ongoing game** when supported. Distinguish “No new empty room right now” from existing joinable rooms. |
| 2: Host a game | J5; file, label, visibility, create. | N15–N17: the UI says others need the same file but does not say whether a verified included file lets guests download it. N19: selected file/validation state is absent. | Remove the always-visible Connection selector; show connection policy in the create confirmation only if it changes peer exposure. Drop “or drop one here” if the whole file area supports drop and the picker is clear. | Show selected file's local validation and public room label separately; after validation, state either “Guests download this included game” or “Guests choose their own matching file.” Hide local path from published preview. |
| 3: Room before play | J1/J2/J3/J6; player slots and Start. | N07/N25: Start availability during asset download or when a guest is preparing is unclear. N30: From Below's single-controller arrangement is absent. N04: first-join race recovery needs the updated role. | Replace separate Room settings and Leave if settings can hold Leave/Close without extra taps? No: Leave is a core escape, so retain it; keep advanced settings behind one button. Remove duplicated game-ready prose once slot/status line says it. | Show Host/P1, guest slot, game readiness, and Start's effect. If P2 is preparing, say Start begins solo and P2 joins later. Label From Below as shared controller. |
| 4: Playing | J3/J4/J7; game is dominant and open slot shown. | N26–N27: no visible pending-guest notice or host choice at safe pause. N32–N33: host/guest loss state not connected to room controls. | Hide Save, Controls, Settings, and Game help behind one relevant Game menu? No: Save, help, and settings support frequent play tasks. Keep a compact toolbar; remove duplicate Room and Leave by placing Leave inside Room. | Show guest request and safe-pause action next to player slot. Keep canvas dominant; use Room for invitation, roles, access, and Leave. Show chat/voice only when two people are present. |
| 5: Recovery | J1/J2/J4/J7; failures stay near their cause. | N04: a first-join race might fill P2 before the loser retries; **Join as guest** needs current availability. N26–N29: Retry together cannot be offered to a guest if the host declined or room closed. | Remove Page 5 as a navigable page; these are state variants on Pages 1, 3, and 4. | Annotate each variant with role/room preconditions and offer only valid actions. Return to the list on room closure; preserve host progress on failed late join. |

## Coverage judgment

The ordinary path is visible but not yet self-explanatory at first claim, during guest preparation, or during a late join. The public-list structure satisfies the user's main correction. The next revision should keep the same pages, make role and state changes explicit, and trim repeated controls. Accessibility, content length, focus return, narrow desktop fit, and actual network behavior remain implementation checks; ASCII alone cannot prove them.

## Step 6 six-rule score by page

M = met in the ASCII page; F = failed and needs the named v2 repair; U = unproven at this fidelity. The principles are detailed journeys (J), feature support (Ftr), just-in-time information (JIT), one forward route (One), concise/consistent content (Clean), and reference-grounded choice (Peer).

| Page | J | Ftr | JIT | One | Clean | Peer | Evidence and required repair |
|---|---|---|---|---|---|---|---|
| 1 Public rooms | M | F | F | F | M | M | A 0/2 Join conceals Host/P1 and a playing row is absent; label actions by role/state and add the playing-row variant. |
| 2 Host file | M | F | F | M | M | M | The guest-file rule is wrong for an exact included asset and validation status is missing; show the result after file choice. |
| 3 Room | M | F | F | M | M | M | Start's effect with a preparing guest and From Below's controller mode are missing at the decision point. |
| 4 Playing | F | F | F | M | F | M | Later join, chat, voice, and room exit are described outside the screen; draw the active/pending states and consolidate session actions. |
| 5 Recovery variants | M | F | M | F | M | M | Join as guest and Retry together may be invalid after a race or closure; make each action conditional on current state. |

No page earns an unqualified implementation claim. The [revised design](lobby-wireframe-v2.md) must fix each F, then run its own final principle check.
