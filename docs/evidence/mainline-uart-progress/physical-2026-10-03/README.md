# Physical finite UART-progress comparison

The coordinator ran the reviewed controller at `3dc78e07` in
`/home/jadams/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`. Root alone reserved the board/UART. Camera and
build slot were not used. The [fixed public result](result.json) preserves the
observations, immutable artifacts, completion timestamp, private capture hash
and limits; raw UART, protected baseline and reception nonce remain private.

Actual matching host qualification had passed. The board downloaded and verified
the new candidate export, imported its eight additional paths and staged the
matching boot files; staging returned zero. The controller then independently
verified protected normal system/kernel/profile, boot file hashes and services,
rebooted into U-Boot, qualified every loaded artifact's size/CRC and verified the
volatile arguments. Persistent normal boot selection was not changed.

Operator command (private directory contains no repository credentials):

```sh
python3 tools/mainline-drm-initrd-shell-trial.py \
  --mode minimal --same-image-shell-pid1 --uart-progress \
  --bundle /nix/store/gmsmqkjcb8vmh6h44xvq7y59dd9xihsh-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE_RUN/candidate-manifest.json" \
  --normal-report "$PRIVATE_RUN/normal-report.json" \
  --log "$PRIVATE_RUN/trial.private.log" \
  --result "$PRIVATE_RUN/result.private.json"
```

The command returned 2 (observation saved, recovery required), rather than a
successful mainline acceptance. The 180.079-second passive capture saw the fresh
7.3.0-rc5 banner, exact received kernel arguments, `/bin/sh` init entry and
anchored Bash primary prompt. It attempted exactly one fresh builtin receipt
command. No receipt and no complete reporter records arrived. There were no
parser protocol errors; an empty set of records is not proof of healthy counters.
No candidate retry, proc command, guard or reboot followed the input attempt.
No fresh protected normal return was observed. Operator reset/postflight remains
**PENDING**; mainline root, timer health, UART delivery and panel/glass acceptance
remain **UNVERIFIED**.

## Interpretation and next discriminator

The kernel printed that the SBI DBCN extension was detected. In selected
`arch/riscv/kernel/sbi.c`, that detection sets `sbi_debug_console_available`.
This grounds availability detection, not successful reporter initialization or
firmware output. The reporter currently creates a normal-priority kthread and
its first output follows worker scheduling, `msleep(5000)` returning, the cached
snapshot and direct firmware write. No report distinguishes none of those steps.
There are no UART or timer counter values to compare in this trial. Earlier
source/config/object evidence does not replace that missing physical observation.

The next narrow comparison should add a separately qualified fixed direct-SBI
worker-entry breadcrumb before the first sleep, preserving the existing six
samples, runtime opt-in and normal priority. It stays off IRQ, TTY and PID1 paths.
Presence proves the worker reached that firmware call, not that the call returned;
absence still leaves scheduling versus output unknown. A later sample would
then prove return from the entry call and a delayed wakeup. This is a proposed
source comparison, not implemented or tested hardware behavior. Stronger markers
on the init/PID1 path need an explicitly reviewed scope change. Repeating the
identical sleeping-worker experiment offers no new discriminator.
