## 1. Ground the physical test layout

- [ ] 1.1 Trace physical CPU0's reset/vector and the U-Boot command from the
  pinned overlay into the built stage 1; record source paths and build
  configuration. Verify with `rg -n 'CONFIG_LINUX_RUN_CORE_ID|boot_baremetal|cpu0_hart_rstvec' /nix/store/g58y0fnasf1gapxjnjmbdnmg6zs58yhs-source/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/{board/canaan/common,arch/riscv/cpu/k230}` (pinned-source proof).
- [ ] 1.2 Establish nonoverlapping payload and output addresses from pinned
  stage-1 source and a known card's memory layout; document U-Boot cache
  invalidation/readback behavior and refuse to choose an address if this
  cannot be grounded. Verify with a cited map and `openspec validate
  the-small-core-runs-a-recoverable-heartbeat --strict` (source/document
  proof, no board claim).

## 2. Build a standalone scalar heartbeat

- [ ] 2.1 Add a tiny RV64I physical CPU0 payload and linker layout using
  the addresses established in 1.2, plus a host check for entry, footprint,
  and absence of V instructions. Verify with
  `sh tools/test-small-core-heartbeat.sh` (host binary proof, not board).
- [ ] 2.2 Record the exact load, release, repeated readback and stop/normal
  boot commands in a disposable-card runbook; verify with
  `openspec validate the-small-core-runs-a-recoverable-heartbeat --strict`
  (document proof, not board).

## 3. Physical recovery and execution

- [ ] 3.1 **BOARD-GATED.** With the sole board/console reservation and a
  disposable rollback card, rehearse the current one-shot or independent
  UMS/card-reader recovery and capture its result under
  `docs/evidence/second-core/`. Verify with the board console transcript
  showing restored normal boot and matching image hashes (physical proof).
- [ ] 3.2 **BLOCKED on 3.1. BOARD-GATED.** Load the inspected payload on the
  disposable card, run the source-grounded `boot_baremetal 0` sequence, and
  observe at least three increasing output values while the CPU1 U-Boot
  prompt responds; then restore normal boot and record Linux CPU masks.
  Verify with the exact U-Boot command and timestamped board transcript
  committed under `docs/evidence/second-core/` (physical CPU0 execution
  proof; any hang or static output fails this task).
