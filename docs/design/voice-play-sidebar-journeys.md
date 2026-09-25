Audience: Human

Players can find controls, speak with a partner, recover from errors, and leave without losing the game.

# Voice and play sidebar: player journeys

This scope begins after a player has entered or started a game. Each path names the next action, visible feedback and a way out when it fails.

| ID | Player journey | Outcome and recovery |
|---|---|---|
| V1 | Host or guest enters shared play → sees `Voice · Off` in the side rail → chooses `Enable voice` → browser asks for microphone access → card shows pending, then `Mic on` or `Hold to talk` → speaks with the other player. | If access is denied or no device exists, card states why and offers `Try again`; detailed device choice is in Voice settings. Game and text chat continue. |
| V2 | Speaking player sees `Mic on` → chooses `Mute` → card shows `Muted` → chooses `Unmute` when ready. Push-to-talk player holds the displayed mapped key or `Hold to talk` control; release stops transmission. | On blur, the captured mic stays present but muted; unmute deliberately. Reconnect or leave stops tracks and requires new opt-in. |
| V3 | Player cannot hear partner → reads `Remote voice muted` or playback error in Voice detail → chooses `Unmute remote voice` or `Enable voice sound` → hears partner. | If audio is still unavailable, adjusts remote volume/device/browser output; game continues. |
| C1 | Player enters play → sees current local `Controls` card beside canvas → focuses game → presses displayed direction/A/B/Start/Select binding. | If a key is `Unbound` or wrong, chooses `Edit controls` → remaps in Settings → returns to play and sees updated label. |
| C2 | Player selects gamepad in Settings → returns to game → side card identifies the selected device and its mapped actions → plays. | If device disconnects, existing input warning offers `Use keyboard`; the card then shows keyboard bindings. |
| C4 | Player and partner accept a controller reassignment in Session controllers → return to shared play → card shows the accepted local P1/P2 port or says the player is idle while the partner owns Shared P1. | If a proposal is declined/cancelled, card keeps the old assignment; a lost peer follows existing pause/recovery. |
| C3 | Player uses a narrow viewport or keyboard/assistive input → game and cards remain in document order, with no overlay → reads/activates controls. | If a card must wrap, its text remains readable and controls reachable without horizontal overflow. |
| E1 | Player leaves room or peer drops → voice card stops or reports connection state → player can retry connection or leave. | Microphone tracks stop on leave, kick, expiration and peer replacement; solo local game remains available where existing recovery allows. |

V1/V2/V3 derive from the user request plus approved U7 voice behavior. C1/C2/C3/C4 derive from the new shortcut request and current remappable controls. E1 preserves the approved release path. The primary route for editing remains Settings; the side card is a readout, not a second editor.