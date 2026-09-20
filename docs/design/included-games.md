Audience: Human

# Included games and arbitrary NES files

Visitors can start Super Tilt Bro or From Below without choosing a local ROM. Super Tilt Bro appears first. Visitors can also drop their own NES files and host internet rooms; the included catalog never limits which titles they may try.

## Direction and order

This amendment records the user's 2026-09-20 request to add the supplied `Super_Tilt_Bro_(E).nes`, rank it above From Below, make both included games directly playable, and show license placeholders for now. “From the deep” in that request refers to the already selected From Below. It extends the existing [platform design](browser-nes-platform.md) and [UI](browser-nes-ui.md) without replacing their room, privacy, consent or recovery rules.

The permanent included-games section presents two choices in this order:

1. **Super Tilt Bro** — first and most prominent.
2. **From Below** — remains available as another choice.

Before play, each game is a compact launcher with one primary **Play** action and a secondary **Show lobbies** action. The launcher may show a short factual genre/player label, but it must not spend the main screen on credits, a description panel, an About tab, or promotional copy. Both launchers remain visible when no rooms exist. Missing deployment assets produce an honest unavailable state for the affected game.

Instructions, credits and **“License details pending”** move into the playing view behind **Game help**, where they directly support the loaded game and do not compete with finding or starting a session. A license placeholder is not an invented license or a new attachment gate; the user states both supplied games are freely licensed and requests the placeholders. This supersedes the earlier instruction to omit From Below license text only to the extent of adding that placeholder.

Start loads the selected included game and uses the normal anonymous room flow. Opening an invitation shows its identity and content source; explicit Join downloads the same pinned game automatically. A matching game already loaded in the tab is reused without resetting it. Downloads validate exact bytes, can be canceled, and offer retry after failure. Game menus remain real menus: opening emulation must not be described as skipping them.

Show lobbies filters the already-visible directory by the selected catalog identity and offers Show all lobbies. It never opens a separate informational screen. The directory preserves distinct rooms, live counts, keyboard focus, stale-result protection and public/unlisted rules.

## Screen states

Before a game starts, the live lobby directory is the largest part of the screen. It is visible without opening a tab, scrolling past a marketing hero, or choosing a game first. Above it, Super Tilt Bro and From Below each have a one-click Play action. A compact **Host your NES file** drop/picker action sits beside the launchers. Search, connection policy and public/unlisted choice stay close to the action they affect. Remove slogans such as “Make yourself at home,” “Your game. Your browser,” “Pick a classic. Press play,” “Good games. Good company,” “A little nostalgia. A new game night,” and “Try the local player. Drop your NES game and start playing.” Do not replace them with another tagline.

```text
RETRO COOP                                      Settings

[ Play Super Tilt Bro ]  [Show lobbies]
[ Play From Below      ]  [Show lobbies]
[ Drop or choose any NES file to host ]  Public ▾

LIVE LOBBIES (all)
[Search room, host, or code________________]
Super Tilt Bro · Alex   Waiting       1/2  [Join]
From Below · Jo         Playing solo  1/2  [Join]
Host-provided game      Full          2/2  Full
[Previous]  Page 1 of 4  [Next]
```

After a game has loaded, the game canvas becomes the dominant surface. The launcher and full directory leave the primary layout; **All lobbies** returns to discovery without discarding the current game. Only now show play controls such as Pause/Resume, Saves, Rewind, Fullscreen, Settings, sound and session actions. Room/player/chat status remains adjacent when shared play needs it. **Game help** exposes instructions, factual credits and the requested license placeholder for the loaded included game.

```text
RETRO COOP  [All lobbies]  From Below · Playing together
+------------------------------------------------+----------+
|                                                | Players  |
|                  GAME CANVAS                   | Room     |
|                                                | Chat     |
+------------------------------------------------+----------+
[Pause] [Saves] [Rewind] [Fullscreen] [Settings] [Game help]
```

While a game is loading, replace its Play action with progress plus Cancel; keep the lobby directory usable. A failed load returns the same launcher with Retry and a concise cause. Returning to All lobbies preserves the loaded game and progress. Starting another game uses the existing replacement safeguard when progress or a room would be affected.

## One-window layout

The application fits the browser viewport and does not make the document scroll in either discovery or play. Header, launchers and directory controls use fixed minimum space; the lobby rows use the remaining height. If every lobby cannot fit, use compact pagination with a stable row count derived from the available height. Previous/Next, page count and keyboard focus make every admitted lobby reachable without page scrolling or a nested scrolling pane. Filtering resets to the first valid page and live updates keep the focused row stable when possible.

The playing view also fits one viewport. The canvas scales up to the largest size that fits beside shared room/chat status and above the revealed controls while preserving the emulator's source aspect ratio and integer scaling when space permits. Narrow supported desktop windows move the room/status column below or into a switchable panel, then reduce the canvas; they do not create vertical or horizontal document overflow. Browser zoom, long errors, open dialogs and enlarged text must keep the primary action reachable, using bounded overlays or compact wrapping rather than page scroll.

## Any NES title, without a catalog restriction

The drop/picker and internet hosting flow accepts arbitrary NES titles rather than a title allowlist. It must not require a game to appear in this catalog, reject an unknown title, impose the obsolete blanket 8 MiB limit, or reject NES 2.0 merely because of the format. User ROM bytes remain local; other players supply their own exact matching file. Included assets are the explicit exception supplied independently to each browser from the catalog.

Universal flawless emulation is not yet demonstrated. Malformed files, unavailable memory and unsupported cartridge hardware need clear errors, with previous progress preserved where possible. Untested hardware is labeled honestly and enters the compatibility workstream rather than being silently treated as supported. A checkpoint codec limitation must not be mistaken for a local-file admission rule; report local-play, save/rewind and shared-play capabilities separately. The objective remains broad NES support and internet lobbies for arbitrary titles, not a two-game platform.

## Multiplayer presentation

The application supplies synchronized controller inputs and room networking. It does not invent native multiplayer in a single-player game or delegate room networking to a cartridge's own online menu. From Below's supplied version remains single-player with optional shared-P1 handoff. Super Tilt Bro's exact supplied build needs actual controller/menu qualification before claiming its supported versus mode. Do not infer behavior from a different upstream release sharing the filename.

## Success

Before play, the public lobby directory is immediately visible and every admitted lobby is reachable through in-window pagination; both included choices are one-click Play actions in the requested order. After load, the canvas is the main surface and play controls appear. The document never scrolls; marketing copy and standalone informational tabs are absent. Both games support the existing Start/Join/retry/cancel flow with exact identity validation. Arbitrary local files still use the same player and room owners. Existing consent, progress-preserving joining, controller handoff, public internet and release qualification remain required by their owning issues.
