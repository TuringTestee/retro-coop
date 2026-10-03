Make NES controls recognizable and reachable with two thumbs; borrow the arrangement, not unrelated game menus.

Audience: Human

# Mobile controller references

| Observed source | Interaction → proposal | Transfer limit |
|---|---|---|
| [Nintendo Super Mario Bros. manual](https://www.nintendo.co.jp/clv/manuals/en/pdf/CLV-P-NAAAE.pdf) | Physical direction pad left, Select/Start center, B/A right → keep that Famicom arrangement and matching keyboard lines. | Physical hardware does not establish touch target size or browser usability. |
| [Riot Wild Rift move-stick notes](https://wildrift.leagueoflegends.com/en-us/news/game-updates/wild-rift-patch-notes-2-2/#controls-and-settings) | Riot reports an initial drag can reverse direction when stick-center placement is constrained → keep the touch origin inside a bounded pad, avoiding initial-direction reversal. | NES has eight digital directions; do not introduce analog movement, aiming or MOBA menus. Two-thumb placement is owner direction, not proven by this article. |
| [Pointer Events guide](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_events/Using_Pointer_Events) | Track simultaneous contacts by pointer ID and remove canceled contacts → independent direction/A/B holds with reliable release. | API guidance is an implementation reference, not product journey evidence. |

Current source at `a8eed786`: `PlayingTools` already renders the static controller and configured-key lines in started Game settings; `Settings` owns remapping and `LocalPlayer` owns the emitted mask. No browser reproduction of complete controller absence was performed. The requested replacement removes the extra settings-selection step needed to see the controller and makes its buttons actual input.

Inspected #208 capture supplied by its owner (`fe2ef51`): 320×568, legal maximum CJK names, five occupied places. Header 104px/status 40px/footer 52px; stage 372px includes chat 50px. Player rail 224px leaves only 96px for game/settings; actual NES is 96×90. This is design evidence for a space constraint, not acceptance of #216.
