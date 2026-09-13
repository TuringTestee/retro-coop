# Retro Coop UI design

Visitors see every public game session, drop a local ROM to host, and join a two-player room with a clear next step. The game stays central while chat, controller ownership, and shared pause/recovery remain visible. These text wireframes cover the first-release stories and failure states; they are a design proposal, not a working interface or a usability-test result.

## Scope and reading guide

This companion to [the platform design](browser-nes-platform.md) covers AC-01–AC-12 at the interaction level. It adds no gameplay spectators, accounts, password rooms, cloud saves, recordings, mobile controls, or emulator compatibility promises. The existing browser/network, cost, and rights constraints still apply. Labels such as “Evening puzzle,” player names, counts, and timers are illustrative. “Featured homebrew” is a placeholder for the unspecified special Tetris variant, not an approved title or invented ruleset.

The candidate is intended for review in [planning PR #3](https://github.com/TuringTestee/retro-coop/pull/3), under [epic #2](https://github.com/TuringTestee/retro-coop/issues/2). ASCII establishes hierarchy, actions, and state changes. Real-browser visuals, accessibility checks, network evidence, and user approval are still required later. UI labels use “game matches” and “waiting for connection”; hash algorithms and protocol epochs stay in the engineering specification.

Square brackets denote controls. A disabled control is explicitly labelled unavailable with nearby explanatory text. Full/Reserved are status text, not misleading clickable buttons. Screens U1–U9 and stories S01–S32 provide stable references for implementation and review.

## Direction and layout

Use a restrained arcade theme: dark charcoal page, slightly lighter panels, warm off-white text, and one bright accent for the next action. Reserve amber for attention and red for errors/destructive actions, always paired with words or icons. Body text uses a readable system sans-serif; a pixel-style wordmark is optional. No scanlines on page text, flashing decoration, fabricated cartridge art, or automatic background gameplay.

At a wide desktop viewport, center a content area around 1200 px. Directory rows stay compact so multiple games are immediately visible. Session layout gives roughly three quarters of the width to play and one quarter to players/chat, with the game preserving the emulator's 256:240 source ratio. Do not stretch its pixels to match these schematic boxes. Narrow desktop windows stack the side panel below play and expose a chat tab with an unread marker; they must retain every action without horizontal page scrolling. This responsive treatment does not expand first-release support to mobile play.

Use at least 16 px body text, clear focus outlines, comfortably sized controls, readable contrast, and reduced-motion behavior. Screen-reader labels name the game and host for each Join action. Announce join outcomes and pauses politely; do not announce every heartbeat, game frame, or countdown tick. Dialogs receive focus and return it to their trigger when closed. There is no drag-only, hover-only, color-only, or pointer-only task.

## Iteration record

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

Final self-critique: the permanent homebrew entry is now honest with zero players, and every first-release story below has an entry point, feedback, and completion/recovery path. The game-specific title, image, instructions, two-player behavior, and rights remain unknown; these are explicit content gates rather than visual blanks a builder should guess. ASCII cannot validate actual density, contrast, audio/input interactions, or discoverability; the implementation must supply that evidence. Independent local review is recorded on the PR and is separate from this author's critique.

## U1 — Directory

```text
RETRO COOP                             Guest Alex [Settings]

+------------------------------------------------------------+
| FEATURED HOMEBREW · [Title pending]                         |
| Game included · Always available to start                   |
| [Start a session]   [Browse its sessions (2)]   [About]      |
+------------------------------------------------------------+

LIVE SESSIONS (4)                              [Host a game]
Game / host                 Status          Players   Action
------------------------------------------------------------
Evening puzzle · Alex        Waiting         1 / 2     [Join]
  Bring your own matching ROM
Featured game · Jo           Playing solo    1 / 2     [Join]
  Game included
Space adventure · Sam        Playing         2 / 2     Full
  Bring your own matching ROM
Featured game · Pat          Reconnecting    2 / 2     Reserved
  Game included

+------------------------------------------------------------+
| Drop a .nes file here to host, or [Choose file]              |
| Your file stays on this device. Joiners need their own copy.|
+------------------------------------------------------------+
```

Default listing shows all admitted public sessions, including multiple sessions with the same label. Each row includes host, content source, occupancy, lifecycle status, and an accurate action. The platform does not certify user-entered game labels; an adjacent information label says “Host-provided title.” Do not show private filenames, ROM hashes, third-party download links, private sessions, or auto-generated artwork. Guest identity is a temporary nickname; Settings explains that it is not an account.

Featured “Browse its sessions” filters the directory with a visible “Featured game” chip and [Show all sessions]. With no sessions, show “No sessions yet” and keep [Start a session] active when the catalog asset is configured. Loading the directory uses row placeholders; a failed connection shows “Can't update sessions” and [Retry], marks old rows stale, and disables joining stale rows until refreshed. An empty directory says “No public sessions yet. Start one and invite a friend.” The featured entry and hosting affordance remain visible. Development without authorized content shows “Featured game not configured,” no playable claim, and a disabled Start action.

Join reserves an available slot on the server before U3 opens; a race shows “That place was just taken” with [Back to sessions]. Full or reserved sessions cannot admit visitors; there is no implied spectating. Browse-filter counts and row states update together. Directory changes retain keyboard focus and do not move the selected row out from under a click.

## U2 — Create session and connection privacy

The file drop and file picker enter the same local validation flow. Opening [Host a game] opens this dialog with a file chooser if none has been selected. Catalog Start uses the same name/visibility choices with the authorized game fixed and local-file controls omitted.

```text
+------------------------------------------------------------+
| Host a game                                            [X] |
| Game file: Ready on this device       [Choose another file] |
| Session game title  [Evening puzzle                       ] |
| Other players will see this title, not your filename.       |
|                                                            |
| Visibility  (o) Public — listed for everyone                |
|             ( ) Unlisted — people with the invite can join |
|                                                            |
| Joiners need their own matching ROM.                       |
| [Cancel]                                  [Create session] |
+------------------------------------------------------------+
```

The title starts blank for user files, with a neutral example placeholder; do not derive it from the filename. During validation, show “Checking your file…” and make Create unavailable. Oversize, archive, malformed, unsupported mapper/region, read failure, and hashing failure each preserve the form and offer [Choose another file]. Show the 8 MiB/.nes constraint by the chooser. A cancelled chooser leaves the previous valid selection intact. A catalog download displays progress; integrity failure does not launch and offers [Retry] or [Back]. Creation rejection due to rate/capacity limits retains local choices and provides a retry path, with a server-provided wait duration where available.

Privacy is decided before any peer connection, not merely before gameplay. Metadata-only lobby entry and chat may proceed first. The first peer-connection attempt opens this panel on each device; it is also reachable from U3/U7:

```text
+------------------------------------------------------------+
| Connect to the other player                                |
| Direct connections may share your network address with     |
| the other player.                                         |
| (o) Standard connection — direct when available             |
| ( ) Relay only — hide your address from the other player    |
| Relay availability is limited.                            |
| [Stay in lobby]                                  [Connect] |
+------------------------------------------------------------+
```

Record the choice on that device. If either participant requires relay-only, both ends must use a relay-only connection before peer contact; the stricter choice wins. A denied/unavailable relay offers [Retry] or [Stay in lobby], never an automatic direct fallback. Switching privacy mode while connected pauses and reconnects with the new policy before shared resume. A text status shows Standard or Relay only once connected. Do not promise anonymity from the relay/service operator.

## U3 — Waiting room and shared start

```text
< All sessions       Evening puzzle        Public [Copy invite]
+-------------------------------+----------------------------+
| PLAYERS                       | YOUR GAME                  |
| P1  Alex · Host   Ready       | Choose your matching ROM.  |
| P2  You           Needs game  | [Choose file] or drop here  |
|                               | File stays on this device. |
| [Controls]                    |                            |
| [Connection privacy]          | [Ready — unavailable]      |
|                               | Load a matching game first.|
+-------------------------------+----------------------------+
| CHAT                                                       |
| Alex: Hello!                                               |
| [Write a message…                                ] [Send]  |
| Voice off [Enable push-to-talk]                            |
+------------------------------------------------------------+
```

The host sees [Practice alone], [Swap controllers], a guest action menu, visibility controls, and [Start together] when eligible. The guest sees [Ready]/[Not ready] and [Leave session]. Each player's readiness is explicit; a nickname never grants host authority. Copy invite confirms “Invite copied” or offers selectable text if clipboard access fails. Unlisted rooms carry “Unlisted · Invite required”; revealing/copying the invite is deliberate. Changing to public confirms “This session will appear in the public directory” before publishing. Changing to unlisted removes its public listing; explain that people with an existing invite can still join.

Game and connection checks are separate short rows: “Game matches,” “Connection ready,” and “Controller 2 assigned.” Their pending/error states explain why Ready is unavailable. File mismatch says “This is a different version of the game. Choose the exact same file as the host” with [Choose another file]; no download suggestion. Build/settings mismatch says “This session uses an incompatible version” and offers [Reload compatible session] if available, otherwise [Back to sessions]. Reload warns that a local ROM may need reselection. This action must not silently reset an active shared timeline. Compatibility details may live in a collapsed Details section, not the primary flow.

When both players are ready, the host sees [Start together] and the guest sees “Waiting for Alex to start.” Show “Starting together…” until both acknowledge. A failed start returns to the waiting state with the failed prerequisite explained. If a guest joins during host practice, pause the host immediately and say “A player joined. Start together from the beginning or load a save.” Both players confirm the selected starting point; do not insert the guest into solo progress. Swapping controllers clears readiness for both and announces the new assignments.

For catalog lobbies, replace the local chooser with “Game included · [Load game]” and progress, then matching status. Loading is a deliberate interaction and can unlock browser audio. Chat works before ROM matching. Voice enables only once a peer connection and microphone permission are available.

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

Both players can request Pause; it pauses the shared timeline and identifies the requester. Resume requires both players to be present and acknowledge readiness, then the host selects [Resume together]. While awaiting the other player, show “Waiting for Jo to resume” instead of an apparently broken button. System pauses (connection, focus, disconnected controller, slow device) use U8 and cannot be bypassed while their prerequisite is unresolved.

Save is local and non-disruptive at a committed frame. It opens U6 and reports success only after persistence succeeds. Rewind is host-only in multiplayer; guests see “Host controls shared rewind” as explanatory text in More, not an actionable button. More exposes [Saves], [Request restart] for the host, [Session settings], and [Leave session]/[Close session] appropriate to role. Solo practice permits immediate local rewind/restore/reset with the same confirmation for replacing progress, without a nonexistent peer approval.

Click/tap [Enable sound] appears if browser audio is suspended; volume preferences are local. Fullscreen keeps an obvious [Exit fullscreen] action and explains Esc; if the browser declines fullscreen, keep play usable in the normal layout. Chat focus releases game buttons and visibly says “Typing in chat”; clicking/focusing the game restores game input. Losing page focus releases held keys and push-to-talk immediately. Settings that only affect display/audio/mapping do not independently rewind or reset either client.

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

In chat, Enable push-to-talk first explains its binding and requests microphone access on click. Off, permission pending, listening/not transmitting, transmitting, microphone unavailable, and muted states have text. Provide an on-screen hold-to-talk button with keyboard equivalent plus [Mute voice] for incoming audio and [Disable microphone] for local capture; switching away releases transmission. A denied microphone shows “Microphone access was denied. Text chat still works” with [Try again] and browser-settings help, not a blocking modal. No recording/transcription controls are present.

Chat input has a 500-character counter near the limit; oversize cannot send. A rate limit displays the remaining wait without discarding typed text. Disconnected send shows “Not sent” with explicit Retry after reconnect; never imply delivery or automatically duplicate a message. Lobby closure clears chat, and the panel explains “Chat is temporary; messages from before you joined aren't shown.” Messages use plain text with no HTML/link previews or attachments.

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

Featured About shows the confirmed title, creator credits, actual licence/permission notice, controls/how-to-play supplied with the game, and Start/Browse actions. This panel cannot be finished until the variant is specified. User-ROM information says “Host-provided title · Bring your own matching ROM” and explains local file handling; it has no supplied cover image or download action.

Operator removal and temporary admission blocks remain a restricted operational tool/runbook, not a new public admin dashboard. Its required interaction is: authenticated operator identifies a session or admission subject → sees a confirmation naming that target and action → receives success/failure → affected clients get the corresponding U8 removal/capacity state. No public page exposes operator credentials, chat inspection, ROM hashes, or private invites. Exact operational tooling is selected with the deployment package; UI review checks the resulting public feedback and authorization evidence.

## Story coverage and critique checklist

Each row names a first-release story, its visible path, and the edge case that could otherwise leave it incomplete. This is a design traceability check, not evidence the behavior already works.

| Story | Outcome and screens | Required alternate state | Platform acceptance |
|---|---|---|---|
| S01 | Visitor browses every public session, including duplicate titles — U1 | Empty/loading/stale/filter-reset; full rows remain visible | AC-01 |
| S02 | Host drops or picks a file and publishes a chosen label/visibility — U1→U2→U3 | Invalid/oversize/unsupported/read/hash failure; no filename publication | AC-02 |
| S03 | Visitor starts or discovers the permanent included game — U1→U2/U3, U9 | Zero sessions, missing configuration, download/integrity failure | AC-04 |
| S04 | Guest joins before loading a file — U1/invite→U3 | Concurrent slot loss, full/reserved, stale/closed invite | AC-03, AC-09 |
| S05 | Players prove matching local games — U3 | Wrong exact file, incompatible build/settings, reload/reselect | AC-03 |
| S06 | Host shares an invite and controls visibility — U2/U3/U9 | Clipboard failure; explicit public transition; unlisted omission | AC-01, AC-09–10 |
| S07 | Both ready, assigned controllers, and shared start — U3→U4 | Start failure, assignment clears ready; role authority | AC-03, AC-05, AC-09 |
| S08 | Host practices while waiting; newcomer joins deliberately — U3/U4 | Practice pauses; both choose reset or accepted save | AC-05, AC-09 |
| S09 | Players choose connection privacy before peer contact — U2/U7 | Stricter policy wins; relay unavailable; reconnect on change | AC-10–11 |
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
| S29 | Visitor understands content source and featured rights — U1/U9 | Unverified host label, no supplier links, missing title gate | AC-02, AC-04, AC-10 |
| S30 | Keyboard/screen-reader user completes the core journey — U1–U9 | Focus restore, announced status, picker alternative, no traps | AC-08, AC-12 |
| S31 | Player loses focus/device without stuck input or live microphone — U4/U7/U8 | Chat/game focus distinct; shared pause/resume | AC-05, AC-08 |
| S32 | Reviewer/operator verifies the complete release journey — U1–U9 | Actual browser/demo evidence and operational recovery checks | AC-01–12 |

AC-05's determinism, AC-06's state codec safety, AC-10's server/privacy enforcement, AC-11's cost/load measurements, and AC-12's CI budgets cannot be proven by a screen. The implementation plan retains those engineering checks. This matrix covers their human-visible consequences without replacing technical acceptance.

## Interaction acceptance for implementation

For each story, record the trigger, visible feedback, authorized action, resulting state, and recovery path. The builder's real-browser demo must cover directory → local/catalog host → independent guest join → mismatch correction → ready/start → play/chat/voice → save/shared rewind → disconnect/reconnect → leave. Include both roles, zero-player discovery, a full-row race, unlisted non-discovery, denied microphone, failed save, and forced-relay denial. Capture matched before/after UI evidence for actual product changes; do not claim these wireframes are product screenshots.

Check that every unavailable action has an accessible reason, every pending operation has an honest status and escape where safe, every destructive/shared operation names its effect, and every failure preserves valid local work. Apply keyboard checks and the narrow-desktop layout to the same journey. Contrast, focus ordering, real text wrapping, canvas sizing, performance, voice/input contention, and actual game instructions remain implementation validation tasks.

## Notes for a future skill

This task does not create or install a skill. The reusable process worth extracting later is: read the agreed stories and exclusions; sketch the primary journey in the conversation; criticize concrete missing states; revise the screens; trace each story to a screen and an alternate path; independently review; then store the final design with a short iteration record. Keep product-specific controls and policy out of that future generic skill. Distinguish author critique, user feedback, independent review, and measured usability evidence; none substitutes for the others.
