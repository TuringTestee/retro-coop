Retro Coop needs more than a browse-and-join path. This inventory lists every distinct player-facing action and recovery state in the approved S01–S37 stories, the seven project journey stories, and the new lobby-browser proposal, so the wireframes can be checked screen by screen.

Audience: Human

# Complete player scenario inventory

This is a historical interaction inventory, not proof that the application works. It covers the supported desktop browser scope and the earlier [lobby browser proposal](lobby-browser-proposal.md). The [current scenario inventory](lobby-scenarios-v2.md) and [lobby amendment](lobby-refactor.md) supersede the cases marked below once approved and merged. “Approved” records an earlier product requirement, not an implementation claim or priority over a later approved amendment. “Proposal” changes that requirement and needs alignment. “Later” means a deferred journey; it must not appear as a working promise. Operator-only actions are included only where a player sees their effect. Technical tests, pricing, and infrastructure are outside this player inventory.

Each row follows **entry or trigger → player action → visible outcome or recovery**. The source references point to the existing [UI stories S01–S37](browser-nes-ui.md#story-coverage-and-critique-checklist) and [journey gate UJS-1–7](https://github.com/TuringTestee/retro-coop/issues/66). Some rows split one story into the ordinary and failure paths that need distinct UI states.

## A. Arrive, discover, and choose

| ID | Scenario and player-visible result | Source | Status |
|---|---|---|---|
| A01 | Open Retro Coop → see an honest directory loading state → populated list or service-error retry. | S01, UJS-2 | Approved |
| A02 | Open with no public rooms → see an empty list with a useful Host action, not empty space. | S01, UJS-1/2 | Approved |
| A03 | Browse every public room → see separate rows even for the same game or room name, with host, occupancy, access, and state. | S01, S33, UJS-2/7 | Approved |
| A04 | Browse waiting, reserved, full, playing, or reconnecting rooms → understand which can be joined and why others cannot. | S01, S04, UJS-2 | Approved |
| A05 | Search by room, host, or exact public code → reach the intended room despite duplicate nicknames; clear or change the search. | S33, UJS-2/7 | Approved |
| A06 | Move between public-result pages and search again → keep keyboard focus and the search query; Clear search when no match. | S01, S30 | Approved |
| A07 | No search result → see “No matching rooms” and Clear search; an unlisted room cannot be found by public search. | S01, S33 | Approved |
| A08 | Directory refresh fails or becomes stale → old rows are marked unavailable; Retry preserves query and the player's current game. | S01, S28 | Approved |
| A09 | Choose a direct included-game Play action on arrival → download/verify and enter solo play without first navigating a host form. | S03, S37, UJS-1 | Superseded in the proposed refactor by J1/N01–N03: claim a 0/2 room, then host Start |
| A10 | Included game is absent, download fails, integrity fails, or load is canceled → specific feedback and Retry/return without a false playable claim. | S03, S37, UJS-1/5 | Approved |
| A11 | Drop or choose a local NES file on arrival → see intended Public/Unlisted state and open a waiting room without an account or naming gate. | S02, S36, UJS-3/7 | Approved direct action; waiting timing is proposed |
| A12 | Return from play to Browse games → see an active-game banner; Resume returns to the same progress, Leave is explicit. | S25, UJS-4/5 | Approved |
| A13 | Try to join or host a second room while already in one → see the current room and a deliberate leave/replace choice; no silent switch. | S25, UJS-5 | Approved |
| A14 | Read a host-provided game label → understand it is host-entered and unverified; no implied game download or certification. | S29, S36 | Approved |

## B. Create and manage a room

| ID | Scenario and player-visible result | Source | Status |
|---|---|---|---|
| B01 | Choose Super Tilt Bro or From Below to host → local verified asset loads; the correct one-player or two-player behavior is explained. | S03, S35, UJS-1/7 | Superseded entry in the proposed refactor by J1/N03; asset and controller rules remain |
| B02 | Choose an arbitrary `.nes` file → validate locally; create a room without uploading its bytes, filename, or path. | S02, S29, S36, UJS-3 | Approved |
| B03 | Choose an invalid, truncated, archive, or unreadable file → remain at file choice with a specific reason and Choose another file. | S02, S36, UJS-3/5 | Approved |
| B04 | Choose unsupported hardware or unavailable-memory file → explain the unsupported combination or resource limit before publishing a misleading room. | S02, S36 | Approved |
| B05 | Choose structurally valid but unqualified hardware → label actual local/netplay support honestly; do not use a title allowlist. | S29, S36 | Approved |
| B06 | Cancel file picking or validation → retain an earlier valid selection and any loaded game; create no orphan room. | S02, S37 | Approved |
| B07 | Accept generated room and guest names, then optionally edit labels in Room settings → see the exact public label; no filename-derived name or account claim. | S02, S29 | Approved |
| B08 | Choose Public → room appears as one row in all public results with a code and joinable state. | S01, S06, UJS-7 | Approved |
| B09 | Choose Unlisted → room stays out of directory and public-code lookup; high-entropy invitation remains the entry route. | S06, S33, UJS-7 | Approved |
| B10 | Set Standard or Relay only before peer contact → understand address/privacy effect; stricter choice cannot silently weaken. | S09 | Approved |
| B11 | Submit room creation → see checking/creating, then confirmed room and Player 1 slot; canceled/late responses cannot publish a ghost room. | S02, UJS-3/5 | Superseded separate submit in the proposed refactor by J5/N14/N19: valid file selection creates automatically |
| B12 | Hit capacity or rate limit → keep local bytes and choices, see retry timing and Retry; no claimed room creation. | S28, UJS-5 | Approved |
| B13 | Arrive in a waiting room with Player 2 empty → copy invite, wait, or start; room name, visibility, game, and code remain visible. | S04, UJS-7 | Proposed essential J1/J3/N23 after amendment approval |
| B14 | Copy an invitation → receive copy confirmation or selectable fallback text; invitation points to this exact room. | S06, UJS-7 | Approved |
| B15 | Rename room or change Public/Unlisted after creation → confirm newly public exposure; both views update or explain failure. | S06, S26 | Approved |
| B16 | Close the room as host → confirm effect on the guest; room disappears from directory and invite becomes closed. | S24, S25 | Approved |

## C. Inspect and join someone else's room

| ID | Scenario and player-visible result | Source | Status |
|---|---|---|---|
| C01 | Choose a joinable public row → inspect game, host, slots, and access, then Join this exact room. | S04, S33, UJS-2/7 | Approved |
| C02 | Open a public or unlisted invitation → preview room identity before Join; opening the URL alone starts no peer contact or microphone. | S04, S06 | Approved |
| C03 | Enter a public code → resolve only the matching public room; invalid/expired code offers another search or Browse. | S33 | Approved |
| C04 | Open an unlisted invitation → reach only that room; it remains absent from public search and codes. | S06, S33, UJS-7 | Approved |
| C05 | Select a full, reserved, already-playing, reconnecting, or closed room → see why Join is unavailable, without an apparent button that fails silently. | S01, S04, UJS-2/5 | Approved |
| C06 | Another guest takes the last slot during Join → see the changed room state and return to results or Retry when open. | S04, UJS-2/5 | Approved |
| C07 | Join succeeds → Player 2 reservation and the host room open before ROM selection; no account, nickname, or setup wizard. | S04, S07, UJS-7 | Approved |
| C08 | Join an included game → verified pinned asset downloads locally with progress, Cancel, and Retry on failure. | S03, S05, UJS-2/7 | Approved |
| C09 | Join a user-file room → choose exact matching local `.nes`; host bytes never transfer to guest. | S05, S29, UJS-7 | Approved |
| C10 | Choose wrong file or incompatible build/settings → see a precise mismatch, retain the valid room/lease while allowed, and Choose another file or leave. | S05, UJS-5/7 | Approved |
| C11 | Join a one-player game → understand P1 handoff rather than simultaneous co-op before committing. | S35 | Approved |
| C12 | Review Standard or Relay only before peer contact → choose policy; connection route or denial is visible. | S09 | Approved |
| C13 | Relay unavailable or peer connection times out → retain safe room state where possible; Retry or Leave, with no direct fallback from Relay only. | S09, S28 | Approved |
| C14 | First-time slot reservation expires → see that the place is lost; Retry must obtain a new slot, while a canceled Join must release it. | S04, S22 | Approved |
| C15 | Guest is ready while host is not → see “Waiting for host” and Cancel, with a status that distinguishes file, connection, and host readiness. | S07, UJS-5/7 | Approved |
| C16 | Both players are ready → start together automatically at a common game state; failed acknowledgement offers retry/exit without false play. | S07, UJS-7 | Automatic trigger superseded in proposed refactor by J3/N25: host Start initiates the acknowledged shared barrier |
| C17 | Chat before selecting a ROM → text works for current room members, without revealing prior messages or blocking file selection. | S20 | Approved |

## D. Wait, coordinate, and control the room

| ID | Scenario and player-visible result | Source | Status |
|---|---|---|---|
| D01 | Host sees guest join → Player 2 changes from Empty to Checking game to Ready; guest's private file details stay hidden. | S04, S05, UJS-7 | Proposal presentation |
| D02 | Guest leaves, cancels, or lease expires while host waits → slot visibly returns to Empty; host may invite another guest. | S04, S24 | Approved |
| D03 | Both players become ready → room reports “Starting together” and automatically enters shared play; failure retains honest waiting/retry. | S07 | Automatic trigger superseded in proposed refactor by J3/N25: only host Start begins shared play |
| D04 | Host starts alone → explain that a progressed game cannot admit a guest in the focused MVP; Cancel keeps waiting. | S08 | Proposed essential J3/N24; playing room shows Join unavailable |
| D05 | Host plays while waiting; prepared friend arrives → preserve host progress and offer Continue current game, agreed Restart, or Keep playing alone. | S08 | Deferred J4/N26; no Join in essential delivery |
| D06 | Late-join checkpoint fails or guest cancels → preserve old host timeline and show Retry transfer or Resume solo. | S08 | Deferred J4/N27; no transfer in essential delivery |
| D07 | Host requests a controller-slot change while paused/waiting → both accept before assignment changes and inputs clear. | S07, S35 | Approved |
| D08 | Host removes current guest → confirmation names the affected guest; guest loses slot and reconnect entitlement. | S26 | Approved |
| D09 | Guest is removed or room closes → guest sees the true reason and Browse games; no false reconnect action. | S24, S26 | Approved |
| D10 | Host edits name, visibility, or room settings while guest present → both see confirmed state or an error retaining prior state. | S06, S26 | Approved |
| D11 | Check controls or game help before starting → inspect input mapping and any included-game instructions, then return to the same waiting room without losing a slot. | S03, S18, S29 | Approved need; proposed waiting-room placement |
| D12 | Talk before starting → send room chat or opt into voice without making microphone permission a prerequisite for gameplay; denial keeps text available. | S20, S21, S34 | Approved |

## E. Play, communicate, learn, and adjust

| ID | Scenario and player-visible result | Source | Status |
|---|---|---|---|
| E01 | Game loads → large canvas, correct controller owner, current room/connection state, and relevant play controls. | S10, UJS-4 | Approved |
| E02 | Use keyboard or gamepad → mapped NES inputs act only while the game owns focus; chat typing cannot press game buttons. | S18, S20, S31 | Approved |
| E03 | Use the game's own title/menu/start controls → NES menu behavior remains real; the app does not claim loading skipped it. | S03, S29 | Approved |
| E04 | Play native simultaneous or alternating-turn title → label real behavior; a single-player game is not called co-op. | S35 | Approved |
| E05 | Pass shared P1 control → named host request, recipient accepts/declines, one owner shown, held inputs cleared. | S35 | Approved |
| E06 | Pause voluntarily → both players see who paused and why; Resume waits for both to be ready. | S11 | Approved |
| E07 | Game stalls because of peer/focus/device → pause safely, release held inputs, show what must recover before Resume. | S11, S31 | Approved |
| E08 | Make a local save → choose slot, receive success only after persistence; multiplayer timeline does not jump. | S14 | Approved |
| E09 | Overwrite a save → name the existing slot and confirm; Cancel leaves it intact. | S14 | Approved |
| E10 | Save fails due to storage denial/quota → say it was not saved and offer export or local-data management. | S14, S17 | Approved |
| E11 | Export a save → download compatible local file; failure keeps current state and offers Retry export. | S15 | Approved |
| E12 | Import a save → validate game/version and add compatible slot; invalid file leaves prior slots intact. | S15 | Approved |
| E13 | Load a local save solo → warn before replacing progress; shared load requires host request and both players' consent. | S15, S16 | Approved; shared part later in focused MVP |
| E14 | Delete a slot or all local data → name irreversible effect, offer export first, then confirm or cancel. | S17 | Approved |
| E15 | Rewind solo → choose available duration; short history explains limit and never prompts a nonexistent peer. | S12 | Approved |
| E16 | Request shared rewind/load/restart → both see effect and accept/decline; timeout/failure leaves prior shared state safe. | S13, S16 | Later; deferred shared timeline controls |
| E17 | Open Game help → see controls/instructions and included-game credits/license placeholder; close to the same game. | S03, S29, UJS-4 | Approved |
| E18 | Open help for host-provided file → see matching-file/controls guidance, without invented artwork, rules, or download links. | S29 | Approved |
| E19 | Remap keyboard/gamepad → test input, resolve conflicts, Apply or Cancel; Restore defaults names affected mappings. | S18 | Approved |
| E20 | Selected gamepad disappears → pause, offer reconnect or keyboard fallback; no stuck inputs. | S18, S31 | Approved |
| E21 | Change pixel filter or volume → see/hear local result without changing shared emulation settings. | S19 | Approved |
| E22 | Browser refuses audio activation or fullscreen → explain denial and keep normal play usable; Exit fullscreen remains reachable. | S19 | Approved |
| E23 | Send chat → see acknowledgement; messages are plain text, temporary, and scoped to current room. | S20 | Approved |
| E24 | Chat is too long, rate-limited, or disconnected → retain draft, show wait/not-sent state, and offer explicit Retry after recovery. | S20 | Approved |
| E25 | Enable voice → request microphone permission only on action; show listening/transmitting state and local/remote mute. | S21, S34 | Approved |
| E26 | Deny microphone, unplug/switch device, or lose voice route → text/gameplay continue and voice Retry does not reset the game. | S21, S34 | Approved |
| E27 | Use push-to-talk or open mic → release/mute on blur; returning focus never silently unmutes. | S21, S31, S34 | Approved |
| E28 | Change connection policy mid-game → pause/reconnect with new effective route; Relay only never silently becomes direct. | S09, S28 | Approved |
| E29 | Browse rooms during play → current game stays loaded and can be resumed; Leave/replace has a deliberate effect. | S25, UJS-4 | Approved |
| E30 | Ask to leave or quit → host/guest sees effect on other player and whether Continue locally is safe; Cancel returns to game. | S24, S25 | Approved |
| E31 | Local game hits unsupported runtime behavior → pause, preserve available saves, explain exit/report without ROM upload. | S36 | Approved |

## F. Recover, end, and regain control

| ID | Scenario and player-visible result | Source | Status |
|---|---|---|---|
| F01 | Guest disconnects → game stalls/pauses; host sees reconnecting slot and honest retry or wait state. | S22, S24 | Later automatic recovery; immediate pause approved |
| F02 | Guest reconnects within authenticated grace → reselect file if needed, restore matching state, both acknowledge resume. | S22 | Later; deferred automatic reconnect |
| F03 | Guest grace expires → slot opens; host can invite a new player or continue solo, and old guest must join anew. | S22, S24 | Later recovery path |
| F04 | Host disconnects or grace expires → guest sees waiting, then room closed; Continue locally only if safe. | S22, S24, S25 | Later recovery path |
| F05 | State hashes diverge → pause and attempt one bounded, validated recovery; repeated/invalid recovery offers reset or exit. | S23 | Later; deferred desync recovery |
| F06 | Coordinator restarts → ephemeral room closes; both see explanation, Browse games, and possible local continuation. | S28 | Approved consequence |
| F07 | Network or forced relay fails → show exact route/capacity issue, Retry or Leave; keep privacy choice intact. | S09, S28 | Approved |
| F08 | Service is full or rate limits admission → retain file/selection and show retry timing; no phantom room or slot. | S28 | Approved |
| F09 | Host kicks guest → host sees confirmed removal; guest sees removed status and cannot reclaim old reservation. | S26 | Approved |
| F10 | Operator removes abusive room or temporarily denies admission → affected player sees room closed or capacity/denial state, without private operator details. | S27 | Approved consequence |
| F11 | Invitation or code is stale, closed, malformed, or unauthorized → explain unavailability and return to Browse games without exposing unlisted metadata. | S04, S06, S33 | Approved |
| F12 | Save data is missing after reload/clear/eviction → show empty local saves and Import; do not pretend cloud recovery or know why data vanished. | S15, S17 | Approved |
| F13 | Page reload loses a user ROM → ask for the same local file again; saved preferences remain if storage survives. | S05, S22 | Approved |
| F14 | Browser loses focus during held input or open mic → release game buttons, stop transmission, then show deliberate resume/unmute. | S31, S34 | Approved |
| F15 | Player clicks Cancel during download, join, save dialog, or shared proposal → stop only the current action and preserve prior valid state. | S03, S04, S13, S14, S37 | Approved |
| F16 | A late server response arrives after cancel/leave/change room → it cannot reopen an old room, spend a slot, or replace the current game. | S04, S07, S26 | Approved visible invariant |

## G. Access and presentation across every path

| ID | Scenario and player-visible result | Source | Status |
|---|---|---|---|
| G01 | Keyboard-only player completes browse → host/join → play → recover; focus order follows visible task order. | S30, UJS-6 | Approved; browser proof needed |
| G02 | Screen reader receives room/result/pause/error status and usable labels, without repeated frame or heartbeat announcements. | S30, UJS-6 | Approved; browser proof needed |
| G03 | File host uses picker instead of drag; dialogs take and return focus; Esc cancels rather than accepts a destructive action. | S02, S30 | Approved; browser proof needed |
| G04 | Narrow supported desktop, zoom, long room names, large text, and open dialogs keep actions inside the viewport without document overflow. | S10, S30, UJS-6 | Approved; browser proof needed |
| G05 | Unavailable actions explain why at the point of use; loading, success, failure, and retry are distinct states. | S01–S37, UJS-5 | Approved; browser proof needed |
| G06 | Anonymous guest understands temporary nickname and local data; no account, cloud save, ROM server, spectator, or matchmaking promise is shown. | S02, S17, S29 | Approved |
| G07 | Empty, full, waiting, playing, and error layouts preserve the main next action without promotional or irrelevant controls. | S01, S10, UJS-1–7 | Approved; browser proof needed |

## Coverage and decisions

The inventory names **all 37 approved UI stories (S01–S37)** and **all seven project journey stories (UJS-1–7)**. It expands them into ordinary, alternate, and recovery scenarios. S32 is the integrated verification of these scenarios rather than another player action: a reviewer must exercise both roles, both included games, a user-file room, an unlisted room, play features, failure recovery, and accessibility in a real browser. Completing this document does not satisfy S32.

This inventory records the earlier wireframe and approval lineage. For the proposed essential refactor, use [J1–J7](lobby-journeys-v2.md), [N01–N34](lobby-scenarios-v2.md), and the [current wireframe](lobby-wireframe-v3.md): included Play becomes first-claim Host/P1, direct file hosting remains, and host Start replaces automatic shared start. J4/N26–N27 defer progress-preserving later join. Earlier status cells cannot re-enable automatic Start or later Join after the amendment is approved.
