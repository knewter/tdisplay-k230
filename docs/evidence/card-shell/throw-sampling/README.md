# Preserve throw velocity across repeated millisecond timestamps

The policy previously set velocity to zero whenever two consecutive motion
events had the same millisecond timestamp. A valid upward movement followed
by another movement or a duplicate endpoint in that timestamp then failed to
request close. This is independently reproduced in the actual C policy and
the cross-built compositor's native wlroots input path.

The policy now measures those samples from the preceding distinct timestamp.
Coordinates still update on every event. A same-time downward reversal resets
the velocity reference conservatively, and motion with no elapsed interval
cannot throw. A later stationary sample, slow drag and held release continue
to reject close. The 120-pixel displacement, 0.4-pixel/ms speed and 150-ms
release-age thresholds are unchanged, as are dispatch-time close deadlines,
graceful close/refusal behavior and performance budgets.

## Host and native runtime proof

```sh
python3 tests/test_card_shell_state.py
TMPDIR=/mnt/MediaVolume/home/jadams nix build .#card-shell \
  --max-jobs 1 --cores 8 --no-link --print-out-paths
python3 tests/card_shell_runtime.py --native-touch --delayed-touch \
  --sway /nix/store/d7pxj3jviq5ghax97hy98fnqlmhbiy0f-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output NEW_HEADLESS_DIRECTORY
```

All 23 compiled policy cases pass with address/undefined-behavior sanitizers.
Two new case groups cover duplicate and advancing same-time endpoints, a
zero-duration whole movement, same-time reversal, a later stationary sample,
slow movement and held release. The new positive group fails with the original
policy from base `4ba9f58a`; its other 22 cases pass.

`build.json` identifies the built package and source hashes. `headless.json`
records 17 compositor runtime checks and eight independent source-timing
checks, including repeated-timestamp close and reversal/held-release rejection.
This executes the RISC-V compositor under QEMU user emulation with native
Wayland clients and wlroots/cursor/seat routing, not a full Linux guest.

For the runtime negative control, substitute the previous timestamp-corrected
Sway `/nix/store/bggwbi2nx72c494xpjvgyi98yxz3w3c0-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
in the same command. It passes the preceding timing checks, then fails waiting
for the first same-millisecond motion close request. `negative-control.json`
records that expected exit 1 and the exact runtime-test hash.

## Remaining physical gate

This does not establish the cause of the four intermittent upward-throw misses
in the [RVV comparison](../kernel-rvv/card-cost/README.md). Its input injector's
absolute scheduling deadlines can produce bursts after a delay, but those runs
did not retain the individual gesture source timestamps needed for attribution.
An unchanged injected board workload repeat with this package is still needed.
Real-finger acceptance, default-image integration and all failed card cost
budgets remain open. The normal image has not changed.
