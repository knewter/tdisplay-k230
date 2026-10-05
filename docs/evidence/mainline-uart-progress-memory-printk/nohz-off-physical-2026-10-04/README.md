# Tickless-off comparison: Bash ready, no observer record

The same built MemoryPrintk candidate reached exact arguments including the sole
trailing `nohz=off`, fresh Linux ttyS0 registration/console enable, bin-sh entry
and corrected Bash Readline readiness. In a 180.025-second passive capture,
no K230_UMK1 record or normal return arrived. Input attempts were zero, receipt
**NOT_REQUESTED**, RX **NOT_TESTED** and protocol errors empty. No candidate
reboot or persistent boot-selection change was issued. The changed-policy test
did not restore observed reporter progress. It does not identify a timer/IRQ/
firmware cause or prove runtime policy independently.

Root used `~/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, frozen controller `87e5a344`. Image/config/source
remain the reviewed p2/24h/0l4 artifacts. [Actual host gate](../nohz-off-host/README.md)
and independent qualification/CI/site publication passed. A NEW user reset
first passed the [previous capture's protected recovery](../physical-2026-10-04/recovery.json),
followed by Home IPC and separate camera observation. This trial independently
rechecked exact normal identities, eight boot hashes and three services; the
executed preflight helper asserts registration absence before its fresh state
receipt. All five existing load/CRC guards passed. No new kernel build, transfer,
image flash or readback was performed.

Fresh host preparation initially failed because the exact source path was absent.
No candidate/UART trial had started. Root reserved only the host build slot to
realize the same existing source derivation and pin its output with a GC root.
The worker hash still matches the reviewed variant; fresh preparation then
passed. [Source-only restore receipt](source-restore.json) preserves the actual
command/result and initial failure; this was not a kernel build.

[Safe result](result.json) preserves timestamps, code/artifact identities and
private transcript hashes. [Fixed records](fixed-records.txt) is exactly empty.
Raw UART, helpers, protected state and boot IDs remain private.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus --uart-progress-memory-printk \
  --uart-progress-memory-printk-nohz-off \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_LOG --result PRIVATE_RESULT
```

Worker/observer scheduling, sleep/wakeup completion and printk call return stay
unknown. Earlier n0/n1/time/IRQ progress in another boot limits claims that timers
universally fail. No candidate camera or real-glass acceptance was obtained.
Ordinary /init/root/panel/glass and task 5b.5 remain **UNVERIFIED**.

Capture is complete and board/UART/build/camera reservations are released.
Automatic return was not observed during capture. A subsequent NEW user reset
passed [protected normal recovery](recovery.json): distinct boot, exact system/
profile/kernel/init, eight matching boot hashes, three active services and
registration absence. The predecessor's reset was not reused. This follow-up is
physical UART evidence; no camera or real-glass proof was obtained for it.
