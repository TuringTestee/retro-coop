Use one controller and one input owner across the lobby and expanded game. Current bindings, editing and feedback follow the gameplay-controls direction; retained older sketches record the original phone-layout approval.

Audience: Agent

# Mobile controller implementation

Governing sources: [mobile direction](../design/mobile-controller-direction.md), [current gameplay controls](../design/gameplay-controls.md), [journeys](../design/mobile-controller-journeys.md) and [scenarios](../design/mobile-controller-scenarios.md). The [v4 wireframe](../design/mobile-controller-wireframe-v4.md) is a historical geometry/approval baseline, not authority for superseded Profile placement or inline editing.

## Ownership and layout

- One semantic Famicom controller occupies a reserved game band: pad left, Select/Start center and B/A right. Phone geometry follows the authoritative [touch-area table](../design/mobile-controller-direction.md#phone-touch-areas-272): derive all targets from one controller rectangle and adapt its height within the specified viewport shares. Keep visible NES artwork separate from the interactive regions; borders, padding and visual gaps cannot subtract from their hit areas. Never branch on one test viewport. Controller actions cannot activate the canvas expansion gesture.
- The existing input owner combines independent keyboard, gamepad and virtual masks. Releasing one source preserves other held sources. Blur, hidden state, rotation, capture loss, pause, editing, dialogs, role loss and exit release stale input. Typing and spectators cannot drive the emulator.
- Derive current labels and pressed feedback from active controls/input. Controls shows every implemented mapping together. Selecting its key opens the screen-covering capture dialog with validation and Save/Cancel; remove the superseded inline editor and one-row pagination. Scope drafts and delayed preference writes to the editor, loaded game and storage generation.
- Phones show one fixed Game/Players/Settings/Chat panel. Names remain readable/editable through reserved header values and centered dialogs. Automatically expand once on actual usable phone play entry, including synchronized late join. Return retains the selected panel and live game; repeated snapshots, pause/resume or reconnect cannot reopen it. Desktop expansion stays manual. The canvas and top-right control share this presentation owner.
- Complete Settings, centered preparation, idle key hints, Save feedback and shared Load/Restart follow the current gameplay-controls source. Use existing player, preferences, shared-load and voice owners; remove replaced callers, guides and tests together.

## Deliver the #272 geometry revision

After this governing revision is reviewed and merged, update the existing controller layout and pointer targets together. Replace fixed phone band/target dimensions rather than adding a second controller or input manager. Use the existing responsive layout and safe-area handling to choose a continuous band height within the approved range, including rotation and in-window expansion. Maintain the current draggable direction interpretation, multi-pointer ownership and release rules. Coordinate with the gameplay-controls implementation so live feedback, idle labels and capture dialogs use the same targets; do not change bindings or create another Settings route.

## Verification

Exercise J1–J6 through the public product with real native input and release, current/remapped keys, capture Save/Cancel/conflicts, late join, ownership changes, pending-write context replacement and exit. Verify simultaneous touch directions/A+B, keyboard direction plus virtual A, independent release and neutral input after interruption. Keep chat and live frames usable. For #272, measure the actual band and target rectangles against the governing fractions, including padding/borders. Exercise touches away from the visible artwork and at the outer edges, simultaneous pad plus A/B holds, and release outside the target. Confirm the unused center upper half sends no input, controller touches never toggle expansion, and rotation releases stale holds before applying new geometry.

Use one Chromium engine at ordinary desktop, 320×568 portrait, 568×320 landscape and real 200% zoom; viewport data must not alter product rules. Check the proportional band and nonoverlapping hit regions over varying phone heights and both orientations, with safe-area constraints, without device-specific exceptions or page scrolling. Test maximum accepted names and five visible slots in Players, readable header/dialog names, fixed regions and first-entry expansion/Return. Browser emulation proves event handling; physical comfort/safe-area qualification remains an explicit limit.

Run the README preflight and [platform verification strategy](browser-nes-platform.md#verification-strategy). Retain meaningful failures and publish actual transition captures, native frame/input observations and current-head results under all six review agendas. Reuse unaffected proof; no duplicate browser suite or matrix.
