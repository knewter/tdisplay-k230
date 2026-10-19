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

## Risks

- The landscape plate shrinks from 108 to about 97 px; it stays above the
  48 dp tap floor and the cell (the tap target) is unchanged.
- Long app names ("Terminal", "Settings") are shortened in a narrow cell.
