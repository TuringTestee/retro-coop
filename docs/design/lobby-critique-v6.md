The v6 design shows Cancel preparation during every acquisition phase and Leave while waiting for peer connection. The remaining checks require a running product.

Audience: Human

# Lobby wireframe v6 critique

Review of [v6](lobby-wireframe-v6.md) against [approved transfer behavior](room-rom-transfer.md) and the shared six rules. Each row names the visible evidence; runtime results remain separate.

| Page/state | Journeys | Feature support | Just in time | One route | Concise/consistent | Borrow before inventing | Remaining runtime check |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Directory/invitation | Met: both show Join and size. | Met: “Host-shared NES · 2.1 MB download” precedes Join. | Met: size appears before the download decision. | Met: one Join per eligible entry. | Met: same disclosure for public and unlisted. | Met: approved Warcraft III-style host distribution. | Verify public row, invitation, and no private filename/hash leakage. |
| Guest acquiring | Met: Join leads to progress or cached check. | Met: cache check, download, and local load each show Cancel preparation. | Met: Cancel appears at each stall point. | Met: each phase has one exit and no competing Leave. | Met: the three phase labels describe current work. | Met: standard progress/cancel pattern. | Verify abort, reservation release, and search focus. |
| Guest ready/recovery | Met: Prepare leads to host Start; error exits or retries. | Met: peer wait shows Leave; failure shows Retry and Leave. | Met: storage notice appears when saving fails, beside Prepare. | Met: Prepare is sole forward action after load and peer. | Met: “Ready” only follows verified load. | Met: retry follows the same transfer route. | Verify peer gating, failed load, late result, and status announcements. |
| Host waiting | Met: host can wait or Start solo/shared. | Met: exact guest phase appears beside Start. | Met: phase matters before Start. | Met: one Start. | Met: phase terms match guest screen. | Met: established lobby readiness pattern. | Verify phases are membership-scoped and cleared on leave. |
| Local data | Met: saved copy can be removed. | Met: game row, empty state, one/all deletion. | Met: deletion impact in confirmation. | Met: one action per row. | Met: neutral identity and readable size. | Met: familiar local-data list. | Verify focus, deletion, and rejoin download. |

No design-rule gap remains in the sketches. Runtime checks are separate.
