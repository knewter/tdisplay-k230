# Autonomous PID 1 reaches both markers and interactive Bash

The one physical comparison produced strict fresh-nonce **B then E**, followed
by an interactive Bash primary prompt. Linux 7.3-rc5, the exact selected kernel
arguments, ttyS0 registration/console enable and `/bin/sh` init entry qualified
the records. The passive capture lasted 60.035 seconds, sent **zero** input,
and recorded no protocol errors. Zero attempted input is supported by the
reviewed passive controller and absence of later command frames; it is not
an independent electrical direction measurement. RX remains **NOT_TESTED**. No candidate reboot
or persistent selection change was requested.

The selected fixed script first tests PID 1 and UID 0, prints B, runs
`/bin/sleep 5`, prints E and executes interactive `/bin/sh`. B supports the
limited builtin tests and reaching the first output. E supports successful
return from the preceding B printf and selected sleep. Each marker alone does
not prove its own output call returned; the later primary prompt adds progress
through the E output and interactive-shell handoff. The five-second argument is
verified, but this UART transcript does not timestamp each marker independently.
No full `/proc` identity guard or runtime instruction/IRQ trace was collected.

This establishes userspace execution and sleep completion in **this boot**,
with all optional progress-reporter/trace/tick gates absent. It narrows claims
that all mainline userspace or timed waits universally stall. It does not
identify why ordinary init or the earlier enabled reporter failed to progress,
prove serial RX, or show the normal root/panel/glass. Ordinary init was not
attempted in this comparison; task 5b.5 remains **UNVERIFIED**.

Root operated `~/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, frozen at
`c0c8e50c47abfb165d3c4b4c0b51b2653fb48e91`. The preceding nohz-off capture first
passed [NEW protected normal recovery](../../mainline-uart-progress-memory-printk/nohz-off-physical-2026-10-04/recovery.json).
A fresh byte-identical [host qualifier](../host/qualification-command.py)
then passed against that report and the same p2/24h/0l4 artifacts, native
receipt, archive, loader and Bash exports; its executed safe
[receipt](fresh-host-qualification.json) is preserved. The runtime controller
independently rechecked protected normal state and all five load/CRC guards
before its exact volatile `printenv` check and sole candidate `bootm`.
No new build, transfer, flash or readback was performed.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --autonomous-bash-pid1 \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --log PRIVATE_LOG --result PRIVATE_RESULT
```

[Result](result.json) preserves timestamps, code/artifact identities, limited
observations and private transcript hashes. The
[public fixed records](fixed-records.redacted.txt) replace only the runtime
nonce with the explicitly public native-fixture placeholder. They are a
redacted display copy; strict parsing was performed against the private actual
nonce and raw wire. Raw UART, boot IDs, runtime nonce and protected reports
remain private.

The controller exited 2 because protected normal return was not observed;
`diagnostic_ok` is true. This is a completed diagnostic with independent recovery
still required. Board/UART/camera/build reservations are released. A NEW user
reset after this comparison is requested; recovery is **PENDING**. The reset
used before this comparison is not reused.

Independent read-only review **PASS**: five strict load counts/CRCs, exact
volatile arguments and final boot command, complete fresh B/E ordering and
later prompt, and pure chunked-parser replay agree with the saved result.
The preceding NEW protected normal recovery was also reviewed against its
unique raw postflight receipt. No reviewer opened UART or performed a build.
