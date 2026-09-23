## 1. Source-grounded readiness decision

- [x] 1.1 Extend `docs/research/second-core-feasibility.md` with the pinned DTS/Linux/OpenSBI call chain and the vendor AMP source contract; verify source paths and primary links distinguish facts from hypotheses.
- [x] 1.2 Add a read-only second-core snapshot helper and a host fixture test; verify `sh -n tools/second-core-readiness.sh` and `bash tools/test-second-core-readiness.sh` pass without a board.

## 2. Physical handoff evidence

- [ ] 2.1 The board coordinator runs `tools/second-core-readiness.sh` on the known-good board and commits a sanitized transcript; verify it shows the OpenSBI/domain, live DT, and Linux CPU observations without changing CPU state. **Hardware proof; not runnable under QEMU.**
- [ ] 2.2 Compare the committed transcript with the source gates and record the remaining prerequisite or a separately authorized rollback-image SMP/AMP proposal; verify the decision cites hart identity, firmware start, interrupt/timer, and coherency evidence. **Hardware/source review; no release action in this change.**

## 3. Change validation

- [x] 3.1 Validate the proposal and applied host artifacts with `openspec validate the-second-c908-core-is-investigated-safely --strict` and the helper fixture test; leave hardware tasks unchecked until the coordinator records board evidence.
