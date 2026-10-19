## 1. Home

- [x] 1.1 Home app and folder labels in the Caption role across the cell,
  with a smaller plate where the cell is too short; columns, pages and saved
  layouts unchanged. Verify with `cargo test --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --tests` (updating `home-*.png`
  baselines deliberately). Host class.
  Done 2026-10-19 (host): all test targets pass; `home_grid::content_in`
  serves Home tiles and folder members, and the `home-*.png` baselines under
  `docs/evidence/shell-responsive/` were updated deliberately.
- [x] 1.2 Battery and Weather widget captions on the Caption role with its
  floor at a Home-sized cell. Host renders at four steps in both
  orientations. Host class.
  Done 2026-10-19 (host): the 2x2 Battery card, the Battery details
  absent state and the Weather card use `widget_line` at the Caption role
  (26 px at a 240 px-wide card, scaled down for picker previews), growing
  with the step only as far as the card's height allows and shrinking to
  fit a column before shortening. Tracked capitals are gone (the
  `caption_glow` helpers were removed). The Weather card lays out from
  the bottom: forecast strip, high/low line, then the temperature in the
  height left. Renders: `render_accessibility_scale_evidence` writes
  `<step>-home-small-<size>.png`.

## 2. The rest of the shell

- [x] 2.1 The volume HUD's expanded stream and output rows and the
  notification banner on the roles. Host class.
  Done 2026-10-19 (host): HUD row names use the Caption role, growing only
  as far as the 64 px row leaves above the slider and shrinking to fit
  before a long name is shortened. The banner's source line is Caption and
  its summary Body; its height comes from those roles and the step (98 px
  at 100%, inside the 256 px banner bound at 200%). Renders:
  `docs/evidence/rest-of-text/host-banner-*.png`. All test targets pass.
- [ ] 2.2 The Wi-Fi pages, the Help page, the theme grid and the recovery
  menu on the roles. Host class.
  Progress 2026-10-19 (host): Help is laid out by `help::layout` from the
  Title, Label and Caption roles at the current step and the theme's base
  size; text wraps instead of ending in "…". Content taller than the
  output scrolls with a vertical drag (`help_scroll`, reset on close and
  on the aid toggle), and `help::hit` uses the same layout and scroll. The
  wide layout fits a 600-unit height so the landscape panel shows all of
  Help at 100% with no scrolling (a unit test). The guide splits across
  the two columns to keep the taller one short. Renders:
  `docs/evidence/rest-of-text/host-help-{steps,wide}.png`. All test
  targets pass. Wi-Fi, the theme grid and recovery remain.
  Progress 2026-10-19 (host): the Wi-Fi pages' `wifi_ui::Layout` is now
  built from the roles at the current step (titles Title or Body, rows and
  buttons Label, status and detail Caption). Rows, cards and buttons take
  their heights from those roles; card text wraps; the counter sits inside
  the password field; with the keyboard raised a too-tall Entry page pans
  up so its field stays visible. Renders:
  `docs/evidence/rest-of-text/host-wifi-{100,200}-*.png`. All test targets
  pass. The theme grid, recovery and the card Overview remain.
  Progress 2026-10-19 (host): the theme chooser's headings and card names
  are Label, its hint, statuses, feedback and message Caption. Portrait
  sizes both carousels from the room that text leaves (the hero card is
  530 px tall at 100%, was 640). Grid names wrap to two lines; when a
  grid's cards are narrower than about five Caption characters (seven
  themes on the 1232x568 panel) the chooser shows its carousels instead.
  Renders: `docs/evidence/rest-of-text/host-themes-*.png`. All test
  targets pass. Recovery and the card Overview remain.
  Progress 2026-10-19 (host): the app actions (recovery) menu names the
  app in Label, its subtitle in Caption (two lines) and its rows in
  Label; its header, rows and width come from those roles and the step.
  The launch and recovery splash put the name or recovery copy in Body
  and its hints in Caption, wrapped. Renders:
  `docs/evidence/rest-of-text/host-menu-splash-*.png`. All test targets
  pass. The card Overview remains.

## 3. Board

- [ ] 3.1 Native `grim` captures of Home, a folder, the volume HUD with
  audio streams, a notification banner, Wi-Fi and Help at 100% and 200% on the landscape panel. Board
  class.
- [ ] 3.2 The operator's look on glass. Board class; stays open until the
  operator has looked.
  Progress 2026-10-19: the operator looked at Home (both pages: the Video
  label, the Clock, Battery details and the Weather card) on glass from
  the e11757ee closure and said "seems good to me". Help, Wi-Fi, the
  theme grid, recovery, the volume HUD and the banner still need a look.
