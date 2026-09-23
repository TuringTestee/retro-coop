Retro Coop should let a visitor choose one real public room or host a local NES file from the same first view. The included games begin as 0/2 rooms, the first joiner becomes host, and that host decides when to start. Joining after Start is deferred.

Audience: Human

# Prior lobby UI design: ASCII wireframe v3

**Status:** Superseded by [v6](lobby-wireframe-v6.md) for custom-room game downloads; retained as the prior full lobby baseline. It follows [reference evidence](lobby-references-v2.md), [direction](lobby-server-rooms-direction.md), [journeys](lobby-journeys-v2.md), [scenarios](lobby-scenarios-v2.md), and the [v2 critique](lobby-critique-v2.md). [V2](lobby-wireframe-v2.md) and the [earlier proposal](lobby-browser-proposal.md) remain as prior context; v1 was pruned after v6. These sketches are not runtime evidence.

The approved [room game download amendment](room-rom-transfer.md) replaces the custom-room guest matching-file states below with automatic download, then Prepare. The current app still shows the earlier states until that delivery integrates. Included-game rows and host Start remain.

## Page 1: Find or host a room

```text
RETRO COOP                                               [Settings]

HOST YOUR NES FILE           Access: Public [Unlisted]
[Choose NES file]             or drop a file here

NETWORK PRIVACY  Standard: your peer may see your network address
                 [Use Relay only]  (applies before Host or Join)

PUBLIC ROOMS             [Search room, host, or code............]
Updated just now

ROOM / GAME                  HOST       PLAYERS  STATE / ACTION
Super Tilt Bro  A4Q7M2CX     No host     0/2    Waiting for host [Join as host]
From Below  B9M2K6TR         No host     0/2    Waiting for host [Join as host]
  One controller; share turns with a guest
Tilt with friends  C3R8W5JN  Silver      1/2    Waiting [Join]
  Super Tilt Bro
Puzzle night  D6X4T2QP       Maya        1/2    Waiting [Join]
  Custom NES game; bring matching file
Puzzle break  F7N3P5KL       Rowan       1/2    Waiting [Join]
  From Below; shared controller
Sunday match  E2P9V4MR       Noor        1/2    Playing; Join unavailable
  Super Tilt Bro
Final round  H5K8R3TW        Iris        2/2    Full
  Super Tilt Bro

Showing 7 public rooms                         [Previous] 1/1 [Next]
```

**One forward action per room.** Join as host atomically claims Host/P1 in that exact 0/2 room. A new 0/2 row is published for that included game if the service has capacity. Join on a waiting 1/2 room reserves Guest/P2. Playing, full, reserved, stale, and reconnecting rooms remain visible with the actual reason and no invalid Join. An unlisted room is absent here and opens through its invitation. Search keeps duplicate labels separate by eight-character code.

**Information timing.** Host role, controller mode, and a custom guest's file need are visible before Join. The single Network privacy control is immediately beside the Host and public Join actions and remains available before peer contact. Switching to Relay only explains capacity failure without falling back to direct. Settings contains other local preferences, not a hidden substitute for this choice.

**Variants.** Loading says “Looking for rooms.” Empty says “No public rooms right now” while Choose NES file remains. No match offers Clear search. Stale rows cannot Join and have Retry. If 20 active rooms are full, the 0/2 offers say “Temporarily unavailable — room capacity” until a place opens. A first-claim race says who became host and offers one currently valid next action. Focus returns to the row or search after live changes.

An unlisted invitation opens the same room preview and presents Standard/Relay only beside its one Join action before peer contact. It never creates a public directory row or a second way to enter that room.

**Coverage:** J1/J2/J5/J6 and deferred J4; N01–N13, N24. The one-list Browse/Host split and visible slots/Start are adapted from the [publisher reference study](lobby-references-v2.md).

## Page 2: File check and automatic room creation

Choosing or dropping a file on Page 1 begins this in-place state; there is no setup form and no second Create button.

```text
HOST YOUR NES FILE
Checking the selected file on this device...     [Cancel]

File valid. Creating a Public room...             [Cancel]
```

After confirmation, Page 3 opens with a generated neutral room name. The host may rename it in Room options later. For Unlisted, the second line says “Creating an Unlisted room…” and no public row appears. Only the host sees their selected filename locally; path, filename, and bytes never enter public metadata. If the exact file is a verified included asset, guests may download it; otherwise the room says guests need their own matching file.

Invalid or unsupported input stays beside the picker with Choose another file. Network/capacity failure keeps the valid local selection and offers Retry. Cancelled or stale creation leaves no directory row. No generic explanation appears until an error needs it.

**Coverage:** J5; N14–N22.

## Page 3: Room before Start

First joiner, ready to host:

```text
< Public rooms       SUPER TILT BRO  A4Q7M2CX      Public
                     [Copy invite] [Room options]

PLAYER 1                         PLAYER 2
You - Host - game ready           Open

Start now or wait for a guest.
[Start game]                                      [Leave room]
```

With a guest present, both people can chat **before** a file match or game connection:

```text
PLAYER 1                         PLAYER 2
You - Host - ready               Maya - choosing game

Chat [Message.................................] [Send]
Voice off [Enable voice]

Start now begins solo and releases Maya's pending place.
[Start game]                                      [Leave room]
```

If Maya is ready, Start begins the existing acknowledged two-person barrier instead. The host's action remains one Start button; the sentence beside it changes with state. A From Below room labels the one active controller and explains handoff before the guest agrees to join. Room options contains rename, Public/Unlisted, controller arrangement, remove guest, and Close; only authorized roles see these actions. Leave stays directly reachable while waiting.

