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
