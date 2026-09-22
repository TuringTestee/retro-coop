Audience: Human

# Retro Coop UI design

Visitors see every public game session, drop a local ROM to host, and join a two-player room with a clear next step. The game stays central while chat, controller ownership, and shared pause/recovery remain visible. These text wireframes cover the first-release stories and failure states; they are a design proposal, not a working interface or a usability-test result.

The [included-games amendment](included-games.md) updates U1/U3/U4/U9: before play it shows the complete lobby directory plus one-click launchers for Super Tilt Bro and From Below; after load it enlarges the game and exposes play controls. It removes promotional copy and standalone About tabs. Other interaction and consent rules below remain unchanged.

The proposed [lobby experience amendment](lobby-refactor.md) and its [current ASCII wireframe](lobby-wireframe-v2.md) replace those launcher and automatic-start sketches once reviewed, approved, and merged. The S01–S37 interaction checklist remains useful for unaffected play, accessibility, and recovery states.

## Scope and reading guide

This companion to [the platform design](browser-nes-platform.md) covers AC-01–AC-16 at the interaction level. It adds no gameplay spectators, accounts, password rooms, cloud saves, recordings, mobile controls, or an unqualified universal emulator compatibility promise. Broad compatibility qualification is now a release workstream. The existing browser/network, cost, and rights constraints still apply. Labels such as “Evening puzzle,” player names, counts, and timers are illustrative. Historical “Featured homebrew” placeholders below are replaced by the linked catalog amendment.

