This earlier lobby proposal is kept for comparison. The [current ASCII design](lobby-wireframe-v2.md) puts the two included games into the ordinary public room list and makes the first joiner the host.

Audience: Human

# Clean lobby and play wireframe

This is the previous design proposal, not approved behavior or a claim about the running app. The [new direction](lobby-server-rooms-direction.md) and [v2 wireframe](lobby-wireframe-v2.md) supersede its special Play and Host included-game actions. The page sketches below remain available as an earlier iteration. They follow the [115-scenario player inventory](lobby-scenario-inventory.md) and the approved [journey gate](https://github.com/TuringTestee/retro-coop/issues/66). The existing [UI stories S01–S37](browser-nes-ui.md#story-coverage-and-critique-checklist) still govern detailed controls and consent.

DST supplies the clear Browse Games and Host Game paths. Warcraft III shows a distinct room with visible player slots. AoE2 makes room visibility and access legible. [Klei](https://support.klei.com/hc/en-us/articles/5579659658772-DST-How-to-play-split-screen-online-offline-LAN-on-Nintendo-Switch) · [Blizzard](https://news.blizzard.com/en-us/article/23395649/revisiting-the-warcraft-iii-editor) · [AoE2](https://support.ageofempires.com/hc/en-us/articles/360047306372-How-do-I-create-a-multiplayer-match-in-Age-of-Empires-II-Definitive-Edition)

## Rules that keep the interface honest

- Each public row is one actual room. Show all public rooms, including full and playing rooms, with Join only where a new player can enter. Unlisted rooms appear only through an invitation.
- **Play now** starts the selected included game solo. **Host included game** creates a waiting room that a friend can enter. **Host your NES file** opens a waiting room directly. This separation is proposed behavior and changes the earlier automatic solo-start rule.
- A public-room Join uses one action. An invitation URL shows a room preview, then Join. The guest supplies an exact matching local NES file when the game is host-provided; ROM bytes are never sent by the host.
- Two matching, connected players start together automatically. The host may choose Play alone from a waiting room, with a warning that a progressed game cannot admit a late guest in the focused MVP. Password rooms, manual Start, accounts, spectators, and matchmaking are absent from this flow.
- Every state shows only an action the player can take now. Room settings, game help, chat, voice, saves, and recovery appear where they support the current task.

## Page 1 — Find or start a game

```text
RETRO COOP                                   [Host included game]

PLAY NOW              [Super Tilt Bro]  [From Below]
HOST YOUR NES FILE    Public [Change to Unlisted]  [Choose .nes file]
Connection: Standard                         [Change to Relay only]

PUBLIC ROOMS
[Search room, host, or public code...........................]

ROOM / GAME                 HOST          PLAYERS  STATE
Tilt with friends · K7PM4R2X Guest Maya    1 / 2    [Join]
Super Tilt Bro
Tilt rematch · T6Q2H9AW      Guest Noor    2 / 2    Full
Super Tilt Bro
Puzzle night · R4WC2D7K     Guest Rowan   1 / 2    [Join]
From Below · shared controller
Solo challenge · M8Y2F6JK   Guest Iris    1 / 2    Playing · cannot join
From Below

Showing 4 public rooms                          [Previous] 1/1 [Next]
```

**Behavior.** The room list is the largest region. Included-game Play is one action, with download progress, Cancel, Retry, and asset-error feedback in place. The file row accepts drop or picker; the visibility choice is made before choosing a file. A valid file creates a waiting room without a name form. Search resolves room/host names or an exact public code; duplicate names stay separate. Joining a public row reserves Player 2 and opens Page 3 without another Join confirmation. The shared Standard/Relay-only choice applies to hosting or joining before peer contact and can explain its privacy effect inline, without a blocking setup page.

**Variants.** Loading says “Looking for rooms”; an empty directory says “No public rooms yet” without a tall blank panel or duplicate Host button. A stale or failed directory says Retry and prevents joining stale rows. No-match says Clear search. A returning player sees “Your game is still open [Resume] [Leave room]” without losing progress. If a game cannot be downloaded or a file is invalid, the attempted action shows its specific error and retains the other paths.

**Page 1 review.** **Supports:** UJS-1/2/3/7 and inventory A01–A14: immediate play, public discovery, direct file hosting, duplicates, empty/error recovery. **Still needed:** test whether the compact action strip and rows fit a narrow supported desktop and keyboard focus order; show the connection choice in the real row design before Join. **Removed:** game cards, genre/promotional copy, Show lobbies buttons, a second lobby heading, extra filters, separate code entry, and guest nickname in the page header.

## Page 2 — Host a room

```text
< Public rooms                 HOST AN INCLUDED GAME

Game        ( ) Super Tilt Bro
            ( ) From Below · shared controller

Access      (*) Public · appears in Public rooms
            ( ) Unlisted · invitation only
Connection  Standard [Change to Relay only]

                                      [Create room] [Cancel]
```

**Behavior.** This page serves a visitor who chose Host included game on Page 1. Host your NES file uses its direct Page 1 route instead. Create room gives a generated room name and opens Page 3. An unavailable included asset or service capacity error stays here with a specific reason and Retry. Cancel returns to Page 1 without changing the current game.

**Page 2 review.** **Supports:** included-game hosting, visibility, connection, and creation (B01/B08/B09/B10–B12). **Still needed:** an unavailable-asset and capacity-error variant. Local-file validation belongs on Page 1's direct hosting path. **Removed:** duplicate local-file choice, required room naming, password entry, decorative game descriptions, and extra setup steps. Renaming is optional after creation.

## Page 3 — Room before shared play

Host view:

```text
< Public rooms       TILT WITH FRIENDS · K7PM4R2X       Public
Super Tilt Bro       [Copy invitation] [Room settings]

PLAYER 1                              PLAYER 2
You · Host · game ready               Empty · waiting for a player

Your room appears in Public rooms. A friend can also use the invitation.
[Play alone]                          [Close room]
```

After a guest arrives, Player 2 says “Choosing game,” “Connecting,” or “Ready”; room Chat and optional Voice appear. When both players are ready, show “Starting together…” and enter Page 4 automatically. Play alone first explains that a late guest cannot join this progressed game in the focused MVP; Cancel keeps waiting. Host settings can rename the room, change Public/Unlisted, inspect controllers, remove the current guest, or close the room, with role-appropriate confirmation.

Guest view after a public row Join:

```text
TILT WITH FRIENDS                    You are Player 2
Host: Guest Silver · game ready      You: choosing game

Super Tilt Bro: downloading and checking locally... 64%
For a host-provided game: [Choose matching .nes file]

[Chat with host]                       [Cancel join]
```

The included-game line and host-provided-file line are alternatives, never both shown. A mismatch offers Choose another file; failed download offers Retry; an expired reservation says Retry join and rechecks the slot. A guest ready before the host sees “Waiting for host” and may Cancel. An invitation link uses the same room view but first shows a small preview with game, host, occupancy, mode, connection choice, and Join; a closed/full invite explains why Join is unavailable. A one-player game explains shared-controller handoff before Join.

**Page 3 review.** **Supports:** C01–C17 and D01–D12: exact room identity, slots, file match, invitation, pre-game chat, and automatic start. **Still needed:** real UI states for slot races, lease expiry, relay denial, and optional voice permission. The proposed waiting room cannot fulfill approved play-while-waiting late join until that later feature exists. **Removed:** dead Start together button, chat while the host is alone, duplicate Change access button, and a separate invitation page.

## Page 4 — Play

```text
< Public rooms       Super Tilt Bro       Playing with Guest Maya

+------------------------------------------------+----------------------+
|                                                | P1 Silver · Host     |
|                   NES GAME                     | P2 Maya             |
|                                                | Chat [message][Send] |
|                                                | Voice off [Enable]   |
+------------------------------------------------+----------------------+

[Pause] [Save] [Rewind when available] [Fullscreen]
[Game help] [Controls] [Settings] [Room]
```

**Behavior.** The game canvas is dominant. Chat, voice, room actions, game help, saves, local rewind, and settings appear only when usable. Game help supplies real controls/instructions and included-game credits/license placeholder; a host-provided game gets no invented artwork or download link. Room shows players, invitation, current access, and role-specific Leave/Close/Remove. Save reports success only after persistence; shared rewind/load/reset and controller handoff require the existing consent rules when delivered. Returning to Public rooms keeps the game loaded and provides Resume.

**Variants.** Solo play omits Player 2/chat/voice. Pause names its cause and what enables resume. A gamepad disconnect releases held buttons and offers keyboard fallback. Failed microphone permission leaves chat and play available. Failed save states that it was not saved and offers export/retry. Settings changes local controls, display, sound, or connection without silently resetting the game. Leave or Close says who is affected and offers Cancel.

**Page 4 review.** **Supports:** UJS-4/5 and E01–E31: play, help, communication, settings, progress, and quit have contextual entry points. **Still needed:** real paused, save-failure, voice-denial, shared-consent, controller-handoff, and narrow-layout states. **Removed:** an About page, pre-play controls, duplicate Sound button, and room settings mixed into the game toolbar.

## Page 5 — Recover at the point of failure

These are state variants, not a general error dashboard:

```text
ROOM CONNECTION FAILED                 (in Page 3)
Your place is still reserved for this attempt.
[Retry connection] [Cancel join]

GUEST LEFT DURING PLAY                 (over Page 4)
Shared play stopped. This browser still has the loaded game.
[Continue alone, if safe] [Close room]

ROOM CLOSED BY HOST                    (guest returns to Page 1)
This room ended. It cannot be rejoined.
[Browse public rooms] [Continue locally, if safe]
```

Each message must match the actual server and local-game state. Other failures stay beside their action: directory Retry on Page 1, file Choose another on Page 2/3, voice Retry beside Voice, and save recovery beside Save. Never show Continue locally if the current game cannot safely continue, or Retry connection if there is no live room to retry. Automatic reconnect and desync repair remain deferred from the focused MVP.

**Page 5 review.** **Supports:** UJS-5 and the applicable F01–F16 paths by keeping cause and next action together. **Still needed:** separate tested variants for host loss, service restart, reservation expiry, forced-relay denial, runtime failure, and inaccessible storage. **Removed:** one catch-all recovery page, unconditional “progress is safe,” and actions that might be impossible in the current state.

## Core journey check and open behavior change

| Journey | Page path | Result or recovery |
|---|---|---|
| Play an included game now (UJS-1) | 1 → 4 | One Play action, local loading/cancel/retry; no accidental public room. |
| Find and join a room (UJS-2) | 1 → 3 → 4 | One public Join action, exact game match, automatic shared start; full/stale/mismatch recover in place. |
| Host a local NES file (UJS-3/7) | 1 → 3 → 4 | Visibility before file choice, local validation, open Player 2 slot, matching guest file; no ROM transfer. |
| Host an included game (UJS-7) | 1 → 2 → 3 → 4 | Create public/unlisted room, friend sees it or uses invite, both start together. |
| Use play features (UJS-4) | 4 | Game remains dominant; relevant help, chat, voice, controls, saves, and room exit. |
| Recover (UJS-5) | 1–5 | Error stays near its cause and names one valid next action. |
| Keyboard/narrow desktop (UJS-6) | 1–5 | Same journeys and recovery actions, pending real-browser focus and viewport proof. |

**Approval needed before implementation:** The proposal makes Play now a solo action and hosting a waiting-room action. The approved design currently starts the host solo immediately after room creation and allows a progress-preserving later join. This separation is intended to keep the focused MVP honest while late join is deferred, but it changes product behavior and needs a reviewed planning update and user approval. Password rooms and manual Start are omitted because no listed core journey needs them.
