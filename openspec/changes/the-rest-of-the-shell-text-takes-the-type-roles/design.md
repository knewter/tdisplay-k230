## Context

The roles are `TYPE_TITLE` 40, `TYPE_BODY` 30, `TYPE_LABEL` 26 and
`TYPE_CAPTION` 26 px in `render.rs`, with `themed_role_fit` to shrink a line
toward (never below) its role at a large step. The drawer showed the pattern:
size the cell from the label it must hold, wrap names onto two lines, and fit
shell text rather than ellipsize it.

## Decisions

- **Home grid.** Size a cell from the plate, a gap and one 26 px label line
  (two at larger steps) rather than from the plate alone. Fewer columns fit;
  `home_grid::columns_for_width` and `HomeLayout::reflow_to` already handle a
  column change. Folder overlays follow the same cell.
- **Widgets.** Captions use the Caption role scaled to the cell, with the
  role's floor at a Home-sized cell, as Battery details already does
  (`BATTERY_TEXT_FLOOR`).
- **Shade rows, Wi-Fi, Help, theme grid, recovery.** Replace literal sizes
  with roles and derive row heights from `vision_line(role)`.

## Risks

- A Home grid with fewer columns moves a person's icons. The reflow keeps
  their order; the board check confirms it on a populated layout.
