# Vision option: larger text and high contrast (tasks C.1–C.3)

## What changed

- **Preference (C.1).** `tools/theme_vision.py` stores the choice as
  `vision.json` beside the theme state (`text_scale` is `default` or `large`;
  `contrast` is `standard` or `high`). It is written atomically and refuses
  unknown values and symlinks. The task named `service_data.rs`. The choice
  is stored with the theme state instead, because that is the existing
  theme-choice persistence mechanism the task points to, and it reaches both
  renderers through the generation.
- **Token pipeline (C.2).** `theme_activate.prepare` folds the choice into
  every generation:
  - A non-default choice changes the generation identity. The default choice
    keeps the existing identity.
  - High contrast rewrites the palette (black background, white foreground,
    saturated accents) before the templates run, so every templated
    consumer picks up the same colours.
  - `appearance.json` gains `sections.accessibility` with `text-scale` (1.0 or
    1.25) and `high-contrast`.
  - Rust `render.rs` multiplies both context and themed text by the step.
  - `nix/card-shell/appearance.c` multiplies its font scale by the same token.
- **Settings control (C.3).** "Vision ›", beside "Themes ›" in Settings, opens a
  Vision page with two toggles, Larger text and High contrast. A toggle sends
  `k230-theme vision --text-scale … --contrast …` through the theme helper.
  The helper saves the choice and re-activates the active theme with it. If
  that fails, the previous choice is restored. With no active theme, the
  choice is saved and applies with the next activation.

## Host evidence (2026-10-16)

Evidence class: host renders and unit tests only. The board check is task
C.4 and is recorded separately.

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
  --no-fail-fast`: 562 lib tests passed (2 ignored), and all integration
  targets passed.
- `PYTHONPATH=tests:tools python3 -m unittest tests.test_theme_vision …` (the
  theme suites listed in the change): 140 tests OK.
- `nix build .#card-shell --max-jobs 1 --cores 4 --no-link --print-out-paths`:
  built `k230-card-shell` (exit 0) from this tree.

### Renders

The three generations were prepared on the host from
`nix/handheld-theme-default/catppuccin` with `theme_activate.prepare`, once
per choice. Each prepare was preceded by `theme_vision.save(state, choice)`
and used `state_root=<state>`, `user_themes=<state>/none`, `builtins=None` and
`tools=HOST_TOOLS`. Generation ids:

| Name | Choice | Generation |
|---|---|---|
| default | default / standard | `e1a358a6af0533bf8f1ef70b` |
| large | large / standard | `e60e8ad8b173237d6a98737d` |
| high | default / high | `956c733aca3ac6093f1351b0` |

They were rendered with:

```
cargo run --offline -q --manifest-path nix/rust-shell-client/Cargo.toml \
  --example render_accessibility_scale_evidence -- <out> <state>/generations \
  default=e1a358a6af0533bf8f1ef70b large=e60e8ad8b173237d6a98737d \
  high=956c733aca3ac6093f1351b0
```

The example writes 24 frames. Twelve of them are committed in `host/`: for
each choice, Settings and the Vision page at 1280x800, and the Shade and the
drawer at 568x1232. The grey area under the portrait Shade is the example's
backdrop, not the shell.

### Limits

- These are host renders of the Rust shell. The card-shell headers are covered
  by `tests/test_card_shell_appearance.py` (metrics with the token), not by a
  render.
- With high contrast on, the secondary text keeps the theme's muted
  foreground. It is light grey on black, not pure white.
- Persistence across a reboot, and legibility on the real panel (C.4), are
  not shown here.

## Board evidence by injected input (2026-10-16, task C.4 progress)

Evidence class: native `grim` captures from the board's compositor, with taps
injected through `uinput`, plus a soft reboot. These are not a camera recording
or a real-finger interaction. The output was HDMI at 1280x800.

- Image: `kernelMainlineDrmShellLandscapeHdmiBootFiles` built from branch
  `vision-scale` commit `bc14b524`. It was installed live with
  `switch-to-configuration test` and set as the system profile, so the reboot
  booted the same system
  (`z42i9i3wq012i8jdglwxbxy88d3im4km-nixos-system-…`).
- `k230-theme list` reported the default choice
  (`text_scale: default`, `contrast: standard`).

| File | What it shows |
|---|---|
| `board/01-settings.png` | Settings with "Vision ›" beside "Themes ›" (default). |
| `board/02-vision-default.png` | Vision page after the tap, both Off. |
| `board/03-large.png` | After tapping Larger text: On, text larger, "Applied to every theme". The helper log shows `handle vision … outcome=ok`, and `vision.json` read `large`/`standard`. |
| `board/04-both.png` | After tapping High contrast: black background, white and yellow text. `vision.json` read `large`/`high`. |
| `board/05-both-settings.png` | Settings with both on. |
| `board/06-reboot-shade.png` | After `systemctl reboot` (16:51:17Z → ssh back 16:52:52Z): the Shade still draws large and high contrast. `vision.json` still read `large`/`high`. |
| `board/07-reboot-vision.png` | Vision page after the reboot, both On. |
| `board/08-restored.png` | Both toggled Off by tap; `vision.json` back to `default`/`standard`. |

