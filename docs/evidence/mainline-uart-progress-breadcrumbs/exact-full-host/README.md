# Exact configured objects and full matching host artifacts

Evidence class: completed matching host artifacts and exact selected-header
RISC-V object compilation. No board/UART/camera action, worker execution,
receipt, physical counters, usable root/touch or recovery was tested here.
Physical tasks 5g.5–6 and task 5b.5 remain **UNVERIFIED**.

The coordinator built the matching bundle/dev from frozen revision
`2a54813575deecce790d4f0df048e5d3746e3d0e`. Its initial session ended 143 without
a completion receipt; the coordinator reported a 78-byte broken-pipe message
after the log showed all 13 derivations built. That interruption is retained
privately by the coordinator; no cause or successful completion is inferred
from it. The same frozen command resumed with protected file stdout and
completed return 0, 2026-10-04T02:13:45.683156Z–02:14:09.485195Z, using cached
outputs. Its actual command/times/paths are in [proof.json](proof.json).

The exact-object invocation used worktree
`/home/jadams/tmp/k230-mainline-uart-progress-breadcrumbs`, branch
`mainline-uart-progress-breadcrumbs`, source revision
`071086bc64418c04f7affd67ef56cddac960c896`. Only after the successful receipt
and immutable dev availability did we acquire the shared lock. The offline
dry run listed only the exact-object derivation; the narrow command passed
return 0 and released the lock. [Narrow invocation receipt](object-build-receipt.json) records that observed result. No full build was duplicated.

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineUartProgressBreadcrumbsExactObjects --offline --no-link \
  --print-out-paths --max-jobs 1 --cores 2
python3 docs/evidence/mainline-uart-progress-breadcrumbs/exact-full-host/verify.py \
  /nix/store/wi55m1p11zsi5shqrip4da6c4j420n2w-k230-mainline-uart-progress-exact-objects \
  ~/tmp/k230-mainline-uart-breadcrumbs-board/full-build-result.private.json \
  docs/evidence/mainline-uart-progress-breadcrumbs/exact-full-host
```

The reproducible read-only [verifier](verify.py) passed. Owned changes are
this exact/full host evidence and only task 5g.2–3 entries. Source/protocol,
existing outputs, controllers and protected card files were not changed.

| Artifact | Exact installed identity |
| --- | --- |
| Bundle | `/nix/store/mhq10143lsmgr6wlll431a8s3ggb8q6m-k230-mainline-drm-trial-boot-files` |
| System | `/nix/store/ac7radxa3iazk4gd5m8scg8yad9h3q5j-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/n8f93vnx87nq5n36zsal7idp2s6c9dkv-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Dev | `/nix/store/xl3cyf9bbksb5yy2nxc6dgy0fbfd0ii8-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| Source | `/nix/store/k5a5zrhqy9ypr3mja1r50mdlcgi74i1f-linux-mainline-k230-uart-progress-breadcrumbs-src` |
| Exact objects | `/nix/store/wi55m1p11zsi5shqrip4da6c4j420n2w-k230-mainline-uart-progress-exact-objects` |

Kernel/dev share the reviewed `4hc3qsi5…` derivation; bundle matches `c4zr3pa3…`.
Actual worker SHA-256 is
`7207dcae9462694a07bd4f7d37d1d9ea43a536496f1b96dd94fed3dfa78c6a22`.
The cached getter/timer sources, headers and reporter Kconfig are byte-identical
to original 4av3 source, with per-file digests retained in the receipt.

All three returned objects are ELF64 little-endian RISC-V relocatables from
GCC 15.3.0, W=1. Actual copied config/autoconf match the selected installed dev
bytes before/after compilation; no forced overlay is used. Config SHA-256:
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`;
autoconf SHA-256:
`99f44d781b246202edab1d5ef8c4836b15ae99c590999ff268541dfd673865d0`.
Effective config is unchanged from the original installed reporter, including
K230_UART_PROGRESS and its SBI/8250/DW/OF/timer dependencies built-in, 4KiB pages,
VMAP_STACK=y and KUNIT disabled. [Compile log](exact-object-compile.log) retains
the pahole-version mismatch (kernel 131/object environment0); no C warning
was observed. [Checksums](exact-object-SHA256SUMS) pass.

[Worker ELF inspection](k230-uart-progress.o.readelf.txt) records ordinary
`.text` worker, `.sbss` flags, aligned 256 ordinary BSS sample buffer, and
`.rodata` breadcrumbs at offsets 0/64 with section alignment64, sizes 31/35
including NUL. Their exact bytes match the reviewed records, each <=64 and
page-contained; neither uses VMAP_STACK or init-freed storage. GCC inlines the
breadcrumb helper into the ordinary worker; no separate helper symbol exists.
Only setup/late-init functions use `.init.text`. The complete header/section
tables (trailing whitespace removed) and K230 symbol excerpts also ground ordinary
[8250 getter](8250_core.o.readelf.txt) and
[timer getter/state](timer-riscv.o.readelf.txt) lifetimes.

The existing inspector passed Image equality to selected kernel, initrd
payload equality to selected system, uImage header/data CRCs and sizes, DT
bootargs equality, all checksums, nonempty registration and all 629 inventoried
closure paths including selected system/kernel. The selected system init is
executable. [Inspector output](inspector-output.txt) and receipt retain exact
sizes/hashes/arguments. Image contains each complete breadcrumb and setup key
uniquely, plus original reporter strings. Artifact arguments exactly match
the prior evaluated parameters plus sole selected init: original two trace
tokens and sole ttyS0, with no rdinit/async/reporter/breadcrumb/retained-console
comparison flags baked in.

Complete decoded hardware DT matches original `gmsmq…` bundle after copying
both immutable DTBs to temporary files, deleting only `/chosen/bootargs` via
`fdtput -d`, then comparing sorted `dtc -I dtb -O dts -s` output. Canonical
SHA-256 is `c36085249e61fc1ed6f8f586b1ccbf11f22a4e27428a3e7e23b046384268fc02`.
Original DTBs were not modified. The [source evaluation receipt](../source-host/identities.json)
preserves all 91 existing package and ten kernel source/config identities.

These host gates justify tasks 5g.2–3 only. Coordinator review/integration/push
and CI remain; root owns manifest preparation/staging and the explicit
`--mode minimal --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs`
physical comparison after its protected preflight. A breadcrumb proves only
reaching that call; a later record proves progress past an earlier call, not
its full write count. Missing output is unknown, finite attempts are not a
firmware wall-clock deadline, and no RX/Bash delivery or automatic recovery
is inferred from these host artifacts.
