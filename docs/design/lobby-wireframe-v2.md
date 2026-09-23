Retro Coop opens on one list of real public rooms. The two included games begin as empty 0/2 rooms; the first person to join becomes host and can start whenever ready. Anyone can publish a room from a local NES file, and other browsers can join it with a matching copy.

Audience: Human

# Prior lobby UI design: ASCII wireframe v2

**Status:** Superseded by [v3](lobby-wireframe-v3.md), kept as an iteration record. It was never implemented or approved production behavior. This version followed the [reference study](lobby-references-v2.md), [direction](lobby-server-rooms-direction.md), [journeys](lobby-journeys-v2.md), [scenarios](lobby-scenarios-v2.md), The first draft and its critique were pruned when v6 became current; the [earlier proposal](lobby-browser-proposal.md) remains as source context.

## Design principles and review checks

1. **Detail every journey.** For each player goal, show arrival, the next action in each state, feedback, outcome, and recovery. The [journey map](lobby-journeys-v2.md) and [scenario inventory](lobby-scenarios-v2.md) are the coverage checklist; a feature name alone does not count.
2. **Support every visible feature in the UI.** A feature needs a discoverable entry, its usable state, feedback, and an exit or recovery path. If those are missing, add the state or remove the feature from this design.
3. **Present information just in time.** Show the first-join host role on a 0/2 row, matching-file needs when a guest considers a custom room, Start's effect when the host can start, and transfer choices only when a guest joins ongoing play. Do not preload those details on unrelated pages or hide them at the decision point.
4. **Give each journey one clear forward path.** The list has one action per joinable row; the file-host path has one Create action; the room has one host Start action. Remove duplicate navigation and competing calls to action. Keyboard and assistive input use the same path, and recovery may branch when the original action fails.
5. **Keep pages concise and consistent.** Use the same room code, role names, status words, and control placement across list, room, and game. Keep only information or controls that help a player decide, act, or understand current state; remove promotion and repeated explanation.
6. **Borrow before inventing.** When uncertain, inspect successful comparable products and adapt a documented interaction. The [reference study](lobby-references-v2.md) explains why Browse/Host separation and visible slots/Start fit here, and where those games' patterns do not transfer.

## Page 1: All public rooms

```text
RETRO COOP                    [Host your NES file] [Settings]

PUBLIC ROOMS                [Search name, host, or code........]
Updated just now

ROOM / GAME                         HOST       PLAYERS   NEXT ACTION
Super Tilt Bro  A4Q7                No host     0/2      [Join as host]
From Below  B9M2                    No host     0/2      [Join as host]
  One game controller; share turns with a guest
Tilt with friends  C3R8             Silver      1/2      [Join]
  Super Tilt Bro | Waiting
Puzzle night  D6X4                  Maya        1/2      [Join]
  Custom NES game | Waiting | Bring matching file
Sunday match  E2P9                  Noor        1/2      [Join ongoing game]
  Super Tilt Bro | Playing
Final round  F7N3                   Rowan       2/2      Full
  Super Tilt Bro | Playing

Showing 6 public rooms                       [Previous] 1/1 [Next]
```

**Actions → next state.** A 0/2 Join as host atomically claims Host/P1 and opens Page 3. If another person wins the claim, the updated row offers Join as guest if P2 remains open, and the replenished 0/2 row offers another Host claim. A 1/2 Join reserves P2 and opens Page 3. Join ongoing game opens Page 3 in guest preparation and then the Page 4 late-join flow. Host your NES file opens Page 2. Settings includes connection privacy before peer contact and local preferences. The list contains service-created and player-created rooms without separate sections or cards.

**State variants.** Loading says “Looking for rooms.” Empty says “No public rooms right now” while the existing Host your NES file action stays available. Search with no match offers Clear search. Failed refresh marks old rows stale, disables their Join buttons, and offers Retry. If room capacity prevents a fresh 0/2 offer, say “New empty rooms are temporarily unavailable”; occupied joinable rooms remain usable. Full, reserved, reconnecting, and unsupported-late-join rows remain visible with an honest reason instead of an invalid button. Unlisted rooms never appear here.

**Coverage:** J1/J2/J5/J6; N01–N13, N24. The single list and action labels follow the [DST Browse/Host evidence](lobby-references-v2.md); exact room identity/open slots follow the Warcraft III evidence.

## Page 2: Host a game from your NES file

```text
< Public rooms                            HOST A GAME

Game file      [Choose NES file]
               Super_Tilt_Bro_(E).nes - checked on this device
Public name    [Tilt with friends.........................]
Access         (x) Public   ( ) Unlisted

Guests will need their own exact matching file.
This local file and its path will not be published.

                                      [Create room] [Cancel]
```

