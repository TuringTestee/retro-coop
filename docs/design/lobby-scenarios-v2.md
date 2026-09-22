The lobby design must work when a room is empty, claimed, playing, or interrupted. This checklist adds the new first-join host and room-replenishment cases to the existing player scenario inventory.

Audience: Human

# Lobby scenario coverage, iteration 2

The [earlier exhaustive inventory](lobby-scenario-inventory.md) still covers file validation, controls, voice, chat, saves, accessibility, moderation, and general failures. Its special included-game launcher and automatic solo-start cases are superseded by [the new direction](lobby-server-rooms-direction.md) and the scenarios below. These scenarios are design requirements, not observed product behavior.

Each row names the trigger, visible result, and recovery. J1–J7 refer to the [journey map](lobby-journeys-v2.md).

## Discover and claim a room

| ID | Journey | Scenario and result |
|---|---|---|
| N01 | J1/J2 | Open the site → see a single public directory with every public session, including one 0/2 room for each healthy included game. |
| N02 | J1/J2 | Two rooms use the same game or label → see distinct codes, hosts, counts, and statuses; do not merge rows. |
| N03 | J1 | Join a 0/2 included-game room → receive Host/P1 and remain in that exact room. |
| N04 | J1 | Two people race for 0/2 → one becomes host; the other sees the updated room and can join as guest or select the fresh room. |
| N05 | J1 | First claim uses the last 0/2 room → directory gains a new 0/2 row without resetting the claimed room. |
| N06 | J1 | Replenishment reaches capacity → existing rooms stay intact; directory explains that a fresh room is temporarily unavailable and retries when capacity returns. |
| N07 | J1 | Included asset is absent, download fails, or hash fails → claimant sees Retry/Leave; role and room status stay truthful. |
| N08 | J2 | Join a 1/2 waiting room → reserve P2, identify the host, and prepare matching content. |
| N09 | J2/J4 | See a 1/2 playing room → Join is unavailable in the essential release; choose a waiting room without resetting host progress. Later join is deferred. |
| N10 | J2 | Open a 2/2, reserved, closing, or reconnecting row → see why Join is unavailable while the row remains identifiable. |
| N11 | J2 | Directory is loading, empty, stale, or disconnected → show status/Retry, keep current game safe, and never join from stale data. |
| N12 | J2/J6 | Search room, host, or exact public code → preserve duplicate names as separate rows; clear no-match query. |
| N13 | J6 | Open unlisted invitation → preview exact room without public listing or public-code discovery. |

## Create and use a human room

| ID | Journey | Scenario and result |
|---|---|---|
| N14 | J5 | Choose Public/Unlisted before a local NES file → validate locally and automatically create one distinct room with a generated neutral label. |
| N15 | J5 | Local path contains a name or personal directory → never show path or filename to others; generate a neutral public label that the host can rename later. |
| N16 | J5 | File exactly matches an included asset → label by verified identity and permit guest auto-download; the human room remains distinct from the service-created room. |
| N17 | J5/J2 | File is not an included asset → guest chooses their own exact matching file; host bytes are not uploaded. |
| N18 | J5 | Host chooses a structurally valid but unsupported/unqualified ROM → show the correct compatibility status before claiming others can play. |
| N19 | J5 | Host cancels or file validation/create fails → preserve valid local selection and prevent an orphan directory row. |
| N20 | J5 | Host creates Unlisted → invitation works, public directory/search does not reveal it. |
| N21 | J5/J7 | Host changes room label or access → update the same row and invite view; do not create another session. |
| N22 | J5/J7 | Host leaves or closes → remove only that human room; a service-created 0/2 supply remains independent. |

## Start, join, and leave play

| ID | Journey | Scenario and result |
|---|---|---|
| N23 | J1/J3 | First joiner waits at 1/2 → sees Host/P1, empty guest slot, Invite, Start game, and Leave. |
| N24 | J3 | Host starts alone at any time → game loads in the same room and room changes to Playing 1/2 · Join unavailable for now. |
| N25 | J2/J3 | Guest enters before Start → host can start both players when content/connection are ready; guest sees the host's start decision. |
| N26 | J4 | Deferred: guest enters after Start → future work must safely pause, transfer validated progress, and resume together. Essential UI offers no Join. |
| N27 | J4 | Deferred: late-join decline, cancel, or expiry → future work must preserve the host timeline. Essential UI offers no Join. |
| N28 | J2 | Exact file, core, settings, or controller assignment differs → explain the mismatch and next action; no false shared start. |
| N29 | J2 | Two guests race for P2 → one reserves the slot; the other sees Full/Reserved and can choose another room. |
| N30 | J3 | From Below has two humans in a one-player game → show one active controller and explicit handoff; do not label it native P1/P2. |
| N31 | J3 | Super Tilt Bro has two supported players → show P1/P2 ownership and start only after matching local copies are ready. |
| N32 | J7 | Host disconnects or closes → guest sees room ended and a valid local continuation or directory route; no invented host migration. |
| N33 | J7 | Guest disconnects or leaves → host sees open slot and can continue solo or wait, with progress preserved. |
| N34 | J7 | Service restarts → human rooms end with an explanation; fresh 0/2 included-game rooms are republished after recovery. |

## Small tasks and recovery carried forward

| Existing inventory | Applies here |
|---|---|
| A01–A08, A12–A14; C01–C17 | Browse/search, stale states, exact room identity, guest reservation, file mismatch, and invitation. |
| D01–D12, E01–E31 | Shared play, chat/voice, help, settings, controls, save/rewind, pause, and leave. Show each only where usable. |
| F01–F16 and keyboard/narrow-layout cases | Capacity, rate limit, network interruption, permission denial, storage failure, focus, zoom, and accessible recovery. |

The next wireframe must show the ordinary J1/J2/J3/J5 paths directly and annotate N04–N10, N15–N19, and essential N28–N34 as state variants. N26–N27 remain deferred requirements for a separate design. It must not turn every scenario into a permanent control.

## Step 4 principle check: feature support and timing

| Feature | Entry and usable state | Feedback and recovery | Information timing / duplication check |
|---|---|---|---|
| Join as host / Join | One action on each applicable waiting public row; playing rows show Join unavailable | N03–N10, N28–N29 | Show role, slots, and game/file need before Join; do not show a later-join path in this delivery. |
| Host a local file | One drop/picker action after choosing access | N14–N22 | Show Public/Unlisted and peer privacy before file selection; generate the label and create automatically after validation. |
| Start game | Host room after file readiness | N23–N25 | Explain solo/two-person effect beside Start, not on arrival; playing rooms cannot admit a guest in this delivery. |
| Invite and room management | Current room, role-appropriate controls | N20–N22, N32–N34 | Identify exact room and affected people at the action; no duplicate room menu on one page. |
| Help, settings, controls, save, chat, voice, exit | Loaded game or occupied room, as applicable | Earlier inventory D/E/F and N30–N34 | Show each only when usable; error and exit feedback remain beside their control. |

The first ASCII pass must show these entries and states, not just mention them in prose. Its critique must flag every missing UI surface, duplicate action, premature explanation, and inconsistent label.
