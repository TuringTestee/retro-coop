Retro Coop should show every game session in one lobby list. The service keeps an empty room ready for each included game; the first person to join becomes its host, and people can also host a room with their own NES file.

Audience: Human

# Lobby direction and reference evidence

This is the direction artifact for the next UI iteration. It records the user's September 22 corrections to the [earlier lobby proposal](lobby-browser-proposal.md). It describes intended behavior, not what the running application already supports.

## User direction

- Super Tilt Bro and From Below are ordinary public lobbies. They have no special game cards, Play buttons, or separate lobby browser.
- The main service keeps one **0/2, joinable** room for each included game. It creates a fresh empty room when the last available one gets its first player. Filled or playing sessions stay separate rows with their actual status.
- The first person to join an empty included-game room becomes **host and Player 1**. They may start at any time, including alone. A second person may join as Player 2 while the host is waiting. Joining a game after it starts is deferred; playing rooms remain visible but say Join unavailable. For From Below, the second person shares or takes turns with the single game controller; the UI must say so before joining.
- A person can host a room from a local `.nes` file. Other people on other devices see its public room in the same list and can join to play. The file path and bytes remain on the host's device. A guest needs the exact matching file, unless it matches a verified included-game asset that the app can download.
- Public rooms appear together; unlisted rooms are invitation-only. Each row is a separate session even when two rooms use the same game or name.

The [reference evidence](lobby-references-v2.md) supports one visible browse path, a distinct Host action, open player slots, and a host-controlled Start action. It does not imply that the service runs the game.

## Step 2 principle check

| Player decision | Agreed behavior and content needed at that decision | Content to remove |
|---|---|---|
| Which game or room should I enter? | One room list shows game, room identity, host, slots, state, and valid next action. | Separate included-game Play cards, Show lobbies links, and duplicate game lists. |
| Will I become host or guest? | A 0/2 row identifies the first joiner as Host/P1; a 1/2 row names its current host. | A generic Join label that hides the role change. |
| Can I start now? | The host sees Start when their game is ready, plus the effect of starting alone or with a guest. | Automatic solo start and unrelated controls before a room exists. |
| Can my friend join my own file? | Host publishes one public room; a guest sees whether they need a matching file. | Public local paths, implied ROM downloads, and a separate custom-game directory. |

The [journey map](lobby-journeys-v2.md) must trace each decision to a result and recovery. The wireframe must put each fact at its decision point and remove repeated actions; this direction table alone does not prove the UI does so.

## Architecture boundary and choices for the next artifacts

The main service **supplies rooms, not gameplay**. Two browser peers still run matching game files; the first joiner becomes the host peer. A zero-player room is a service-owned offer, not a connected fake player. Its first-join claim must be atomic so two people cannot both become host. Replenishment must respect room and connection capacity; if no fresh room can be published, the list must say so rather than show an unusable Join action.

Host Start while alone keeps that room's identity but closes its Player 2 admission for this essential delivery. Progress-preserving late join is deferred and is not a dependency for the first refactor. A host leaving closes their room; the service-created room supply is a separate concern and remains available. A service restart recreates empty included-game rooms and reports interrupted human sessions honestly.

The [approved platform design](browser-nes-platform.md) currently says the host creates a room and starts solo automatically. The [included-game amendment](included-games.md) currently gives these games special launchers. The running coordinator requires a connected host to create a room. These are explicit design and implementation changes that need a reviewed plan amendment before build work.
