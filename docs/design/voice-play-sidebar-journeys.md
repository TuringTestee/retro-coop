Audience: Human

Players can find controls, speak with a partner, recover from errors, and leave without losing the game.

# Voice and play sidebar: player journeys

This scope begins after a player has entered or started a game. Each path names the next action, visible feedback and a way out when it fails.

The later [minimal room journey](minimal-room-journey.md) replaces the always-visible binding list in C1/C2 with a Controls action that opens Settings. Voice and input recovery paths below still apply.

| ID | Player journey | Outcome and recovery |
|---|---|---|
| V1 | Host or guest enters shared play → sees `Voice · Off` in the side rail → chooses `Enable voice` → browser asks for microphone access → card shows pending, then `Mic on` or `Hold to talk` → speaks with the other player. | If access is denied or no device exists, card states why and offers `Try again`; detailed device choice is in Voice settings. Game and text chat continue. |
| V2 | Speaking player sees `Mic on` → chooses `Mute` → card shows `Muted` → chooses `Unmute` when ready. Push-to-talk player holds the displayed mapped key or `Hold to talk` control; release stops transmission. | On blur, explicit mute stays unchanged and held push-to-talk releases under [Background voice](background-voice.md). Reconnect or leave stops tracks and requires new opt-in. |
| V3 | Player cannot hear partner → reads `Remote voice muted` or playback error in Voice detail → chooses `Unmute remote voice` or `Enable voice sound` → hears partner. | If audio is still unavailable, adjusts remote volume/device/browser output; game continues. |
| C1 | Player enters play → sees the current role and Controls action → opens Settings when a binding needs checking or changing. | If a key is `Unbound` or wrong, remaps it in Settings → returns with focus on Controls → reopens to see the saved value. |
| C2 | Player selects gamepad in Settings → returns to game and plays. | If the selected device is absent or disconnects, keep playing with keyboard/touch automatically; preserve that device preference and show usable bindings. |
| C4 | Player and partner accept a controller reassignment in Session controllers → return to shared play → card shows the accepted local P1/P2 role or Observer. | If a proposal is declined/cancelled, card keeps the old assignment; a lost peer follows existing pause/recovery. |
| C3 | Player uses a narrow viewport or keyboard/assistive input → game and cards remain in document order, with no overlay → reads/activates controls. | If a card must wrap, its text remains readable and controls reachable without horizontal overflow. |
| E1 | Player leaves room or peer drops → voice card stops or reports connection state → player can retry connection or leave. | Microphone tracks stop on leave, kick, expiration and peer replacement; solo local game remains available where existing recovery allows. |

V1/V2/V3 derive from the user request plus approved U7 voice behavior. C1/C2/C3/C4 reflect the later minimal room journey and current remappable controls. E1 preserves the approved release path. Settings remains the sole mapping list and editor.
