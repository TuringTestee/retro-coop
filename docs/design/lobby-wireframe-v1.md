Retro Coop opens on one public room list. An empty included-game room becomes a real player-hosted session when the first person joins; a player can also create a room from a local NES file.

Audience: Human

# Lobby ASCII wireframe, iteration 1

This first screen set uses the [direction](lobby-server-rooms-direction.md), [journeys](lobby-journeys-v2.md), and [scenario inventory](lobby-scenarios-v2.md). It is a proposal for critique, not the final design or implemented UI.

## Page 1: Public rooms

```text
RETRO COOP                                            [Host a game]

PUBLIC ROOMS                          [Search room, host, or code.......]
Connection: Standard [Change]                  Updated just now

ROOM / GAME                    HOST          PLAYERS    STATUS / ACTION
Super Tilt Bro  A4Q7          -               0/2       [Join]
From Below     B9M2          -               0/2       [Join]
Tilt with friends C3R8        Silver          1/2       [Join]
Super Tilt Bro
Puzzle night   D6X4          Maya            1/2       [Join]
Custom NES game
Sunday match   E2P9          Noor            2/2       Full
Super Tilt Bro

Showing 5 public rooms                       [Previous] 1/1 [Next]
```

**Transitions and coverage.** Join on 0/2 claims Host/P1 and opens Page 3. Join on 1/2 reserves Guest/P2 and opens Page 3. Host a game opens Page 2. Search narrows this same list; codes distinguish duplicates. Rows for full or reconnecting sessions stay visible. Covers J1/J2/J5/J6; N01–N05, N08, N10–N13.

**State variants.** Loading says “Looking for rooms.” A failed refresh leaves old rows marked stale with Retry and disables Join. No public rooms says so and retains Host a game. Replenishment or room-capacity failure displays its actual status near the list.

## Page 2: Host a game from a local file

```text
< Public rooms                             HOST A GAME

NES file        [Choose .nes file]    or drop one here
Room name       [Custom NES game.......................]
Visibility      (x) Public    ( ) Unlisted
Connection      Standard [Change]

Your file stays on this device. Others need the exact same game.
                                           [Create room] [Cancel]
```

**Transitions and coverage.** Choose validates locally; Create room opens Page 3 as Host/P1 and publishes one public row or an unlisted invite. Cancel returns to Page 1. A verified included-game file may use its trusted game title and guest download path. Covers J5; N14–N21.

**State variants.** Invalid or unsupported files report the specific error next to file choice. Capacity and network errors keep the selected file and show Retry. Cancelled creation publishes no room.

## Page 3: Room before play

Host view:

```text
< Public rooms                  TILT WITH FRIENDS  C3R8       Public
Super Tilt Bro                 [Copy invite] [Room settings]

PLAYER 1                       PLAYER 2
Silver - You - Host            Empty - waiting

Game ready. You can start now or wait for a guest.
                       [Start game] [Leave room]
```

Guest view:

```text
< Public rooms                  TILT WITH FRIENDS  C3R8       Public
Super Tilt Bro

PLAYER 1                       PLAYER 2
Silver - Host                  You - preparing game

Checking exact game...  [Choose matching .nes file if needed]
Waiting for host to start.                   [Leave room]
```

**Transitions and coverage.** Host Start opens Page 4, alone or with a ready guest. The guest cannot start. Copy invite identifies this exact room. Room settings contains access, name, controller roles, remove/close when applicable. Covers J1/J2/J3/J6; N03, N07–N08, N23–N25, N28–N31.

## Page 4: Playing

```text
< Public rooms      Super Tilt Bro  C3R8       Playing - 1/2

+------------------------------------------------+--------------------+
|                                                | P1 Silver - Host   |
|                   NES GAME                     | P2 Open           |
|                                                | [Copy invite]      |
+------------------------------------------------+--------------------+

[Pause] [Save] [Fullscreen] [Game help] [Controls] [Settings]
[Room] [Leave]
```

**Transitions and coverage.** The host can continue solo. A guest joins the same room through Page 1 or the invitation; the host sees a pending guest and a safe-pause/transfer step before both resume. Public rooms keeps the game loaded; Return to game restores this view. Covers J3/J4/J7; N24–N34 and carried-forward play tasks.

**State variants.** Chat and optional voice appear only with a second person. From Below labels P2 as a shared-controller participant. A failed save, device loss, or microphone denial explains its next action near the relevant control.

## Page 5: Recovery at the failed action

```text
FIRST-JOIN RACE (in Page 1)
Someone joined first. This room now has a host.
[Join as guest] [Join another empty room]

GAME MISMATCH (in Page 3)
Your file does not match the host's game.
[Choose another file] [Leave room]

LATE JOIN FAILED (in Page 4)
Shared play could not start. The host's game is preserved.
[Retry together] [Continue solo] [Leave room]
```

**Transitions and coverage.** Each recovery stays with the action that failed. The displayed action depends on the actual membership and game state. Covers J1/J2/J4/J7; N04, N07, N26–N29, N32–N34.

## Step 5 principle check before critique

This pass has one public list and no advertising, and every page names its ordinary next state. It still fails three design rules: Page 1's generic **Join** hides first-host assignment and late-join status; Page 2 gives a custom-file warning without the included-file alternative; Page 4 mentions chat/voice and later join only in prose, so their usable controls and feedback are not yet visible. The [page critique](lobby-critique-v1.md) records those failures rather than treating this draft as complete.
