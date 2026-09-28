**Note, 2026-09-28 (redirected, not archived):** the user has formally
redirected the second-core project to AMP; see
`openspec/changes/the-small-core-runs-as-a-coprocessor/`, citing
`docs/closeout/second-core-plan.md`. Section 1 (complete) is unaffected.
Section 2 (recovery rehearsal) is carried into that change's own task list
as the same work item, and is itself now **waived** by a further 2026-09-28
operator decision (see task 2.1's own note below) — no external-reader
rehearsal or spare/disposable card is required anywhere in this project's
second-core work; the fallback is the proven U-Boot one-shot/`ums`/
reimaging recovery routes. **Sections 3, 4, and 5 are formally WITHDRAWN**
per that same redirect decision — they exist solely to make Linux treat
CPU0 as a peer SBI hart for SMP, which is no longer pursued — and are left
exactly as unticked as they were, not archived away silently; this change
stays open per AGENTS.md until the user confirms its archival.

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
- [x] 1.3 **BOARD-GATED.** On a known-good board, with the operator's already
  proven read-only MMIO read method (no `/dev/mem` write, no
  read-modify-write), run the extended collector from 1.1 and record the
  three register values plus a fresh `misa`/`uarch`/L2-size cross-check
  against the TRM's CPU0/CPU1 table. Verify with the board console capture
  committed to `docs/evidence/second-core/live-handoff-v2.txt` (board
  physical read-only observation). Needs the operator to hold
  `/dev/ttyACM0` for one session; no reset or reflash.
  Closed 2026-09-28 on audit: `docs/evidence/second-core/live-handoff-v2.txt`
  (captured `2026-09-27T03:32:04Z`) records `cpu1_rst_ctl=0x00013000` and
  both PWR fields as `<unavailable:EPERM>` — recorded, not inferred, per the
  read-only-probe requirement — plus `isa=rv64imafdcv...` and a 256K L2,
  cross-checked against the TRM's CPU1 profile in the same file. The earlier
  `live-handoff-v2-partial.txt` documents the pre-fix EPERM abort this run
  superseded. No MMIO write occurred in either run.
- [x] 1.4 Update `docs/evidence/second-core/README.md`'s decision table with
  the 1.3 result, stating explicitly whether the new register/ISA evidence
  corroborates or falsifies "Linux already runs on physical CPU1." Verify
  with `openspec validate the-system-runs-on-both-cores --strict` after the
  edit (documentation-consistency proof, not new physical evidence).
  Closed 2026-09-28 on audit: `docs/evidence/second-core/README.md`'s
  "2026-09-26 read-only continuation" section and table already state the
  CPU1 reset-control read is "consistent with physical CPU1 released" and
  the live ISA/cache reading "corroborates the physical big-core handoff";
  it does not claim the PWR reads. `openspec validate the-system-runs-on-both-cores --strict`
  re-run clean during this audit (see report).
- [x] 1.5 Build and package the default-off CPU0 SPL identity diagnostic
  without changing the normal stage-1 derivation. Verify with
  `nix build .#uboot-k230-cpu0-identity-probe --no-link --print-out-paths --max-jobs 1 --cores 4`,
  `nix build .#stage1-cpu0-identity-probe --no-link --print-out-paths --max-jobs 1 --cores 4`,
  `nix eval --raw .#uboot-k230.drvPath`,
  `nix eval --raw .#stage1-packaging.drvPath`, and `cmp` of packaged U-Boot
  proper against normal. Results and exact paths/hashes are in
  `docs/evidence/second-core/spl-cpu0-identity-host-build.md` and
  `docs/evidence/second-core/cpu0-identity-trial.md`. This is host build
  proof only; it does not close 1.3, 3.1, or any Linux SMP gate.
- [x] 1.6 Run the bounded default-off physical CPU0 SPL identity diagnostic,
  preserve verified copies of both original SPL slots on and off board,
  capture the diagnostic boot, restore both original slots, and prove a
  subsequent normal boot. Verify by the direct-read hashes and serial
  excerpts in `docs/evidence/second-core/cpu0-identity-physical-trial.md`
  (physical board proof of CPU0's sampled CSRs). The pinned OpenSBI
  `sbi_init.c` and `riscv_asm.h` source chain also establishes that the
  CPU1-side `Boot HART ID : 0` comes from `CSR.MHARTID`. The external-reader
  restoration rehearsal and all Linux SMP gates remain open.

## 2. Recovery rehearsal (must pass before any stage-3 task starts)

- [x] 2.1 WAIVED, NOT PERFORMED: before any experimental SPL flash or CPU0
  reset/vector write, identify the board's *current* known-good stage-1
  bytes and preserve a verified backup, confirming an external SD-card
  reader can restore the raw stage-1 offsets at 1 MiB and 1.5 MiB even if
  U-Boot never starts. Audited 2026-09-28: `cpu0-identity-physical-trial.md`
  proves a same-session on-board `dd` restore from a verified backup (works
  only if U-Boot still runs well enough for Linux to read the card), and
  `cpu0-identity-trial.md`'s "Prepared external-reader procedure" is
  written but was never run. **Waived by a further 2026-09-28 operator
  decision** (recorded in `the-small-core-runs-as-a-coprocessor`'s own
  proposal.md/design.md/tasks.md addenda and `docs/closeout/second-core-
  plan.md`'s addendum): the user said "we can easily fix the sd card damn.
  don't worry about recovery we've literally done that fine already
  before. i don't want to do a heartbeat test on a spare card." No task in
  this project's second-core work may require a separate spare/disposable
  card; the fallback recovery for any future register-writing board step is
  the already-proven U-Boot one-shot boot from `boot-prev` or `ums`/flash
  reimaging, on the normal card. This does not waive per-write
  authorization: any later register-writing task still needs the user's
  explicit authorization at the time it runs.
- [x] 2.2 WAIVED, NOT PERFORMED: confirm the independent SD-card-reader
  recovery route for an experimental SPL and retain U-Boot `ums` as an
  additional route only while U-Boot is reachable (`docs/uboot-ums.md`).
  Audited 2026-09-28: host portion re-run clean (`python3 -m unittest
  discover -s tests -p test_ums_target.py` → 16 tests OK) but the task's own
  physical-card-identity/backup requirement was never recorded, since 2.1's
  external-reader rehearsal was never run. **Waived by the same 2026-09-28
  operator decision as 2.1**: the external-reader route is no longer
  required; `ums` and U-Boot one-shot/reimaging remain the fallback,
  reachable on the normal card without a separate rehearsal.

## 3. OpenSBI + device-tree hart-release experiment (stage b — first stage that writes a reset/power register)

**WITHDRAWN 2026-09-28** per the user's formal redirect of the second-core
project from SMP to AMP (`the-small-core-runs-as-a-coprocessor`, citing
`docs/closeout/second-core-plan.md`'s recommendation): this stage exists
solely to make Linux treat CPU0 as a peer SBI hart, which is no longer
pursued. Left unticked, not archived away, per AGENTS.md.

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
  Audited 2026-09-28: partially grounded, left open per its own text. The
  physical measurement half is done — `mhartid=0x0` is now a first-hand
  CPU0 SPL reading (`cpu0-identity-physical-trial.md`), and the CPU1-side
  `Boot HART ID : 0` is traced to the same CSR through pinned OpenSBI source
  (`docs/research/second-core-feasibility.md`, "2026-09-27 physical CPU0
  identity measurement"). The distinct-logical-identity half is not: the
  2026-09-26 audit in that same doc greps the pinned U-Boot/OpenSBI overlays
  for another physical core-ID CSR and finds none defined. No design or
  vendor source establishes a working virtual-ID scheme, so this remains
  blocked on a result nobody has yet — not on a board session.
- [ ] 3.2 **BLOCKED on 3.1 and the pre-Linux coherency gate in 4.1.
  BOARD-GATED.** Build a rollback-capable *experimental* stage-1/OpenSBI/DT
  path that starts physical CPU0 alongside Linux on physical CPU1, preserving
  unique logical IDs and verified per-core interrupts/timers. The normal
  image remains unchanged. After the recovery rehearsal, verify a board
  transcript with `Platform HART Count : 2`, Linux
  `smp: Brought up 1 node, 2 CPUs`, and timer/IPI tests. A failed route
  leaves this unticked. Requires the board operator's coordinated session
  and the recovery requirement in the delta spec.
  Audited 2026-09-28: still open, blocked on 3.1 and 4.1, no new evidence.
  Writes a reset/power/vector register; per AGENTS.md this needs explicit
  user authorization for the board session in addition to being blocked.

## 4. Coherency validation (stage c)

**WITHDRAWN 2026-09-28**, same reason and citation as section 3.

- [ ] 4.1 **BOARD-GATED; required before 3.2 Linux SMP boot.** Establish
  the CPU0/CPU1 cache and atomic-sharing contract from Canaan source or run
  a bounded pre-Linux cross-core diagnostic of shared cached lines,
  uncached lines, AMO and LR/SC behavior, at least three repeats. Linux
  shared locks/page tables must not be the first coherence experiment.
  Capture the command, boot identity and pass/fail counts under
  `docs/evidence/second-core/`; no host or QEMU result satisfies this.
  Audited 2026-09-28: still open, no new evidence. No Canaan coherency
  statement has surfaced; the bounded pre-Linux diagnostic itself has not
  been designed or run. Requires explicit user authorization: it is a
  hardware-writing, board-exclusive diagnostic gating 3.2.

## 5. ISA-aware SMP scheduling (stage d)

**WITHDRAWN 2026-09-28**, same reason and citation as section 3.

- [ ] 5.1 **BLOCKED on 3.2/4.1. BOARD-GATED.** Build the initial Linux SMP
  image to a scalar common ISA baseline (RVV off in kernel and userspace),
  then show ordinary unpinned processes can execute and migrate on both
  logical CPUs under load with no illegal-instruction traps. Record
  `sched_getcpu`/affinity, `/sys/devices/system/cpu/{possible,present,online}`,
  per-CPU timers, and repeated runs in a board transcript. Restoring RVV
  requires a separately proved per-hart scheduling/userspace contract.
  Audited 2026-09-28: still open, blocked on 3.2/4.1, no new evidence.
