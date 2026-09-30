Public rooms should lead directly to a game and a clear waiting room. People see only the choices needed now; everyone in the room prepares before the host starts, and opening Public rooms ends the current session first.

Audience: Human

# Minimal room journey

The later [room access and automatic connection amendment](room-access-and-routing.md) replaces this document's temporary Standard/Relay-only exception and Public/Unlisted wording with automatic routing and Public/Password protected. Its password Join step applies before the shared readiness journey below.

## Direction and sources

This amendment originally covered the agreed non-routing portion of [issue #169](https://github.com/TuringTestee/retro-coop/issues/169). The audience is the general public, including teenagers. The owner asked to remove **all distractions** from the core journey, require every occupied member (including observers) to be prepared before initial Start, and make Public rooms exit an active room or game. The later access amendment resolves the deferred routing/access decision. This amendment supersedes conflicting Start and background-room text in [the five-slot design](five-slot-lobby.md), [the old room design](lobby-refactor.md), [the Create Game wireframe](create-game-library-wireframe-v4.md), and [the original UI inventory](browser-nes-ui.md). Other supported tasks remain reachable when invoked, rather than filling the ordinary room screen.

The [Warcraft III Custom Game list](https://classic.battle.net/war3/ladder/features.shtml) and [Blizzard lobby walkthrough](https://news.blizzard.com/en-us/article/23395649/revisiting-the-warcraft-iii-editor) show the useful list → lobby slots → Start progression. They do not establish this product's readiness or exit rules. Retro Coop also needs game verification and acquisition, so it keeps progress and recovery while those steps are active. [Issue #158's fixed-region design](stable-lobby-layout.md) owns the exact page geometry; this amendment removes content from those regions without letting their bounds depend on content.

## Keep, remove, and reveal when needed

| State | Keep visible | Remove from ordinary view or reveal only for a task |
|---|---|---|
| Public rooms | Search, concise room/game and host identity, available places, protected-room lock, Join, Create game, and relevant loading/empty/error feedback. For host supplied games, name the file source and possible download size before Join. | Repeated status/occupancy text, decorative previews, a second control to clear the search field, and technical route controls. Exact room code is searchable and available when sharing; it need not be repeated in every row. |
| Create game | Game list/Add NES file, selected game identity, Public/Password protected, Create room, Back, and validation/upload feedback while active. | Always-on preview and technical route selector. Play locally is a secondary action where its separate journey starts, not a competing Create action. |
| Waiting room | Five numbered slots as the single source for member name, role, game/connection preparation, and readiness; Copy invite, the member's Ready action, host Start game, Leave room. | Duplicate room/role paragraphs, visible invite URL, permanent per-slot management form, performance counters, generic connection detail. Host management opens from the affected slot; chat and optional voice stay compact and usable. |
| Playing | Game, current player role, a visible Players action, microphone state and mute, Pause/Resume when applicable, Leave room, and a compact way to open Controls, chat, Saves, Help or Settings for their real tasks. | Always-visible key mapping lists, persistent FPS/ping/frame/delay counters, repeated room summary, full five-slot management controls beside the game, technical route status when connected normally. Show connection trouble and Retry only when relevant. |

The [access amendment](room-access-and-routing.md) owns the protected-room password step and automatic connection policy. Routine performance diagnostics remain out of ordinary play.

The Controls action opens the existing Settings mapping list and editor. This replaces the persistent binding readout in the earlier [voice sidebar design](voice-play-sidebar-direction.md); device identity and any unbound action appear when the player asks to inspect controls. The public search field can clear its own query, so it needs no adjacent duplicate button.

## Journeys and recovery

| Journey | One forward path and visible result | Recovery and exit |
|---|---|---|
| Find or create | From Public rooms, Join one eligible row, or Create game → select game/access → Create room. An invitation gives the same Join outcome. Game loading/download shows progress inside its reserved area. | Empty/offline directory offers Retry. Invalid game, failed upload/download, full room or stale invitation explains the problem and offers the relevant Retry or Back. Cancel acquisition releases the place. |
| Prepare and start | The room shows five stable slots. Each occupied person, host and observer included, acquires and verifies the same game, reaches a usable connection to any current peers, then chooses Ready. A host alone has no peer connection prerequisite. Host sees who is waiting. Start game is available only when all occupied people are prepared and ready; empty/closed slots do not count. | An unprepared or disconnected member blocks Start. Host waits or removes that member with confirmation. A join, role/game change or lost readiness updates the rows and blocks Start. A rejected Start refreshes the same room; it never starts some members or ejects an unready member automatically. Late observer joining an already running game follows the separate five-slot journey and does not pause current players merely to satisfy initial Start. |
| Play and leave | Play opens after Start. Opening Public rooms, browser Back, an invitation, or any route away from the active room uses the same exit sequence. Host sees that closing ends the room for everyone; a member sees that they will leave. Confirm only when the effect merits it. The destination appears after room/game membership, input, audio and voice end. | Failed leave/close keeps the active room visible with Retry or Stay. A local-only game also stops before Public rooms appears. No Return to room or Resume local game background state appears in the directory. |

## Current screen sketch

```text
PUBLIC ROOMS                                    [Create game]
Search [________________]
Game / room                     Host          Places       Action
Super Tilt Bro                  —             5 open       [Join as host]
Lilac Harbor                    Guest Amber   3 open       [Join]
[Rooms unavailable. Retry] appears here only on failure.

CREATE GAME                                                [Back]
Choose a game
  Super Tilt Bro
  From Below
  [Add NES file]
Selected: Lilac Harbor · Ready to create
Access: (●) Public  ( ) Password protected      [Create room]
If protected: Room password [________] [Show]
[Checking / Uploading / Retry / Cancel in this reserved area]

WAITING ROOM · LILAC HARBOR
1  You · Host · Player 1              Preparing     [Manage]   | [Ready]
2  Guest Amber · Player 2             Preparing     [Manage]   | [Copy invite]
3  Guest Blue · Observer              Ready         [Manage]   | [Start game disabled]
4  Open · Observer                                  [Manage]   | Waiting for you and Guest Amber.
5  Closed                                                    | [Leave room]
[Chat] [Microphone off]   (compact, with feedback when used)

PLAYING · LILAC HARBOR                         [Leave room]
┌────────────────── GAME ────────────────────┐  [Players]
│                                             │  [Chat]
└─────────────────────────────────────────────┘  [Mute]
[Pause] [Saves] [Help] [Settings]

LEAVING · HOST
Close this room for everyone?                  [Close room] [Stay]
If close fails: Could not close room.          [Retry] [Stay]
```

“Manage” is host-only and opens the selected slot's Change role, Remove member, or Open/Close slot actions in that slot's reserved region. It is absent for a guest and for an action that cannot apply. A one-controller game's role explanation appears only when the host manages controller assignments. The Ready action is available only after the member's game and connection prerequisites succeed. Keep current voice permission, chat recovery, save, input, accessibility and local data journeys when their controls are opened.

## Review and implementation proof

Walk public discovery, creation, invitation, five-member preparation, waiting/removal, initial Start, play, local play and every exit route in real browsers. Check the host, a player and an observer; verify failure and return paths. Inspect whether each visible item changes the next decision, action or current-state understanding; remove it if it does not. Check keyboard and screen-reader paths, short/narrow/zoomed desktop layouts, and fixed regions across loading and errors under #158. This is a design contract, not proof that the running application already behaves this way.
