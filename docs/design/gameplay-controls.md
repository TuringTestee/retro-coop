Players should see their inputs, discover their keys when idle, and save or load without leaving their game. Settings offers Controls and Audio; lobby access belongs beside the lobby name.

Audience: Human

# Gameplay controls and feedback

This bounded revision implements the owner's [#261 request](https://github.com/TuringTestee/retro-coop/issues/261). It supersedes the Game/Lobby/Controls/Sound/Voice/Profile section arrangement and phone Profile placement. The [unified journey](unified-lobbies-direction.md), approved one-panel phone layout, [controller references](mobile-controller-references.md) and [lobby references](unified-lobbies-references.md) otherwise remain applicable. The owner specified these changes and the new N restart shortcut; no new input protocol or emulator is proposed.

## Direction

- Once a game is loaded and the local player needs preparation, place one large **Prepare** button at the center of its preview, above the controller visuals. Use a semi-transparent background and a dim/filter layer over the preview; this replaces the bottom-right preparation button. Preserve authoritative eligibility, progress, cancellation and failed-preparation recovery in that region. Prepared players and spectators have no preparation overlay; Start remains the host's subsequent action.
- Keep the recognizable controller and its reserved region. Accepted keyboard, gamepad and pointer inputs use the same pressed styling. Derive highlights from the gameplay input owner, not a second keyboard handler. Editing, typing, lost focus and lost controller authority release feedback with actual input.
- After five seconds without action, display each visible action button's current keyboard binding. Holds count as activity; interaction hides hints. Hints occupy reserved space or a noninteractive overlay and never change target geometry. Unbound or suppressed shortcuts are identified truthfully. Remapping immediately changes hints.
- Show saving progress and success/failure at the game's top left in both lobby and expanded views, with accessible status text. A late result cannot describe a replacement game. Keep blocking Load/consent/recovery dialogs above the expanded game.
- Load compatible saved progress for the whole lobby through the existing controller-consent and coordinated state-transfer path. Keep membership, chat and the current view; resume using the existing shared journey. Cancel and failure retain a usable current game. Reproduce the reported exit before deciding whether a repair is needed.
- **N — Restart game** reloads the selected cartridge from the beginning, not the webpage. The host initiates a coordinated fresh timeline for all members; other members cannot reset a private timeline while shared play continues. A centered confirmation and existing coordination/recovery retain the old playable state on cancel or failed preparation. Keep the lobby, ROM identity, settings and saved copies. Local play uses the same confirmed action without a shared barrier. Respect remapped-key conflicts and include Restart in the binding inventory and hints.
- Settings has two sections: **Controls** and **Audio**. Controls combines controller configuration, complete binding help and game actions; Audio combines game sound and voice, including permissions, devices and recovery. Retain display filtering and local-data access in Controls. Remove old section navigation and duplicate help/action routes.
- Saved games shows a full readable list rather than one cartridge per page. Only overflow beyond the reserved list region needs pagination, with multiple entries per page where space permits. Keep complete accepted names, empty/error states, cancellation and corrupt-file retry in the existing game-selection journey.
- Controls displays every current mapping together, with each key shown as an editable button. Selecting a key opens a centered capture dialog over a screen-covering dimmed backdrop, using the exit-dialog pattern. Ask for the replacement input, reject conflicts, and offer Save/Cancel. Capture blocks gameplay/shortcuts; dismissal restores focus and input. This replaces inline key capture and one-row mapping pagination. Include rapid, game-action and voice keys as well as NES buttons; preserve valid personal mappings, unbound states and existing gamepad configuration.
- Put host-only **Set Password** after the lobby name; it opens the existing access controls in a centered dialog. Current public/password access and invitation semantics stay intact. Remove Profile navigation; identity values keep the centered name-edit dialog. On phones, readable lobby/personal values have reserved header rows, with compact actions and full values in their edit/inspection dialog. This explicitly replaces the prior Profile placement while preserving one lobby panel at a time.
- Controls lists every implemented binding: directions, A/B, rapid A/B, Select/Start, Save/Load, pause/resume, mute, push to talk and any existing slot/navigation shortcuts. Use actual configured keys and shortcut eligibility. Do not add an unsupported slot-switch shortcut or silently show a default key that has been reassigned. Keep keyboard/gamepad editing and Save/Cancel recovery in the current session.

