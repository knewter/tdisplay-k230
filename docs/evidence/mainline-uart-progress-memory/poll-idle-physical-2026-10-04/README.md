# Idle-polling comparison: no memory summary observed

The already-built Memory image reached a fresh 7.3.0-rc5 banner, exact arguments
including the sole trailing bare `nohlt`, `/bin/sh` entry and primary Bash prompt.
During 180.0929 seconds of passive capture, no memory summary or normal return
was observed. Candidate input remained zero; receipt is **NOT_REQUESTED** and RX
**NOT_TESTED**. No protocol error or candidate reboot was recorded.

Root exclusively operated board/UART from `~/tmp/k230-mainline-probe-integration`,
branch `integrate/mainline-probe-path`, controller revision `a55e1ed4`. The exact
same lznjjfx1 Image/config/dev/DT/initrd/manifest were used; only the qualified
literal argument command gained `nohlt` (381→387 bytes). No new build/export/
transfer or persistent boot selection was performed. [Actual host proof](../poll-idle-host/README.md)
passed, then fresh normal preflight and all five load/CRC guards passed.
[Result](result.json) preserves artifact/time/policy identities and private UART
hash/size. [Fixed records](fixed-records.txt) is exactly empty. Raw UART, boot
identities and protected baseline remain private; no candidate camera/glass proof
was obtained.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus --uart-progress-memory-poll-idle \
  --bundle /nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE_RUN/candidate-manifest.json" \
  --normal-report "$PRIVATE_RUN/normal-report.json" \
  --log "$PRIVATE_RUN/trial.private.log" \
  --result "$PRIVATE_RUN/result.private.json"
```

The compiled polling setup and exact received argument are verified; runtime
execution of that setup is not separately observed. This run did not produce a
summary under the intended idle/tick-policy intervention. It does not isolate
WFI, timer, IRQ, firmware or scheduler causation. Worker/observer progress,
advancing kernel jiffies and expiry of the observer's 45-second wait remain
unknown. Final DBCN output can still fail or block. Missing output is not worker
failure proof. Ordinary mainline `/init`, usable root and task 5b.5 stay **UNVERIFIED**.

The capture finished before a NEW user-confirmed reset. [Protected recovery](operator-reset-recovery.json)
then passed: distinct boot, exact system/profile/kernel/init, eight boot hashes,
three active services and registration absence. Home IPC returned 0 and a
reviewed camera image showed its clock/icons/background, with oblique upside-down
framing, glare and soft focus. This is not touch/orientation acceptance or an
automatic return. Board/UART/camera are released; the normal system is restored.

The timer/DT audit found no advertised SSTC or timebase mismatch to justify a
new timer-backend switch. The next useful planned intervention is one observer
summary through the registered Linux 8250 printk console instead of explicit
firmware DBCN output, with its own source/controller/artifact/physical gates.
Silence on that channel would also remain inconclusive.
