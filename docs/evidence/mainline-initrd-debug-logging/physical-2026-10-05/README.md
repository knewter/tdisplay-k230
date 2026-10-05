# Fixed initrd debug logging: physical comparison

Physical UART evidence at revision `d1cd3ca0e5c6227e71e465bc116d1e8082bca689`,
captured 2026-10-05 02:26:45–02:30:11 UTC. Total invocation 205.575 seconds
includes preparation/loading; passive readiness was bounded to 180 seconds.
Exit 1 records **ordinary init login readiness unverified**.

Reviewed [actual host qualification](../host/README.md) passed with unchanged
p2/24h artifacts, selected source/config/Image/DT/archive/manifest, matching
systemd init and five load/CRC expectations. The preceding NEW
[protected ordinary recovery](../../mainline-system-trial/current-p2-ordinary-physical-2026-10-05/recovery.json)
passed exact identities, distinct boot, eight hashes, three services and
registration absence. The begin invocation performed its own protected
normal preflight before reboot/loading.

One board/UART reservation ran:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers --initrd-debug-logging \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report NEW_PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

Fresh Linux and `Run /init as init process` appeared. That kernel announcement
precedes execution success; it is not proof systemd ran or a runtime PID1 guard.
No systemd startup/version, closure-unit or login messages were observed within
the bound. This comparison stopped observably earlier than the
[quiet ordinary run](../../mainline-system-trial/current-p2-ordinary-physical-2026-10-05/README.md),
which showed mounted sysroot and starting closure lookup. Additional logging
can change timing or console pressure. Absence of a line identifies neither a
blocked instruction nor a logging/backend/hardware cause.

[Result](result.json) preserves safe facts and private-log hashes.
[Fixed observations](fixed-observations.txt) are derived, not a raw transcript.
No camera or real-glass proof was obtained for this comparison. Independent
full-transcript review **PASS**: five strict load counts/CRCs, exact printed and
fresh received arguments, source hash, unique protected preflight and replayed
readiness failure match. Command annotations and source show no input after
bootm; this is not independent electrical TX-direction proof.

All reservations are released. **NEW operator reset after this capture is
pending**, and the prepared checker has not run. No previous reset is reused,
fallback input or automatic return claimed. Ordinary root, panel/glass and
task 5b.5 stay **UNVERIFIED**. The [next bounded plan](../../../research/mainline-initrd-info-console-comparison-2026-10-05.md)
considers a one-value debug→info comparison with the same console destination;
it is not run.
