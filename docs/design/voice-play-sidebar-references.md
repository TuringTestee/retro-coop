Audience: Human

These references show why current controls and voice status should sit beside the game while detailed settings remain separate.

# Voice and play sidebar: comparable interactions

Players need to see how to control a game and opt into voice while the game remains visible. This note records the outside patterns used for the proposed sidebar.

| Reference and evidence | Observed action and result | Decision for Retro Coop | Limit |
|---|---|---|---|
| [Steam Input guidance](https://partner.steamgames.com/doc/features/steam_controller/getting_started_for_devs) | Valve describes in-game prompts using controller glyphs for the active device and action names tied to remappable controls. | Show the current local bindings for NES actions, sourced from saved controls. Switch the displayed device when the player selects a gamepad. | The guidance does not specify a persistent sidebar or exact layout. |
| [Steam Input player guide](https://partner.steamgames.com/doc/features/steam_controller/getting_started_for_players) | Player changes a controller region's assigned action in a separate configuration view; games can change active action sets as context changes. | Keep remapping in existing Settings; the playing reference only reads mappings. Include Push to talk only when that mode applies. | Retro Coop has one NES action set, so no action-set selector. |
| [Discord voice troubleshooting](https://support.discord.com/hc/en-us/articles/360045138471-Discord-Voice-and-Video-Troubleshooting-Guide) | A player checks mute state, then microphone/device settings and permission when speech fails; remote volume has a separate control. | Show microphone state and the immediate Enable/Mute/Unmute action beside the game; keep device and remote volume in the existing Voice detail. | Discord's server roles and social interface do not transfer to a two-player room. |
| Current Retro Coop shared play screenshot at `aa2c897` (`/tmp/retro-gameplay-full/shared.shared-playing.png`, local author evidence) | Canvas fills the left region; room details fill the right; Voice is collapsed and control bindings are absent. | Put one compact play reference in the existing right region, above less frequent room tools. Keep the canvas fixed in its own region. | The screenshot shows one desktop size, not accessibility or narrow-window success. |

The selected pattern is an inference from these observed controls: current actions should be visible in play, while configuration remains in a separate page. This is a proposal, not implementation proof.