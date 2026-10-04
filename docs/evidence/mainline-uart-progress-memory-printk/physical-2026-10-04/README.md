# Linux-console comparison: no observer summary observed

The fresh 7.3.0-rc5 candidate reached exact received arguments, registered UART0
as Linux ttyS0 and enabled that console, then entered `/bin/sh`. During the
180.1019-second passive capture, no K230_UMK1 summary or normal return arrived.
No candidate input was sent: zero attempts, **NOT_REQUESTED** receipt and
**RX NOT_TESTED**. There was no protocol error or requested candidate reboot.

Root operated exclusively from `~/tmp/k230-mainline-probe-integration`, branch
`integrate/mainline-probe-path`, controller revision `877bec0e`. All source/native,
[exact/full artifact](../exact-full-host/README.md) and
[actual controller](../positive-controller-host/README.md) gates passed first.
The matching p2kdar89 bundle was locally built from frozen `1c59f856`. Actual
transfer/import/staged checksums returned 0; only eight changed closure paths
were exported. Fresh protected normal preflight passed exact identities, eight
boot hashes, three services and registration absence. All five load/CRC guards
then passed. No image flashing or persistent boot selection was performed.

[Safe result](result.json) retains exact source/kernel/config/manifest hashes,
timestamps, transfer and private UART identities. [Fixed records](fixed-records.txt)
is exactly empty. Raw UART, protected state and boot identifiers remain private.
No candidate camera, injected-event, touch or ordinary-root acceptance was obtained.

```sh
python3 tools/mainline-drm-initrd-shell-trial.py --mode minimal \
  --same-image-shell-pid1 --uart-progress --uart-progress-memory \
  --uart-progress-memory-no-stimulus --uart-progress-memory-printk \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest "$PRIVATE_RUN/candidate-manifest.json" \
  --normal-report "$PRIVATE_RUN/normal-report.json" \
  --log "$PRIVATE_RUN/trial.private.log" --result "$PRIVATE_RUN/result.private.json"
```

The original live parser reports primary prompt/readiness false. The captured
bytes contain the exact Bash Readline `ESC[?2004h` prefix followed by its prompt;
that prefix was missing from the controller fixtures. A later
[labelled host-only correction/replay](../readiness-host/README.md) recognizes
those prompt bytes and changes only readiness classification. It does not alter
the original physical result, timing, raw kernel parsing, zero input, missing
summary or missing normal return. No new physical trial was performed by replay.

The final explicit DBCN call is absent from the selected observer branch, but
silence on Linux printk still does not isolate the fault. Observer scheduling,
completion wait/45-second kernel timeout, timer delivery, printk ownership and
UART progress remain unknown. One ordinary print call has no absolute return
bound. Host capture time does not prove kernel jiffies advanced. Historical
Breadcrumbs sleeps/samples did make progress in another comparison; this is not
proof that timers universally fail. Ordinary `/init`, root, panel/glass and task
5b.5 remain **UNVERIFIED**.

The controller capture ended with reservations released and protected recovery
pending. A subsequent NEW user-confirmed reset passed the protected normal
postflight: distinct boot, exact system/profile/kernel, all eight boot hashes,
three active services and registration absence. Home IPC returned 0 and a
separate reviewed C920 frame showed Home clock/icons/background (oblique, soft
focus and glare; no glass test). [Follow-up recovery receipt](recovery.json)
retains safe identities and private evidence hashes. This is operator recovery,
not automatic return or ordinary mainline acceptance; the prior polling reset
was not reused.
