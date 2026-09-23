# Preserve touch cadence across compositor dispatch delays

The adapter previously substituted processing time for every touch event's
source timestamp. Queued delivery could turn a slow movement into a throw or
make a fast throw fail its velocity threshold. It now passes wlroots source
milliseconds through down/motion/up, recovers the nearest 64-bit epoch across
32-bit rollover, and retains the policy's backward-time rejection. Real board
libinput timestamps use the monotonic clock
([upstream documentation](https://wayland.freedesktop.org/libinput/doc/latest/timestamps.html)).
Close timeout starts when the adapter dispatches the close request, so an old
queued event cannot exhaust the application's response interval before dispatch.

The benchmark still measures actual dispatch-to-submit/presentation costs using
its original producer clock. This fix does not alter benchmark thresholds,
backdate telemetry, change the throw threshold, or claim to fix frame cost.
It is a concrete timing defect but does not by itself establish the cause of
one failed board throw in the longer cost baseline.

Host proof:

```sh
python3 tests/test_card_touch_clock.py
python3 tests/test_card_shell_state.py
nix build .#card-shell --max-jobs 1 --cores 8 --no-link --print-out-paths
python3 tests/card_shell_runtime.py --native-touch --delayed-touch \
  --sway /nix/store/bggwbi2nx72c494xpjvgyi98yxz3w3c0-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --client /nix/store/6nskh3ldk3ya7mwxbb258qszrxhw2i61-card-composition-probe-client-0.1/bin/card-composition-probe-client \
  --output /tmp/card-touch-timestamp-runtime
```

Clock conversion and all 21 policy cases pass with sanitizers. The product
cross-build produces `/nix/store/iyxcmrirznbl45ggzx6y4i42kp1wybzv-k230-card-shell`.
The actual RISC-V compositor under QEMU user emulation passes all 17 runtime
checks and four explicit source-time checks: quickly delivered slow input does
not close; a source-time pause before release does not close; a fast source
throw delayed 450 ms between dispatches does close; and the refusing application
still receives its full timeout despite timestamps three seconds old. The
fixture's optional timestamps remain restricted to its existing explicit
headless/environment guard. Input traverses wlroots, cursor and seat routing.

`headless.json` is the resulting report. This is not physical touch, panel,
full-system QEMU, or board performance acceptance. Default image integration
and real-finger review remain open.
