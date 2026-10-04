# Exact configured objects and matching full host artifacts

Evidence class: completed matching host artifacts and exact selected-header
RISC-V object compilation. No board/UART/camera action, worker execution,
receipt, physical counters, root/touch or recovery was tested here. Physical
5h.5–6, positive controller preparation and task 5b.5 remain **UNVERIFIED**.

The coordinator's full matching bundle/dev invocation used frozen revision
`75cc49df12972235be411e6eca739935ce75614d` and returned 0, from
2026-10-04T03:00:57.305156+00:00 to 2026-10-04T03:33:55.986861+00:00.
Its exact public-safe command, times and returned paths are in
[proof.json](proof.json). That full build was not duplicated.

The narrow object invocation used worktree
`/home/jadams/tmp/k230-mainline-uart-progress-post-sample`, branch
`mainline-uart-progress-post-sample`, source revision
`e3edc5e6e71219216c78cddae6cf14166c82144d`. Only after the actual successful
receipt and installed dev availability did we acquire the shared lock.
[Offline dry run](object-dry-run.txt) selected only the exact-object derivation.
[Narrow receipt](object-build-receipt.json) records return 0,
2026-10-04T03:35:05.945773+00:00–03:35:18.333116+00:00. The lock was released.

```sh
flock -n /tmp/k230-nix-build.lock nix build \
  .#kernelMainlineUartProgressPostSampleExactObjects --offline --no-link \
  --print-out-paths --max-jobs 1 --cores 2
python3 docs/evidence/mainline-uart-progress-post-sample/exact-full-host/verify.py \
  /nix/store/jaxswy1k0vj56460sxc80mh4za57nrga-k230-mainline-uart-progress-exact-objects \
  ~/tmp/k230-mainline-uart-post-sample-board/full-build-result.private.json \
  docs/evidence/mainline-uart-progress-post-sample/exact-full-host
```

The read-only [verifier](verify.py) passed. Owned changes are this evidence and
only task 5h.2–3 entries; source, protocol, recipes, defaults, controllers and
protected card files were not changed. The first verifier attempt incorrectly
assumed kernel.dev's `source` was a symlink to the complete selected source.
It is the installed build skeleton directory. The corrected check compares its
Makefile with the selected source, while the exact recipe compiles the actual
three selected C files against that installed dev's config/generated headers.
The selected complete source is independently pinned by the object output,
source derivation layering and worker digest; no artifact was altered.

| Artifact | Exact installed identity |
| --- | --- |
| Bundle | `/nix/store/fjmxf6kn1yq0xk9v783amgymybhcrwkb-k230-mainline-drm-trial-boot-files` |
| System | `/nix/store/5ha786snzrp5c8gkfamlzrmdw1anyj6m-nixos-system-nixos-26.11.20260919.20b1ddd` |
| Kernel | `/nix/store/xhglqk1w6xvvr1f3nbbazgf2mm9fz225-linux-riscv64-unknown-linux-gnu-7.3.0-rc5` |
| Dev | `/nix/store/js4by9macr407x7zp8hraykh23bb9an7-linux-riscv64-unknown-linux-gnu-7.3.0-rc5-dev` |
| Source | `/nix/store/wnvbxaiqgbhhajsajy5mlpn36zf8alga-linux-mainline-k230-uart-progress-post-sample-src` |
| Exact objects | `/nix/store/jaxswy1k0vj56460sxc80mh4za57nrga-k230-mainline-uart-progress-exact-objects` |

Kernel/dev share derivation `0ldhm7ay…`; bundle matches `zgkkp2km…`.
Actual worker SHA-256 is
`aee68aaec5c5c0e2b23919901eb99189265fd2b4787a0e50bc11159afd81ef9b`.
The realized source derivation layers exactly over immutable `k5a5…`
Breadcrumbs source with only the new PostSample patch. Six cached getter/timer
source/header/Kconfig dependencies are byte-identical to that parent, with
per-file SHA-256 receipts retained.

All three objects are ELF64 little-endian RISC-V relocatables from GCC 15.3.0,
W=1. Actual config/autoconf bytes match selected installed dev before/after
compilation, without a CONFIG overlay; both also match the parent `xl3cy…` dev.
Config SHA-256:
`52e7470b108ad094dbdf88b94e3e8838564edbda9e7a015b4279012e6765c9f1`;
autoconf SHA-256:
`99f44d781b246202edab1d5ef8c4836b15ae99c590999ff268541dfd673865d0`.
Effective config differences from parent are empty. Reporter/SBI/8250/DW/OF/
timer dependencies remain built-in, pages are 4KiB, VMAP_STACK=y and KUNIT is
disabled. The [compile log](exact-object-compile.log) retains the pahole-version
mismatch (kernel131/object environment0); no C warning was observed.
[Checksums](exact-object-SHA256SUMS) passed.

The [worker ELF inspection](k230-uart-progress.o.readelf.txt) shows four ordinary
`.rodata` arrays, section alignment64: worker-entry offset0 size31,
third-post-sleep offset64 size35, first-post-sleep offset128 size35,
after-n1-write offset192 size33 (sizes include NUL). Exact bytes match the four
reviewed records, each <=64 and page-contained, with no stack/init-freed storage.
Worker is `.text`; flags are `.sbss`; helpers are inlined into that ordinary
worker. Only setup/late-init functions use `.init.text`. Original sample buffer
remains ordinary `.bss`, size256/alignment256. Complete section/header tables
and K230 symbol excerpts ground ordinary [8250 getter](8250_core.o.readelf.txt)
and [timer getter/state](timer-riscv.o.readelf.txt) lifetimes.

The existing [inspector](inspector-output.txt) passed selected kernel Image and
selected system initrd payload equality, uImage header/data CRCs and sizes, DT
bootargs, all checksums, nonempty registration and all 629 closure paths including
selected system/kernel. Selected init is executable. Image contains each of the
four complete records and all three reporter setup keys uniquely. Original
numeric reporter strings remain linked. Artifact arguments exactly match
inherited parameters plus sole selected init: original two trace tokens and
sole ttyS0; no rdinit/async/reporter/Breadcrumbs/PostSample/retained-console
comparison flags are baked in.

Complete decoded hardware DT matches parent `mhq…` after copying both immutable
DTBs to temporary files, deleting only `/chosen/bootargs` with `fdtput -d`, and
comparing sorted `dtc -I dtb -O dts -s` output. Canonical SHA-256:
`c36085249e61fc1ed6f8f586b1ccbf11f22a4e27428a3e7e23b046384268fc02`.
Original DTBs were not modified. The [source identity receipt](../source-host/identities.json)
preserves all 95 old package and 11 exposed kernel source/config identities.

These actual host gates justify only 5h.2–3. Root owns review/integration/push,
CI, positive controller preparation, manifest/staging and any explicit
`--mode minimal --same-image-shell-pid1 --uart-progress --uart-progress-breadcrumbs --uart-progress-post-sample`
physical comparison after its protected preflight. A visible after-n1 point
proves the previous numeric call returned, not its full count or this call's
return; a later point proves later progress. Missing output remains unknown,
and finite attempts provide no firmware wall-clock deadline. No physical RX,
Bash delivery, usable root or automatic recovery follows from host proof.
