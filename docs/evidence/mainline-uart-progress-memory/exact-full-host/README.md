# Memory matching host artifacts and exact configured objects

Evidence class: completed matching host artifacts and actual selected-header
RISC-V object compilation/API/layout inspection. No board/UART/camera action,
concurrent worker/observer execution, physical summary/receipt/root/touch or
recovery was tested here. Physical tasks 5i.5–6 and task 5b.5 remain
**UNVERIFIED**; positive controller/physical evidence is separate.

The coordinator's full matching invocation used frozen revision
`7af8f7b8b5849c75df61d39ee772c2cc8f38542c` and returned 0,
2026-10-04T04:16:00.152160+00:00–04:47:18.845096+00:00. The exact command,
times and outputs are retained in [proof.json](proof.json). No full build was
duplicated. The narrow object invocation used worktree
`/home/jadams/tmp/k230-mainline-uart-progress-memory`, branch
`mainline-uart-progress-memory`, source checkpoint
`29979175f000a92ca687ce7a990fb18e0e3d4595`.

Only after the actual successful full-build receipt and immutable dev presence
did we acquire the shared lock nonblocking. The [offline dry run](object-dry-run.txt)
selected only exact-object derivation `86bw9hjq…`, with no fetch/full rebuild.
The [narrow receipt](object-build-receipt.json) records return0,
2026-10-04T04:48:37.513368+00:00–04:48:48.757130+00:00; lock released.

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineUartProgressMemoryExactObjects --offline --no-link \
  --print-out-paths --max-jobs 1 --cores 2
python3 docs/evidence/mainline-uart-progress-memory/exact-full-host/verify.py \
  /nix/store/v5b3a2ny1gsiyd9fbwqrhq1c9g4lc6xf-k230-mainline-uart-progress-exact-objects \
  ~/tmp/k230-mainline-uart-memory-board/full-build-result.private.json \
  docs/evidence/mainline-uart-progress-memory/exact-full-host
```

Read-only [verifier](verify.py) passed, including the added target API/compiler
excerpt. Owned changes are this exact/full evidence and only task 5i.2–3 proof;
source/protocol/recipes/defaults/controller/protected files are unchanged.

| Artifact | Exact installed identity |
| --- | --- |
| Bundle | `/nix/store/lznjjfx1kzm8mp2j0r06c87h2vdymkhd-k230-mainline-drm-trial-boot-files` |
| System | `/nix/store/sja2fw7arlkkjws7ax7h1r2b9can7y8j-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/zk5rbsrgqgp40bk1314mj0i50qhn260m-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Dev | `/nix/store/1pvqbm4r3gqcvsabgkz5wvrpxfbk5k1v-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| Source | `/nix/store/f7xg031sjb9dy3bswm5s3qjr9xwx1g02-linux-mainline-k230-uart-progress-memory-src` |
| Exact objects | `/nix/store/v5b3a2ny1gsiyd9fbwqrhq1c9g4lc6xf-k230-mainline-uart-progress-exact-objects` |

Kernel/dev share reviewed derivation `c7rd5pii…`; bundle matches `lm3s9n0w…`.
Actual worker SHA-256:
`307d7c0588499dd32826c1d05476e0bf6d46ca0c8939d42e0b4f7180545b98dc`.
Realized source derivation layers exactly over immutable PostSample `wnvb…`
with only the Memory patch. Six cached getter/timer source/header/Kconfig files
are byte-identical to that parent, with per-file SHA-256 receipts.

All three objects are ELF64 little-endian RISC-V relocatables from GCC15.3.0,
W=1. The exact recipe compiles actual selected worker/getter/timer C against
installed selected dev config/generated headers, with no CONFIG overlay.
The installed dev `source` is a prepared build skeleton rather than a symlink
to complete selected source; its Makefile matches that source. Actual config/
autoconf bytes match selected dev before/after compilation and also parent
PostSample `js4…`. Config SHA-256:
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`;
autoconf SHA-256:
`99f44d781b246202edab1d5ef8c4836b15ae99c590999ff268541dfd673865d0`.
Effective config differences are empty. Reporter/SBI/8250/DW/OF/timer dependencies
remain built-in; 4KiB pages, VMAP_STACK=y and KUNIT disabled. The
[compile log](exact-object-compile.log) retains the pahole-version mismatch
(kernel131/object environment0); no C warning was observed.
[Checksums](exact-object-SHA256SUMS) passed.

[Worker/observer ELF inspection](k230-uart-progress.o.readelf.txt) shows ordinary
`.text` worker, Memory observer and active helper; flags plus four-byte atomic
state in `.sbss`; completion in ordinary `.data`, size32. Memory summary buffer
is ordinary `.bss`, size256/alignment256/offset0; inherited numeric buffer
remains size256/alignment256/offset256. Each is page-contained, not VMAP_STACK
or init-freed storage. Four inherited fixed arrays remain ordinary `.rodata`,
alignment64, offsets0/64/128/192 and sizes31/35/35/33 including NUL. Only setup/
late-init functions use `.init.text`; publication helper is inlined.
Ordinary [8250 getter](8250_core.o.readelf.txt) and
[timer getter/state](timer-riscv.o.readelf.txt) lifetimes are inspected too.

The actual matching object references `wait_for_completion_timeout` and
`complete`. [Target instruction excerpt](memory-api-disassembly.txt) shows the
observer's single state `lw` followed by acquire `fence r,rw`, bit-field decoding,
and an inlined release publication `fence rw,w` followed by state `sw`.
These match the source's one packed release/acquire observation without retries.
Compilation/API/instruction inspection is not proof of concurrent runtime
progress or hardware memory ordering under a stalled kernel.

The existing [inspector](inspector-output.txt) passed selected Image equality,
selected system initrd payload equality, uImage header/data CRCs and sizes,
all hashes, DT bootargs, nonempty registration and all629 closure paths including
selected system/kernel. Selected init is executable. Linked Image contains the
unique exact Memory format and setup key, inherited four records/three setup
keys and numeric reporter strings. Artifact arguments exactly retain parent
params plus sole selected init: sole ttyS0 and original two trace tokens; no
rdinit/async/reporter/Breadcrumbs/PostSample/Memory/retained-console comparison
gate is baked in. Host typing will transform those qualified args separately.

Complete hardware DT matches parent PostSample `fjmx…` after copying immutable
DTBs, deleting only `/chosen/bootargs` via `fdtput -d` and comparing sorted
`dtc -I dtb -O dts -s`. Canonical SHA-256:
`c36085249e61fc1ed6f8f586b1ccbf11f22a4e27428a3e7e23b046384268fc02`.
Original DTBs are untouched. [Source identity receipt](../source-host/identities.json)
preserves all99 existing package and12 exposed kernel source/config identities.

These performed host gates justify only 5i.2–3. Coordinator owns integration/
CI, actual positive controller preparation, protected staging and any typed
`--mode minimal --same-image-shell-pid1 --uart-progress --uart-progress-memory`
physical comparison. Suppressed worker output and the added observer change
workload/timing: this is an intervention. One received summary proves recorded
progress before its final firmware call, not that call's return, a firmware/IRQ
cause, Bash RX or ordinary root/touch. Missing summary leaves worker/observer/
timer/scheduler/output unknown; M-mode can prevent S-mode observer execution.
Kernel timeout/attempt count is not a firmware wall-clock guarantee; recovery
and receipt remain separate facts.
