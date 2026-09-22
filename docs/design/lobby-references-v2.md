Successful lobby systems make it clear where to find a game, which room will be joined, who controls the start, and whether a slot is open. Retro Coop can borrow those interaction patterns while keeping its own two-player browser rules.

Audience: Human

# Comparable lobby evidence

This is the reference-study step of the UI design workflow. The observations below come from publisher documentation; the Retro Coop decisions are design inferences, not claims that those products use our room lifecycle.

| Reference and task | Observed action and result | Retro Coop decision |
|---|---|
| [Don't Starve Together: Browse Games and Host Game](https://support.klei.com/hc/en-us/articles/5579659658772-DST-How-to-play-split-screen-online-offline-LAN-on-Nintendo-Switch) | Klei's instructions send a joining player to **Browse Games** and a host to **Host Game**. The browser exposes a Connection filter. | Open on one browseable room list. Keep **Host a game** distinct and show connection restrictions near joining. Do not copy world generation or DST's server ownership. |
| [Warcraft III: create a custom game](https://news.blizzard.com/en-us/article/23395649/revisiting-the-warcraft-iii-editor) | Blizzard describes creating a named lobby, inviting friends through open slots, then using **Start Game**. | Give each room an exact identity, visible player slots, invitation, and a host-controlled **Start game** action. |
| [Don't Starve Together: missing servers](https://support.klei.com/hc/en-us/articles/360060509731-Missing-Servers-Server-Suddenly-Disappeared) | Klei explains that a server listing can disappear for several reasons and gives recovery checks. | Show directory connection/error status and Retry rather than presenting a stale list as joinable. This is a design inference, not the same failure model. |

## Transfer limits

DST's persistent worlds and Warcraft III's map/lobby creation do not establish that a zero-player room can host itself. Retro Coop's service can list an empty room; the first human must become the browser host. Neither reference proves that a later guest can safely join a progressed NES game. That behavior needs its own implementation and verification.

## Step 1 principle check

The borrowed patterns serve concrete decisions: a visitor chooses a room from one list, distinguishes open slots, and sees who may Start. The source table states the observed action and the Retro Coop decision separately. No artwork, tagline, world-creation flow, or dedicated-server claim is imported. The later artifacts must still prove detailed journeys, feature support, information timing, and one forward action on each screen.
