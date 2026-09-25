## 1. Root cause

- [x] 1.1 Reproduce the confirmed Home/overview bleed-through against the
  real cross-built `.#card-shell` compositor and identify the exact scene
  layering gap (the deck's unpainted title-bar band, and a themed
  transparent canvas, both above Home's `Layer::Bottom`); verify with
  `docs/evidence/card-shell/overview-home-bleed-through/before-overview-
  home-bleeds-through.png` and its `debug-scene` capture.

## 2. Fix (compositor-side, QEMU-provable)

- [x] 2.1 Add `home_layer_sync` to `nix/card-shell/adapter.c`, called from
  the `CS_SHRINK` branch of `handle_result` and from `restore()`, alongside
  the existing `ordinary_backdrop_sync` calls; extend `card_shell
  debug-scene` with a `home_enabled` field. Verify with `nix build
  .#card-shell --max-jobs 1 --cores 6`.
- [x] 2.2 Confirm the existing gesture/state-machine suite is unaffected:
  `python3 -m unittest test_card_shell_state` (29 cases, run from `tests/`).

## 3. Regression coverage (QEMU, no physical touch)

- [x] 3.1 Add `tests/card_shell_home_layer.c` (a native `Layer::Bottom`
  fixture standing in for Home) and wire `--home-layer-client` into
  `tests/card_shell_runtime.py`'s two-axis path: `home_enabled`/pixel
  assertions across the real finger-driven entry/drag/quick-switch/close/
  settle sequence, plus an independent `assert_no_black_flash` sweep of
  every captured frame. Verify with `python3 -m unittest
  test_card_shell_home_bleed test_card_shell_two_axis_runtime` (run from
  `tests/`).
- [x] 3.2 Confirm the new test fails against the unfixed compositor and
  passes against the fixed one (both directions exercised manually against
  real `nix build .#card-shell` outputs); recorded in the evidence README.

## 4. Evidence and specs

- [x] 4.1 Commit before/after screenshots and the root-cause/fix/limits
  writeup under `docs/evidence/card-shell/overview-home-bleed-through/`.
- [x] 4.2 Add the `runtime/shell` requirement delta in this change; verify
  with `openspec validate the-overview-hides-the-home-screen --strict`.
- [x] 4.3 Build `.#card-shell` and `.#handheld-shell-rust`, evaluate
  `nixosConfigurations.k230.config.system.build.toplevel`, and check
  `python3 tools/blob-scan.py`'s exit code. All pass; see the evidence
  README's "Narrow proof commands".

## 5. Outstanding (hardware-only; keep this change open until done)

- [ ] 5.1 Board re-check: repeat the coordinator's original native capture
  (`swaymsg card_shell enter`, a real focused app, the board's actual theme
  and wallpaper configured) on the installed system once this change lands,
  confirming Home no longer bleeds through with a real (not synthetic)
  theme canvas and real finger input. Operator command:
  `./tools/console.py /dev/ttyACM0 --wait=3 "swaymsg card_shell enter"`
  plus a photograph of the panel; requires the board and its serial port
  reserved by one operator, per `AGENTS.md`. Not performed by this task
  (QEMU-only scope, no board/`/dev/ttyACM0` access).

## 6. Follow-up: self-healing against unrelated focus changes

Found while investigating a separate, unrelated report (bottom-band panel
flicker, `docs/evidence/card-shell/bottom-band-flicker/hypotheses.md`):
`home_layer_sync` ran only from `handle_result`'s `CS_SHRINK` branch and
`restore()`, so it depended entirely on `card_shell`'s own state machine
running again to correct any drift. An unrelated Sway focus change while
the overview stayed open (an IPC `[app_id=...] focus` command reaching an
already-mapped card) was observed to re-enable `layers.shell_bottom`'s
scene node without `shell.active` or `shell.policy.mode` changing at all --
nothing in `card_shell`'s state machine would ever run `home_layer_sync`
again to notice or correct it.

- [x] 6.1 Call `home_layer_sync(output)` unconditionally from
  `prepare_impl` (`nix/card-shell/adapter.c`), on every frame, before that
  frame's scene is ever built or committed -- idempotent (a single
  scene-node-enabled read, at most one write) and self-healing regardless
  of what caused the drift. Verify with `nix build .#card-shell --max-jobs
  1 --cores 6`.
- [x] 6.2 Add `tests/test_card_shell_home_layer_self_heal.py`: opens the
  overview, sends two unrelated `focus` IPC commands while it stays open,
  and asserts `debug-scene`'s `home_enabled` never flips back to `1` (then
  confirms Home genuinely returns once the overview is actually left, so
  the fix cannot pass by disabling Home forever). Verified failing against
  the unfixed adapter (a `home_layer_sync` call removed) and passing
  against the fixed one (3/3 consecutive passes observed). Verify with
  `python3 -m unittest test_card_shell_home_layer_self_heal` (run from
  `tests/`).
- [x] 6.3 Add the new scenario to this change's `runtime/shell` delta;
  verify with `openspec validate the-overview-hides-the-home-screen
  --strict`.