**Actions → next state.** Selecting or dropping a file validates it locally. Create room opens Page 3 as Host/P1 and adds exactly one public row; Unlisted creates only an invite. The public row uses the chosen public name and verified game identity if known, never the local path. If the exact file matches a verified included asset, the guest message changes to “Guests can download this included game.” A host may choose a different file without disturbing an existing room until explicitly replacing it.

**State variants.** Invalid, unreadable, unsupported, or unqualified files show their specific result beside the picker. Create shows progress; cancellation, service failure, and capacity failure keep the valid selection and never leave a ghost row. The host can change connection privacy in Settings before creation.

**Coverage:** J5; N14–N22.

## Page 3: Room and player slots

First joiner of the empty Super Tilt Bro room:

```text
< Public rooms          SUPER TILT BRO  A4Q7       Public
                       [Copy invite] [Room options]

PLAYER 1                         PLAYER 2
You - Host - game ready           Open

Start now, or wait for another player.
[Start game]                                    [Leave room]
```

If Player 2 is still preparing, the host sees “Guest is preparing. Start now to play alone; they can join your ongoing game when ready.” Start remains available when the host's game is ready. A From Below room says “One game controller; agree who controls it” and offers handoff after a second person joins.

Guest who joined an existing or player-created room:

```text
< Public rooms          TILT WITH FRIENDS  C3R8   Public
                       Super Tilt Bro | Host: Silver

PLAYER 1                         PLAYER 2
Silver - Host - ready             You - preparing

Choose the exact matching game: [Choose NES file]
The host's file is not sent to you.
                                          [Leave room]
```

For a verified included game, the file line instead says “Downloading and checking Super Tilt Bro…” with Cancel/Retry as appropriate; it never asks for a picker unless the download cannot be used. Once ready, the guest sees “Waiting for host to start” or “Joining the host's ongoing game.” Room options contains access, public label, controller roles, remove guest, and close only for the host. Copy invite and Leave remain directly reachable. A guest sees no host-only control.

**State variants.** A lost 0/2 claim shows the updated Host/Guest assignment. A failed download keeps the host role only while a retry is possible; Leave releases it. Mismatch keeps the guest reservation until its real deadline and offers Choose another file or Cancel. A closed/full invite explains why Join is unavailable. Connection privacy is visible in Settings before peer contact, with its effect explained there.

**Coverage:** J1/J2/J3/J6; N03–N10, N23–N25, N28–N31.

## Page 4: Playing and later join

```text
< Public rooms     Super Tilt Bro  A4Q7       Playing - 1/2

+------------------------------------------------+-------------------+
|                                                | P1 You - Host     |
|                 NES GAME                       | P2 Open           |
|                                                | [Copy invite]     |
+------------------------------------------------+-------------------+

[Pause] [Save] [Fullscreen] [Game help] [Controls] [Room]
```

**Actions → next state.** The game stays loaded when the host browses rooms and returns with Return to game. Room contains access, players, invitation, Leave, and Close. A joined guest adds chat/optional voice beside the game; alone, those controls are absent. The guest's play view names their controller role and omits host management. From Below says “Shared controller” and exposes handoff only when two people are present.

With two players, the player area changes in place:

```text
P1 You - Host                 P2 Maya - Connected
Chat  [Message................] [Send]
Voice: Off [Enable]            [Mute player]
```

Send confirms only after delivery, preserves an unsent message on failure, and offers Retry. Voice controls show permission and connection state beside the action; denial leaves chat and play usable. Mute player affects only this browser. These controls are absent with one player.

When a guest joins a progressed game, keep the host's canvas visible until a safe pause. Then show:

```text
MAYA IS READY TO JOIN
Your current game is preserved.
[Continue current game together] [Restart together] [Keep playing alone]
```

Continue transfers validated state, then both resume only after acknowledgement. Restart asks both people to agree. Keep playing alone releases the guest with an explanation. If transfer fails, keep the old timeline paused and offer Retry or Resume solo. A guest sees “Waiting for host” and may Cancel. Do not reset progress merely because someone clicked Join.

**Coverage:** J3/J4/J7; N24–N34 and carried-forward play/help/settings/communication journeys.

## Page 5: Recovery in place

These are overlays or inline states on Pages 1, 3, and 4, not another destination:

```text
ROOM WAS CLAIMED FIRST (Page 1)
Silver is now host. P2 is open.
[Join as guest] [Join another empty room]

GAME DOES NOT MATCH (Page 3)
This file differs from the host's exact game.
[Choose another file] [Leave room]

HOST LEFT (guest on Page 3 or 4)
This session ended. Your local game remains available if safe.
[Browse rooms] [Continue locally, if safe]

NEW ROOM TEMPORARILY UNAVAILABLE (Page 1)
Existing joinable rooms are still listed.
[Retry] [Host your NES file]
```

Every action is conditional on current membership and safe local state. A closed room never offers Retry together; a full room never offers Join as guest; an interrupted save never claims success. Directory updates and errors announce status without moving keyboard focus unexpectedly.

