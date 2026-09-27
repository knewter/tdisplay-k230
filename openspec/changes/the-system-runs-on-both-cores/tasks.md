## 1. Read-only board probes (stage a — no reset, power, or CPU-state write)

- [x] 1.1 Add the three read-only RMU/PWR register fields (`0x9110100c`
  `CPU1_RST_CTL`, `0x91103018`/`0x9110301c` PWR CPU1 control/status) to
  `tools/second-core-readiness.sh`, reading only, never clearing the W1C
  reset-done bits, plus a matching host fixture case. Verify with
  `sh tools/test-second-core-readiness.sh` (host script-fixture proof, no
  board).
- [x] 1.2 Search the pinned kernel source for any read-only Linux-side path
  that reports OpenSBI HSM hart status without a CPU up/down transition
  (for example an SBI debugfs passthrough), and record the result — present,
  absent, or `<!-- UNVERIFIED -->` — against the exact pinned revision.
  Verify with `rg -n "sbi_hsm|hart_status|debugfs" /nix/store/hn11x8zd5linl193d8q0k9k99b46zqbm-linux-xuantie-k230-src/arch/riscv` (pinned-source audit, not board or emulated proof).
- [ ] 1.3 **BOARD-GATED.** On a known-good board, with the operator's already
  proven read-only MMIO read method (no `/dev/mem` write, no
  read-modify-write), run the extended collector from 1.1 and record the
  three register values plus a fresh `misa`/`uarch`/L2-size cross-check
  against the TRM's CPU0/CPU1 table. Verify with the board console capture
  committed to `docs/evidence/second-core/live-handoff-v2.txt` (board
  physical read-only observation). Needs the operator to hold
  `/dev/ttyACM0` for one session; no reset or reflash.
- [ ] 1.4 Update `docs/evidence/second-core/README.md`'s decision table with
  the 1.3 result, stating explicitly whether the new register/ISA evidence
  corroborates or falsifies "Linux already runs on physical CPU1." Verify
  with `openspec validate the-system-runs-on-both-cores --strict` after the
  edit (documentation-consistency proof, not new physical evidence).

## 2. Recovery rehearsal (must pass before any stage-3 task starts)

- [ ] 2.1 **BOARD-GATED.** Immediately before any reset/power register write
  is attempted (stage 3), rehearse the U-Boot one-shot recovery path used
  2026-09-25 (`docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`):
  one-shot `ext4load mmc 1:2` boot of the files preserved in
  `/var/lib/k230/boot-prev/`, then verify those files' `SHA256SUMS` against
  the running system before any register write proceeds. Verify with a
  board console transcript recording `BOOT_RESTORED_OK` or the equivalent
  hash match, committed under `docs/evidence/second-core/` (board physical
  recovery-rehearsal proof). Requires explicit user authorization to hold
  the board for this session, per AGENTS.md.
- [ ] 2.2 Confirm the independent SD card-reader / U-Boot `ums` recovery
  route (`docs/uboot-ums.md`) is still available as a fallback if the
  one-shot path in 2.1 fails: check that `tools/ums-session.py`'s capacity
  and identity refusal checks still pass against the currently flashed
  card's known sector count. Verify with
  `python3 -m unittest discover -s tests -p test_ums_target.py` (host proof
  of the recovery tool's refusal guards; not a live reflash).

## 3. OpenSBI + device-tree hart-release experiment (stage b — first stage that writes a reset/power register)

- [ ] 3.1 Establish physical CPU0's `CSR.MHARTID` and a usable distinct
  logical hart identity. Pinned stage-1 source already gives CPU0's reset
  vector/control addresses (`arch/riscv/cpu/k230/cpu.c:125-160`); now audit
  an early M-mode identity source, OpenSBI's scratch/HSM/IPI/timer paths,
  Linux's CPU entry, and physical CPU0's PLIC/ACLINT or other interrupt
  routing. A controlled startup diagnostic may read CPU0 registers but is
  not a second-program feature. If both cores read `mhartid=0`, a DT-only
  `cpu@1` is rejected. Record pinned source and any physical measurement
  under `docs/research/second-core-feasibility.md` and
  `docs/evidence/second-core/`; leave this task open until all paths are
  grounded.
- [ ] 3.2 **BLOCKED on 3.1 and the pre-Linux coherency gate in 4.1.
  BOARD-GATED.** Build a rollback-capable *experimental* stage-1/OpenSBI/DT
  path that starts physical CPU0 alongside Linux on physical CPU1, preserving
  unique logical IDs and verified per-core interrupts/timers. The normal
  image remains unchanged. After the recovery rehearsal, verify a board
  transcript with `Platform HART Count : 2`, Linux
  `smp: Brought up 1 node, 2 CPUs`, and timer/IPI tests. A failed route
  leaves this unticked. Requires the board operator's coordinated session
  and the recovery requirement in the delta spec.

## 4. Coherency validation (stage c)

- [ ] 4.1 **BOARD-GATED; required before 3.2 Linux SMP boot.** Establish
  the CPU0/CPU1 cache and atomic-sharing contract from Canaan source or run
  a bounded pre-Linux cross-core diagnostic of shared cached lines,
  uncached lines, AMO and LR/SC behavior, at least three repeats. Linux
  shared locks/page tables must not be the first coherence experiment.
  Capture the command, boot identity and pass/fail counts under
  `docs/evidence/second-core/`; no host or QEMU result satisfies this.

## 5. ISA-aware SMP scheduling (stage d)

- [ ] 5.1 **BLOCKED on 3.2/4.1. BOARD-GATED.** Build the initial Linux SMP
  image to a scalar common ISA baseline (RVV off in kernel and userspace),
  then show ordinary unpinned processes can execute and migrate on both
  logical CPUs under load with no illegal-instruction traps. Record
  `sched_getcpu`/affinity, `/sys/devices/system/cpu/{possible,present,online}`,
  per-CPU timers, and repeated runs in a board transcript. Restoring RVV
  requires a separately proved per-hart scheduling/userspace contract.
