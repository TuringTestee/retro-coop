Players should see their inputs, discover their keys when idle, and save or load without leaving their game. Settings offers Controls and Audio; lobby access belongs beside the lobby name.

Audience: Human

# Gameplay controls and feedback

This bounded revision implements the owner's [#261 request](https://github.com/TuringTestee/retro-coop/issues/261). It supersedes the Game/Lobby/Controls/Sound/Voice/Profile section arrangement and phone Profile placement. The [unified journey](unified-lobbies-direction.md), approved one-panel phone layout, [controller references](mobile-controller-references.md) and [lobby references](unified-lobbies-references.md) otherwise remain applicable. The owner specified these changes and the new N restart shortcut; no new input protocol or emulator is proposed.

## Direction

- Once a game is loaded and the local player needs preparation, place one large **Prepare** button at the center of its preview, above the controller visuals. Use a semi-transparent background and a dim/filter layer over the preview; this replaces the bottom-right preparation button. Preserve authoritative eligibility, progress, cancellation and failed-preparation recovery in that region. Prepared members wait for the host. Under [#282](https://github.com/TuringTestee/retro-coop/issues/282), the host's single subsequent **Start** action uses the same centered overlay and reserved region; remove footer Start. Keep its readiness reason there when unavailable. Spectators do not block Start.
- Keep the recognizable controller and its reserved region. Accepted keyboard, gamepad and pointer inputs use the same pressed styling. Derive highlights from the gameplay input owner, not a second keyboard handler. Editing, typing, lost focus and lost controller authority release feedback with actual input.
- After five seconds without action, display each visible action button's current keyboard binding. Holds count as activity; interaction hides hints. Hints occupy reserved space or a noninteractive overlay and never change target geometry. Unbound or suppressed shortcuts are identified truthfully. Remapping immediately changes hints.
- Show Save and Load progress and success/failure at the game's top right in both lobby and expanded views, with accessible status text and room for the Return action. When a phone shows another panel, keep the same single notification at the active container’s top right without changing panels. A late result cannot describe a replacement game or timeline. Recovery and other actual blockers still cover the expanded game.
- E or the existing Load action immediately loads the compatible quick save; no quick-save menu, confirmation or participant acceptance dialog. The host loads it for the whole lobby through the existing validated state-transfer barrier; local play uses the same direct action. Keep membership, chat and the current view. Resume a previously running game after every required machine acknowledges; keep an already paused game paused. Empty, incompatible, changed or inaccessible saves report a top-right reason and retain current progress. Failed coordination rolls back rather than partially resuming.
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
| fixed slots      | [preview + centered Prepare or Start] | A [Z] / B [C]    |
|                  |          NES controller              | All key mappings |
|                  | [idle: current keys by each button]   | Save/Load/Restart|
|---------------------------- Chat -----------------------------------------|
[Back to Main Page]
```

This shows Controls selected; selecting Audio replaces its contents in the same fixed right region. Bracketed keys are editable buttons showing actual committed mappings, not fixed defaults. The complete inventory includes directions, rapid buttons and every implemented game/voice action; selecting a key opens the capture dialog. Muting remains one action in Audio, with its shortcut listed in Controls. Phone Game/Players/Settings/Chat still share one reserved panel. Expanded Game reserves top-right feedback and the existing Return action; a blocking dialog covers and dims it. Readable control/binding groups adapt inside the fixed panel; no page or settings scrolling.

| Journey/scenario | Observable outcome and recovery |
|---|---|
| Load → Prepare → prepared | One conspicuous centered preview action, no footer duplicate; preparation shows progress/cancellation and failure recovery. Prepared ordinary members see the preview without the preparation filter; the host uses the centered Start overlay. Only occupied controllers prepare. The host's Start replaces Prepare in the same center region and waits for all required owners; no footer duplicate. |
| Start → keyboard or remapped key → release | Matching button highlights while actual input is accepted; release, blur, typing, editing and reassignment clear it. Spectators cannot send input. |
| Play → no action for 5s → interact | Current hints appear without moving targets, then disappear. A held direction/rapid button prevents false idle. Pointer/touch actions use the same inactivity policy. |
| Play/fullscreen → Save | Visible saving/result feedback; storage failure offers the existing remedy. Replacement/navigation invalidates pending feedback. |
| Play → E/Load → state transfer → restored play | No quick-save or acceptance menu; top-right progress/result is visible, including fullscreen. Same lobby and presentation, matching restored native frame/hash and playable P1/P2 input. Empty/corrupt/stale save, failed transfer or disconnect preserve usable recovery and old authority. A paused game remains paused. |
| Play → N/Restart → confirm → coordinated beginning | Same lobby, same selected cartridge, matching fresh native state for everyone; then playable controller input. Cancel or preparation failure preserves the old timeline and saved copies. Non-hosts cannot independently reset shared play. |
| Controls → edit → Save/Cancel | Current binding inventory and idle hints agree with committed mappings; delayed Save cannot alter a replacement draft/game. Conflicts remain rejected. |
| Controls → click mapped key → capture dialog | One dimmed screen-covering dialog, replacement prompt and Save/Cancel; no gameplay input escapes capture. All bindings remain discoverable, and dismissal/context replacement cannot leave stuck input or apply a stale draft. |
| Load game → Saved games → choose/cancel/retry | Full list or grouped overflow pages; complete names and usable selection. Empty/corrupt entry and delayed-read cancellation preserve the current lobby/game. |
| Audio → permission/device/connection failure | Game and chat continue; one relevant retry stays visible. Existing sound/voice settings survive switching sections. |
| Header → Set Password/name edit | Host can change access without leaving; guests retain correct admission behavior. Full names remain readable and dialogs do not resize unrelated controls. |

## Change the cartridge for the same group

[#282](https://github.com/TuringTestee/retro-coop/issues/282) adds the repeat-game journey. The lobby belongs to its group, so choosing a different cartridge must not close it or remove its members.

- Keep one host **Change game** action reachable before play, during play and while paused. Retain the existing picker, file/catalog/saved choices and supported ZIP input. Phone and expanded views must expose that same action through their reserved controls; no new page or duplicate task button.
- Choosing/canceling the picker does not change the current game. Validate a candidate before replacing it; show progress and Cancel in the current game region. Guests cannot independently replace the shared cartridge.
- A committed replacement retains lobby ID, invite/access, names, occupied physical slots, slot openness, roster and chat. Controller roles follow the new cartridge’s supported player count automatically, using the existing five-slot policy: the second occupant watches a one-controller game without leaving or moving; returning to a two-controller game makes that slot Player 2 again. Other spectators keep watching. No manual role repair or new dialog is required. Show the new preview and fresh preparation state. Each occupied supported controller explicitly prepares again; then the host starts from the centered overlay. Spectators do not gate Start.
- Invalid/unsupported files, canceled selection, failed upload/download, changed authority and failed native staging/commit keep the old game, controller assignments and group. If coordination already paused play, preserve the old completed state and offer the existing preparation/resume route and a usable replacement retry. Do not show success or resume a partially replaced group.
- Old readiness, held input, editing drafts, delayed saves, previews and recovery results cannot apply to the replacement. Existing saved copies remain associated with their original game.

| Journey | Required observation |
|---|---|
| Prepare → waiting → Start | One centered host Start, correct readiness reason, no footer Start; non-hosts have no Start authority. |
| Host/P2/spectator play → Change game → new Prepare/Start | Same identities, occupied slots, invite/access and chat; supported controller roles, new matching native cartridge identity and actual supported input after Start. |
| Two-controller → one-controller → two-controller | Same occupants and positions; former P2 watches the one-controller game and cannot send input or block Start, then explicitly prepares as P2 for the two-controller game. Other spectators remain nonblocking. Failed/canceled replacement in either direction keeps the old assignments. |
| Playing or paused → cancel/invalid candidate | Old playable state and group retained; picker can be used again. |
| Coordinating replacement → failure/disconnect/cancel | Old completed state restored on reachable controllers; no partial play, bounded actionable recovery and no stale success. |
| Phone or expanded game → Change game | Existing selection flow is discoverable and returns to the same lobby; primary action and feedback remain inside fixed regions. |

## Review and implementation gate

Before implementation, independently review and merge this revision. Reuse unaffected reference, journey and scenario artifacts rather than creating another complete design set. Implement with existing Controller, Settings, LocalPlayer, controls and shared-load owners; remove superseded section callers and maintained test expectations together.

Author verification must exercise these journeys through the public entry point on desktop, 320×568 phone, short landscape and real browser zoom. Observe both button state and native input, every supported action's actual binding, five-second hints, fullscreen Save/Load and recovery, ownership/context changes and keyboard typing. Replace superseded Load consent checks with direct-load, rollback and authority checks; preserve voice-decoding and cleanup checks. Local audio testing uses the verified silent sink.

Design critique: complete journeys and feature support are represented in the table; facts appear on idle or deliberate Controls selection; there is one settings route and no Profile/Lobby duplicate; labels distinguish input and actions; geometry stays reserved; controller/lobby patterns reuse the cited references. Fit, accessibility, native input and recovery remain implementation obligations, not proven by this sketch.
