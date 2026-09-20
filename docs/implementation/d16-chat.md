Audience: Agent

# D16 temporary room chat

Friends can send text before loading a matching game. Messages stay in the current room, are rendered as plain text, and disappear locally on departure. Unsent text survives a connection or rate-limit failure until the player explicitly retries or discards it.

## Rules and ownership

`contracts/chat.ts` owns the 500-Unicode-character maximum, five attempts per ten seconds, 100-message client retention bound, message/event shapes and text validation. The existing strict room parser rejects extra fields, attachments and forged sender metadata. The coordinator authorizes current room and membership generation before applying the session's shared rate limiter. Server-assigned nickname/role cannot be supplied by a message sender. The room WebSocket transports chat; peer connectivity and ROM matching are not prerequisites.

Each room owns `RoomChat` retry receipts (one ID, digest and acknowledgement per current member), with no server text history. Reconnect and new joins receive no replay. A retry of the current pending ID and same text returns its existing acknowledgement without rebroadcast. A changed-text retry is rejected. Guest departure deletes its receipt; room closure deletes all room state. The client's bounded 100-message list clears when room or membership changes; late replies/events from an old membership are ignored. No chat persists across a page reload, goes to analytics, or is backed up.

`ChatClient` owns draft, one pending send, explicit retry, acknowledgement/event deduplication and membership reset. A received own message confirms delivery even if its separate request acknowledgement is lost. An ambiguous disconnect is labelled delivery unconfirmed, rather than claiming that it was never received. Retry retains the original ID and text; reconnect does not send automatically. Rate-limit countdown belongs to that failed chat attempt, rather than the general room status.

`ChatPanel` uses an explicit stable textarea label, plain React text, character feedback, live message log and a new-message jump action when scrolled away. It reuses LocalPlayer's existing canvas-focus gate for keyboard and gamepad suppression; no second input-suppression rule is introduced. The application privacy summary now includes temporary chat.

## Evidence and remaining obligations

The committed evidence folder records 27 passing Node tests and the timed complete preflight. Native browser/coordinator proof sends before the guest loads a ROM, rejects pre-join history, renders hostile markup literally, releases a held game button while typing, disables oversized sends, preserves rate-limited text with countdown/retry, retains an unsent draft through socket loss and reconnect without automatic delivery, retries a delivered message after both its event and acknowledgement were suppressed without broadcasting a duplicate, and clears messages on leave/rejoin. Existing room and foundation/settings/battery browser probes remain regression checks. Chrome default global mute is removed; game gain remains muted.

The first browser run exposed a textarea's wrapped label acquiring its text content after typing. The field now uses an explicit `htmlFor`/`id` label; the same typing/oversize/retry workload passes. Visual inspection also caught a stale general room cooldown after chat recovery; chat-specific retry state now owns that countdown. No tests were relaxed to hide those failures.

D10 connectivity, D11 shared gameplay, D17 voice, and later integrated layout/accessibility/abuse/release qualification remain separate work. This slice does not claim microphone, gameplay synchronization, public deployment or a completed release journey.
