# Relay route status: reference evidence

A connection status should tell players when a relay is carrying their session, without guessing why the direct path was unavailable.

| Reference and task | Observed behavior | Decision for Retro Coop | Limit |
| --- | --- | --- | --- |
| [Tailscale connection types](https://tailscale.com/docs/reference/connection-types): identify an active connection's route | Its status distinguishes `direct` and `relay` for an active peer; it explains that network conditions can prevent a direct connection. | Borrow the truthful route distinction after the browser confirms the selected candidate pair. Give one short explanation when `relay` is selected. | Tailscale's CLI and network details are for diagnostics, so do not add IPs, server names or traffic counters to the play UI. |
| [Tailscale device connectivity](https://tailscale.com/docs/reference/device-connectivity): recover from direct-path failure | The product can use a relay when a direct path is unavailable. | Show relay as a successful connection, not a game error. Keep the existing retry controls only for an actual connection failure. | Its transport is different from WebRTC; this observation does not prove why a particular Retro Coop path relayed. |
| [Discord voice connection errors](https://support.discord.com/hc/en-us/articles/115001310031-Voice-Connection-Errors): show a connection failure | It gives separate states such as RTC Connecting and No Route. | Keep failure text and retry distinct from the connected-via-relay state. | The article does not specify Retro Coop's WebRTC route and does not justify copying its wording. |

Observed interaction: label the actual active route and keep errors separate. Inference for this product: a concise, persistent play-side status reduces uncertainty when the selected route is relayed. Do not say a firewall blocked traffic because the selected WebRTC route alone cannot identify the exact cause.
