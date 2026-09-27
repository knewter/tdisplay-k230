# Brightness slider on the headless compositor

Host QEMU capture (evidence class `headless-qemu-injected-touch`, the same
class `tests/rust_service_surface_qemu.py` already uses for this surface --
see `docs/evidence/coherent-shell/rust-service-surface-qemu/README.md`), for
the `the-brightness-control-is-a-slider` change. Real cross-built RISC-V
`sway`/`k230-shell-rust` executables ran under `qemu-riscv64-static`, with a
568x1232 headless Pixman output and touch events injected through Sway's
headless-only `card_shell test-touch` fixture (`ipc "card_shell test-touch
down/motion/up"`), exactly as `tests/rust_service_surface_qemu.py` already
does.

- Rust package: `nix build .#handheld-shell-rust --max-jobs 1 --cores 6`,
  `/nix/store/7hmjpjwbywq554fqr9dmj3lc3yjgc561-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- Sway: the same `sway-k230-card-shell`-patched `sway-unwrapped` this repo's
  own `nix/card-shell.nix` builds for the `card-shell` package
  (`nix build .#card-shell`), `/nix/store/7zvingic0whhz3z80w2gcpc343vipf7q-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`.
- The settings command was a local fixture script reporting a fixed
  `brightness: 45%` on every `status` call and echoing `applied` on every
  `brightness <percent>` call -- no real backlight device, no board.

## What this shows

A finger-drag from x=100 to x=460 across the Settings brightness row (y=374,
within the row's own touch band) drives the slider live: mid-drag at x=300
reads **54%** (`settings-mid-drag-54pct.png`), matching
`slider::value_at_x(300, 64, 504)` exactly, and the release at x=460 commits
**90%** (`settings-after-drag-90pct.png`) through the fixture's `brightness`
call. The same drag repeated on the Shade's own header band (y=218) moves
its slider identically to 90% (`shade-after-drag-90pct-still-open.png`)
**without closing the shade** -- the "Notifications" header, count and
"Swipe up above the list to close" hint are all still visible, proving the
horizontal drag never engaged the close-drag gesture
(`service_ui::shade_panel_close_zone`'s slider-band exclusion). Opening the
Shade fresh (`shade-synced-45pct.png`) shows its slider already at the
fixture's real 45%, not a stale/default value -- the shade now also issues
`RefreshSettings` on open (task: "sync the value").

## Commands

```sh
nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --print-out-paths
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
python3 -u tests/rust_service_surface_qemu.py \
  --sway <card-shell's sway-unwrapped>/bin/sway \
  --rust <handheld-shell-rust store path>/bin/k230-shell-rust \
  --output <dir>
```

The `--surface`-flag route request (spawning a second `qemu-riscv64-static`
process per route change) could not reliably complete inside the Rust
client's own hardcoded 500ms deadline on this shared host (`uptime` showed a
40+ load average across 32 cores from other concurrent worktrees); a direct
write to the same Unix socket that flag uses reached the identical
`RouteServer` without that overhead. This is a host-load workaround for
capturing evidence, not a change to `tests/rust_service_surface_qemu.py`
(whose own `--surface`-based `route()` helper is untouched here) or to the
shipped client's route protocol.

## Limits

Synthetic settings fixture, no physical touch, no real backlight device, no
board. This proves QEMU composition, live slider tracking, the shade's
gesture disambiguation and its sync-on-open -- not an installed image, real
glass, or physical finger input. Those gates remain open; see `tasks.md` in
`openspec/changes/the-brightness-control-is-a-slider/`.
