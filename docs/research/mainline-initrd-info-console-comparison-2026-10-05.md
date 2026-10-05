# Next comparison: lower logging level, same destination

The [quiet ordinary run](../evidence/mainline-system-trial/current-p2-ordinary-physical-2026-10-05/README.md)
showed mounted sysroot and starting closure lookup. The
[debug-plus-console comparison](../evidence/mainline-initrd-debug-logging/physical-2026-10-05/README.md)
showed the kernel's pre-exec `/init` announcement but no systemd/version/unit
output within 180 seconds. Neither identifies a blocked instruction or establishes guarded ordinary-root
acceptance. The debug capture alone does not prove `/init` exec success; the
quiet run did show systemd PID1 startup. Subsequent NEW [protected recovery](../evidence/mainline-initrd-debug-logging/physical-2026-10-05/recovery.json)
after the latter debug capture passed.

Source inspection places backend setup before the version banner. Systemd first
selects kmsg, mounts early API filesystems, parses logging arguments, then opens
the selected backend. Explicit console logging opens `/dev/console` and writes
synchronously. See pinned [startup source](https://github.com/systemd/systemd/blob/4925d9f07fc697efccd98a93046ff535b8832445/src/core/main.c)
and [logging source](https://github.com/systemd/systemd/blob/4925d9f07fc697efccd98a93046ff535b8832445/src/basic/log.c).
These are possible observation boundaries, not a demonstrated console failure.
Selected system init and packaged systemd ELF match digest
`d3e109a270c0b4463ac5b7b0655ce7667d7c55f6f93341bb461300a5dd5c8c63`.
Read-only derivation inspection pins version 261.2 and the tag source. The exact
official archive extracted privately passes `nix hash path --sri PRIVATE_EXTRACTED`
with the derivation source hash `sha256-w0Fxx+zYBs806whyaKBytGwSgn89ARdukAm6Hp+XlQQ=`.
All seven patches/postPatch were inspected: none changes main.c or log.c. Raw
main.c SHA256 is `946eb61164c94f6c4b3f3362137aaf027f91f6182165162d4428a74ccfc16528`;
log.c is `9f639754bd544921001923d3f607496e50c8d81b20c1d09edf27646491d24bce`.
Startup/backend selection is raw main.c:3516–3536, banner call 3713→2488;
console open is raw log.c:102–121, synchronous writes 486–498. These are raw-file
line references; browser extraction renumbers lines. No Nix realization, build
or hardware action was used for this source audit.

The smallest proposed child comparison changes only
`rd.systemd.log_level=debug` to `rd.systemd.log_level=info`, retaining
`rd.systemd.log_target=console`, current p2 artifacts and every prior control.
Argument bytes become 355 and literal command bytes 373. It requires a separate
typed `--initrd-info-logging` selector, both existing join/marker-free selectors,
and exclusion of `--initrd-debug-logging`. Save/restore the selected mode with
old state defaulting false; reject unsupported combinations, types and inherited
aliases before output/UART. Existing defaults and the debug path stay unchanged.

Run meaningful focused fixtures and actual immutable-artifact preparation, then
one passive 180-second capture after NEW protected recovery. Keep five
load/CRC guards, exact printed/live arguments and complete private logs. Unknown
readiness or I/O sends no further candidate input. New recovery is independent.
If systemd progress returns, report sensitivity to this one-value change, not
an identified output-call stall. If silent, earlier startup and console
open/write remain indistinguishable. Do not add kernel verbosity, masks,
targets, tracing, alternate PID1 or a build to compensate.

Implementation, actual host qualification and physical outcome remain
**UNVERIFIED**. Ordinary root/panel/glass acceptance and task 5b.5 stay open.