### Limits

- C.4 also asks for legibility on the real panel, with the operator's
  `capture-feature.py … --provenance real-touch` run. This run used the HDMI
  output and injected taps. It shows that the choice persists across a reboot
  and redraws the shell. It is not a glass or camera observation, so C.4 stays
  open.
- With larger text, the two-line hint in Settings' Keyboard card sits on the
  card's bottom edge (`board/05-both-settings.png`).

## Panel captures (2026-10-16, DSI-1 1232x568 landscape)

Evidence class: native `grim` captures of the panel output, after the operator
unplugged HDMI and turned on Larger text on the device
(`helperd vision … outcome=ok` at 12:19:58). These are compositor frames, not
camera photographs of the glass.

| File | What it shows |
|---|---|
| `board/09-panel-home-ring-overflow.png` | Home at the larger step: the battery ring's "100%" crossed the ring. |
| `board/10-panel-shade.png` | The Shade at the larger step. |
| `board/11-panel-drawer.png` | The drawer at the larger step. Long names (Files (N…, Same G…) ellipsize. |
| `board/12-panel-home-ring-fitted.png` | The same Home after commit `91a60bfb` (`ring_label_size` shrinks only that label to fit inside the ring). Deployed live as `b6wn851s…-nixos-system-…`. |

The operator's own look at the glass, and their judgement of legibility, are
still needed for C.4.

## Redesign: four steps and reflow (2026-10-16, tasks C.5–C.7)

The operator found the drawer "not particularly legible" at the old Large step
(125%) and judged a two-way normal/large choice too coarse. The redesign
offers four steps: 100, 130, 160 and 200%. An existing `large` choice maps
to 130%. Each surface reflows at a larger step instead of clipping.

Measured against the panel (568x1232 at 4.1", about 2.07 px per dp), the
100% body text of 17–18 px is about 8.5 sp. At 200% it reaches about 17 sp.
Tap targets stay at or above 99 px (48 dp).

- **Steps (C.5).** `tools/theme_vision.py` `TEXT_SCALES` holds `default`,
  `large`, `larger` and `largest` (1.0, 1.3, 1.6 and 2.0). The helper's
  `--text-scale` choices come from that table. The Rust and `appearance.c`
  bounds are raised to 2.0. The Vision page shows the four steps as one
  segmented control, plus a High contrast card.
- **Drawer (C.6).** At a larger step:
  - The minimum tile width is 112 px times the step, so the drawer uses fewer
    columns: 2 in portrait and 4 in landscape at 200%.
  - Icons grow toward 99 px.
  - Names wrap onto two lines before they ellipsize.
  - The search pill and Help grow to fit their text.
  - The sheet is opaque whenever a vision option is set.
  - At 100% the drawer is pixel-identical: `tests/responsive_pixel_identity.rs`
    passes.
- **Shade, Settings and Vision (C.7).**
  - **Shade header.** Lines stack by their drawn height. The Settings and
    "Dismiss all" bands widen with the text, up to half the column.
    Notification rows grow to hold three lines.
  - **Settings rows.** Each row gets the height its lines need, plus a full
    slider band on slider rows.
  - **Settings header.** The Vision and Themes links get their own row, with
    tap bands sized for the text.
  - **Settings scroll.** At 200% the rows are taller than the screen, so the
    Settings body scrolls under a fixed header. A drag on a slider row still
    belongs to the slider.
  - **Chooser and Vision headers.** Back and Close widen to fit the text.
  - **Fitting secondary lines.** Values and secondary lines shrink to fit
    before they ellipsize, but never below their 100% size.

### Host evidence

Evidence class: host renders and unit tests. The board and glass checks are
task C.8.

- `cargo test --offline --manifest-path nix/rust-shell-client/Cargo.toml
  --no-fail-fast`: 568 lib tests passed (2 ignored), and all integration
  targets passed, including `responsive_pixel_identity`.
  - `navigation::the_largest_text_step_reflows_the_drawer_without_overlap_or_tiny_targets`
    checks that, at 200% in both orientations, tiles do not overlap, icons are
    at least 99 px and the search pill clears Help.
  - `icon::drawer_names_wrap_without_ellipsizing_at_the_largest_text_step`
    checks that no fixture name is ellipsized.
  - `service_ui::the_largest_text_step_scrolls_settings_and_keeps_every_row_reachable`
    checks each row's text height against its card. It also checks that a
    tap on Power off after scrolling reaches it.
  - `service_ui::the_largest_text_step_grows_notification_rows_and_header_links`
    checks the Shade.
  - `theme_ui::the_vision_layout_never_clips_and_keeps_the_tap_floor_at_every_step`
    checks the Vision page.
- `PYTHONPATH=tests:tools python3 -m unittest` over the `tests/test_theme*.py`
  suites and `tests.test_card_shell_appearance`: OK.

The five generations were prepared as described above, from
`nix/handheld-theme-default/catppuccin`, with `theme_vision.save` before each
prepare:

| Name | Choice | Generation |
|---|---|---|
| default | default / standard | `5c64a4c1de62429c468041bc` |
| large | 130% / standard | `af7b32bfc4793dfe05c678e7` |
| larger | 160% / standard | `bcc10b3fb39a95aa3c43ea80` |
| largest | 200% / standard | `0fc1fc47cd7b409f46f67425` |
| largest-high | 200% / high | `c1792d0524753badee55226d` |

`render_accessibility_scale_evidence` was run with those five names. It drew
40 frames: each name for the drawer, Shade, Settings and Vision, at 568x1232
and 1232x568. The fixture app names include two-word names ("System Monitor",
"Image Viewer").

Each file in `steps/` puts the five frames of one surface and orientation
side by side (portrait) or stacked (landscape), in the table's order, at half
size:

| File | Surface |
|---|---|
| `steps/drawer-portrait.png`, `steps/drawer-landscape.png` | Drawer |
| `steps/shade-portrait.png`, `steps/shade-landscape.png` | Shade |
| `steps/settings-portrait.png`, `steps/settings-landscape.png` | Settings, unscrolled (at 200% the Power section is below the fold and is reached by scrolling) |
| `steps/vision-portrait.png`, `steps/vision-landscape.png` | Vision page |

### Limits

- At 200%, a notification's summary and body each stay on one line, so long
  ones still ellipsize, as the body already did at 100%.
- In landscape at 200%, Settings needs a scroll to reach the lower rows of
  each column.
- The Home deck, the card shell and app windows are outside this change.
  Only the battery ring was fitted, in `91a60bfb`.
- None of this has been seen on the panel yet. That is C.8.

## Panel captures of the redesign (2026-10-16, task C.8 progress)

The board ran `/nix/store/sbn9x5qi1a3qlrd6sh0npjnxwiqyd70y-nixos-system-…`,
built from integration branch `integ-cma-popup` at `0c438090`. That branch
contains `8799961c` (Home widgets) and the fit-margin commit on this branch.
It was deployed live with `switch-to-configuration test`.

Method: the step was chosen by injected taps on the Vision page
(`tools/board-pointer.py`). Each surface was opened with the shell socket
route command. Each frame is a native `grim` capture of DSI-1 at 1232x568.
After each change the theme helper logged `outcome=ok`, and
`k230-theme list` read `larger`/`standard` or `largest`/`standard`.

Evidence class: injected input and native captures. These are not
real-finger interaction and not a judgement on glass.

| File | What it shows |
|---|---|
| `board/13-panel-200-home-before-widget-fix.png` | Home at 200% before `8799961c`: the clock overlaps and the battery stats truncate. |
| `board/14-panel-200-home.png` | Home at 200% after the fix. The widgets keep their cell-proportional text, and the battery grid uses two columns. |
| `board/15-panel-200-drawer.png` | Drawer at 200%. |
| `board/16-panel-200-shade.png` | Shade at 200%. |
| `board/17-panel-200-settings.png` | Settings at 200%, unscrolled. |
| `board/18-panel-200-vision.png` | Vision page at 200%. |
| `board/19-panel-160-home.png` | Home at 160%. |
| `board/20-panel-160-drawer.png` | Drawer at 160%. |
| `board/21-panel-160-shade.png` | Shade at 160%. The title "Notifications" is whole; before the 4% fit margin it ellipsized to "Notificatio…". |
| `board/22-panel-160-settings.png` | Settings at 160%. The keyboard hint caption fits. |
| `board/23-panel-160-vision.png` | Vision page at 160%. |

After the capture, the board was set back to `largest`/`standard`.

### Limits

- Home widgets do not grow with the step. They keep the text sizes they have
  at 100%, scaled only by their cell.
- At 200% the Shade's title and its "Swipe up…" caption shrink to fit beside
  the Settings link and the battery label. In `16-panel-200-shade.png` they
  are smaller than the rest of the Shade.
- The clock widget has text too small to read on the panel (the operator's
  note below). It needs its own redesign.

### Operator judgement on glass (2026-10-16)

Evidence class: the operator looked at the landscape panel. No camera
recording was made. Verbatim: "it's all good however the clock widget could
use a redesign it's got some text too small to see really but yeah it's
good". This accepts C.8 and closes C.4.
