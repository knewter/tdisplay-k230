## 1. Read-only board probes (stage a — no reset, power, or CPU-state write)

- [ ] 1.1 Add the three read-only RMU/PWR register fields (`0x9110100c`
  `CPU1_RST_CTL`, `0x91103018`/`0x9110301c` PWR CPU1 control/status) to
  `tools/second-core-readiness.sh`, reading only, never clearing the W1C
  reset-done bits, plus a matching host fixture case. Verify with
  `sh tools/test-second-core-readiness.sh` (host script-fixture proof, no
  board).
- [ ] 1.2 Search the pinned kernel source for any read-only Linux-side path
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

- [ ] 3.1 Obtain a Canaan statement or shipped stage-1 source establishing
  CPU1's physical hart ID, reset-vector address, and PLIC/ACLINT interrupt
  context. Record the citation or mark it unobtained. **Every task below is
  blocked until this is closed** (`docs/research/second-core-feasibility.md`:
  "An undocumented release sequence is a stop condition."). Verify with a
  cited source path or vendor statement committed to
  `docs/research/second-core-feasibility.md` (source/documentation
  grounding, not board proof).
- [ ] 3.2 **BLOCKED on 3.1. BOARD-GATED.** On a disposable rollback card
  only — never the board's only working card — choose one release
  mechanism from design.md decision 2 (OpenSBI platform writes
  `CPU1_RST_CTL`/reset-vector, or U-Boot spin-table release), build it, and
  boot it after 2.1/2.2 are current. Verify with a captured board console
  transcript requiring `Platform HART Count : 2` and Linux's
  `smp: Brought up 1 node, 2 CPUs`; any hang, missing hart, or
  interrupt/timer failure stops the task unticked (board physical
  hart-release proof). Requires explicit user authorization before the
  first register write, per AGENTS.md and proposal.md's Risk and recovery.

## 4. Coherency validation (stage c)

- [ ] 4.1 **BLOCKED on 3.2. BOARD-GATED.** Run an atomic/litmus-style
  cross-hart stress (concurrent AMO/load-reserve/store-conditional against
  shared cache lines from both harts) and a timer/IPI stress (repeated
  cross-hart IPI and ACLINT timer delivery under load), repeated at least
  three times. Verify with a board console transcript recording pass/fail
  counts for all repeats, committed under `docs/evidence/second-core/`
  (board physical coherency-stress proof; a single clean run does not pass
  this task).

## 5. ISA-aware SMP scheduling (stage d)

- [ ] 5.1 **BLOCKED on 4.1. BOARD-GATED.** Implement and verify one of
  design.md decision 4's constraints (hard CPU affinity keeping
  vector-using code off the non-RVV hart, a per-hart `hwprobe` gate, or a
  `nosmt`-style exclusion of the second hart from the general scheduler)
  before enabling scheduling across both harts. Verify with a board console
  transcript showing a synthetic RVV-using task correctly pinned or gated
  away from the non-RVV hart across repeated iterations, with zero
  illegal-instruction traps (board physical scheduling-safety proof). Do
  not enable general scheduling across both harts if this task is unticked.
