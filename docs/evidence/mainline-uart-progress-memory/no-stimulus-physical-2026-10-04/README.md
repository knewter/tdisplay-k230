# Zero-input comparison: no memory summary observed

The same built Memory image reached a fresh 7.3.0-rc5 banner, exact arguments,
`/bin/sh` entry and primary Bash prompt. During 180.0995 seconds of passive
capture, no final memory summary or normal return was observed. The controller
sent **zero candidate bytes after boot**, reporting receipt **NOT_REQUESTED** and
RX **NOT_TESTED**. No protocol error or candidate reboot was recorded.

Root exclusively operated board/UART from `~/tmp/k230-mainline-probe-integration`,
branch `integrate/mainline-probe-path`, controller revision `d12091bd`. The
matching built bundle was unchanged from the preceding one-input comparison:
`/nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files`.
[Result](result.json) preserves exact artifacts, UTC times, return code 2 and the
private UART hash/size. [Fixed records](fixed-records.txt) is exactly empty.
Raw UART, boot identities and the protected normal baseline remain private.

[Actual host preparation](../no-stimulus-host/README.md) passed before UART access.
The [new operator reset before this test](../physical-2026-10-03/operator-reset-recovery.json)
passed fresh protected normal postflight and reviewed Home camera observation.
The test repeated normal preflight, all five load/CRC guards and the exact
381-byte Memory argument command. No new kernel build, export or transfer was
needed. Persistent normal boot selection was unchanged.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus \
  --bundle /nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE_RUN/candidate-manifest.json" \
  --normal-report "$PRIVATE_RUN/normal-report.json" \
  --log "$PRIVATE_RUN/trial.private.log" \
  --result "$PRIVATE_RUN/result.private.json"
```

Withholding the one input attempt did not produce a summary in this run. That
observation does not locate the failure or exclude an input-dependent effect
under other timing. Worker/observer progress, advancing kernel jiffies and the
45-second completion timeout remain unknown. A summary's final DBCN output call
can itself fail or block; silence cannot separate timer/scheduling/idle/firmware
and output dependencies. No camera or real-glass proof was obtained in candidate
mode. Ordinary mainline `/init`, usable root and task 5b.5 remain **UNVERIFIED**.

The capture is complete and board/UART released. A NEW operator reset has been
requested after completion; the reset preceding this trial cannot establish its
recovery. The proposed next comparison changes only idle/tick policy through
one bare volatile `nohlt` argument, using this same built image and passive
controller. It requires its own reviewed plan, typed selector, real artifact
qualification and fresh recovery before another boot.
