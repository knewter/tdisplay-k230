# Exact init exec-return outputs restored and retained

Worktree `/home/jadams/tmp/k230-mainline-init-exec-return`, branch
`mainline-init-exec-return`, base `8557a21494a46d26e9df195e7d5a17fbeea6a6b1`,
source revision `7a99b32d979b9c4df5372476271e24b7546966cb`.
Root's later host preparation found the previously qualified bundle, kernel,
dev and source paths absent and stopped before opening UART. The prior
[successful proof](../actual-host/README.md) remains historical evidence;
its receipts and failed attempts were not overwritten. No source, controller,
Nix recipe, config, default package or hardware change was made for restoration.
No board/UART/camera operation or live preflight was performed here.

[Fresh evaluation](evaluation.json) matched every prior selected derivation and
output path before rebuilding. `/nix` had 1.2 TiB free. The same exact outputs
were rebuilt sequentially under `/tmp/k230-nix-build.lock`, `max-jobs=1`,
`cores=16`: source, kernel/dev, bundle, then the already built system explicitly.
[Build receipt](build-result.json) records all four commands and **return 0**,
completed 2026-10-05 15:33:10 UTC. Source took 60.17 seconds, kernel/dev
1,522.84 seconds, bundle 96.40 seconds, explicit system realization 16.93 seconds.
The driver kept the exclusive lock for the entire sequence and released it.
Only logging and retention flags changed from the original build command:
`-L`, and persistent `--out-link` paths in place of `--no-link`.

Registered permanent roots now retain:

| Root under `~/tmp/k230-mainline-init-exec-return-host/retained-store/` | Exact output |
| --- | --- |
| `source` | `dsgrv7744lzh418z22gb865c0j09g1qs-linux-mainline-k230-init-exec-return-src` |
| `kernel` | `wdrzkb9idb4pl88ws1b7y7vx0j79840l-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| `kernel-1-dev` | `9ddh3qgnq1sj3ibqvd9124w4bfij2y6w-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| `bundle` | `5f2j4y8hy9cclbqjx4nshhxi4jiwz7iq-k230-mainline-drm-trial-boot-files` |
| `system` | `gi850b5xn2s398grgfw7xlbwdf1n5cbf-nixos-system-nixos-26.11.20260919.20b1ddd` |

The existing p2 bundle and 24h dev comparison inputs also have roots in that
protected directory. `nix-store -q --roots` independently confirmed all seven
registered links; [retention receipt](retention.json) records the exact command.
Current Nix settings are `keep-derivations=true`, `keep-outputs=false`. Explicit
links retain the selected outputs without relying on inter-output references. Retention lasts while these roots
remain; it does not claim a global GC-policy change or explain the earlier absence.

[Byte comparison](byte-comparison.json) confirms **exactly unchanged** SHA256 for
main.c, actual config, system init, Image, wrapped initrd, hardware DT and artifact
bootargs. There is no rebuilt byte-hash delta. The source remains `a21ac6…`, config
`52e747…`, Image `fb2e66…`, initrd.uimg `86ede1…`, DT `0538ae…`. Full hashes are in
the receipts. No object or broad fixture suite was repeated: the reviewed source
and actual artifact bytes are unchanged.

The [fresh executed qualifier command](qualification-command.json), using the
new successful restoration receipt, returned **0**. [Positive receipt](positive-host-result.json)
revalidates actual same-derivation source/dev/config/Image, archived ELF/common
loader, exact module-tree relocation, DT hardware, SHA256SUMS, five load/CRC
expectations and sole volatile `k230.init_exec_return=1`. Raw argument bytes remain
299 → 323 and the literal command 341 bytes. [Comparison receipt](result.json)
shows all prior qualification identities and the protected manifest digest match.
Private normal data, manifest and transport remain outside the repository under
`~/tmp/k230-mainline-init-exec-return-host/restore-qualification`.

The normal report is the last reviewed protected host anchor, not a fresh live
preflight or recovery performed by this qualifier. Root still owns staging,
protected live preflight and the bounded physical trial. No restoration action
changed the board or its persistent normal profile. Physical output, output-call
return, userspace transition, ordinary root/login and real touch remain
**UNVERIFIED**; task 5b.5 stays open. The previously documented
[operator command](../actual-host/README.md) remains unchanged.

Private restoration logs and hashes are preserved alongside all historical logs;
[result.json](result.json) records their identities. Strict OpenSpec/link/whitespace
checks pass. This is host restoration and preparation evidence, not deployment or
hardware acceptance.
