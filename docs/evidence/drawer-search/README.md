# The drawer search finds Settings and app actions: evidence

Change: `openspec/changes/the-drawer-search-finds-settings-and-app-actions/`.

## Host (tasks 1.x, 2.x)

Evidence class: host build, unit tests and host renders only. No board,
compositor, camera or glass was involved.

- `cargo test --offline` in `nix/rust-shell-client`; the narrow runs are
  `search::` (ranking, gating, activation, privacy), `catalog::` (action names
  read once at scan time), `drawer_search_activation` (what choosing a result
  does, and the Settings scroll that shows an inline row), `navigation::`
  (result row geometry and hit-testing) and
  `render::tests::drawer_search_results_paint_as_rows_at_the_largest_text_step`
  (both panel shapes at the 200% text step).
- `cargo run --offline --example render_drawer_search_evidence` wrote the PNGs
  in `host/`: `<shape>-<step>-<query>.png` for 1232x568 (`landscape`) and
  568x1232 (`portrait`) at 100% and 200%, with queries `""` (the grid),
  `wifi`, `ti`, `pref` and `location` with and without the modem.

Limits of the renders:

- The catalog is a fixture (Calculator, Files, Terminal, Timer, Video) with no
  icons, so app rows show the initial circle. The Terminal and Files entries
  carry fixture actions.
- There is no theme generation. The first-row outline is the theme's
  `hover-cursor` border, which an unthemed render does not draw, so the outline
  is not visible in these images; its geometry is covered by the same row rect
  Enter and hit-testing read. UNVERIFIED on the board.
- Without a generation the text is drawn at the 100% size inside the 200%
  layout, so the 200% images show the row geometry (card height, gap, how many
  rows fit), not the enlarged type. UNVERIFIED on the board at 200%.
- The modem and key-backlight rows follow the flags the renderer is given; on
  the board they follow `ServiceView::modem` and `key_backlight`, refreshed at
  the first typed character.
