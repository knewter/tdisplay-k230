# Rust service panels on the headless compositor

At 2026-09-24T06:09:24Z, `tests/rust_service_surface_qemu.py` ran actual
cross-built Sway and Rust shell executables under QEMU user emulation, with a
568×1232 headless Pixman output and touch events injected through Sway's
headless-only `card_shell test-touch` fixture. The Rust package was built from
the service UI source checkpoint `5e70fa8f736b58bcf3512448c6c9da8290cb8d0f`:

```sh
python3 -u tests/rust_service_surface_qemu.py \
  --sway /nix/store/ildcfqicn8j22yih16x42b4mmajqq6x8-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/25x514z4808av6mq4j6bh5iyxlwjfc7b-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --output /tmp/k230-service-debug4
```

The result was `headless-qemu-injected-touch` PASS for six checks: private
history changes did not alter the broker-redacted preview pixels; a failed
notification action appeared in the history row; an upward header swipe
closed and reopened the shade; a shade tap reached Settings below its old
input-region boundary; brightness and keyboard taps reached the bounded
settings worker; and fake reboot/power-off confirmation, cancellation, and
denial reached the actual panel. The two history frames are
[first](shade-private-first.png) and [second](shade-private-second.png);
[the failed action](shade-action-error.png), [confirmation](settings-confirm.png),
and [fake denial](settings-fake-power-denied.png) show the other visible states.
All screenshot content is synthetic fixture text.

The harness supplies a private fake notification socket and a fake settings
command. Its `confirm` operation returns `fixture-power-blocked`; it never
invokes reboot, shutdown, or the board's settings service. This proves QEMU
composition and injected touch routing, not an installed image, real glass,
physical input, or device power behavior. Those gates remain open for the
board operator.
