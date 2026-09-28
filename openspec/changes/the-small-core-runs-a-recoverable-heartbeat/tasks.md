**Audited 2026-09-28.** This change is suspended per `proposal.md`'s
2026-09-26 note: the requested outcome is Linux SMP
(`the-system-runs-on-both-cores`), and a CPU0 heartbeat/AMP payload is not a
substitute for it. Tasks 1.1/1.2/2.1/2.2 are ticked below because their host
evidence exists and was independently reproduced during this audit
(`impl/small-core-heartbeat-20260926` at `4e6be10d`, cherry-picked onto
`close/second-core`). Tasks 3.1 onward are board-gated *and* suspended: do
not run them without a new decision that un-suspends this proposal, even
though the runbook and payload for 3.1/3.2 are otherwise ready.

**Note, 2026-09-28 (resequenced, not archived or implemented):** the user
has formally chosen AMP for the second-core project; see
`openspec/changes/the-small-core-runs-as-a-coprocessor/`. Tasks 1.1/1.2/2.1/2.2
(complete) and 3.1/3.2 (board-gated, ready) are carried into that change's
own stage-1/stage-2/stage-3 tasks in the same order — recovery rehearsal,
then the board release. Task family 4 (patch the CPU0 SPL parking loop for
unconditional coexistence) is recorded as superseded by that change's
Linux-driven runtime start/stop design instead. Nothing here is ticked,
archived, or run by this note; the change stays open per AGENTS.md until the
user confirms otherwise.

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

- [x] 3.1 WAIVED, NOT PERFORMED: with the sole board/console reservation and
  a disposable rollback card, rehearse the current one-shot or independent
  UMS/card-reader recovery and capture its result under
  `docs/evidence/second-core/`. **Waived by the operator's 2026-09-28
  decision** (recorded in `the-small-core-runs-as-a-coprocessor`'s own
  addenda and `docs/closeout/second-core-plan.md`'s addendum): "we can
  easily fix the sd card damn. don't worry about recovery we've literally
  done that fine already before. i don't want to do a heartbeat test on a
  spare card." No disposable/spare card is required; recovery, if needed,
  is by the already-proven U-Boot one-shot boot from `boot-prev` or
  `ums`/flash reimaging, on the normal card. This whole change remains
  suspended in favor of the AMP successor (see the note at the top of this
  file); this task is not being run here.
- [ ] 3.2 **BOARD-GATED.** Load the inspected payload on the
  normal card, run the source-grounded `boot_baremetal 0` sequence, and
  observe at least three increasing output values while the CPU1 U-Boot
  prompt responds; then restore normal boot and record Linux CPU masks.
  Recovery, if needed, is by the fallback routes named in task 3.1 (no
  disposable card). Verify with the exact U-Boot command and timestamped
  board transcript committed under `docs/evidence/second-core/` (physical
  CPU0 execution proof; any hang or static output fails this task).

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
- [ ] 4.3 **BLOCKED on 4.2. BOARD-GATED.** Confirm the fallback recovery
  route named in task 3.1 is available, boot the experimental stage 1/DT on
  the normal card (no disposable card required), record at least three
  changing heartbeat values under a responsive Linux console and shell, and
  restore known-good stage 1. Verify with a timestamped `/dev/ttyACM0`
  console transcript and normal-boot hash/CPU-mask checks committed under
  `docs/evidence/second-core/` (physical coexistence proof).
