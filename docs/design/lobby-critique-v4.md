The v4 sketch puts game size before Join and recovery beside download and deletion; runtime testing still has to prove the transitions and focus.

Audience: Human

# Lobby wireframe v4 critique

This checks [v4](lobby-wireframe-v4.md) against the approved [room game journey](room-rom-transfer.md) and the shared six design rules. It preserves unaffected [v3](lobby-wireframe-v3.md) pages.

| Page | Supports | Missing or unnecessary | Revision or runtime check |
| --- | --- | --- | --- |
| Public rooms and invitation | Host-shared identity and size appear before one Join. Included rows stay distinct. | Actual announcement and focus after live row changes are unproven. | Keep one Join per eligible row; verify keyboard and responsive width. |
| Waiting room | Download, cancel, retry, load, Prepare, and lost-place exit each have relevant state. Chat remains available. | A failed load needs the same Retry route; host status must follow guest events, not guessed progress. | Treat failed load as Retry download; prove host text in two sessions. |
| Local data | Saved game size, individual deletion, all deletion, and active-game memory rule are clear. | Browser eviction may make the list empty after a previous successful save. | Say no downloaded games are saved when empty; verify deletion and next Join. |

| Rule | Design result | Runtime limit |
| --- | --- | --- |
| Detailed journeys | Met: public and unlisted Join reach Prepare, Start, and recovery. | Two-session proof pending. |
| Feature entry and recovery | Met: every affected control appears in a usable state. | Cancellation and failure need exercise. |
| Information just in time | Met: size before Join; fallback when save fails. | Announcements need checking. |
| One forward route | Met: Join, then Prepare, then host Start. | Disabled and stale controls need checking. |
| Concise and consistent | Met: no guest picker or repeated matching-file instructions. | Existing shell may still show old text until implementation. |
| Borrow before inventing | Met: approved Warcraft III-style host distribution pattern remains the source. | Transfer/cache behavior is Retro Coop's approved decision. |

No further sketch revision is needed. The implementation review should check the stated runtime limits at desktop widths and keyboard focus.
