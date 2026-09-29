A room will hold up to five people in five stable slots. The host can assign controller roles or observers and close empty slots. Everyone can chat, and observers watch the same game running locally in their browser.

Audience: Human

# Five-slot lobbies

The [minimal room journey](minimal-room-journey.md) supersedes this document's assigned-players-only **initial Start** gate: every occupied member, including observers and the host, must prepare and choose Ready. Midgame observer isolation and late joins below remain current.

## Source and scope

This is the governing proposal for [feature #157](https://github.com/TuringTestee/retro-coop/issues/157). The user's request is: “do NOT assume there are only 2 players for any games. support multiple slots like war3, and host can choise to change roles like observer, player1 player2 etc, or close slots. make max 5 slots.” Implementation starts only after independent review and merge of this document and its [technical plan](../implementation/five-slot-lobby.md).

This amendment replaces the two-person room ceiling, single Guest place, deferred observers, and blanket refusal of joins after Start in [the platform design](browser-nes-platform.md), [lobby design](lobby-refactor.md), and [v4 room wireframes](create-game-library-wireframe-v4.md). Their unaffected journeys remain. Browser-local emulation, host-provided custom ROM acquisition, included-game acquisition, privacy choices, and explicit microphone permission remain. No video streaming or host migration is introduced.

Five people does not imply five emulated controllers. The current NES adapter exposes Player 1 and Player 2; additional members can observe. Slot roles come from the game's supported controller capabilities rather than a universal two-person room model. Observer means a synchronized local game with no controller authority. It is not an empty label or a video stream. Existing single-controller/shared-controller behavior remains representable without assigning two owners to the same controller.

The separate [layout feature #158](https://github.com/TuringTestee/retro-coop/issues/158) governs deterministic positions throughout the application. This feature supplies five stable slot rows and bounded inline status/action areas for those rows; #158 follows with the wider layout changes. The separate voice fix [#156](https://github.com/TuringTestee/retro-coop/issues/156) governs focus-independent microphone behavior; five-member voice must preserve that behavior when integrated.

## Room behavior

A new room shows Slots 1–5. The host initially occupies Slot 1 as Player 1. Remaining supported controller roles occupy the next open slots; other slots are open as observers. Thus a two-controller game opens Slot 2 as Player 2, while From Below opens Slots 2–5 as observers because it uses Player 1 only. The host badge represents administration, independently of controller role. Changing roles never moves or renumbers a person's slot. At most one member or reservation occupies each slot, and a sixth person cannot join.

The host can change any slot's role, including their own. Controller ownership is unique. Assigning an already occupied controller role swaps the two affected members' roles in one operation, with the pending result visible before it takes effect; it never gives duplicate input authority. An empty role change cannot displace an occupied controller owner. Closing is available for empty slots; an occupied slot retains explicit removal confirmation before it can be closed. Host closure of their own occupied slot is unavailable; leaving as host closes the room under the existing policy.

Directory cards and invitation previews show people out of five and whether an open slot is available. Join claims the first open slot in stable slot order; host reassignment provides placement afterward. Closed and full rooms remain discoverable with truthful admission status. Once a game is running, new members can occupy open slots: observers synchronize without interrupting play, while a new controller owner joins through the progress-preserving pause described below.

All members get text and opt-in voice, even while a game is downloading or synchronization needs retry. Every observer obtains the matching game through the same included-game or host-provided acquisition journey as players. Acquisition failure belongs to that slot and never ejects another member or stops an established game.

## Journeys and completion

| Journey | Entry and actions | Success and completion | Recovery |
|---|---|---|---|
| F1: Fill and manage a room | A host creates or claims a room from the normal page. Friends join through the directory, room code, or invite. The host changes roles, removes a member with confirmation, and closes/reopens an empty slot. | Five named members occupy stable rows; the host can observe while other members own the controllers. Admission, role labels, and host controls agree in every browser. The journey ends when the intended membership and roles are visible. | Concurrent joins have one winner per slot. A sixth join, stale role change, or unauthorized command explains the current state and allows retry/back. Failed removal preserves the member; closing an occupied slot never silently removes them. |
| F2: Play and observe | Members acquire the room game. The host starts when assigned players are ready. Observers watch local synchronized emulation, chat, and enable voice. A late observer joins a running room. | Assigned players control only their assigned inputs. Observers see the current game without controlling it; all five can communicate. Late observing is complete when the new browser catches up without stopping players. | Download, permission, or synchronization errors show retry in that member's row or existing voice region. A slow or disconnected observer resynchronizes independently. Missing controller input pauses play with progress preserved. |
| F3: Change roles during play | The host selects a new role for a member, swaps controller owners, promotes an observer, or takes an observer role themselves. | Play pauses at a completed frame, or uses the last completed frame immediately if already stalled; incoming controller owners synchronize there; role labels and authority change together. Play resumes from that same game state. The host retains administration when observing. | If the change cannot finish, the previous committed assignment and game progress remain intact and paused. Retry continues the change; cancel retains the old roles and resumes only when those owners are ready. A departed owner is not required to acknowledge their replacement. |
| F4: Recover membership | A participant reconnects in the existing grace period, leaves, or is removed while others remain. | Reconnect retains the reserved slot and role, then restores the current game state. Leaving/removal clears only that membership and its voice/chat/transfer resources. Completion means the remaining room and any reconnecting member show the same authoritative state. | An expired member cannot reuse their old slot authority. Observer loss does not pause players; controller loss pauses until recovery or reassignment. Host timeout closes the room under the existing policy. No host migration is implied. |

Keyboard users can reach each role control, follow inline pending/error feedback, and recover focus after removal. Slot content, loading progress, long nicknames, and errors stay inside their row regions. The five rows remain present across waiting, playing, and reconnecting states; room management remains accessible during play.

## Acceptance boundary

Feature #157 is complete only when F1–F4 work through the public application entry point with five real browser members, including distinct same-origin tabs and separate browser processes. Evidence includes actual controller authority, matching local game states, midgame swaps without progress loss, all-member communication, and recovery—not merely five rendered rows. Current advertised game compatibility is preserved: an existing checkpoint-codec gap is implementation work, not permission to silently remove observers or role changes for those supported games. Unsupported inputs retain truthful existing admission errors.
