# Rust software client on the physical board

Observed 2026-09-24 UTC. This is a real-board process and native-compositor
capture checkpoint, without injected or real-finger input. It is not the
finished shell UI and does not close coherent-shell task 0.3.

The exact probe source is `6d56d140` (landed as `1acc250f`); package and
installed-system paths are recorded in [result.json](result.json). The
coordinator exclusively held `/tmp/k230-board.lock` and `/dev/ttyACM0`.
The package closure was exported from the host store and imported using a
temporary read-only HTTP transfer on the existing network. Private transport
addresses and raw console files remain outside the repository. Nix imported
the exact store output; no NixOS switch, flash, or compositor restart occurred.

Commands run on the board (the package path is abbreviated with a shell variable):

```sh
rust_probe=/nix/store/ii2dvxw952j33xprfxycphxyqsxj6v6p-k230-shell-rust-probe-riscv64-unknown-linux-gnu-0.1.0
systemd-run --unit=k230-rust-probe --collect \
  --property=User=shell --property=RuntimeMaxSec=180 \
  --setenv=XDG_RUNTIME_DIR=/run/shell --setenv=WAYLAND_DISPLAY=wayland-1 \
  "$rust_probe/bin/k230-shell-rust-probe" --serve
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 \
  "$rust_probe/bin/k230-shell-rust-probe" --surface drawer
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 \
  grim /run/shell/rust-probe-drawer.png
systemctl show k230-rust-probe --property=MainPID \
  --property=MemoryCurrent --property=CPUUsageNSec
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 \
  "$rust_probe/bin/k230-shell-rust-probe" --surface hide
systemctl stop k230-rust-probe
systemctl is-active shell
systemctl is-active k230-rust-probe
readlink /run/current-system
runuser -u shell -- env XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 \
  grim /run/shell/rust-probe-restored.png
```

The service was independently bounded to 180 seconds. The route commands
returned successfully, and the journal recorded:

```text
rust-probe 0ms ready-idle
rust-probe 3ms touch-capability
rust-probe 14217ms map-request
rust-probe 14225ms configure 568x1176
rust-probe 14270ms commit
rust-probe 14291ms configure 568x1176
rust-probe 14291ms frame-done
rust-probe 14314ms commit
rust-probe 14351ms frame-done
rust-probe 49502ms unmap
```

The first map request reached a software-buffer commit after 53 ms and the
first callback after 74 ms in this single trial. These are process-relative
log differences, **not** cold-start, touch latency, output-presented timing,
or a repeated performance measurement. `touch-capability` reports the seat's
capability; no touch/move/cancel events were exercised.

[mapped.png](mapped.png) is an unedited 568×1232 native capture, visually
reviewed before publication. It shows the probe's diagnostic rows and teal
edge below its transparent strip. The original bar and empty terminal remain
visible above it. The client itself configured to 568×1176 because the
existing rollback bar reserves 56 pixels. This does not prove the intended
full-height no-bar session or the final themed drawer.

One mapped-service snapshot reported `MemoryCurrent=5611520` bytes and
`CPUUsageNSec=93487000` cumulative. These are cgroup accounting values, not
RSS/PSS or an application CPU percentage. No C/Qt comparison was performed.

After unmap and stop, the probe was `inactive`, the original shell was
`active`, and `/run/current-system` matched the baseline exactly.
[restored.png](restored.png) shows the unobscured empty terminal and original
bar. The temporary host transfer server stopped and the board lock was
released. Capture hashes and sizes are in the fixed-schema result file.

Remaining proof: real touch/move/cancel, camera/panel presentation, full-height
integrated geometry, repeated cold-start/RSS/CPU/frame measurements and fair
C/Qt comparison. The actual Rust drawer, icons, themed Settings, notifications
and theme chooser remain implementation work. No physical acceptance task is
checked by this diagnostic capture.
