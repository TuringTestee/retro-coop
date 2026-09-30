Room creators choose Public or Password protected. Friends can find either room in Public rooms or open its invitation; protected rooms ask for a password before joining. The app chooses the network route automatically.

Audience: Human

# Room access and automatic connection

## Owner direction and boundaries

This amendment completes the access and routing direction in [issue #169](https://github.com/TuringTestee/retro-coop/issues/169). The owner chose Public or Password protected as the room access choice and directed the app to select its connection route automatically. Standard/Relay-only is technical routing, not a meaningful visitor choice. Replace the old Public/Unlisted access choice with **Public/Password protected** and remove the route selector from Public rooms, Create Game, invitations, waiting rooms and ordinary Settings. Keep the [minimal room journey](minimal-room-journey.md)'s all-member readiness, small UI and exit-before-directory behavior, and [#158's fixed regions](stable-lobby-layout.md).

This supersedes the old opt-in relay-only and unlisted/invite-only UI in the [platform design](browser-nes-platform.md), [Create Game direction](create-game-library-direction.md), [older screen set](create-game-library-wireframe-v4.md), [lobby direction](lobby-server-rooms-direction.md), and [peer privacy plan](../implementation/d10-peer-connectivity.md). Direct peer connections can reveal network addresses to other participants; the product must not promise anonymity. A concise Privacy/Help explanation remains reachable, but the ordinary Join/Create path does not ask visitors to diagnose or select a network route. No new account or matchmaking flow is implied.

## What a visitor sees

| Moment | Primary action and needed information | Recovery |
|---|---|---|
| Browse | Each public and protected room appears in the searchable directory with game/room, host, occupied places and Join. Protected rows show a lock and “Password required”; the lock means admission protection, not network anonymity. | Empty, loading, stale, full and service-error states keep the existing clear status and Retry/Back. An unlisted category or Standard/Relay-only choice does not appear. |
| Create | Choose a game, then Public or Password protected. Selecting protected reveals one **Room password** field with Show/Hide. Create room is enabled only after a valid password. No password field appears for Public. | Invalid or missing password gets a short inline reason. Failed creation/upload leaves the selected game and access choice intact with Retry/Back; never publishes a half-created room. |
| Join | Public Join enters the room. Protected Join opens a small password step naming the room and game. Enter password → Join room. This is the one extra step needed to access a protected room. | Wrong password says “Password didn't work. Try again” without reserving a slot. Too many attempts says when to retry; the person can return to Public rooms. Full/closed/stale room gives the current availability message. |
| Invite | Copy invite shares a link to this exact room, not a password. Opening it shows the same room identity and availability; protected rooms still ask for the password. Host shares the password separately. | An expired/closed invitation returns to Public rooms. Opening a link alone never admits someone, downloads a game, starts peer contact or turns on the microphone. |
| Manage access | Host can change Public ↔ Password protected in room settings. Turning protection on or changing the password requires a new valid password; turning it off names that anyone may join. The change affects future admission, not people already in the room. | A failed change leaves the previous access rule and admitted members unchanged. Old password attempts cannot become a member after a successful change. |
| Connect | After admission, browsers choose a usable route automatically, preferring direct peer connection when it works and using a relay when needed. | If neither route works or relay capacity is exhausted after direct fails, show “Could not connect” with Retry and Leave. Do not show route jargon or a policy selector in the ordinary journey. |

## Screen sketch

```text
PUBLIC ROOMS                                  [Create game]
Search [________________]
Super Tilt Bro             —            0/5       [Join as host]
Lilac Harbor               Guest Amber  2/5       [Join]
Puzzle Night  🔒 Password required  Guest Blue  3/5 [Join]

CREATE GAME                                             [Back]
Choose a game: [game list] [Add NES file]
Selected: Puzzle Night
Room access  (●) Public  ( ) Password protected
When protected: Room password [________] [Show]
                                                   [Create room]

PUZZLE NIGHT · PASSWORD REQUIRED                         [Back]
Room password [________________] [Show]
                                                    [Join room]
If wrong: Password didn't work. Try again.
If limited: Too many tries. Try again in 1 minute.
```

The prompt replaces the Join action area; it does not move the room list, title or surrounding controls. The password is never embedded in the invite URL, copied as part of Copy invite, repeated in the waiting room, or sent to chat. A host who forgets a password may set a new one; the app cannot reveal the old one.

## Complete journeys to verify

Public browse → Join → prepare → Ready → host Start → play → exit. Protected browse or invite → password → Join → the same room journey. Wrong password, throttling, stale links, simultaneous final-slot claims, password change during a pending Join, and failed routing all return to a clear next action without creating a hidden membership. Exercise both access modes with five members, including observers, and check that the password step does not make new regions shift under #158. This document states intended behavior, not current browser proof.
