# Selected init exec return: physical capture

ONE physical UART capture at revision `69d7cbb3`, 2026-10-05
18:30:54–18:34:18 UTC. Total invocation204.576 seconds includes protected
preflight/loading; candidate readiness bound180 seconds. Controller exit1:
**ordinary init login readiness unverified**.

[Reviewed restored artifact qualification](../restoration-host/README.md) and
[actual guarded staging](../staging-2026-10-05/README.md) passed. This begin
ran another complete normal preflight, with exact normal identities/eight boot
hashes/three active services/registration absence and staged new metadata/closure.
Root exclusively reserved board/UART and ran:

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers --init-exec-return \
  --bundle /nix/store/5f2j4y8hy9cclbqjx4nshhxi4jiwz7iq-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

Fresh Linux, exact received323-byte arguments, and the `/init` announcement
preceded ONE valid `K230_INIT_EXEC_RETURN_V1 ret=0` record. The parser observed
no malformed/duplicate/phase errors. No qualified login or primary prompt appeared
within180 seconds. [Fixed observations](fixed-observations.txt) and [safe result](result.json)
retain the record and bindings; raw UART/runtime identities remain protected.

The selected kernel exec setup returned successfully. This does not prove the
transition to userspace, ELF loader/constructors/systemd main, or that the
record's own printk call returned. Missing later output does not locate a failed
instruction or syscall. Adding this optional record may perturb behavior;
ordinary root/panel/glass and task5b.5 remain **UNVERIFIED**.

Complete independent physical review PASS: all five load/CRC pairs, exact
arguments, artifact/time/hash bindings and full 73-byte chunked parser replay
were checked. The replay consumed all candidate bytes with exactly one valid
return record, no readiness, and zero subsequent input. The recovery checker
source also passed review, but has not run without a NEW reset confirmation.
Bootm is the final command
annotation; reviewed source sends no further candidate input on unknown readiness.
That is source/transcript evidence, not independent electrical TX proof.
The port is released. A NEW operator reset after this capture is required for
separate protected normal recovery; no preceding reset is reused, and automatic
return remains **UNVERIFIED**. No camera or real-glass acceptance was obtained.