**Coverage:** J1/J2/J4/J5/J7; N04, N06–N07, N19, N26–N29, N32–N34 and earlier recovery cases.

## Feature-to-journey UI check

| Visible feature | Entry and usable state | Feedback and recovery |
|---|---|---|
| Join as host / Join / Join ongoing game | One row action reflects 0/2, waiting 1/2, or joinable playing 1/2. | Claim/reservation status appears in that room; a race shows the updated role and a valid next row. |
| Host your NES file | One list action opens Page 2; Create becomes usable after local validation. | Creation confirms the exact room; file/capacity failures retain the selection and offer correction. |
| Search and pagination | The list keeps one query and one result set. | No match offers Clear; refresh failure marks stale rows; page changes keep focus predictable. |
| Start game | Host-only in Page 3 once the host's game is ready. | Says whether Start begins solo or with a ready guest; loading/error remain in the room. |
| Invitation and room options | Copy invite and Room options appear in a room; Room opens the same management controls during play. | Copy confirmation or selectable fallback; access/close changes update that room or explain rejection. |
| Game help and Controls | Game toolbar while a game is loaded. | Help names actual controls; remapping reports conflicts and can cancel without losing prior bindings. |
| Save | Game toolbar while a game is loaded. | Only persisted saves report success; failure offers retry/export without losing current play. |
| Chat and Voice | Player area only with two connected people. | Delivery, mute, permission, and connection state appear at the control; failed chat retains the draft. |
| Settings | Header before play and while browsing; includes connection privacy before peer contact. | Changes show their effect or refusal and preserve the current room/game. |
| Leave / Close | Leave is direct in the waiting room and inside Room during play; Close is host-only. | States who is affected, offers Cancel, then returns to the public list with the actual result. |

This table checks design coverage. It is not evidence that the features work in the current build.

## Step 7 final principle check

| Principle | Design evidence in this version | Design result and remaining proof |
|---|---|---|
| Detailed journeys | J1–J7 are mapped through Pages 1–5; N01–N34 and the earlier inventory cover ordinary and recovery states. | Covered in design; a real browser walkthrough must test each applicable path. |
| Every visible feature has UI support | The feature-to-journey table above names entry, usable state, feedback, and recovery; Page 4 draws two-person chat/voice. | Covered in design; runtime behavior remains unverified. |
| Information just in time | Page 1 shows host role and custom-file need before Join; Page 3 shows Start's effect; Page 4 shows progress-transfer choices when a guest joins. | Met in the ASCII pages; visual density and timing need browser inspection. |
| One clear forward path | Each joinable row has one state-specific Join action; the file form has one Create; the host room has one Start. Invitation is a separate entry to the same room. | Met in the proposed pages; disabled/race states need live validation. |
| Concise and consistent | One directory, stable room code/role/status terms, no special game cards or promotional copy; room controls stay together. | Met in the proposed pages; long names, zoom, and narrow widths need real rendering. |
| Borrow from successful peers | The [reference study](lobby-references-v2.md) ties Browse/Host and visible slots/Start to Klei and Blizzard sources and rejects nontransferable behavior. | Met for these interaction choices; novel networking behavior needs its own tests. |

The design rules are satisfied at wireframe fidelity where marked. None of these rows claims that the current application already satisfies them.

## What changed from v1

- Empty rows now say **Join as host**; playing rooms show explicit later-join status.
- The host sees what Start does while a guest is preparing. A guest sees the exact-file requirement or verified included-game download.
- The room and play screens name role, controller arrangement, and progress-preserving late join.
- Recovery actions are attached to their real page and offered only when valid. Leave remains visible in the room; the game toolbar uses Room for session actions.

## Recommendations and remaining work

1. **Build the room lifecycle before polishing visuals.** Atomically claim 0/2 offers, replenish the last empty included-game room, and preserve occupied room identity. Verify concurrent first joins, capacity exhaustion, restart, and cleanup in real multi-browser tests.
2. **Make manual Start and later join one coherent flow.** The host can start solo, but a playing 1/2 row should advertise Join only once progress-preserving transfer and consent work. Until then, show the row as Playing with Join unavailable and explain why.
3. **Keep the custom-file privacy promise precise.** A host's local path, bytes, and filename never enter public room metadata. Verify a second device can discover the room, choose an exact matching file, connect, and play; a local screenshot is insufficient evidence.
4. **Test the list at real densities.** Use zero, one, and many rooms; duplicates; live status changes; keyboard navigation; a narrow supported desktop; zoom; and long names. Keep a single directory and remove any separate included-game launchers.
5. **Review this behavior change as a plan amendment.** Current approved documents and code use browser-created rooms, immediate solo start, and special included-game launchers. The final target here changes those rules and needs reviewed product/technical alignment before implementation.
