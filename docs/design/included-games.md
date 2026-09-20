Audience: Human

# Included games and arbitrary NES files

Visitors can start Super Tilt Bro or From Below without choosing a local ROM. Super Tilt Bro appears first. Visitors can also drop their own NES files and host internet rooms; the included catalog never limits which titles they may try.

## Direction and order

This amendment records the user's 2026-09-20 request to add the supplied `Super_Tilt_Bro_(E).nes`, rank it above From Below, make both included games directly playable, and show license placeholders for now. “From the deep” in that request refers to the already selected From Below. It extends the existing [platform design](browser-nes-platform.md) and [UI](browser-nes-ui.md) without replacing their room, privacy, consent or recovery rules.

The permanent included-games section presents two choices in this order:

1. **Super Tilt Bro** — first and most prominent.
2. **From Below** — remains available as another choice.

Each has Start a session, Browse its sessions, and About with instructions, credits and **“License details pending.”** Both remain visible when no rooms exist. Missing deployment assets produce an honest unavailable state for the affected game. A license placeholder is not an invented license or a new attachment gate; the user states both supplied games are freely licensed and requests the placeholders. This supersedes the earlier instruction to omit From Below license text only to the extent of adding that placeholder.

Start loads the selected included game and uses the normal anonymous room flow. Opening an invitation shows its identity and content source; explicit Join downloads the same pinned game automatically. A matching game already loaded in the tab is reused without resetting it. Downloads validate exact bytes, can be canceled, and offer retry after failure. Game menus remain real menus: opening emulation must not be described as skipping them.

Browsing an included game's sessions filters by its catalog identity, shows the selected game, and offers Show all sessions. It preserves distinct rooms, live counts, keyboard focus, stale-result protection and public/unlisted rules.

## Any NES title, without a catalog restriction

The drop/picker and internet hosting flow accepts arbitrary NES titles rather than a title allowlist. It must not require a game to appear in this catalog, reject an unknown title, impose the obsolete blanket 8 MiB limit, or reject NES 2.0 merely because of the format. User ROM bytes remain local; other players supply their own exact matching file. Included assets are the explicit exception supplied independently to each browser from the catalog.

Universal flawless emulation is not yet demonstrated. Malformed files, unavailable memory and unsupported cartridge hardware need clear errors, with previous progress preserved where possible. Untested hardware is labeled honestly and enters the compatibility workstream rather than being silently treated as supported. A checkpoint codec limitation must not be mistaken for a local-file admission rule; report local-play, save/rewind and shared-play capabilities separately. The objective remains broad NES support and internet lobbies for arbitrary titles, not a two-game platform.

## Multiplayer presentation

The application supplies synchronized controller inputs and room networking. It does not invent native multiplayer in a single-player game or delegate room networking to a cartridge's own online menu. From Below's supplied version remains single-player with optional shared-P1 handoff. Super Tilt Bro's exact supplied build needs actual controller/menu qualification before claiming its supported versus mode. Do not infer behavior from a different upstream release sharing the filename.

## Success

Both included choices boot from the ordinary UI without a local picker, in the requested order, and both support the existing Start/Join/retry/cancel flow with exact identity validation. Arbitrary local files still use the same player and room owners. Existing consent, progress-preserving joining, controller handoff, public internet and release qualification remain required by their owning issues.
