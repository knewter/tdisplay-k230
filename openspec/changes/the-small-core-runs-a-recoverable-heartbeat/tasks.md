## 1. Ground the physical test layout

- [x] 1.1 Trace physical CPU0's reset/vector and the U-Boot command from the
  pinned overlay into the built stage 1; record source paths and build
  configuration. Verify with `rg -n 'CONFIG_LINUX_RUN_CORE_ID|boot_baremetal|cpu0_hart_rstvec' /nix/store/g58y0fnasf1gapxjnjmbdnmg6zs58yhs-source/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/{board/canaan/common,arch/riscv/cpu/k230}` (pinned-source proof).
- [x] 1.2 Establish nonoverlapping payload and output addresses from pinned
  stage-1 source and a known card's memory layout; document U-Boot cache
  invalidation/readback behavior and refuse to choose an address if this
  cannot be grounded. Verify with a cited map and `openspec validate
  the-small-core-runs-a-recoverable-heartbeat --strict` (source/document
  proof, no board claim).

## 2. Build a standalone scalar heartbeat

- [x] 2.1 Add a tiny scalar RV64 physical CPU0 payload and linker layout using
  the addresses established in 1.2, plus a host check for entry, footprint,
  and absence of V instructions. Verify with
  `bash tools/test-small-core-heartbeat.sh` (host binary proof, not board).
- [x] 2.2 Record the exact load, release, repeated readback and stop/normal
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

## 4. Coexistence with the Linux handheld

- [ ] 4.1 **BLOCKED on 3.2.** Ground a region that remains reserved from
  Linux in the experimental device tree and specify the CPU0 write/Linux
  read cache protocol; include the physical address, size, and exclusion
  from normal allocator use. Verify with `nix build .#deviceTree` and a
  decompiled `reserved-memory` node check (DT build proof, not board).
- [ ] 4.2 **BLOCKED on 4.1.** Patch only the experimental SPL CPU0 parking
  path to update that heartbeat after releasing CPU1, and add a read-only
  Linux observer. Verify with `nix build .#stage1` and the narrow host
  observer fixture (cross-build/host proof, not board).
- [ ] 4.3 **BLOCKED on 4.2. BOARD-GATED.** Rehearse recovery in this board
  session, boot the experimental stage 1/DT on a disposable card, record at
  least three changing heartbeat values under a responsive Linux console
  and shell, and restore known-good stage 1. Verify with a timestamped
  `/dev/ttyACM0` console transcript and normal-boot hash/CPU-mask checks
  committed under `docs/evidence/second-core/` (physical coexistence proof).