## Screen and journeys

```text
[RETRO COOP] [Lobby name: … ✎] [Set Password] [Copy invite] [Your name: … ✎] [Theme]
| Players          | ROM name                              | Controls | Audio |
| P1 / P2 / watchers| [Saving… / Saved / Save failed: Retry] | Current bindings |
| fixed slots      | [preview + centered Prepare if needed]| Edit controller  |
|                  |          NES controller              | Save / Load      |
|                  | [idle: current keys by each button]   | Pause / Mute     |
|---------------------------- Chat -----------------------------------------|
[Back to Main Page]                                         [current action]
```

This shows Controls selected; selecting Audio replaces its contents in the same fixed right region. Muting remains one action in Audio, with its shortcut listed in Controls. Phone Game/Players/Settings/Chat still share one reserved panel. Expanded Game reserves top-left feedback and the existing Return action; a blocking dialog covers and dims it. Readable control/binding groups adapt inside the fixed panel; no page or settings scrolling.

| Journey/scenario | Observable outcome and recovery |
|---|---|
| Load → Prepare → prepared | One conspicuous centered preview action, no footer duplicate; preparation shows progress/cancellation and failure recovery. Once prepared, reveal the preview without its filter. Only occupied controllers prepare; Start still waits for all required owners. |
| Start → keyboard or remapped key → release | Matching button highlights while actual input is accepted; release, blur, typing, editing and reassignment clear it. Spectators cannot send input. |
| Play → no action for 5s → interact | Current hints appear without moving targets, then disappear. A held direction/rapid button prevents false idle. Pointer/touch actions use the same inactivity policy. |
| Play/fullscreen → Save | Visible saving/result feedback; storage failure offers the existing remedy. Replacement/navigation invalidates pending feedback. |
| Shared play → Load → consent → state transfer | Same lobby and presentation, matching restored native frame/hash and playable P1/P2 input. Decline, timeout, cancel and stale save preserve usable recovery and old authority. |
| Play → N/Restart → confirm → coordinated beginning | Same lobby, same selected cartridge, matching fresh native state for everyone; then playable controller input. Cancel or preparation failure preserves the old timeline and saved copies. Non-hosts cannot independently reset shared play. |
| Controls → edit → Save/Cancel | Current binding inventory and idle hints agree with committed mappings; delayed Save cannot alter a replacement draft/game. Conflicts remain rejected. |
| Controls → click mapped key → capture dialog | One dimmed screen-covering dialog, replacement prompt and Save/Cancel; no gameplay input escapes capture. All bindings remain discoverable, and dismissal/context replacement cannot leave stuck input or apply a stale draft. |
| Load game → Saved games → choose/cancel/retry | Full list or grouped overflow pages; complete names and usable selection. Empty/corrupt entry and delayed-read cancellation preserve the current lobby/game. |
| Audio → permission/device/connection failure | Game and chat continue; one relevant retry stays visible. Existing sound/voice settings survive switching sections. |
| Header → Set Password/name edit | Host can change access without leaving; guests retain correct admission behavior. Full names remain readable and dialogs do not resize unrelated controls. |

## Review and implementation gate

Before implementation, independently review and merge this revision. Reuse unaffected reference, journey and scenario artifacts rather than creating another complete design set. Implement with existing Controller, Settings, LocalPlayer, controls and shared-load owners; remove superseded section callers and maintained test expectations together.

Author verification must exercise these journeys through the public entry point on desktop, 320×568 phone, short landscape and real browser zoom. Observe both button state and native input, every supported action's actual binding, five-second hints, fullscreen Save/Load and recovery, ownership/context changes and keyboard typing. Preserve existing consent, voice-decoding and cleanup checks. Local audio testing uses the verified silent sink.

Design critique: complete journeys and feature support are represented in the table; facts appear on idle or deliberate Controls selection; there is one settings route and no Profile/Lobby duplicate; labels distinguish input and actions; geometry stays reserved; controller/lobby patterns reuse the cited references. Fit, accessibility, native input and recovery remain implementation obligations, not proven by this sketch.
