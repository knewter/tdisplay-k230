# INT0 press/release on the physical board, 2026-09-28

Evidence class: a real-finger button press on the physical board,
observed in the kernel log and interrupt counters over serial.

System: `9ix1cka3…` / `z3zbk6gx…` (both carry the `feat/power-key-ui`
kernel, with `k230-pmu-pwrkey` registered on IRQ 88). The operator pressed
the top buttons. The board's kernel log then showed:

```
[ 6297.189681] k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 press
[ 6297.384012] k230-pmu-pwrkey 91000000.pmu-pwrkey: INT0 release
```

`/proc/interrupts` line 88 (`91000000.pmu-pwrkey`) went from 1 to 3: one
press edge and one release edge, 195 ms apart. Only one of the two top
buttons produced events. The other top button isn't routed to this input,
and the bottom button is the hardware Reset.

This is the real press/release proof that the `powerKeyTrial` option
requires, so the gesture service is enabled in the coherent-shell
configuration. The gesture behaviour itself (tap for display, hold for the
power menu) is not yet verified.

## Gesture acceptance (operator report)

After the gesture service was enabled (system `f3dh9yxg…`, `shell-power-key`
active), the operator used the upper button and reported, verbatim: "power
button works great". Evidence class: an operator's real-finger report. No
camera recording was made.
