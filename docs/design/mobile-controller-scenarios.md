The acceptance cases include release and ownership races, not just painted buttons.

Audience: Human

# Mobile controller scenarios

| Scenario / journey | Trigger → visible result | Recovery |
|---|---|---|
| S1/J1 empty/loading/ready | Controller region is reserved from initial desktop preparation; mappings use current preferences, Load/Ready remains primary. Controls cannot alter an unprepared game. | Current cancel/retry game selection remains in its region. |
| S2/J1 draft mapping | Edit → choose action → capture key → connected line updates in draft; Save/Cancel share the reserved editor footer. | Duplicate action, Tab/Escape navigation or failed preference persistence cannot silently replace saved mappings; explain and permit correction/cancel. |
| S3/J2 simultaneous contacts | Drag diagonally while holding A+B; each held target lights independently. Two contacts on A do not lose A when one releases. | pointerup/cancel/lostcapture clears only that contact; release all becomes neutral. |
| S4/J2 interrupted input | Blur, hidden, orientation, pause, editing, dialog, role loss, reconnect or leave while held. | Clear virtual holds without resuming old presses. Preserve the existing game/role recovery. |
| S5/J3 compact geometry | 320×568 portrait and 568×320 landscape, safe-area insets; legal 80-codepoint lobby label/32-codepoint names/five members in lobby view. | Use the owner's selected expanded-play policy; no viewport-equality branches, clipped targets, tiny text or new scroll. |
| S6/J3 fullscreen control | Pointer/touch activation, keyboard focus or idle timeout. | One toggle remains discoverable and keyboard accessible when faded; focus/proximity restores full contrast. Return restores the same lobby, not Main Page. |
| S7/J4 chat/settings | Type mapped keys in chat or capture dialog; touch controller around menu transitions. | No game input from editable fields or stale pointer ownership; return with a fresh press. |
| S8/J5 authority | Spectator presses, preparing late join, promotion, demotion or departure shifting players. | Existing synchronization/ownership is authoritative; no duplicate local driver, auto-Ready or state reset. |
| S9/J6 teardown | Pending pointer capture plus centered leave confirmation. | Cancel does not revive held input; confirmed teardown leaves zero virtual mask before navigation. |

Feature → entry/state/feedback/recovery: NES buttons are in the controller during eligible play, highlight actual held masks, and clear on interruption. Keyboard edit has one Edit entry in the controller; Controls section reveals that same entry during live play, Save validates/persists, Cancel restores. Gamepad and talk remapping retain their current single owner. The top-right fullscreen control and requested canvas gesture activate the same presentation state; failed presentation retains the in-window game. Controller input cannot activate that gesture. Other lobby tools keep their existing entry/feedback/recovery.
