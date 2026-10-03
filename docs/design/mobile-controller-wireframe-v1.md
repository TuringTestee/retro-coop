This first sketch preserves all lobby regions and tests whether the requested controller can be added without concealing existing work.

Audience: Human

# Mobile controller wireframe v1

## Desktop preparation / J1

```text
┌ Lobby name: Pixel Harbor [Invite] ─ Your name: Alex ─ Theme ┐
│ Waiting for all players                                  │
├ Players ──────┬ Super Tilt Bro ───────────────┬ Settings ──┤
│ P 1 Alex Ready │        NES preview           │ Controls ▾ │
│ P 2 Sam Ready  │                              │ Device ▾   │
│ Spectator 3   │  ↑←↓→ ── Arrow keys          │ Gamepad ▾  │
│ Open Slot 4   │  Select ─ Alt  Start ─ Space  │ Voice      │
│ Open Slot 5   │  B ─ C            A ─ Z      │ Sound      │
│              │  [ + ] [Select][Start] [B][A]│            │
│              │                   [Edit]     │            │
├──────────────┴ Chat messages / message [Send]┴────────────┤
│ [Back to Main Page]                       [Ready][Start] │
└─────────────────────────────────────────────────────────┘
```

Edit replaces its own mapping band with focused key capture and Save/Cancel; duplicate-key feedback stays in that band. Loaded/empty/error content changes only the reserved preview. Game start hides key lines but keeps button positions.

## Portrait lobby play at 320×568 / J2–J4 (does not fit)

```text
┌ Lobby name / Invite / Your name / Theme ┐ 104px
│ Playing together                       │  40px
├ Five player rows ────────┬ Game/menu ───┤
│ Full legal names        │96px available│ 322px rail
│ Current states/actions  │ NES / menu   │
├ Chat messages / message [Send] ────────┤  50px
│ [Back to Main Page] [Ready / Pause]    │  52px
├ [96px pad] [Select][Start] [64px B][A] ┤ NEW≥100px
└───────────────────────────────────────┘
```

Existing rows already consume 568px. New controls exceed height and need 312px in one row before spacing, not the 96px game track. This sketch cannot be built faithfully by clipping, reducing name text or obscuring chat.

## Expanded landscape / J3

```text
┌ NES game ──────────────────────────────[Return to lobby]┐
│                 unobscured main game                  │
│                                                       │
│ [ direction pad / dot ]  [Select][Start]  [ B ] [ A ]  │
└────────── translucent targets; safe-area inset ─────────┘
```

The top-right control stays discoverable at idle and restores contrast on focus/proximity. Contacts belong to individual targets and do not toggle presentation. Actual thumb reach/game occlusion remain unproven.
