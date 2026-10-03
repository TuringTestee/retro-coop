The portrait sketch cannot fit. Keep existing lobby content intact and separate expanded thumb play from lobby interaction.

Audience: Human

# Mobile controller critique v 1

| Screen | Supports / missing / remove / exact revision |
|---|---|
| Desktop | Supports J 1 and preparation feedback. Current source has a second NES mapping list: remove its duplicated NES keyboard rows when the controller editor becomes authoritative; keep gamepad/talk configuration. Live editing must enter the same controller editor through Controls, not a new page. |
| Portrait lobby | Supports lobby/chat/slot actions, but adding controls exceeds 568px and the 96px game track. Failed J 2: buttons cannot be reached without covering another required region. Revise to expanded-play view, with an explicit owner decision about automatic versus manual entry. Do not call an undersized controller an implementation of the request. |
| Landscape expanded | Supports J 2/J 3, but minimum dimensions/idle/exit need explicit bounds. Add 96px pad,64px A/B targets,44px Select/Start and fullscreen target; keep a visible idle target and clear holds before layout changes. |

Seven-rule assessment (D desktop, P portrait lobby, L expanded landscape):

| Rule | D | P | L | Evidence / revision |
|---|---|---|---|---|
| Complete journeys | unproven | failed | unproven | Add live edit, spectator/late-join and interrupt states; portrait route cannot reach usable play. |
| Feature support | failed | failed | unproven | Remove second editor; replace impossible portrait controller with explicit expanded entry policy. |
| Information just in time | met | failed | met | Desktop prep shows saved keys; portrait crowded controls prevent distinguishing next action. |
| One clear forward path | failed | failed | met | One Edit and fullscreen toggle; no canvas-click second toggle; policy needed for portrait entry. |
| Concise and consistent | met | failed | met | NES names/key lines are concrete; remove impossible appended row, not existing names/chat. |
| Stable layout | unproven | failed | unproven | Reserve controller/mapping bands; current portrait addition has no available region. |
| Borrow before inventing | met | met | met | [Nintendo/Riot/API references](mobile-controller-references.md); touch comfort remains to prove. |

These scores concern the sketch, not an implemented product. V 2 must expose the unresolved mobile choice and reserve actual target geometry.
