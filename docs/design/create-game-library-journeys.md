Create Game lets a player pick one verified NES game, choose who can see the room, and create it. The browser library shortens repeat hosting without putting file controls in the public room list.

Audience: Human

# Create Game journeys

Based on [direction](create-game-library-direction.md) and the approved [room transfer journey](room-rom-transfer.md).

| Journey | Entry → decisions and actions → feedback → outcome | Recovery |
| --- | --- | --- |
| J1 Join a public room | Open Retro Coop → scan/search Public rooms → choose one available row's **Join** or **Join as host** for an empty bundled offer → room preparation → guest **Prepare to play** or host **Start game** → shared/solo play. | Stale directory shows Retry; a full/playing row has no Join; failed guest acquisition offers Retry or Return. Create controls never interrupt this route. |
| J2 Host a saved game | Public rooms → **Create game** → inspect recent preview and Your games → select one verified saved or bundled entry → choose Public/Unlisted → **Create room** → creation/upload progress → waiting room → Start alone or after guest prepared. | Missing/corrupt saved bytes show the affected row unavailable and **Add NES file**; failed upload offers Retry with the same selected bytes or Cancel to Create Game. |
| J3 Host a new file | Public rooms → **Create game** → **Add NES file** or drop on this page → validation result and selected game's name/size → choose access → **Create room** → upload progress → waiting room → Start. | Invalid file leaves selection unchanged with an inline reason; quota denial says “Available in this tab only”; cancelled/failed upload returns to selected Create Game state without a public ghost room. |
| J4 Reuse a guest download | Join a host-shared room → exact verified download → browser saves by hash → leave room → **Create game** → the downloaded title appears once in Your games → select it and **Create room** → host upload of that saved copy. | Storage denial leaves the current tab playable and explains it will be absent next visit; a deleted/evicted copy disappears or becomes unavailable and can be added again. |
| J5 Manage local games | Settings → Local data → inspect Downloaded games → delete one or clear all with confirmation → Create Game reflects removal while current loaded play stays in memory. | Cancel confirmation leaves the list; deletion failure preserves the row and reports the error. |
| J6 Leave setup | Public rooms → **Create game** → **Back to rooms** before publishing. | Any validated selection remains available in this tab; no room or upload is left behind. Browser Back follows the same route. |

At each setup state, selection is the next action until a game is selected; then **Create room** is the single primary forward action. Public/Unlisted changes the room's visibility but does not create it. Settings and Local data remain secondary tasks.
