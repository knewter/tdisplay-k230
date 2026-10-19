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
