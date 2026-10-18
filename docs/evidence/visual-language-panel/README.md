# The visual language on the panel

Change: `openspec/changes/the-shell-has-one-visual-language`, task 5.1.

Evidence class: native `grim` captures on the board. They show what the
shell draws; they are not the operator's judgement on glass (5.2).

## Setup (2026-10-17)

- **System.**
  `/nix/store/a4241ifl36r41l3ccx24prrsq5p2q1n0-nixos-system-nixos-26.11.20260919.20b1ddd`,
  built from `caaf4ff4`. That commit includes the type roles (2.1), the
  card jobs and accent rule (3.1–3.3) and the stroked icons (4.1). It was
  deployed live with `switch-to-configuration test`.
- **Output.** DSI-1 was the only active output, at 1232x568 landscape;
  HDMI was unplugged.
- **Theme.** retro-82 with its vinyl wallpaper.
- **Steps.** Set with
  `k230-theme vision --text-scale default|largest --contrast standard`. The
  board was returned to `default` afterwards.
- **Navigation.**
  - Home, the drawer, Settings and the Shade were opened with
    `k230-shell-rust --surface hide|drawer|settings|shade`.
  - The Vision page was reached with an injected uinput tap on "Vision ›"
    (`/tmp/bp.py`), at (981,108) at 100% and (800,163) at 200%.

| File | Surface |
|---|---|
| `board-panel-100-home.png`, `board-panel-200-home.png` | Home: Clock, Battery widget, dock |
| `board-panel-100-drawer.png`, `board-panel-200-drawer.png` | Drawer |
| `board-panel-100-settings.png`, `board-panel-200-settings.png` | Settings |
| `board-panel-100-vision.png`, `board-panel-200-vision.png` | Vision page |
| `board-panel-100-shade.png`, `board-panel-200-shade.png` | Shade, with no notifications |

## What the frames show

- **Home.**
  - The Clock has a cream hour and an orange minute with the dark halo,
    over the teal and orange vinyl.
  - The dock is a Control card.
  - At 200%, the date and the Battery labels grow. The digits stay sized
    to the widget cell.
- **Drawer.**
  - The search pill has the stroked search glyph.
  - At 200%, the labels grow and the grid drops to four columns.
- **Settings.**
  - Control rows have a leading glyph sized to the label line.
  - Links are in the foreground colour.
  - At 200%, the Keyboard hint shrinks to fit its column rather than being
    cut off.
- **Vision.**
  - The chosen step is an orange Chosen pill: 100% in one frame, 200% in
    the other.
  - High contrast is off and drawn as a Control card.
- **Shade.**
  - The slider ends are stroked suns and a speaker.
  - The Keyboard toggle has its glyph.
  - At 200%, the header ("Notifications", "Settings ›", the battery line,
    the count) is shrunk to fit the narrow left column, keeping its
    proportions, as described in `docs/evidence/type-roles/README.md`. The
    empty-state line and the Keyboard toggle grow.

## Limits

- Only 100% and 200% were captured; 130% and 160% are covered by the host
  renders and the HDMI captures in `docs/evidence/type-roles/`.
- The Shade had no notifications, so "Dismiss all" and notification rows are
  not in these frames. They are in the host renders.

## Drawer on the type roles (task 2.3)

`board-panel-100-drawer-roles.png` and `board-panel-200-drawer-roles.png`:
native `grim` captures on DSI-1 (1232x568), retro-82, from the 80b12e58
closure (`/nix/store/5da7ihmgcabh7cpbyb28j3108yhbxiwk-nixos-system-…`,
deployed with `switch-to-configuration test`), 2026-10-18 about 06:05 UTC.
The drawer was opened with `k230-shell-rust --surface drawer`; the step was
set with `k230-theme vision --text-scale largest|default`.

- At 100%: six columns; names in the 26 px Caption role. "Files
  (Nautilus)", "Files (Portfolio)" and "Same Game" wrap onto a second line;
  nothing is ellipsized.
- At 200%: three columns; "Search apps" and Help in the Label role at the
  step, unshortened. The second row is cut by the scroll viewport, not by
  its tile.
- The search glyph stays 24 px at 200%.
- A terminal prompt shows through the 32 px gap above the sheet. That gap
  existed before this change.

`host-drawer-steps-568x1232.png` (100/130/160/200/200 high contrast) and
`host-drawer-steps-1232x568.png` (100, 130 / 160, 200) are host renders from
`render_accessibility_scale_evidence` over catppuccin generations with stock
app names.
