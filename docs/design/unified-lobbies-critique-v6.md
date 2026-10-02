The v6 screens keep settings open in the right column. Change game stays above the game; Copy invite sits beside the lobby name. This critique covers the menu correction against the current lobby journey.

# Unified lobbies: critique v6

| Screen | Supports | Removed or changed | Remaining implementation check |
| --- | --- | --- | --- |
| Directory | Host row and clickable lobby rows lead directly into the lobby | No new controls | Recheck long names and unavailable reasons in the running app |
| Lobby | Players, center game, settings, chat and footer hold their tracks; sections change within settings | No close control for settings; voice and access stay inside settings; Copy invite remains a direct action | Confirm the settings column persists after outside click, Escape and clipboard failure at narrow widths |
| Slot menu | Direct legal moves and kick stay attached to the slot | No new controls | Recheck dropdown alignment at all five positions |
| Playing | Game stays central, with settings on the right and chat below; click fills the screen | No duplicate sound/voice action outside settings | Confirm center game and settings remain visible after fullscreen return |
| Theme and guide | Top-right theme control, matched player/settings surfaces, centered Select/Start and color-linked keyboard rows preserve the same layout | No separate theme screen or controller popup | Check light contrast, 320-pixel header and every guide row in both modes |

## Seven-rule check

| Rule | Design result and evidence |
| --- | --- |
| Audience choice | Met: toolbar actions name outcomes; access is Public or Password protected; connection route is automatic in [direction](unified-lobbies-direction.md). |
| One primary path | Met: directory Host or row join, lobby Load → Ready → Start, and live play are shown in [v6](unified-lobbies-wireframe-v6.md). |
| Timely information | Met: game selection is deferred until the lobby; the key guide and sound appear in settings during play. Voice starts when a peer connects and uses push to talk until deliberately changed. |
| Terms and actions | Met: Settings remains the right column across lobby and play; Copy invite appears once beside the lobby name. |
| Complete recovery | Met in design: [scenarios](unified-lobbies-scenarios.md) give clipboard failure a selectable link and preserve the settings column. Runtime proof remains required. |
| No duplicate route | Met: the lobby has no separate settings page, close control, or second invite action. |
| Stable regions | Met in design: the fixed players/game/settings/chat/footer tracks appear in both lobby states and both themes; [implementation](../implementation/unified-lobbies.md) records browser geometry proof. The narrow header gets a second fixed line rather than clipping names. |

The wireframe is design evidence. Runtime accessibility and the stated narrow-width checks are evaluated in the browser suites.
