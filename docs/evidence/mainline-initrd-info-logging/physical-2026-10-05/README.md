# Fixed initrd info logging: physical comparison

Physical UART evidence at revision `48716910242b941ff956dd2e4e7e707eadfc7de3`,
captured 2026-10-05 02:53:41–02:57:06 UTC. Total invocation 205.527 seconds
includes preparation/loading; passive readiness was bounded to 180 seconds.
Exit 1 records **ordinary init login readiness unverified**.

Reviewed [actual host qualification](../host/README.md) passed with unchanged
p2/24h artifacts, selected source/config/Image/DT/archive/manifest, matching
systemd init and five load/CRC expectations. The preceding NEW
[protected debug-comparison recovery](../../mainline-initrd-debug-logging/physical-2026-10-05/recovery.json)
passed exact identities, distinct boot, eight hashes, three services and
registration absence. The begin invocation performed its own protected
normal preflight before reboot/loading.

One board/UART reservation ran:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers --initrd-info-logging \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report NEW_PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

Fresh Linux and `Run /init as init process` appeared. That kernel announcement
precedes execution success; it is not proof systemd ran or a runtime PID1 guard.
No systemd startup/version, closure-unit or login messages were observed within
the bound. Observed output ended earlier than the
[quiet ordinary run](../../mainline-system-trial/current-p2-ordinary-physical-2026-10-05/README.md),
which showed mounted sysroot and starting closure lookup. It also remains
silent like the prior debug/console run despite lowering the level. Additional logging
can change timing or console pressure. Absence of a line identifies neither a
blocked instruction nor a logging/backend/hardware cause.

[Result](result.json) preserves safe facts and private-log hashes.
[Fixed observations](fixed-observations.txt) are derived, not a raw transcript.
No camera or real-glass proof was obtained. Independent full private review
**PASS**: five strict loads/CRCs, exact printed/fresh received arguments, source
hash, uniquely guarded normal preflight and false readiness replay match.
Command annotations/source show no input after bootm; this is not independent
electrical TX-direction proof. All reservations are released. NEW reset after this capture is
PENDING; its checker has not run. No earlier reset is reused or automatic
return claimed. Ordinary root, panel/glass and task 5b.5 stay **UNVERIFIED**.
The next source-grounded comparison keeps info level and changes only the
console destination to kmsg; it has not been implemented or run.
