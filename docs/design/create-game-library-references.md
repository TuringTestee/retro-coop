Players should be able to browse rooms without seeing hosting controls, then open a dedicated Create Game page to choose a game they already have or add one. Successful custom-game flows separate these tasks; Retro Coop adapts that structure to a two-player browser game.

Audience: Human

# Create Game reference study

| Reference and task | Observed action and result | Decision for Retro Coop |
| --- | --- | --- |
| [Don't Starve Together: Browse Games / Host Game](https://support.klei.com/hc/en-us/articles/5579659658772-DST-How-to-play-split-screen-online-offline-LAN-on-Nintendo-Switch) | Klei gives players separate **Browse Games** and **Host Game** actions. The browse path shows connection filters. | Put **Create game** in the room browser header; the ROM picker and access choice live on a separate page. A DST persistent world is not a model for our temporary room. |
| [Warcraft III: custom game](https://news.blizzard.com/en-us/article/23395649/revisiting-the-warcraft-iii-editor) | Blizzard describes **Custom Games → Create → choose a map → Create** before reaching the lobby. | Choose the game before publishing the room, then show the host's waiting room. We use one clear **Create room** action after selection to avoid two indistinguishable Create buttons. |
| [Age of Empires II: create a multiplayer match](https://support.ageofempires.com/hc/en-us/articles/360047306372-How-do-I-create-a-multiplayer-match-in-Age-of-Empires-II-Definitive-Edition) | Its support guide separates **Host Game**, lobby name/visibility setup, **Create Lobby**, and later **Start Game** after players ready. | Show Public/Unlisted in Create Game and retain the existing host-only Start in the waiting room. Extra AoE settings do not transfer to a two-player NES room. |
| [Age of Empires II: installed mods](https://support.ageofempires.com/hc/en-us/articles/360050397471-Scenario-Mods-Download-and-Installation-Instructions) | The game's Mod Manager distinguishes browsing from an **Installed Mods** tab where already downloaded content can be selected. | Show a browser-local **Your games** list on Create Game. Reuse verified ROM bytes by exact hash; do not imply server accounts or permanent storage. This is an adaptation, not a claim that AoE stores NES files. |

**Preview inference:** None of these sources establishes a ROM screenshot or cover requirement. Use an actual locally captured game frame for the most recent game's preview when one exists, with a text fallback. Never invent cover art or mistake an unrendered/blank frame for a successful preview.
