# Rust drawer touch interaction under headless QEMU

Observed 2026-09-24 05:11 UTC. This test ran the cross-built Sway from
source `7fa79b5c` (`/nix/store/w395hanhg1p2hr5fca773f4inwzz2fdw-k230-card-shell`)
and the corrected RISC-V Rust client from source `22db5329`
(`/nix/store/6833xrvjzznh11m8hx0fvnz01qpggw49-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`)
under `qemu-riscv64-static` with a 568×1232 headless Pixman output. The
native compositor test-touch route supplied synthetic Wayland touch events.
The desktop catalog contained 20 temporary public `Fixture NN` entries in
a private XDG data directory; each `Exec` wrote its number to a temporary
marker. The client used the matching target `swaymsg` through a QEMU wrapper,
with `SWAYSOCK` set to the compositor's private IPC socket.

Reproduce with the committed runner and exact executables:

```sh
python3 tests/test_rust_drawer_interaction_runtime.py \
  --sway /nix/store/ix0gf208psg2f2z43p25hjrh2x79bbhm-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --swaymsg /nix/store/ix0gf208psg2f2z43p25hjrh2x79bbhm-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/swaymsg \
  --rust /nix/store/6833xrvjzznh11m8hx0fvnz01qpggw49-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/k230-rust-interaction-repro-qemu
```

PASS. [drawer-open.png](drawer-open.png) and
[drawer-scrolled.png](drawer-scrolled.png) show a visible row movement after
native touch down/move/up; the list-region pixel difference was nonempty.
The next tap selected the visible Fixture 06 row. The Rust log records
`touch-down 3`, `touch-up 3`, `unmap`, then `app-launch-requested`; Sway logged
`card_shell back`, and the GIO desktop `Exec` wrote only `06` to the marker.
A separate reopened drawer received a downward swipe and unmapped without
another launch. [deck.png](deck.png) and
[drawer-dismissed.png](drawer-dismissed.png) show the same deck pixel at
`(10,1000)` after dismissal. [result.json](result.json) retains the exact
machine-readable outcome and executable paths. Captures were visually
reviewed: only the public synthetic card and fixture labels appear.

The earlier generic reveal test's hard-coded tap at `(284,1000)` became a
valid app-row tap in the new interactive drawer. Its missing `K230_SWAYMSG`
correctly blocked launch and made its subsequent shade capture stale. The
first version of this dedicated fixture likewise omitted `SWAYSOCK`; the
target `swaymsg` returned nonzero and Rust correctly refused GIO launch.
Setting the private IPC socket yielded the passing run above. Neither
fixture error was counted as a product success.

This proves a headless QEMU compositor/client path with injected touch and
temporary desktop entries. It does not prove a real finger, panel optics,
installed application behavior, physical latency, CPU/frame budgets, or
the complete coherent image. Those gates remain open.
