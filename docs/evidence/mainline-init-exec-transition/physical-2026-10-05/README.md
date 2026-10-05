# PID1 return and first userspace syscall: physical capture

ONE physical UART capture of the default-off two-point transition variant,
2026-10-05 20:24:27–20:28:01 UTC, controller revision `bfef07f1` (tools and
flake unchanged from frozen build revision `a60b0eae`). Candidate readiness
bound180 seconds. Controller exit1: **ordinary init login readiness
unverified**. [Actual host proof](../actual-host/README.md) and both independent
actual-host reviews passed first.

## Guarded staging

[Staging receipt](staging.json): root ran the reviewed private stage guard once
(20:19:56–20:21:16 UTC), return0. A fresh prompt and full protected preflight
against the old `5f2j…` staged bundle preceded one acknowledged upload. The
board checked the compressed NAR SHA256, imported the 8 new of 630 closure
paths, retained a separate candidate GC root, copied only trial files and
verified staged checksums. One exact fresh-token RC0 frame preceded the full
post-guard against the new candidate. Protected normal identities, eight boot
hashes, three active services and registration absence were identical on the
same boot. No reboot, profile switch or boot-file replacement. Independent
complete UART staging review PASS. The transfer server was stopped afterwards.

## Capture

```sh
python3 tools/mainline-drm-system-trial.py begin \
  --wait-initramfs-in-initcall --without-boot-markers --init-exec-return \
  --init-exec-transition \
  --bundle /nix/store/jx56x86gihamimhj6hqr8d13rn6ax25r-k230-mainline-drm-trial-boot-files \
  --manifest PRIVATE_MANIFEST --normal-report PRIVATE_NORMAL \
  --state NEW_PRIVATE_STATE --log NEW_PRIVATE_LOG --result NEW_PRIVATE_RESULT
```

All five U-Boot load size/CRC pairs matched the manifest. The kernel received the
exact 351-byte arguments with both gate tokens. A fresh 7.3.0-rc5 banner and
`Run /init as init process` (4.573720) preceded exactly one of each record, in
order ([fixed observations](fixed-observations.txt), [safe result](result.json)):

```
[    4.584221] K230_INIT_EXEC_RETURN_V1 ret=0
[    4.584235] K230_INIT_EXEC_TRANSITION_V1 point=kernel-init-return
[    4.584361] K230_INIT_EXEC_TRANSITION_V1 point=first-user-ecall
```

The parser reported a complete sequence, no missing records and no errors. No
qualified login or primary prompt appeared within180 seconds. The last
host-to-board annotation is `bootm`; the reviewed source only reads after it.
That is source/transcript evidence, not electrical TX proof.

What this shows, within the diagnostic's stated limits: the selected
`kernel_init` returned to `ret_from_fork_kernel`, user mode executed and issued
an ECALL whose kernel-entry setup succeeded. It does not prove the syscall
handler returned, loader constructors or systemd main ran, or that the last
record's own print returned.

## Bytes after the last record

The raw UART ends with exactly `\r\n ESC P + q 6E616D65 ESC \` and then nothing
for the rest of the 180-second bound. This is a DCS XTGETTCAP query for the hex
string `6E616D65` ("name"). On the protected normal 6.6.36 boot, systemd PID1
emits the same query and immediately follows it with further terminal queries
(`ESC[18t`, `ESC[6n`, …) and its version banner. The earlier
[5s capture](../../mainline-init-exec-return/physical-2026-10-05/README.md) ends
with the same bytes, which that write-up did not mention; it made no claim of
silence. The emitter of these bytes, and where execution stopped after them,
are **UNVERIFIED** from UART alone. They are recorded here as an observation for
the next source-grounded plan, not as a cause.

## Recovery

After the capture completed, the user performed a NEW operator reset. The
independently source-reviewed recovery checker (adapted from the 5s checker
only for the new bundle, both flags and a fresh-only output guard) ran once and
returned0: fresh prompt, distinct boot, exact normal system/profile/kernel/init,
uname 6.6.36, eight protected boot hashes equal to the trial preflight, three
active services and registration absence ([recovery receipt](recovery.json)).
No passive fresh SPL or automatic return is claimed.

Independent physical capture review PASS: hashes, loads/CRCs, arguments, three
ordered unique records, trailing bytes, read-only window and result fields.
Raw UART, URLs, tokens and boot IDs remain private; receipts bind their hashes.
Ordinary root, panel, camera/real glass and task5b.5 remain **UNVERIFIED**.
