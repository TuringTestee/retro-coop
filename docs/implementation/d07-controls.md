Players can keep playing with keyboard and on-screen controls when an optional gamepad is unavailable. Personal mappings remain intact for its return.

Audience: Agent

# Local controls and presentation

## Input and recovery

Keyboard and on-screen controls remain usable alongside a selected gamepad. Missing, disconnected, replaced or restricted gamepad APIs must not block loading, preparation, Start or Resume, pause a running game, or suppress the remaining working inputs. Preserve the selected device and personal mappings. On its return, suppress held buttons/axes until released; do not replay old holds. Show bindings for usable input, without a required settings visit.

Focus loss, dialogs and typing release game input. Only the current synchronized controller owner can contribute shared input. Compatible ROM validation, shared state/barriers, membership authority and all occupied players Ready remain required. Optional sound, voice permission/negotiation, non-mutating preview and local persistence failures keep the core journey available; report an actionable failure without resetting progress or erasing saved data.

## Optional browser exclusion

When Web Locks is absent or fails, discard any copied stored guest token before connecting. A new server-issued guest may live only in this client’s memory, without writing its token to browser storage. That guest can reconnect within this client. A reload gets a separate guest; it cannot take over another tab’s active host/controller session. With usable Web Locks, retain normal exclusive ownership, stored-session recovery and real duplicate-tab protection. A lock contention result is not an API failure and cannot bypass exclusion.

## Scope and proof

Source: [#266](https://github.com/TuringTestee/retro-coop/issues/266) supersedes D07/issue #11’s selected-device pause/manual fallback requirement. Preserve remapping conflict checks, preference persistence, display/audio controls and the current lobby journey.

Exercise the public Host/Join → Load → Prepare/Ready → Start path for host and Player 2 with missing remembered input and loss/return during play. Verify actual keyboard/touch input, neutral return holds, retained preferences, matching native shared state, and pause/resume authority. Test missing Web Locks separately from copied-token contention. Cover optional sound/voice denial, preview failure and storage denial as preservation cases. Browser API emulation proves those capability boundaries, not a physical hardware matrix. Debug with text logs; keep automated audio on the verified silent test sink.

Run the README pre-flight and maintained Chromium checks within the [verification strategy](browser-nes-platform.md#verification-strategy). `controls.ts` owns shared input interpretation; `LocalPlayer` owns emulator resources, and `TabSession` owns browser exclusion. No emulator, role protocol or readiness relaxation is requested.
