# CPU0 SPL identity diagnostic: host build only

Recorded 2026-09-26. Branch `investigate/second-core-linux-smp-20260926`
at base `ba23c967`, using the pinned Canaan U-Boot overlay at SDK revision
`1104236db4d1e47873bd68924f912747b820228c`.

The optional `uboot-k230-cpu0-identity-probe` derivation applies
`nix/patches/second-core/spl-cpu0-identity.patch` to the physical CPU0 SPL
handoff. It reads `CSR.MHARTID` and `CSR.MISA` and prints one
`CPU0_SPL_IDENTITY` line immediately before the existing release of physical
CPU1. It adds no second-core payload, reset write, or Linux CPU.

Host commands and results:

```text
patch --dry-run -d <pinned U-Boot overlay> -p1 < nix/patches/second-core/spl-cpu0-identity.patch
  checking file board/canaan/common/k230_img.c; exit 0
nix eval --raw .#uboot-k230.drvPath
  /nix/store/kac0dycgcny0m9yapbhmdydyhps6a75q-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10.drv
nix eval --raw .#uboot-k230.outPath
  /nix/store/zzz867rp8drrwkhibj0rlqc04sk9g7f8-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10
stat -c '%s' <normal output>/spl/u-boot-spl.bin
  222816
sha256sum <normal output>/spl/u-boot-spl.bin
  f311eef0432aa2652508c9374567b4dbf1d9bd347031310a9d69fa3f92ade90b
nix eval --raw .#uboot-k230-cpu0-identity-probe.drvPath
  /nix/store/4mp1lwik2lc1jnlmzdjh9dfkpksms2y5-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10.drv
nix build .#uboot-k230-cpu0-identity-probe --no-link --print-out-paths --max-jobs 1 --cores 4
  /nix/store/27iwj9m4vfacsgagdf5pimi6f7g75y6i-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10
nix log /nix/store/4mp1lwik2lc1jnlmzdjh9dfkpksms2y5-uboot-k230_canmv_v3_defconfig-riscv64-unknown-linux-gnu-2022.10.drv
  SPL size check: 222880 bytes (0x366a0) against 0x80000 (524288 bytes)
sha256sum <probe output>/spl/u-boot-spl.bin
  55a69d761c72e31963ecce5430192b7d17de4c1aff944a9ef36a8ed6a97b001d
strings <probe output>/spl/u-boot-spl | rg CPU0_SPL_IDENTITY
  CPU0_SPL_IDENTITY mhartid=0x%lx misa=0x%lx
```

The normal U-Boot derivation path above matches the pre-change master
evaluation; the diagnostic is default-off. These are host source/compile
checks. No experimental SPL was installed and no CPU0 CSR was measured on
the board. A physical trial requires a verified known-good raw-stage-1
backup, external card-reader recovery, and the board operator's exclusive
serial/card session. Even a confirmed duplicate `mhartid` would only settle
one SMP design gate; it would not prove interrupt routing or coherency.
