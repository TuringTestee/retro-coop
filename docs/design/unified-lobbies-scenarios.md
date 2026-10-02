These scenarios define the visible states and recovery paths of the current lobby journey.

# Unified lobbies: scenarios

| ID | Trigger | Visible result | Recovery |
| --- | --- | --- | --- |
| D1 | Directory opens empty or with lobbies | Host row first; count and search in one row; each lobby row shows name, game or no game, access and occupancy | Stale service shows Retry; no second Host/Join control |
| D2 | Available, protected, full, or reconnecting row | Whole available row joins; protected row opens the password field; unavailable row states its reason | Wrong password stays in place; full/reconnecting row remains disabled |
| H1 | Host creates, renames, changes access, or copies invite | Immediate generated public lobby; fixed header edits only the value; right Lobby menu owns access; toolbar owns invite | Failure preserves current state and offers a local retry or selectable link |
| S1 | Host opens occupied row | Attached dropdown lists direct moves/swaps by Player 1, Player 2, or Spectator place, plus Kick for a guest | Toggle row/outside/Escape closes; stale revision shows retry |
| S2 | Host opens empty or closed row | Empty open has only Close slot; closed has only Open slot | Occupied place cannot close; server keeps member identity |
| S3 | Person leaves, is kicked, or joins during play | Remaining members compact through open places; host can kick live; newly free place admits a new member | Controller change freezes at a completed frame, transfers state to the replacement, and resumes after confirmation |
| G1 | No NES game, selecting, selected, or failed | Same fixed center frame shows Load, progress, actual preview or failure; name and Change game are above it | Cancel/failure retains lobby; failed acquisition can retry |
| P1 | One or more controller owners unready | Ready belongs to each active owner; host Start is unavailable while anyone required is unready | Host waits or kicks; old readiness invalidates after membership/game change |
| P2 | Solo host Ready | Start appears and one broadcast countdown leads to live play | Failed start returns to preparation in the same lobby |
| P3 | Late spectator or controller | Spectator observes; new controller sees Prepare to play and remains unassigned until synchronized | Failed transfer preserves completed frame and offers retry |
| M1 | Menu changes or game expands | Right menu swaps in place; game remains center. Click game fills window; click or Escape restores it | Section-specific audio/voice errors stay in the menu |
| C1 | Own message sent or delivery fails | Own nickname is prefixed `(you)` in chat; only chat history scrolls | Retry or Discard keeps draft and message identity visible |
| E1 | Logo or Back to Main Page clicked | Centered blocker names Close or Leave and dims the current lobby | Stay returns to play; failed exit keeps context and retry |

A menu item appears only for a supported action. Roles and transport mechanics are assigned by the product; players see the outcome of a move, not an internal routing decision.
