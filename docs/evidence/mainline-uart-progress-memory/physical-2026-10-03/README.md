# Memory comparison: no final summary observed

The matching Memory variant reached a fresh 7.3.0-rc5 banner, exact received
arguments, `/bin/sh` entry and primary Bash prompt. One fresh builtin receipt
stimulus was sent. During 180.1021 seconds of passive capture, neither its receipt
nor the independent observer's final memory summary was observed. No protocol
error or normal return was recorded. This is an incomplete physical diagnostic;
worker progress, observer execution and serial output remain unknown.

Root exclusively operated board/UART from worktree
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, controller revision `c3ba705f`. The full matching
build used frozen `7af8f7b8`; intervening host-proof commits did not change source.
[Result](result.json) preserves exact artifacts, UTC times, return code 2, staging
receipt and private UART SHA256/size. Raw UART, boot identities, nonce, protected
normal baseline and transfer URL remain private. No candidate camera/glass proof
was obtained.

[Actual full/exact proof](../exact-full-host/README.md) and
[positive controller proof](../positive-controller-host/README.md) passed before
board access. The exact selected config/autoconf and hardware DT match PostSample;
worker hash 307d7c and the linked summary format/setup were verified. Fresh normal
preflight checked exact system/profile/kernel/init, eight boot hashes, three
services and registration absence. Eight new closure paths transferred/imported
with staging return code 0 and checksum verification. U-Boot load size/CRC guards passed
before the matching Image/initrd/DT boot. Persistent normal selection was unchanged.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --bundle /nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE_RUN/candidate-manifest.json" \
  --normal-report "$PRIVATE_RUN/normal-report.json" \
  --log "$PRIVATE_RUN/trial.private.log" \
  --result "$PRIVATE_RUN/result.private.json"
```

The completed structured parser, including qualified prompt/receipt framing,
reports receipt UNKNOWN and memory_summary null. [Fixed records](fixed-records.txt)
contains no summary line. Only one stimulus was attempted; no retry, proc/guard
command, further input or candidate reboot followed. Host capture duration is
not proof of advancing kernel jiffies or the observer's 45-second wait expiring.

In selected Memory mode, all worker output is suppressed and finite progress is
published in one coherent atomic word. A separately created normal-priority
observer waits once and attempts one final DBCN summary. The lack of a summary
cannot establish which part ran or stopped; even a final firmware output call
can fail or block. A possible M-mode stall can prevent S-mode observation. This
run does not establish that repeated worker output caused the earlier result,
or identify a UART/IRQ/timer/scheduler/firmware fault.

Capture is complete. A subsequent NEW operator reset passed guarded protected
normal postflight: distinct boot identity, exact system/profile/kernel/init,
eight boot hashes, three services and registration absence. Home IPC completed
with exit 0 and a camera image showed its clock/icons/background. The oblique,
upside-down image has glare and soft focus; it is not touch/orientation acceptance.
[Recovery receipt](operator-reset-recovery.json) preserves fixed checks and hashes
without raw UART or boot identities. This is operator recovery, not automatic
return. Ordinary mainline `/init`, usable root, panel/glass and task 5b.5 remain
**UNVERIFIED**.

The next comparison should use the same qualified built image while withholding
the candidate shell stimulus. This changes one runtime dependency without a
kernel rebuild; any resulting progress supports only a difference under removed
input, not its cause or RX acceptance. It needs a separately reviewed typed policy,
zero-stimulus fixtures, explicit NOT_REQUESTED receipt status and fresh recovery.
