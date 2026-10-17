## 1. Clock

- [x] 1.1 Restyle the Clock widget in every style: hour in the foreground
  colour and minute in the accent, a tighter and larger Bubble, a Light Thin
  style with a quiet colon, a dot matrix with faint unlit dots, and one
  neutral sentence-case date of at least 32 px at 100%. Verify with `cargo
  test --offline --manifest-path nix/rust-shell-client/Cargo.toml --lib
  clock_date` (the date's size, width and clearance against
  `bubble_lines`, at 100/130/160/200%) and `--tests` (including
  `responsive_pixel_identity`). Host class.
  Done 2026-10-16 (host): 569 lib tests and all integration targets passed.
- [x] 1.2 Host renders of the four styles on a teal and an orange backdrop,
  before and after, at 100%, 130%, 160%, 200% and 200% with high contrast,
  committed under `docs/evidence/clock-restyle/`. Host class, from
  `examples/render_clock_styles_evidence.rs`.
  Done 2026-10-16 (host).
- [x] 1.3 Portrait (568x1232) renders of the four styles at the four steps.
  Verify with `cargo run --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --example render_clock_styles_evidence`
  after adding a portrait size. Host class.
  Done 2026-10-17 (host): `CLOCK_SIZE=portrait`;
  `docs/evidence/clock-restyle/host-portrait-steps.png`.
- [x] 1.4 Renders over a real wallpaper and in a light theme (for example a
  retro-82 and a catppuccin-latte generation) to confirm the halo on the
  accent minute. Host class.
  Renders done 2026-10-17 (host): `host-retro82-wallpaper.png` and
  `host-latte.png` in `docs/evidence/clock-restyle/`. Latte is legible. Over
  the retro-82 vinyl the Bubble and Thin minutes read through the halo, but
  the dot-matrix minute over the orange label was weak.
  Done 2026-10-17 (host): each lit dot now has a crisp ring in the halo
  colour. The re-rendered sheets show the dot-matrix minute legible over
  the label at every step. The analog ticks remain faint there; the hands
  read.

## 2. Type scale and spacing

- [x] 2.1 Add the five type roles and the 8 px rhythm as named constants in
  `render.rs` and move the Settings, Vision and Shade text onto them.
  Update `tests/responsive_pixel_identity.rs` baselines deliberately and say
  so in the commit. Verify with `cargo test --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --tests`. Host class.
  Done 2026-10-16 (host): roles and rhythm are `TYPE_*`/`SPACE_*` in
  `render.rs`; Settings, the Vision page and the Shade use one layout at
  every step; all eight test targets pass and the `settings-*.png`
  baselines were updated in the Settings commit. Renders at four steps in
  both orientations are in `docs/evidence/type-roles/`.
- [x] 2.2 Replace tracked capitals in the Battery details grid labels with
  the Label role and check it at 160% and 200%. Host class.
  Done 2026-10-16 (host): labels, graph captions and the input line are on
  the 26 px floor as one-line label/value pairs. Renders at all four steps in
  both orientations are in `docs/evidence/battery-details-type/`.

## 3. Cards and the accent

- [x] 3.1 Implement the Chosen card treatment (accent fill and rim) and use
  it for the Vision segments, the High contrast card when on, and the
  current theme. Host renders at 100% and 200% in a dark and a light theme.
  Done 2026-10-17: `paint_card` with `CardJob::Chosen`. The chosen
  text-size step is a pill. Renders in catppuccin and catppuccin-latte are
  in `docs/evidence/card-jobs/`.
- [x] 3.2 Implement the Control card treatment and use it for Settings rows,
  the Shade controls, the drawer search and the dock.
  Done 2026-10-17: `CardJob::Control` is applied to the Settings rows,
  Reboot/Power off, the Shade's Keyboard toggle, the drawer search and
  the dock. The Wi‑Fi pages, the Help buttons and the theme carousel are
  not converted. See `docs/evidence/card-jobs/`.
- [x] 3.3 Apply the one-accent rule: links, Done and Close take the
  foreground colour with a chevron; the accent stays on the current choice
  and one primary action per surface. Verify with a test that counts
  accent-coloured pixels groups per surface fixture. Host class.
  Done 2026-10-17: links, Done, Close, values and source names use the
  foreground colour. Navigation links carry a chevron (‹ Settings, Vision ›,
  Themes ›, Settings ›); Done and Close dismiss and have none. "Dismiss all" is the Shade's primary action. Slider
  fills are exempt as current-value marks. The test
  `the_accent_marks_only_the_current_choice_on_settings_vision_and_the_shade`
  counts the accent groups: Settings 0, Vision 1, Shade 1, in both
  orientations.

## 4. Icons

- [x] 4.1 Add a stroked vector icon set (3 px round caps) for Settings rows
  and the Shade, replacing the ad hoc glyphs, and a test that the icons
  render nonblank at 48 px and 64 px. Host class.
  Done 2026-10-17: `glyph.rs` provides eleven glyphs, which replace the
  filled sun, speaker and search shapes. Settings rows, the power cards and
  the Shade toggle get a leading glyph. That glyph is sized to the label
  line rather than a fixed 48 px, so it grows with the text step without
  cutting off values. Tests and renders are in
  `docs/evidence/stroked-icons/`.

## 5. Board

- [x] 5.1 Native `grim` captures of Home, the drawer, the Shade, Settings and
  the Vision page at 100% and 200% on the landscape panel, with the vinyl
  wallpaper, after the coordinator deploys the closure. Board class.
  Progress 2026-10-16: Home (the restyled Clock) at 100%, 160% and 200% is
  in `docs/evidence/clock-restyle/board-panel-*-home.png`.
  Progress 2026-10-16: Settings, Vision and the Shade on the type roles
  (2.1) at 100%, 160% and 200% on the HDMI output (1280x800, the only
  active output) are in `docs/evidence/type-roles/board-hdmi-*.png`. Panel
  captures of those surfaces and of the drawer remain.
  Done 2026-10-17: native captures of Home, the drawer, Settings, the Vision
  page and the Shade at 100% and 200% on DSI-1 (1232x568), retro-82 with
  the vinyl wallpaper, from `caaf4ff4`, are in
  `docs/evidence/visual-language-panel/`.
- [ ] 5.2 The operator's judgement on glass that the Clock and each restyled
  surface are readable and that the accent marks what is live. Board class;
  this task stays open until the operator has looked.
  Progress 2026-10-16: the operator looked at the restyled Clock on glass
  (retro-82, 160%) and said "clock lookgs good".
  Progress 2026-10-17: after Settings, Vision and the Shade moved onto the
  type roles (2.1), the operator said "text sizes are fine". This covers
  readability only; the card treatments and the accent rule (3.x) and the
  icons (4.1) still need their look.
  Progress 2026-10-17: the operator looked at the card treatments and the
  accent on glass (retro-82, 100%), was told where the accent remains, and
  said "it's dope". The icons (4.1) still need their look.
