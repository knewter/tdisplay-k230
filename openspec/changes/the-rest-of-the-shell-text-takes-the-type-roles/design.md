## Context

The roles are `TYPE_TITLE` 40, `TYPE_BODY` 30, `TYPE_LABEL` 26 and
`TYPE_CAPTION` 26 px in `render.rs`, with `themed_role_fit` to shrink a line
toward (never below) its role at a large step. The drawer showed the pattern:
size the cell from the label it must hold, wrap names onto two lines, and fit
shell text rather than ellipsize it.

## Decisions

- **Home grid.** Keep the column count and pages: fewer columns would push
  a 4-wide widget (Clock, Battery details) off the landscape page and out of
  a 3-column portrait page entirely. Instead the label takes the whole cell
  width in the Caption role, and a cell too short for the full plate above
  that label (the landscape panel's compact rows) gets a smaller plate.
  At a larger step the label grows only as far as the cell leaves room.
  App names longer than the cell are shortened, as the requirement allows.
  Open folders use the same cell content.
- **Widgets.** Captions use the Caption role scaled to the cell, with the
  role's floor at a Home-sized cell, as Battery details already does
  (`BATTERY_TEXT_FLOOR`).
- **Shade rows, Wi-Fi, Help, theme grid, recovery.** Replace literal sizes
  with roles and derive row heights from `vision_line(role)`.
- **Help and Wi-Fi layouts.** Both are computed from the roles at the
  current step and theme size (`help::layout`, `wifi_ui::Layout`), with
  wrapped text measured before it is painted. Help scrolls when it is
  taller than the output. A Wi-Fi Entry page that does not fit above the
  raised keyboard pans up, header included.
- **Theme chooser.** The portrait carousels take the height the role text
  leaves. Every output shows the omarchy-style carousels; the wide card
  grid is removed (operator decision 2026-10-19), and on a monitor the
  carousels grow, each centred card up to 70% of its half.
- **Card Overview.** The C card shell mirrors the roles as `CARD_TYPE_*` in
  `render.h` and sizes each label box from the theme's font scale.

## Risks

- The landscape plate shrinks from 108 to about 97 px; it stays above the
  48 dp tap floor and the cell (the tap target) is unchanged.
- Long app names ("Terminal", "Settings") are shortened in a narrow cell.
- Network names, app names and one-line status messages can still end in
  "…" when they are longer than their line at a large step.
- Monitors lose the all-at-once theme grid; browsing is by carousel only.
