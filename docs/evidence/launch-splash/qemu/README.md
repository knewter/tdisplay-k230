# Launch splash under headless QEMU

Observed 2026-09-26. This test ran the cross-built Sway from source
`1ff6a837` (`/nix/store/6xrc0x9kb1gpy6v8g2v3512a0373vwcm-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`,
via `nix-store -qR` of `.#card-shell`), the RISC-V Rust client with this
change's splash source
(`/nix/store/71v0ssqfkp89yaw8ssxs2d08ysg97rbv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`),
and the existing `card-composition-probe-client` fixture
(`/nix/store/dw3p6aq52mz55mqrm97hlc0056sj9x1g-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1`)
under `qemu-riscv64-static`, with a 568x1232 headless Pixman output. Native
compositor test-touch supplied synthetic Wayland touch events. The desktop
catalog held one private fixture entry ("Splash Fixture") whose `Exec` is a
shell wrapper: `sleep 1` then `exec qemu-riscv64-static
card-composition-probe-client --app-id k230.card.two`. `exec`, not a fork,
keeps the pid GIO's `AppLaunchContext` reports identical to the pid that
ends up owning the mapped Wayland window, so this exercises the exact-pid
match path this feature's window-matching depends on.

Reproduce with the committed runner and exact executables:

```sh
python3 tests/test_launch_splash_qemu.py \
  --sway /nix/store/6xrc0x9kb1gpy6v8g2v3512a0373vwcm-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --swaymsg /nix/store/6xrc0x9kb1gpy6v8g2v3512a0373vwcm-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/swaymsg \
  --rust /nix/store/71v0ssqfkp89yaw8ssxs2d08ysg97rbv-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/dw3p6aq52mz55mqrm97hlc0056sj9x1g-card-composition-probe-client-riscv64-unknown-linux-gnu-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-launch-splash-qemu
```

PASS (reproduced twice). [deck.png](deck.png) shows the initial card
overview with fixture card `k230.card.one`; [drawer-open.png](drawer-open.png)
shows the drawer opened over it with the single "Splash Fixture" entry (an
initial-letter "S" fallback plate -- no icon theme is staged in this
private harness, so `icon.rs`'s resolution correctly no-ops rather than
drawing nothing incorrectly). [splash.png](splash.png), captured while the
fixture's own `sleep 1` guarantees its window has not mapped yet, shows the
full-screen splash -- the theme background colour and the app's name --
having already replaced the drawer. The Rust log recorded `touch-down`,
`app-launch-requested`, and critically **zero** `unmap` events at this
point: the overlay was never torn down, so the drawer/deck could not have
flashed through even for one frame. [handoff.png](handoff.png), captured
after the fixture's window actually mapped, shows the probe client's own
striped card content with the splash gone; the Rust log then showed exactly
one `unmap` (the hand-off itself), `app-launch-mapped`, and the sway IPC
tree's focused `app_id` was `k230.card.two` -- the launched window, not the
splash or the original deck. [result.json](result.json) retains the
machine-readable outcome and executable paths.

This is host/QEMU wiring and timing evidence under a headless Pixman
backend with synthetic touch and a private single-fixture catalog. It does
not establish real-glass splash readability, real-finger touch-dismiss
feel on the `TimedOut`/`Failed` states, a real `Terminal=true`/`foot`
app_id-mismatch hand-off, or that the previously active app is
imperceptible on the physical panel -- those remain the open board tasks
in `openspec/changes/launching-an-app-shows-a-splash/tasks.md`. The bounded
`/proc`-ancestry matching this exact-pid case does not exercise is covered
instead by `splash::pid_or_ancestor`'s own host unit tests in
`nix/rust-shell-client/src/splash.rs`.
