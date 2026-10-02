# Quiet runtime-trace attempt: shell input did not complete

The board operator ran the exact reviewed candidate with ordinary boot
logging and `--runtime-shutdown-trace` on 2026-10-02. The protected normal
preflight passed. Linux 7.3.0-rc5 reached `Run /bin/sh as init process` at
uptime 4.026622, followed by Bash's `sh-5.3#` prompt and no-job-control
warnings. Input then echoed with corrupted characters and line-editing
controls; subsequent receipt commands appeared at the continuation prompt
`>`. No complete fresh-token receipt returned.

The controller exited 2 at reception and wrote a structured unknown result.
It sent no later probe or candidate reboot. Sysfs setup and runtime tracing
were **not attempted**. This attempt therefore provides neither shutdown
trace nor automatic restart evidence, and does not identify a kernel stall.
The quoted continuation state explains why the later receipt lines did not
execute; the origin of the corrupt input remains **UNVERIFIED**.

Controller source: `6c03cc496fe8f74d1222099280fe0de458d8b05e`.
Worktree: `/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`; root held the board, UART and camera.
No kernel build or persistent boot-selection write was performed.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --runtime-shutdown-trace \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/runtime-trace-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/runtime-trace-result.json"
```

[Observation](observation.json) preserves candidate artifact hashes, controller
hash, timestamps, protected preflight and exact result limits.
[Console excerpt](console-excerpt.txt) contains selected fixed kernel/shell
lines and explicitly labeled curations. The complete raw log and result stay
in protected host scratch; no secret-bearing normal-system output is copied.
[Camera provenance](camera.json) identifies the reviewed, cropped physical
[boot-text photograph](boot-panel.jpg). Glare prevents reading all panel text.
This is camera observation, not native capture or deliberate touch acceptance.

The controller's existing shell-init readiness gate ran only for boot-debug
mode. Ordinary modes began bounded receipt attempts after the early kernel
banner. Extending that read-only gate is the next host correction; it does
not prove that waiting alone fixes this physical failure. Operator recovery
and protected postflight are pending. Tasks 5d.4 and 5b.5 remain open.

A subsequent 10-second receive-only UART check obtained zero new bytes.
No recovery or additional probe input was sent; silence does not establish
a kernel stop.

## Reviewed next trial after recovery

The [UART source audit](../../../research/mainline-uart-readiness-2026-10-02.md)
distinguishes early-input/FIFO risk from an unproved persistent baud fault.
The common readiness correction is integrated at `e2e984bf` and passes 92
host tests. It waits passively for candidate shell entry and a fresh initial
Bash prompt in every mode; no physical retry is claimed by those tests.
After protected operator recovery, the sole board operator uses fresh paths:

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal --runtime-shutdown-trace \
  --bundle /nix/store/asj7l4zj5jrjkgng4nrcx3y72p7jf7aa-k230-mainline-drm-trial-boot-files \
  --manifest "$HOME/tmp/k230-mainline-restart-board/candidate-manifest.json" \
  --normal-report "$HOME/tmp/k230-mainline-restart-board/normal-report.json" \
  --log "$HOME/tmp/k230-mainline-restart-board/runtime-ready-trace-uart.log" \
  --result "$HOME/tmp/k230-mainline-restart-board/runtime-ready-trace-result.json"
```

This is the next invocation, not an executed or successful physical trial.
