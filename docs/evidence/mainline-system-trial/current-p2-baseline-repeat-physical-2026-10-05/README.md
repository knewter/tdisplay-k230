# Unchanged quiet baseline: physical repeat

One physical UART capture at revision `62f0ca41d539dc6045c83d297673c480dcaa53d5`,
2026-10-05 03:50:20–03:53:46 UTC. Total invocation205.485 seconds includes
protected preflight and loading; passive candidate readiness bound180 seconds.
Exit1: **ordinary init login readiness unverified**.

[Actual same-artifact qualification](../current-p2-baseline-repeat-host-2026-10-05/README.md)
passed independent review: unchanged controller/source/config/Image/DT/initrd,
archived init, manifests, helper identities and five load/CRC expectations.
The exact original quiet policy is299 argument/317 literal-command bytes:
synchronous initramfs, boot markers disabled, all three logging selectors false.
Preceding NEW [kmsg recovery](../../mainline-initrd-info-kmsg-logging/physical-2026-10-05/recovery.json)
passed full protected identities/eight boot hashes/three active services,
registration absence and distinct boot. This begin ran its own protected preflight.

The root operator held the sole board/UART reservation for this command:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers \
  --bundle /nix/store/p2kdar89q7dhwdajjy0mrhmxxzcgsalw-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report NEW_PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

Fresh Linux and `Run /init as init process` appeared. This announcement precedes
exec success; it does not prove PID1 began executing systemd. No candidate
systemd startup, closure-unit or login messages appeared within the bound.
The [earlier quiet run](../current-p2-ordinary-physical-2026-10-05/README.md)
reached sysroot and closure lookup; that boundary **did not reproduce** here.
The three explicit logging comparisons and this repeat now share the same
observed early boundary. This does not identify logging causality, an output
stall, a failed syscall or a hardware cause. Absence of output is not absence
of execution. Conditional closure-helper instrumentation is premature.

[Result](result.json) records safe facts and protected raw-file hashes;
[fixed observations](fixed-observations.txt) are derived, not a transcript.
Independent full private review PASS: five strict loads/CRCs, exact printed
and fresh received299/317 policy, unique protected preflight/two ACKs,
registration absence and source/hash/time bindings match. A73-byte chunked
replay consumed the complete candidate stream, returned false readiness and
sent zero writes. Bootm is the final command annotation; reviewed source sends
no later candidate input. This is not independent electrical TX proof.
Subsequent NEW user-confirmed [protected recovery](recovery.json) passed the
full guard and independent review: fresh prompt, unique postflight/two upload
ACKs, distinct boot, exact identities/eight hashes/three active services and
registration absence. The report was updated only after success. No passive
SPL proof is claimed for this check. The port is released; no preceding reset
was reused. Automatic return, ordinary root/panel/glass and task5b.5
remain **UNVERIFIED**. No new build, host artifact transfer, flash, readback, camera or glass proof
was performed for this unchanged repeat.

[Publication receipt](publication.json): exact94920520 CI37261983348 and deployment
passed, with work revision and capture page/timestamps independently verified
via HTTP200. Group5r is complete as a bounded control. That publication receipt records
pending recovery at its historical revision; subsequent NEW protected recovery
has now passed independently. Ordinary task5b.5 stays open.