The candidate is intended for review in [planning PR #3](https://github.com/TuringTestee/retro-coop/pull/3), under [epic #2](https://github.com/TuringTestee/retro-coop/issues/2). ASCII establishes hierarchy, actions, and state changes. Real-browser visuals, accessibility checks, network evidence, and user approval are still required later. UI labels use “game matches” and “waiting for connection”; hash algorithms and protocol epochs stay in the engineering specification.

Square brackets denote controls. A disabled control is explicitly labelled unavailable with nearby explanatory text. Full/Reserved are status text, not misleading clickable buttons. Screens U1–U9 and stories S01–S37 provide stable references for implementation and review.

## Direction and layout

The current agent-proposed visual direction remains a restrained arcade theme; the user’s governing product principle is minimal setup, not a mandated aesthetic: dark charcoal page, slightly lighter panels, warm off-white text, and one bright accent for the next action. Reserve amber for attention and red for errors/destructive actions, always paired with words or icons. Body text uses a readable system sans-serif; a pixel-style wordmark is optional. No scanlines on page text, flashing decoration, fabricated cartridge art, or automatic background gameplay.

At a wide desktop viewport, use the full available window up to a readable maximum width. The document has no horizontal or vertical scroll in discovery or play. Directory rows stay compact and paginate within the remaining viewport height; do not add a nested scrolling list. Session layout gives roughly three quarters of the width to play and one quarter to players/chat, with the game preserving the emulator's 256:240 source ratio. Do not stretch its pixels to match these schematic boxes. Narrow supported desktop windows move the side panel into a compact switchable region and shrink the canvas to fit; they retain every action without document overflow. This responsive treatment does not expand first-release support to mobile play.

Use at least 16 px body text, clear focus outlines, comfortably sized controls, readable contrast, and reduced-motion behavior. Screen-reader labels name the game and host for each Join action. Announce join outcomes and pauses politely; do not announce every heartbeat, game frame, or countdown tick. Dialogs receive focus and return it to their trigger when closed. There is no drag-only, hover-only, color-only, or pointer-only task.

## Iteration record

The first three passes below are historical; pass 4–6 and U1–U9 describe the current candidate.

### Pass 1: discovery sketch

```text
RETRO COOP                                      [Settings]
Play something together.
+----------------------------+----------------------------+
| FEATURED HOMEBREW          | HOST YOUR GAME             |
| [Game title pending]       | Drop a .nes file here      |
| [Start a session]          | or [Choose file]           |
+----------------------------+----------------------------+
LIVE SESSIONS
Game                   Host          Players       Action
Evening puzzle         Alex          1 / 2         [Join]
Space adventure        Sam           2 / 2         [Full]
```

Critique: a Join button does not explain that the visitor needs their own ROM. Capacity alone hides waiting, solo play, and reconnect states. The featured entry lacks a way to find an existing session, and Full looks clickable. This version also says nothing about public visibility, readiness, recovery, or coordinated rewind.

### Pass 2: honest session rows and readiness

Added per-session content-source labels, explicit lifecycle status, Full/Reserved text, a featured-session browser action, and a lobby checklist. Kept public ROM labels separate from private filenames. The revised discovery screen is U1; the lobby is U3.

Critique: those screens cover arrival, but not what happens after Start. They need stable play/chat placement, distinct host/guest controls, persistence feedback, connection privacy before peer contact, and a visible agreement step for timeline changes. A missing-game message alone does not cover hash mismatch, incompatible builds, invalid files, or catalog download failures.

### Pass 3: role-aware play and recovery

Added U4–U9, explicit state/action tables, and the story coverage matrix. A pause overlay names the requester and effect, local Save does not imply cloud storage, and shared restore/rewind has acceptance/timeout states. Full-room races return to discovery; reconnect keeps a reservation separate from a newly joinable slot. The interface explains source and privacy where they affect the user's next choice.

Historical pass-3 self-critique: the permanent homebrew entry was honest with zero players, but its game-specific title, image, instructions, two-player behavior and rights were still unknown at that time. [The catalog amendment](included-games.md) supersedes that old content status with two fixed identities, text-only launchers/help and assigned runtime qualification. ASCII cannot validate actual density, contrast, audio/input interactions or discoverability; the implementation must supply that evidence.

### Pass 4: remove setup gates

S02/S03/S07 → naming, connect, load, ready and start controls delay the first shared frame → replaced them with generated defaults, inline connection policy and automatic prerequisites/start. A local ROM still needs user selection; microphone access still needs consent. Kept destructive/shared timeline consent instead of erasing it to claim one click.

### Pass 5: find friends and preserve progress

S04/S08/S33 → duplicate names, slot squatting and a late guest can strand or disrupt a host → added unique public codes/search, a bounded initial reservation, and a ready-guest checkpoint join that asks the host before changing their running session. A reservation alone does not pause solo play. S35 → a single-player ROM does not provide P2 gameplay → optional, explicit shared-controller handoff rather than a false co-op claim.

### Pass 6: voice and compatibility boundaries

S21/S34/S36/S37 → push-to-talk-only voice, untested hardware and unmeasured setup undermine the requested experience → added conversational voice/device recovery, separate local/netplay qualification, and startup/action-count evidence. Rechecked existing save, privacy, abuse, reconnect and accessibility paths. The catalog identities are fixed by [the catalog amendment](included-games.md); exact-artifact packaging/runtime checks under D19 and the measured supported-hardware matrix under D20 remain release gates. No additional product decisions are silently filled in. These are author walkthroughs, not observed user tests.

## U1 — Directory

[Included games and arbitrary NES files](included-games.md) is the sole full definition and current wireframe for U1. It places compact **Play** and **Show lobbies** actions for Super Tilt Bro and From Below plus compact arbitrary-file hosting above the live directory. The directory is the dominant content. There is no marketing hero, tagline, passive game-information panel, pre-play About action, or page scrolling. Overflowing lobby results use deterministic pagination.

Default listing shows all admitted public sessions, including multiple sessions with the same label. Each row includes host, content source, occupancy, lifecycle status, and an accurate action. The platform does not certify user-entered game labels; an adjacent information label says “Host-provided title.” Do not show private filenames, ROM hashes, third-party download links, private sessions, or auto-generated artwork. Guest identity is a temporary nickname; Settings explains that it is not an account.

Each catalog launcher's **Show lobbies** action filters the directory with a visible game-title chip and **Show all lobbies**. With no matching rooms, show “No lobbies yet” and keep that game's **Play** action active when its catalog asset is configured. Loading the directory uses row placeholders; a failed connection shows “Can't update lobbies” and **Retry**, marks old rows stale, and disables joining stale rows until refreshed. An empty directory says “No public lobbies yet.” Both catalog launchers and arbitrary-file hosting remain visible. Development without an individual configured asset shows that game as unavailable without making a playable claim; the other catalog game and arbitrary-file hosting remain usable.

Show the Standard/Relay only policy beside Join as well as Drop, before peer contact; changing it is optional. Public search matches host/room names or exact public codes, shows no-match feedback and offers Clear search. Codes distinguish duplicate nicknames and are never credentials. Unlisted rooms cannot be found by search or public code.

Join reserves an available slot on the server before U3 opens; a race shows “That place was just taken” with [Back to sessions]. Full or reserved sessions cannot admit visitors; there is no implied spectating. Browse-filter counts and row states update together. Directory changes retain keyboard focus and do not move the selected row out from under a click.

## U2 — Immediate hosting and connection defaults

```text
DROP / CHOOSE ROM
      ↓
Checking file… [Cancel]
      ↓
Room K7PM4R2X · Guest Alex · Public  [Copy invite] [Settings]
+------------------------------------------------------------+
|                     GAME CANVAS                            |
| Playing alone · Your friend can join when ready            |
+------------------------------------------------------------+
[Enable voice]   Keyboard ready [Controls]
```

Drop/picker completion uses the visibility shown at U1, generates a neutral room label/nickname, assigns P1 and opens solo play after successful validation and creation. No mandatory title form, account, connection modal or Practice button. Start included game follows the same flow with a pinned download. Rename, visibility and controller mode live in optional Session settings. Host a game focuses the accessible drop/picker area; it does not introduce a second workflow.

Local validation shows cancel and preserves the previous valid selection on chooser cancellation. Unavailable memory, archive, malformed, unsupported mapper/region and read/hash failure each explain the next action and offer Choose another file. Explain supported file formats and real resource limits by the chooser; there is no blanket 8 MiB gate. Supported hardware with an unknown title is not rejected merely for missing catalog metadata. Unverified support is labelled Experimental with details; unsupported hardware never becomes a misleading playable room. Catalog progress includes retry/back for download or integrity failure. Capacity/rate rejection preserves valid local bytes, offers retry with any wait duration, and does not imply a room was created. A cancelled or stale create response cannot leave an orphan public room.

Connection privacy appears inline at U1 and the invite preview before Join. Standard allows direct connections and explains address exposure; Change offers Relay only. The action uses the visible choice, without a separate Connect action. If either participant requests Relay only, both enforce it before peer candidate exchange. Denial offers Retry or Stay in room, never silent direct fallback. Changing policy during play pauses and reconnects before shared resume. Labels do not promise anonymity from the service/relay operator.

## U3 — Automatic joining and progress-preserving start

```text
< All sessions     Room K7PM4R2X · Alex     [Copy invite]
P1 Alex · Playing alone    P2 You · Preparing

Bring your matching ROM: [Choose file] or drop here
Your file stays on this device.
Connection: Connecting…          [Cancel join]

[Chat…                                             ] [Send]
Voice off [Enable voice]
```

An invite first shows room identity, availability, content source and inline connection policy with Join. Merely opening an invite does not initiate peer contact. Join reserves P2, opens the room, connects and automatically loads included content. A ROM already loaded in this tab may be reused if its exact hash matches; otherwise ask for the matching file. Do not promise ROM persistence across reload. Chat can work before matching. The initial reservation expires after 120 seconds with Retry join and retained local selection; the displayed state distinguishes this from reconnecting an established player.

Game matches, Connected and Controller 2 assigned are automatic status rows, not extra checkboxes. A mismatch offers Choose another file; a build mismatch offers a compatible reload if available, warning about reselection, or Back to sessions. Failed network/compatibility checks retain valid local work and allow retry/cancel. Cancel clears play intent and releases the reservation. No Ready or Start together button for fresh eligible sessions; the shared start barrier reports Starting together and failure truthfully.

A host already playing is not interrupted by an unprepared guest. Once both prerequisites are ready, pause at a committed frame and ask the host:

```text
Alex, your friend is ready.
[Continue current game] [Restart together] [Keep playing alone]
```

Continue current game sends validated dynamic state and resumes after both acknowledge. Restart asks both before replacing progress. Keep playing alone releases the joiner with an explanation. The guest sees Waiting for Alex and Cancel join. Failed transfer preserves the old timeline paused with Retry or Resume solo. A fresh room still at its initial state starts automatically. Assignment changes and later shared timeline changes still require acceptance; they are not initial setup steps.

Voice is optional and never blocks play. Enable voice requests microphone permission and defaults to conversational audio; Settings offers push-to-talk and devices. Copy invite gives success or selectable fallback text. Optional rename, visibility, kick, close and controller assignment remain host-only. A change from unlisted to public names the exposure before confirmation; unlisting removes public lookup and code resolution. Existing high-entropy invites remain usable.

## U4 — Playing and ordinary pause

```text
< All sessions    Evening puzzle     Playing together [Invite]
+--------------------------------------+----------------------+
|                                      | PLAYERS              |
|                                      | P1 Alex · Host       |
|             GAME CANVAS              | P2 You               |
|                                      |                      |
|                                      | CHAT                 |
|                                      | Alex: Nice save!     |
+--------------------------------------+                      |
| [Pause] [Save] [Rewind*] [More…]       | [Message…] [Send]    |
| Sound [====] [Fullscreen] [Settings]  | Voice off [Enable]   |
+--------------------------------------+----------------------+
* Host control. Saving creates a copy on your device.
```

U4 appears only after a game has loaded. The canvas expands into the primary content area and the controls below it become visible at that point. Before load, Pause, Save, Rewind, Fullscreen, sound and controller controls are absent rather than disabled clutter. **All lobbies** returns to the complete directory while preserving the current loaded game. **Game help** replaces a pre-play About tab and contains controls/instructions, credits and the requested license placeholder for an included game.

Both players can request Pause; it pauses the shared timeline and identifies the requester. Resume requires both players to be present and acknowledge readiness, then the host selects [Resume together]. While awaiting the other player, show “Waiting for Jo to resume” instead of an apparently broken button. System pauses (connection, focus, disconnected controller, slow device) use U8 and cannot be bypassed while their prerequisite is unresolved.

Save is local and non-disruptive at a committed frame. It opens U6 and reports success only after persistence succeeds. Rewind is host-only in multiplayer; guests see “Host controls shared rewind” as explanatory text in More, not an actionable button. More exposes [Saves], [Request restart] for the host, [Session settings], and [Leave session]/[Close session] appropriate to role. Solo practice permits immediate local rewind/restore/reset with the same confirmation for replacing progress, without a nonexistent peer approval.

Click/tap [Enable sound] appears if browser audio is suspended; volume preferences are local. Fullscreen keeps an obvious [Exit fullscreen] action and explains Esc; if the browser declines fullscreen, keep play usable in the normal layout. Chat focus releases game buttons and visibly says “Typing in chat”; clicking/focusing the game restores game input. Losing page focus releases held keys and push-to-talk immediately and mutes open mic. Returning focus never unmutes automatically. Settings that only affect display/audio/mapping do not independently rewind or reset either client.

## U5 — Shared rewind, load, and restart

The host opens Rewind, chooses 1–10 seconds within available history, and sees “This rewinds both players” before [Request rewind]. Short history reports the available duration and disables impossible choices. U6 supplies a validated save for [Request load]; More supplies [Request restart]. A guest can save/export their own state but asks the host through chat to load a shared save; guest-side loading cannot change multiplayer state.

```text
+------------------------------------------------------------+
| Alex wants to rewind 5 seconds.                            |
| The game is paused for both of you.                        |
|                                                            |
| [Accept rewind]  [Decline]                   12s remaining  |
| Declining leaves the current game paused.                  |
+------------------------------------------------------------+
```

The requester sees “Waiting for Jo” and [Cancel request]; the recipient sees the explicit action, target/save label, impact, [Accept …], and [Decline]. Show a 15-second response window without per-second screen-reader announcements. A cancelled/declined/timed-out request leaves the original state paused and offers the ordinary resume path. Accept transitions to “Restoring both games…”; no further timeline request is available in flight. A transfer failure leaves play paused with [Try again], [Request restart], and [Leave], subject to role. Successful restore reports “Rewound 5 seconds” or “Save loaded” and resumes only after both complete the barrier. Old future inputs cannot reappear as user-visible movement.

Restart says “Start from the beginning? Current unsaved progress will be replaced for both players.” Save loading shows the selected title/time and warns similarly. Dialog X/Esc has the same effect as decline/cancel, never acceptance. For an accepted request still restoring, closing the presentation does not cancel the protocol or resume play; show persistent recovery status over the game.

## U6 — Saves and local data

```text
+------------------------------------------------------------+
| Saves on this device                                   [X] |
| Evening puzzle · Compatible saves                         |
| [Save current point]                         [Import save] |
|                                                            |
| Slot 1 · Today 19:42      [Request load*] [Export] [Delete]  |
| Slot 2 · Yesterday       [Request load*] [Export] [Delete]  |
|                                                            |
| Saves can be removed by your browser. Export a backup.     |
| * Multiplayer: the host requests; both players agree.      |
+------------------------------------------------------------+
```

This panel is scoped to the current game. In solo mode Request load becomes Load; guests see the shared-load explanation instead of that action. Save creation lets the player select a slot, confirms before overwriting an occupied slot, and reports the resulting local saved time. The initial view's empty state has [Save current point] and [Import save]. Imported files validate before insertion. A wrong game/version or invalid save produces an inline error and leaves existing data unchanged. No game/ROM download accompanies Export.

Storage denial/quota/write failure says “Couldn't save on this device” and offers [Export current save] from memory plus [Manage local data]. It must not report a persisted save. Export failure keeps the in-memory state and provides [Retry export]. Deleting a slot names it and requires confirmation. Settings → Local data shows saves/preferences and [Delete local data], with an explicit warning about irreversibility and an opportunity to export first. Clearing local data does not pretend to delete a server account. A fresh browser or cleared storage shows the empty state and Import; absence cannot be confidently labelled as detected eviction.

## U7 — Controls, display, voice, and settings

```text
+------------------------------------------------------------+
| Settings                                               [X] |
| [Controls] [Display & sound] [Connection] [Local data]       |
|                                                            |
| Your input device  [Keyboard v]                            |
| NES button     Mapping                                    |
| Up             Arrow Up          [Change]                  |
| A              X                 [Change]                  |
| B              Z                 [Change]                  |
| …              …                                          |
| [Restore defaults]                                         |
+------------------------------------------------------------+
```

Controls cover all NES buttons, keyboard and detected gamepads, with an input-test indicator. Remapping captures one input in a labelled dialog, offers Cancel, and identifies conflicts before Apply; include the push-to-talk binding in conflict checks. Restore defaults confirms the affected mapping set. Unplugging a selected gamepad pauses and offers [Use keyboard] or reconnect instructions, then the shared resume path. The mapping is local to the current player; host slot assignment remains U3/Session settings and changes only while waiting/paused.

Display & sound includes nearest-neighbor/scanlines, local volume, and audio activation state. Connection exposes the U2 privacy choice and current connection status. Local data opens U6 management. A guest nickname is editable outside active play and explains “Temporary name for this browser session”; no login/account UI is implied.

In chat, Enable voice requests microphone access on click; optional push-to-talk mode explains its binding. Off, permission pending, listening/not transmitting, transmitting, microphone unavailable, and muted states have text. Provide an on-screen hold-to-talk button with keyboard equivalent plus [Mute voice] for incoming audio and [Disable microphone] for local capture; switching away releases transmission. A denied microphone shows “Microphone access was denied. Text chat still works” with [Try again] and browser-settings help, not a blocking modal. No recording/transcription controls are present.

Chat input has a 500-character counter near the limit; oversize cannot send. A rate limit displays the remaining wait without discarding typed text. Disconnected send shows “Not sent” with explicit Retry after reconnect; never imply delivery or automatically duplicate a message. Lobby closure clears chat, and the panel explains “Chat is temporary; messages from before you joined aren't shown.” Messages use plain text with no HTML/link previews or attachments.

Conversational voice settings provide microphone device, local mute, remote mute/volume and optional Push-to-talk mode. Show permission/device/connection failures separately. Enable starts only after user action; reconnect, focus return and device replacement require deliberate unmute. Stop tracks on leave/kick/expiry or peer replacement. Never let a voice retry reset gameplay. Echo cancellation/noise suppression are best-effort browser settings, verified with game audio and speakers as well as headphones.

Session controller mode defaults to Separate P1/P2. Optional Shared P1 explains “Take turns controlling a single-player game.” The host requests Pass controller while paused; the named recipient accepts or declines. Display the sole current owner, release held input on accepted transfer and acknowledge ownership before resume. Decline/cancel leaves the previous owner and timeline intact. Never infer that an arbitrary ROM supports simultaneous co-op.

## U8 — Recovery and session endings

```text
+------------------------------------------------------------+
| Waiting for Alex to reconnect…                             |
| Your game is paused. Alex's place is reserved for 42s.      |
|                                                            |
| [Leave session]                                            |
| When Alex returns, both players confirm before resuming.   |
+------------------------------------------------------------+
```

The timer reflects the server's 60-second reservation after detection, not a new timer restarted by each dialog render. Before detection, a stalled input stream says “Waiting for the other player's connection” and already freezes emulation. A reconnecting player sees progress through “Reconnecting,” “Choose your game again” if necessary, “Restoring game,” and “Ready to resume.” An invite opened on another unauthenticated device cannot claim the reserved slot.

| Trigger | Feedback and safe continuation |
|---|---|
| Slow/background client | “Paused while Jo's browser catches up” or “Return to the game to resume”; release inputs, then require shared resume. |
| State divergence | “Games got out of sync. Restoring the last shared point…”; one automatic recovery. Success asks both to resume; repeated/invalid recovery offers host Request restart or either player's Leave, never silent play. |
| Guest grace expires | Host: “Jo disconnected. Their place is now open,” with Resume solo, Invite, or Close; directory becomes joinable. Guest returning later must join afresh. |
| Host grace expires | “Host disconnected. This session has ended,” then Back to sessions or Continue locally when a usable game/state remains. No host migration. |
| Coordinator restart | “The session ended after a service restart,” then Back to sessions with status/retry or Continue locally. No claim that the lobby survived. |
| Kicked or expired credentials | “You were removed” / “Your session expired”; Back to sessions. No reconnect using revoked credentials. |
| Invalid/closed invite | “This invite is no longer available”; Back to sessions. Do not disclose hidden lobby metadata. |
| Relay/network unavailable | Preserve loaded local game and lobby membership while possible; Retry connection or Leave. Relay-only never silently switches to direct. |
| Service/admission limit | “Sessions are at capacity” / “Please wait before trying again”; retain the creation form and file, Retry when eligible. |

Leave during play confirms its effect on the other player and can offer [Leave and play locally] when feasible. Host closure explicitly says “End this session for both players?” Guest departure pauses the host and frees the slot; host closure removes the directory entry. Coordinating a normal exit happens before local continuation; on service loss it follows the declared session termination. Export remains available while a valid local state is retained. Returning to the directory never silently reopens a closed session.

## U9 — Session moderation and game information

The host's Session settings shows visibility, copy invite, controller assignment while paused/waiting, guest removal, and Close session. Remove player names the affected guest and confirms “They will lose their place and reconnect access.” It does not claim to ban a person across new anonymous sessions. Server-confirmed changes update both clients; failed changes retain the previous state and explain the failure. Browser Back and All sessions from an active room invoke the same leave/close choice rather than silently abandoning the peer.

Game help for a loaded included game shows the confirmed title, creator credits, the requested licence placeholder and controls/how-to-play supplied with the game. It does not repeat Start/Browse actions. User-ROM help says “Host-provided title · Bring your own matching ROM” and explains local file handling; it has no supplied cover image or download action.

Operator removal and temporary admission blocks remain a restricted operational tool/runbook, not a new public admin dashboard. Its required interaction is: authenticated operator identifies a session or admission subject → sees a confirmation naming that target and action → receives success/failure → affected clients get the corresponding U8 removal/capacity state. No public page exposes operator credentials, chat inspection, ROM hashes, or private invites. Exact operational tooling is selected with the deployment package; UI review checks the resulting public feedback and authorization evidence.

## Story coverage and critique checklist

Each row names a first-release story, its visible path, and the edge case that could otherwise leave it incomplete. This is a design traceability check, not evidence the behavior already works.

| Story | Outcome and screens | Required alternate state | Platform acceptance |
|---|---|---|---|
| S01 | Visitor browses every public session, including duplicate titles, with public room search — U1 | Empty/loading/stale/filter-reset; full rows remain visible | AC-01 |
| S02 | Host drops or picks a file and starts with generated defaults/visible visibility — U1→U2→U3 | Invalid/oversize/unsupported/read/hash failure; no filename publication | AC-02 |
| S03 | Visitor starts or discovers the permanent included game — U1→U2/U3, U9 | Zero sessions, missing configuration, download/integrity failure | AC-04 |
| S04 | Guest joins before loading a file — U1/invite→U3 | Concurrent slot loss, full/reserved, stale/closed invite | AC-03, AC-09 |
| S05 | Players prove matching local games — U3 | Wrong exact file, incompatible build/settings, reload/reselect | AC-03 |
| S06 | Host shares an invite and controls visibility — U2/U3/U9 | Clipboard failure; explicit public transition; unlisted omission | AC-01, AC-09–10 |
| S07 | Automatic readiness, default controllers, and shared start — U3→U4 | Start failure/cancel, assignment clears intent; role authority | AC-03, AC-05, AC-09 |
| S08 | Host practices while waiting; newcomer joins deliberately — U3/U4 | Only a prepared guest prompts host; checkpoint join preserves progress | AC-05, AC-09 |
| S09 | Players see/change inline connection policy before peer contact — U2/U7 | Stricter policy wins; relay unavailable; reconnect on change | AC-10–11 |
| S10 | Players see play, chat, and connection status together — U4 | Narrow desktop layout, audio/fullscreen denial | AC-05, AC-08 |
| S11 | Player pauses and both resume deliberately — U4/U8 | Peer absent/not ready; system pause cannot be bypassed | AC-05, AC-09 |
| S12 | Solo player rewinds within available history — U4/U5 | Short history; no peer prompts | AC-07 |
| S13 | Host requests shared rewind and guest decides — U5 | Cancel/decline/timeout, restoring/failure, no concurrent request | AC-06–07 |
| S14 | Player saves local progress without moving shared play — U4/U6 | Empty/overwrite slot, quota/denial, actual persistence feedback | AC-07 |
| S15 | Player imports/exports compatible local saves — U6 | Wrong game/version/malformed save; export retry | AC-07 |
| S16 | Host loads/restarts the shared game with consent — U5/U6 | Guest cannot load independently; both complete barrier | AC-06–07 |
| S17 | Player manages/deletes local data — U6/U7 | Irreversible confirmation, export first, fresh/cleared storage | AC-07 |
| S18 | Player maps keyboard/gamepad and tests inputs — U7 | Binding conflicts, cancellation/defaults, unplug fallback | AC-08 |
| S19 | Player adjusts filters/audio and uses fullscreen — U4/U7 | Audio gesture/denial; local changes don't alter emulation | AC-08 |
| S20 | Player types temporary text chat — U3/U4/U7 | Input suppression, oversize/rate limit, unsent retry, no history | AC-08, AC-10 |
| S21 | Player opts into voice and can stop it — U3/U4/U7 | Permission denied, muted/unavailable, release on blur | AC-08, AC-10 |
| S22 | Players recover a brief disconnect — U8→U3/U4 | Reselect ROM, reservation expiry, authenticated resume | AC-06, AC-09 |
| S23 | Players recover desync safely — U8/U5 | One recovery attempt; repeat/invalid state remains paused | AC-06 |
| S24 | Host loses a guest or leaves themselves — U8/U9 | Guest slot reopens; host loss closes; no host migration | AC-09 |
| S25 | Player leaves and optionally continues locally — U4/U8 | Confirm effect; no viable local state means no continue action | AC-09, AC-12 |
| S26 | Host moderates membership — U9→U8 | Server rejection; revoked reconnect; no anonymous-ban promise | AC-09–10 |
| S27 | Operator removes abuse or limits admission — U9→U8/U2 | Authorized tool confirmation/failure, public feedback only | AC-10–11 |
| S28 | Players understand service restart, capacity, and degraded network — U8/U1 | Loaded game retained; honest retry; no direct privacy fallback | AC-09, AC-11–12 |
| S29 | Visitor understands catalog versus user-file content — U1/U9 | Unverified host label, no supplier links, missing title gate | AC-02, AC-04, AC-10 |
| S30 | Keyboard/screen-reader user completes the core journey — U1–U9 | Focus restore, announced status, picker alternative, no traps | AC-08, AC-12 |
| S31 | Player loses focus/device without stuck input or live microphone — U4/U7/U8 | Chat/game focus distinct; shared pause/resume | AC-05, AC-08 |
| S32 | Reviewer/operator verifies the complete release journey — U1–U9 | Actual browser/demo evidence and operational recovery checks | AC-01–16 |
| S33 | Visitor finds a friend by room/host/code — U1/U9 | Duplicate names, no match, expired code, unlisted non-resolution | AC-14 |
| S34 | Guest enables conversational voice and manages devices — U3/U4/U7 | Echo, unavailable mic, open-mic blur mute, remote mute, independent retry | AC-16 |
| S35 | Players use native two-player/alternating turns or pass P1 — U7/U9 | Single-player explanation, declined handoff, atomic ownership and clear held input | AC-15 |
| S36 | Visitor drops an unknown title on supported hardware — U2/U8 | Experimental label, unsupported hardware, runtime failure, no ROM upload | AC-15 |
| S37 | Visitor reaches play with minimal actions — U1→U2/U3→U4 | Cold download, local selection, browser prompt, cancellation, measured slow/failure states | AC-13, AC-16 |

AC-05's determinism, AC-06's state codec safety, AC-10's server/privacy enforcement, AC-11's cost/load measurements, and AC-12's CI budgets cannot be proven by a screen. The implementation plan retains those engineering checks. This matrix covers their human-visible consequences without replacing technical acceptance.

## Interaction acceptance for implementation

For each story, record the trigger, visible feedback, authorized action, resulting state, and recovery path. The builder's real-browser demo must cover directory → local/catalog host → independent guest join → mismatch correction → automatic prepare/start → play/chat/voice → save/shared rewind → disconnect/reconnect → leave. Include both roles, zero-player discovery, a full-row race, unlisted non-discovery, denied microphone, failed save, and forced-relay denial. Capture matched before/after UI evidence for actual product changes; do not claim these wireframes are product screenshots.

Check that every unavailable action has an accessible reason, every pending operation has an honest status and escape where safe, every destructive/shared operation names its effect, and every failure preserves valid local work. Apply keyboard checks and the narrow-desktop layout to the same journey. Contrast, focus ordering, real text wrapping, canvas sizing, performance, voice/input contention, and actual game instructions remain implementation validation tasks.

## Reusable workflow reference

The reusable workflow is now contributed as Vaseline’s `ui-wireframing` skill. Product-specific decisions remain here. Planning PR #3 includes the merged skill through the updated Vaseline pin; separate tooling PR #4 was closed as superseded.
