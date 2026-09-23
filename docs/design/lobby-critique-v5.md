The v5 design missed a distinct visible Cancel action for a stalled cached check or local load and a visible Leave action while waiting for peer connection. V6 draws those states explicitly.

Audience: Human

# Lobby wireframe v5 critique

Review of [v5](lobby-wireframe-v5.md) against [approved transfer behavior](room-rom-transfer.md) and the shared six rules. Each row names the visible evidence; runtime results remain separate.

| Page/state | Journeys | Feature support | Just in time | One route | Concise/consistent | Borrow before inventing | Remaining runtime check |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Directory/invitation | Met: both show Join and size. | Met: “Host-shared NES · 2.1 MB download” precedes Join. | Met: size appears before the download decision. | Met: one Join per eligible entry. | Met: same disclosure for public and unlisted. | Met: approved Warcraft III-style host distribution. | Verify public row, invitation, and no private filename/hash leakage. |
| Guest acquiring | Met: Join leads to progress or cached check. | Failed: the single progress sketch omitted a distinct cached-check and local-load Cancel state. | Failed: stalled cache/load lacked a visible exit at that moment. | Unproven: one Cancel was drawn only for download. | Met: “Downloading” and “Loading” name distinct stages. | Met: standard progress/cancel pattern. | V6 draws Cancel preparation in all three phases; verify abort, reservation release, and search focus. |
| Guest ready/recovery | Met: Prepare leads to host Start; error exits or retries. | Failed: peer-wait exit was not separately drawn. | Met: storage notice appears when saving fails, beside Prepare. | Unproven: peer wait lacked its own action. | Met: “Ready” only follows verified load. | Met: retry follows the same transfer route. | V6 draws Leave while waiting for peer; verify peer gating, failed load, late result, and status announcements. |
| Host waiting | Met: host can wait or Start solo/shared. | Met: exact guest phase appears beside Start. | Met: phase matters before Start. | Met: one Start. | Met: phase terms match guest screen. | Met: established lobby readiness pattern. | Verify phases are membership-scoped and cleared on leave. |
| Local data | Met: saved copy can be removed. | Met: game row, empty state, one/all deletion. | Met: deletion impact in confirmation. | Met: one action per row. | Met: neutral identity and readable size. | Met: familiar local-data list. | Verify focus, deletion, and rejoin download. |

The v6 revision resolves the failed and unproven sketch cases. Runtime checks are separate.
