This change was split from `the-shell-manages-apps-as-cards` (task 4.2, plus
its dependent task 5.1). It is staged pending the user's/coordinator's
authorization of that split; task IDs keep the parent's numbering.

## 4. Cost decision (board-gated throughout)

- [ ] 4.2 Measure the panel's actual output/vblank cadence directly (not
  inferred from the advertised mode), then either fix an addressable CPU cost,
  or record an explicit reviewed decision to accept the measured cadence, or
  continue Pixman-path optimization if the cadence measurement identifies a
  real target. Verify with `python3 tools/card-shell-benchmark.py --board
  --output docs/evidence/card-shell/pixman.json` (only once a new variable is
  actually being tested -- ten-plus prior rounds already recorded the same
  failing result; see the parent's tasks.md for the full list) plus whatever
  direct cadence-measurement tool this investigation produces.

## 5. Integration (unblocked once 4.2 resolves)

- [ ] 5.1 Select the card-shell component into the real system/QEMU
  configuration, build `nix build
  .#nixosConfigurations.k230.config.system.build.toplevel` with it integrated,
  and run the non-fixture `tools/qemu-k230.sh --card-shell-smoke`. The fixture
  mode and flag already exist and pass
  (`docs/evidence/card-shell/qemu-fixture/passing/result.json`); this task is
  otherwise ready and only blocked on 4.2's decision landing first, per
  `docs/research/card-shell-qemu-smoke.md`'s own "Remaining integration gate."

## 6. Validation

- [x] 6.1 Validate this change: `openspec validate
  the-card-deck-still-misses-its-frame-budget --strict`. Passed 2026-09-28
  on `close/shell-umbrella`.
- [ ] 6.2 Do not archive until 4.2 is resolved (fixed or explicitly accepted)
  and 5.1's non-fixture QEMU proof is committed.
