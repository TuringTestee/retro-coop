Each controller action stays in the existing lobby or game; editing and returning from expanded play never creates a second session.

Audience: Human

# Mobile controller journeys

[Direction and unresolved mobile default](mobile-controller-direction.md) govern these journeys.

| ID / actor | Entry → action → result | Recovery / completion |
|---|---|---|
| J 1 desktop host or guest preparing | Find/host lobby → load/synchronize game → see Famicom and actual key lines → optionally Edit, select a key/action, Save → Ready; host Start still requires every occupied controller owner prepared. | Conflict blocks Save with the action using that key; choose another or Cancel. Nothing is sent to the emulator while editing. Complete when saved keys match the guide and the player can Ready. |
| J 2 synchronized controller owner playing | Start/late-join synchronization → mappings disappear → hold direction plus A/B with mouse/touch/keyboard → ordinary existing frame input advances the game. | Releasing one contact retains other contacts. Cancel/lost capture/focus loss/pause/role loss releases virtual input; resume requires a fresh hold. Complete when combined input reaches only the assigned controller and all releases return neutral. |
| J 3 touch portrait/landscape | Enter live play → expanded-view policy chosen by owner → pad left, Select/Start center, B/A right near bottom → rotate while playing. | Rotation clears holds and lays out the same reserved targets using safe areas. If expansion is declined/unavailable, existing in-window expansion remains usable; no frozen game or lost lobby. Complete with reachable controls and an unobscured main game area. |
| J 4 live settings/chat/moderation | Return to lobby view → same five slots/chat/settings → select Controls to reveal the existing inline editor, or type/send/kick using current paths → Full screen to continue thumb play. | Focus/edit/dialog boundaries release input. A role change or late join never bypasses authoritative preparation. Complete after returning to the same advancing game with the saved mapping or resolved lobby action. |
| J 5 spectator or unsynchronized member | Join an ongoing game → preserve current preparation/synchronization feedback → watch without emulator input → promoted synchronized owner gets the controller. | A rejected role change keeps its current remedy. No virtual mask is admitted until the existing game driver grants ownership. Complete at watching or synchronized play; a control's visual presence is not authorization. |
| J 6 leave | Return to lobby view → existing Back to Main Page/confirmation → teardown → directory. | Cancel retains the usable session; failed leave retains its recovery. All virtual contacts, keyboard/gamepad holds and capture ownership end before directory navigation. |