Guest view after joining a waiting custom room:

```text
< Public rooms       PUZZLE NIGHT  D6X4T2QP       Public
                     Host: Maya

PLAYER 1                         PLAYER 2
Maya - Host - ready               You - reserved

Choose your exact matching NES file: [Choose NES file]
Chat [Message.................................] [Send]
Voice off [Enable voice]
                                          [Leave room]
```

For an included game, the file line is instead download/check progress with Cancel or Retry; an exact already loaded file is reused. Chat is available before ROM selection because both people already share the room. Chat delivery, draft retention, voice permission, mute, and connection errors appear beside their controls. If the host starts while a guest is still preparing, the guest sees “Host started alone; this room cannot admit a guest now” and returns to the list; the host's game is not reset.

**Coverage:** J1/J2/J3/J6; N03–N10, N23–N25, N28–N31 and pre-ROM communication.

## Page 4: Playing

```text
< Public rooms    Super Tilt Bro  A4Q7M2CX    Playing solo; Join unavailable

+------------------------------------------------+-------------------+
|                                                | P1 You - Host     |
|                 NES GAME                       | P2 No join now    |
|                                                |                   |
+------------------------------------------------+-------------------+

[Pause] [Save] [Fullscreen] [Game help] [Controls] [Room]
```

The game remains loaded when the host browses rooms; Return to game resumes this view. Room contains membership, visibility, and Leave/Close. Solo play has no invitation control because the room cannot admit a guest after Start. A two-person game begun together shows P1/P2, chat, optional voice, and the correct controller arrangement. From Below shows Shared controller and handoff only with two players. Save reports success only after persistence; failures offer retry/export. Help and controls appear only after load.

**Coverage:** J3/J7; N24–N25, N30–N34 and the carried-forward play/help/settings/save/exit journeys. Deferred J4 has no Join control.

## Page 5: Recovery beside its cause

These messages appear on the list, room, or play screen; they are not another page to navigate:

```text
ROOM WAS CLAIMED FIRST (list)
Silver is now host. P2 is open. [Join as guest]

GAME DOES NOT MATCH (guest room)
Your file differs from this host's game. [Choose another file] [Leave]

HOST LEFT (guest room or play)
This session ended. [Browse rooms] [Continue locally, if safe]

ROOM CAPACITY (list)
New empty rooms are temporarily unavailable. Existing waiting rooms remain listed.
```

Every next action is checked against current membership. A closed room never offers Retry together; a full or playing room never offers Join; a failed save never claims success. An interrupted session explains whether loaded local progress is safe before offering Continue locally. Status announcements and focus remain usable by keyboard.

**Coverage:** J1/J2/J5/J7; N04, N06–N07, N19, N28–N29, N32–N34.

## Feature-to-journey UI check

| Feature | Entry when usable | Feedback/recovery |
|---|---|---|
| First claim or guest Join | One state-specific action on a joinable row | Exact role/room confirmation; race or capacity returns to a valid row. |
| Local-file hosting | One drop/picker after access/privacy choice | Local check, creating, confirmed room; invalid/cancel/capacity retains a useful next action. |
| Host Start | One button in the ready host room | Solo or shared effect beside the button; failed start retains the room/game. |
| Invitation and room management | Room options in the room; Room during play | Copy confirmation, role-authorized changes, Leave/Close outcome. No solo-play invite that cannot work. |
| Chat and voice | Occupied waiting room and two-person play | Delivery or permission/connection feedback beside the control; draft survives retry. |
| Game help, controls, save | Loaded-game toolbar | Relevant instructions, conflict/status, persistence result and recovery. |
| Search, pagination, privacy | Public list at the moment of discovery/Join | No-match/clear, focus-safe page changes, relay capacity explanation. |

## Final six-rule check

| Rule | Evidence in this design | Limit |
|---|---|---|
| Detailed journeys | J1/J2/J3/J5/J6/J7 traverse Pages 1–5 with outcomes and recovery; J4 is explicitly deferred. | Real-browser walks still required. |
| Every feature has UI support | The table above names each entry and recovery; pre-ROM chat is drawn in Page 3. | Implementation behavior unverified. |
| Information just in time | Role/mode/file/privacy appear before Join; Start effect changes beside Start; failures explain recovery where they occur. | Visual timing/density needs inspection. |
| One forward path | One row action, one file pick/drop route, one host Start; no Create form or special catalog cards. | Races need live validation. |
| Concise and consistent | Same eight-character code, role and status terms across pages; no advertising or duplicate game list. | Long labels, zoom and narrow viewport need rendering proof. |
| Borrow before inventing | [DST and Warcraft III evidence](lobby-references-v2.md) supports browse/host separation and visible slots/Start. | Atomic offer/claim networking is a Retro Coop implementation to verify. |

## Recommendations for the essential build

1. Ship 0/2 offers behind a server/client compatibility gate, so intermediate deployments do not expose unclaimable rows.
2. Keep the existing direct file-host path and inline privacy choice; test a second browser finding and joining a player-owned room without ROM, path, or filename transfer.
3. Verify host Start alone and with a ready guest, including the case where P2 is preparing. A solo-started room stays visible but Join unavailable.
4. Test every journey with wide/narrow screenshots, keyboard focus, room races, empty/full/stale lists, From Below controller wording, waiting chat, and in-place recovery. Defer later join as a separate feature.
