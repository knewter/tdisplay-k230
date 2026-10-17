# The stroked icon set

Change: `openspec/changes/the-shell-has-one-visual-language`, task 4.1.

## What changed

- **`glyph.rs`** is the shell's own icon set: eleven monochrome glyphs drawn
  as cairo paths on a 24-unit grid.
  - Glyphs: Wi‑Fi, sun, small sun, speaker, muted speaker, keyboard,
    motion, key backlight, reboot, power and search.
  - Strokes have round caps and joins. The stroke is 3 px at 48 px
    (`glyph::ROW`), 4 px at 64 px (`glyph::DRAWER`), and never under 2 px.
- **Where they replace older drawing:**
  - The slider-end suns and the volume speaker (in Settings and the Shade)
    were a filled disc and a filled cone (`paint_sun`, `paint_speaker`).
  - The volume HUD's speaker.
  - The drawer search glyph, which was an ad hoc circle and line.
- **New leading glyphs** on the Settings rows (Wi‑Fi, Brightness, Volume,
  Keyboard, Motion, Key backlight), the Reboot and Power off cards, and the
  Shade's Keyboard toggle.
- **Colour.** Every glyph is in the foreground colour; the small sun and
  the muted speaker are muted. The bright-end sun and the unmuted speaker
  used to be in the accent; they are now in the foreground colour, in line
  with the one-accent rule.
- **Size: a deviation from design §11.** Design §11 gives a fixed 48 px row
  icon. A fixed 48 px column with the text beside it cut the Keyboard value
  ("On-screen keyb…") at 100% in the side-by-side layout, and stayed small
  beside 200% text.
  - Instead, a row's glyph sits on the label line, sized to 1.3 times that
    line's text and centred on it (`paint_line_glyph`).
  - Only the label line is indented; the value and caption keep the full
    width.
  - This makes the glyph about 34 px at 100% and 68 px at 200%. The 48/64 px
    sizes are what the test checks.
- **App icons** still come from the theme and are unchanged. That includes
  the drawer's 64 px app icons.

## Host evidence (2026-10-17)

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml --tests`:
  - All targets passed (lib: 574 passed, 2 ignored).
  - `glyph::tests::every_glyph_inks_its_box_at_the_row_and_drawer_sizes_and_stays_inside`
    renders each glyph at 48 and 64 px. It requires more than 4% and less
    than 50% of the box to be inked, and no ink outside the box.
  - `the_stroke_is_three_pixels_at_the_row_size_and_never_under_two` checks
    the stroke widths.
  - `the_glyphs_are_distinct` checks that no two glyphs render the same.
  - The accent-group test from 3.3 still passes.
- **Pixel-identity baselines.** The `docs/evidence/shell-responsive/drawer-*`
  frames were regenerated deliberately for the search glyph. The Settings
  and Home baselines did not change: their fixture has no services, so it
  shows "Loading settings".
- **Renders.** `render_glyph_evidence` drew the glyph sheet, and
  `render_accessibility_scale_evidence` drew the surfaces, using the
  catppuccin and catppuccin-latte generations from
  `docs/evidence/card-jobs/README.md`. Each surface sheet is at 50%.

| File | Content |
|---|---|
| `host-glyph-sheet.png` | Every glyph; rows: dark 48 px, dark 64 px, light 48 px, light 64 px |
| `host-dark-landscape.png` | 1232x568, 2x2: Settings at 100%, 200% (top); Shade at 100%, 200% (bottom) |
| `host-dark-portrait.png` | 568x1232: Settings 100%, 200%; Shade 100%, 200% |
| `host-latte-*.png` | The same in catppuccin-latte |

## Limits

- The Volume row's "No audio device found" was cut off at 200% in portrait.
  Fixed afterwards (2026-10-17): the line now uses `themed_role_fit` like
  the other row values. It shrinks to fit the column, never below the Body
  role, and a host render of `largest-settings-568x1232` shows it whole.
- The board captures are below. The operator's look at the icons (5.2) is
  separate and still open.

## Board evidence (2026-10-17)

- **Build.** `kernelMainlineDrmShellLandscapeHdmiBootFiles` was built at
  `5f244c0c` and deployed live with `switch-to-configuration test`. The
  active system was
  `/nix/store/a4241ifl36r41l3ccx24prrsq5p2q1n0-nixos-system-nixos-26.11.20260919.20b1ddd`.
- **Capture.** DSI-1 was the only output, at 1232x568 and 100%, with the
  retro-82 theme.
- **Navigation.** Surfaces were opened with `k230-shell-rust --surface`.
  Settings was scrolled with an injected uinput swipe (`/tmp/bp.py`). The
  frames are native `grim` captures.

| File | What it shows |
|---|---|
| `board-panel-settings.png` | Wi‑Fi, Brightness, Keyboard, Motion, Reboot and Power off glyphs |
| `board-panel-settings-scrolled.png` | Volume (40%) with the speaker glyph and slider; Key backlight glyph and level slider |
| `board-panel-shade.png` | Shade: stroked suns and speaker at the slider ends, Keyboard toggle glyph |

- **Observation: audio arrives late after a restart.** The deploy
  restarted PipeWire and the shell together (`shell-ui` started at
  01:36:40). The shell's journal shows its first default-sink snapshot at
  69.6 s: the volume HUD opened at 01:37:56. The two Shade captures without
  a volume slider were mapped at 12.2 s and 43.6 s, before that snapshot.
  The capture with the slider was mapped at 126.8 s. The missing slider was
  PipeWire still starting, not a rendering fault.
