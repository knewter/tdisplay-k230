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
- [ ] 1.3 Portrait (568x1232) renders of the four styles at the four steps.
  Verify with `cargo run --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --example render_clock_styles_evidence`
  after adding a portrait size. Host class.
- [ ] 1.4 Renders over a real wallpaper and in a light theme (for example a
  retro-82 and a catppuccin-latte generation) to confirm the halo on the
  accent minute. Host class.

## 2. Type scale and spacing

- [ ] 2.1 Add the five type roles and the 8 px rhythm as named constants in
  `render.rs` and move the Settings, Vision and Shade text onto them.
  Update `tests/responsive_pixel_identity.rs` baselines deliberately and say
  so in the commit. Verify with `cargo test --offline --manifest-path
  nix/rust-shell-client/Cargo.toml --tests`. Host class.
- [x] 2.2 Replace tracked capitals in the Battery details grid labels with
  the Label role and check it at 160% and 200%. Host class.
  Done 2026-10-17 (host): labels, graph captions and the input line are on
  the 26 px floor as one-line label/value pairs. Renders at all four steps in
  both orientations are in `docs/evidence/battery-details-type/`.

## 3. Cards and the accent

- [ ] 3.1 Implement the Chosen card treatment (accent fill and rim) and use
  it for the Vision segments, the High contrast card when on, and the
  current theme. Host renders at 100% and 200% in a dark and a light theme.
- [ ] 3.2 Implement the Control card treatment and use it for Settings rows,
  the Shade controls, the drawer search and the dock.
- [ ] 3.3 Apply the one-accent rule: links, Done and Close take the
  foreground colour with a chevron; the accent stays on the current choice
  and one primary action per surface. Verify with a test that counts
  accent-coloured pixels groups per surface fixture. Host class.

## 4. Icons

- [ ] 4.1 Add a stroked vector icon set (3 px round caps) for Settings rows
  and the Shade, replacing the ad hoc glyphs, and a test that the icons
  render nonblank at 48 px and 64 px. Host class.

## 5. Board

- [ ] 5.1 Native `grim` captures of Home, the drawer, the Shade, Settings and
  the Vision page at 100% and 200% on the landscape panel, with the vinyl
  wallpaper, after the coordinator deploys the closure. Board class.
  Progress 2026-10-16: Home (the restyled Clock) at 100%, 160% and 200% is
  in `docs/evidence/clock-restyle/board-panel-*-home.png`. The other
  surfaces are not restyled yet, so they were not captured.
- [ ] 5.2 The operator's judgement on glass that the Clock and each restyled
  surface are readable and that the accent marks what is live. Board class;
  this task stays open until the operator has looked.
  Progress 2026-10-16: the operator looked at the restyled Clock on glass
  (retro-82, 160%) and said "clock lookgs good". The other surfaces are not
  restyled yet, so this stays open for them.
