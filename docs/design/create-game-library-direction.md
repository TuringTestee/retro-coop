The room browser should lead with joinable games. Creating a room moves to its own page, where a player can reuse one of their browser's saved NES games or add a new file.

Audience: Human

# Create Game direction

| Source | Behavior and replacement |
| --- | --- |
| User direction, 2026-09-23 | Separate Create Game from the main lobby browser. Replace the current inline **Host your NES file** bar with one **Create game** entry action. |
| User direction, 2026-09-23 | Show the recent game's preview on Create Game and remember available or downloaded ROMs as unique games. |
| User direction, after reviewed PR #101 | Learn Warcraft III Battle.net's game list, selected-game preview, and lobby slot controls. Keep the UI in stable page positions with no overlays. Show only information and controls needed for the current action. |
| Approved room transfer behavior | Upload the chosen custom ROM once during room creation; guests receive its exact bytes automatically and can prepare. Keep public/unlisted rooms and host-controlled Start. |
| Current implementation | Guest downloads already use an IndexedDB ROM store keyed by SHA-256. Locally selected host files are not added to that library. The main page currently has both an inline host bar and a player file picker. |

## Recommended decisions within that direction

1. **Your games** shows one row per exact ROM SHA-256 in this browser, whether it arrived by local selection or guest download. The two bundled games appear once as available choices. Reimports of the same bytes refresh last-used metadata rather than adding rows. Title/label is local only; filenames and paths never enter public room metadata.
2. The most recently used game gets a large preview on Create Game. Prefer a real locally captured frame after the game has rendered; show the game name and “No preview yet” when there is no valid image. A preview is not proof the cartridge works on every mapper.
3. Select a saved or bundled game, choose Public or Unlisted and the existing Standard/Relay-only connection policy, then **Create room**. A new file enters through **Add NES file**, validates, saves a verified local copy if storage is available, and becomes the selected game. The file is uploaded only after **Create room**. The server still sees one room creation and exact-byte upload, and no guest picks a file. The room browser keeps that policy choice beside public Join; invitation preview keeps it beside Join room.
4. If browser storage is denied or full, the selected new file remains usable in this tab; show “Available in this tab only” beside Create. Reuse after reload requires selecting the file again. If a saved entry is missing or corrupt, remove or mark it unavailable and offer **Add NES file**; do not create a room with unverified bytes.
5. The room browser retains search, join status and one **Create game** action. The waiting room retains invite, guest preparation and host Start. Settings → Local data remains the place to delete saved games; the Create page need not duplicate deletion controls.
6. On a wide Create Game page, place a scrollable game list on the left and a selected-game preview on the right, like Warcraft III's documented list/preview relationship. The preview updates in place when selection changes. On a narrow viewport, stack the same regions without covering one another. “Sliding” means the list scrolls inside its region; do not add a decorative carousel or popover. Respect reduced-motion preferences.
7. Keep a stable page frame for Public rooms, Create Game, waiting room, play, Settings, Local data, Saves, Rewind and Game help. No dialog backdrop, floating room drawer, toast over gameplay, or browser confirm may cover page content. A confirmation replaces the relevant page's action area until resolved. The game canvas and room details occupy their own regions in play. At supported zoom and viewport sizes, regions may stack and scroll without clipping.
8. Guest/P2 is Open by default in a waiting room. The host may Close it while empty or Open it again before Start. Closed means no guest Join or active invitation; the directory row remains visible with “Guest place closed.” If occupied, the host first uses the existing Remove guest action and its inline confirmation, then may Close. P1/Host is fixed and has no slot control. Once Start begins, the room's existing no-late-join rule owns admission; slot controls disappear.
9. Keep only the row/slot status, selected-game facts, privacy choice, next action and recovery needed at that moment. Show deeper settings, local-data deletion, save tools and help only on their dedicated pages. Do not repeat Create, Add, Start or Leave in multiple regions of the same page.

## Open product choices for reviewed planning

The user has not specified whether the preview must be a screenshot, cover art, or metadata card, nor a storage cap or “recent” time window. The recommendations above use a rendered frame, newest last-used item, and the browser's existing best-effort IndexedDB store without inventing a quota promise. “Sliding UI” is interpreted as Warcraft III's scrollable list with a selected-game preview inside a fixed layout, since the available official evidence does not establish an animated transition. If review finds a privacy, storage or layout concern, revise the plan before implementation.
