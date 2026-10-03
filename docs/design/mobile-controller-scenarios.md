The acceptance cases include release and ownership races, not just painted buttons.

Audience: Human

# Mobile controller scenarios

| Scenario / journey | Trigger → visible result | Recovery |
|---|---|---|
| S 1/J 1 empty/loading/ready | Controller region is reserved from initial desktop preparation; mappings use current preferences, Load/Ready remains primary. Controls cannot alter an unprepared game. | Current cancel/retry game selection remains in its region. |
| S 2/J 1 draft mapping | Edit → choose action → capture key → connected line updates in draft; Save/Cancel share the reserved editor footer. | Duplicate action, Tab/Escape navigation or failed preference persistence cannot silently replace saved mappings; explain and permit correction/cancel. |
| S 3/J 2 simultaneous contacts | Drag diagonally while holding A+B; each held target lights independently. Two contacts on A do not lose A when one releases. | pointerup/cancel/lostcapture clears only that contact; release all becomes neutral. |
| S 4/J 2 interrupted input | Blur, hidden, orientation, pause, editing, dialog, role loss, reconnect or leave while held. | Clear virtual holds without resuming old presses. Preserve the existing game/role recovery. |
| S 5/J 3 compact geometry | 320×568 portrait and 568×320 landscape, safe-area insets; legal 80-codepoint lobby label/32-codepoint names/five members in lobby view. | Use the owner's selected expanded-play policy; no viewport-equality branches, clipped targets, tiny text or new scroll. |
| S 6/J 3 fullscreen control | Pointer/touch activation, keyboard focus or idle timeout. | One toggle remains discoverable and keyboard accessible when faded; focus/proximity restores full contrast. Return restores the same lobby, not Main Page. |
| S 7/J 4 chat/settings | Type mapped keys in chat or capture dialog; touch controller around menu transitions. | No game input from editable fields or stale pointer ownership; return with a fresh press. |
| S 8/J 5 authority | Spectator presses, preparing late join, promotion, demotion or departure shifting players. | Existing synchronization/ownership is authoritative; no duplicate local driver, auto-Ready or state reset. |
| S 9/J 6 teardown | Pending pointer capture plus centered leave confirmation. | Cancel does not revive held input; confirmed teardown leaves zero virtual mask before navigation. |

Feature → entry/state/feedback/recovery: NES buttons are in the controller during eligible play, highlight actual held masks, and clear on interruption. Keyboard edit has one Edit entry in the controller; Controls section reveals that same entry during live play, Save validates/persists, Cancel restores. Gamepad and talk remapping retain their current single owner. Fullscreen has one top-right toggle; failed presentation retains the in-window game. Other lobby tools keep their existing entry/feedback/recovery.
