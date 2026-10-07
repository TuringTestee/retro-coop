The acceptance cases include release and ownership races, not just painted buttons.

Audience: Human

# Mobile controller scenarios

| Scenario / journey | Trigger → visible result | Recovery |
|---|---|---|
| S1/J1 empty/loading/ready | Controller region is reserved from initial desktop preparation; mappings use current preferences, Load/Prepare remains primary. Mapping edits are available before readiness, but gameplay input is admitted only after authoritative preparation. | File-picker Cancel and failed-selection Retry remain in their region. Shared-game preparation has progress and deadline/error retry, without a visible Cancel preparation action. |
| S2/J1 draft mapping | Controls → click the mapped key → screen-covering capture dialog; Save/Cancel stay in that dialog and leave the surrounding layout unchanged. | Duplicate action, Tab/Escape navigation or failed preference persistence cannot silently replace saved mappings; explain and permit correction/cancel. |
| S3/J2 simultaneous contacts | Drag diagonally while holding A+B; each held target lights independently. Two contacts on A do not lose A when one releases. | pointerup/cancel/lostcapture clears only that contact; release all becomes neutral. |
| S4/J2 interrupted input | Blur, hidden, orientation, pause, editing, dialog, role loss, reconnect or leave while held. | Clear virtual holds without resuming old presses. Preserve the existing game/role recovery. |
| S5/J3 compact geometry | 320×568 portrait and 568×320 landscape, safe-area insets; legal 80-codepoint lobby label/32-codepoint names/five members in lobby view. | Approved phone layout: selected panel keeps its reserved bounds; reserved header values and centered edit dialogs show complete names, Players shows all five members, Chat preserves history and draft. First usable play entry automatically opens the phone expanded view; desktop entry remains manual. No viewport-equality branches, clipped targets, tiny text or new scroll. |
| S11/J3 play-entry expansion | Phone Start or synchronized late join reaches usable play; then Return, pause/resume, reconnect and repeated room updates. | Expand once for the actual play session after the game is locally loaded; preserve the chosen panel and running game after Return. No repeated reopening or browser fullscreen permission dependency. |
| S6/J3 fullscreen control | Pointer/touch activation, keyboard focus or idle timeout. | Lobby game-container click or its Enter/Space activation expands only usable play; no duplicate Full screen entry button. Only the 44px black top row returns; its named Return action remains keyboard accessible. Game/lower letterboxing and the entire controller band, including blank gaps, never return. Return restores the same lobby, not Main Page. |
| S7/J4 chat/settings | Type mapped keys in chat or capture dialog; touch controller around menu transitions. | No game input from editable fields or stale pointer ownership; return with a fresh press. |
| S10/J2 mixed input focus | Hold a keyboard direction, press virtual A with the pointer, release A while the keyboard direction remains held; then move focus to chat. Activate a controller button with its semantic keyboard key. | Pointer focus preserves the independent direction; release clears only its own source. Chat suppresses/releases game input. Semantic activation produces one intended NES action and does not expand the game. |
| S8/J5 authority | Spectator presses, preparing late join, promotion, demotion or departure shifting players. | Existing synchronization/ownership is authoritative; no duplicate local driver, auto-Ready or state reset. |
| S9/J6 teardown | Pending pointer capture plus centered leave confirmation. | Cancel does not revive held input; confirmed teardown leaves zero virtual mask before navigation. |

Feature → entry/state/feedback/recovery: NES buttons are in the controller during eligible play, highlight actual held masks, and clear on interruption. Keyboard editing has one entry per mapped key in Controls, including game and voice actions. Its capture dialog validates/persists on Save and restores on Cancel; it replaces the controller-band editor. Gamepad and talk remapping retain their current single owner. The game-container entry and top-row Return share one presentation owner; failed browser fullscreen retains the in-window game. Controller input and blank gaps cannot activate either transition. Other lobby tools keep their existing entry/feedback/recovery.

| Additional acceptance | Trigger → visible result | Recovery |
|---|---|---|
| Shared desktop/phone targets | Ordinary desktop lobby and expanded desktop/phone play → mouse/touch presses outside NES artwork reach the same proportional targets: pad 1/3, B/A 1/6 each, Select/Start 1/12 each. Center upper half sends no game input or presentation action. | Simultaneous holds, drag, independent release, cancel and rotation preserve the existing input owner; all interrupted holds clear. |
| Interaction exclusions | Click picker, game tools, notifications or preparation action; click a preview/loading game container. | Only the intended action occurs; no expansion/return or duplicate input. Error/deadline retry remains usable without Cancel preparation; file-picker Cancel still works. |

Use the [direction](mobile-controller-direction.md#safe-expansion-and-return) for exact presentation boundaries. Verify ordinary and small desktop, both existing phone orientations, mouse and touch, and keyboard entry/Return without relying on one viewport equality.
