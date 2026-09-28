This change was split from `the-shell-manages-apps-as-cards` (task 4.2, plus
its dependent task 5.1). Task IDs keep the parent's numbering. Authorized by
the user 2026-09-28 ("frame budget go").

## 4. Cost decision (board-gated throughout)

- [x] 4.2a Measure the panel's actual output/vblank cadence directly (not
  inferred from the advertised mode). Done 2026-09-28: hardware vblank is a
  clean 19.16 ms grid even while the deck animates
  (`docs/evidence/card-shell/frame-budget/board-result-2026-09-28.md`,
  `analysis.md`). H1 confirmed (render/commit overrun quantized to the
  vblank grid by `canaan_crtc_atomic_flush`'s synchronous commit); H4
  (vblank IRQ at 1/3 rate) refuted.
- [x] 4.2b Measure where the per-frame time goes on the host, with a ranked
  cost table and a stated host-to-board multiplier. Done 2026-09-28
  (`docs/evidence/card-shell/frame-budget/host-cost-table.md`): Build
  (`wlr_scene_output_build_state`) is 94.9% of render CPU (host p50 28.1 ms,
  p95 30.0 ms; board p95 14.0-19.8 ms depending on card count -- host runs
  1.5-2.1x the board's own Build time on this workload, via QEMU user-mode
  emulation, not a faster proxy for it). Damage-extent instrumentation added
  (`card_bench_render_damage`, new `K230_CARD_SHELL frame-damage` rows) shows
  76-99.6% of the 568x1232 output is damaged on essentially every animated
  frame -- inherent to the webOS-fan deck moving several cards at once, not
  a damage-tracking defect (confirmed by one clean 6.6%-damage counter-example
  at 4.18 ms build). Every other code-level candidate in this task's list
  (avoid re-clip/re-scale of unchanged cards, cache each card's scaled
  result, skip scene sync when unchanged, reduce per-frame allocations) was
  already implemented in prior rounds; verified by reading, not assumed.
  The scaled-cache path (`SWAY_K230_CARD_SCALED_CACHE=1`, default-on in
  `nix/shell.nix`) measured net *negative* on host (Build p50 +8.7%, p95
  +12.1%) in two independent runs against two independent builds -- not
  disabled here because it is also the sole mechanism providing the required
  capped (~15fps) live-preview rate; flagged as a decoupling opportunity for
  a future task, not fixed in this one.
- [x] 4.2c Assess commit pipelining (optional). Done 2026-09-28
  (`docs/evidence/card-shell/frame-budget/commit-pipelining-assessment.md`):
  the mechanism is confirmed (kernel-side, `canaan_crtc_atomic_flush`'s
  synchronous register write, per `analysis.md` H1) but the one known fix
  (`canaan-drm-defer-reg-load-to-vblank.patch`) already caused an unrelated
  boot panic and is deliberately not applied. Not attempted here: it is a
  kernel change, board-gated, and this task was told not to touch the board;
  reopening a change that already caused a boot panic is not "small and
  safe" per this task's own bar for touching the kernel.
- [x] 4.2e "Draw less per frame" (option 1, user-authorized 2026-09-28 "yeah
  work on the card overview smoothness"), on `perf/deck-draw-less`, base
  `d902bac4`: found a real code-level lever 4.2b's own list did not name --
  `nix/card-shell/adapter.c`'s `sync_node` hardcoded
  `WLR_SCALE_FILTER_BILINEAR` for every live mirror's direct composite
  regardless of motion, unlike the scaled-cache path's existing
  motion-aware `fast` filter. Switched it to
  `scene_in_motion() ? NEAREST : BILINEAR`, matching that existing trade.
  Host `tests/card_shell_runtime.py --benchmark`, four alternating
  before/after pairs on the same host: Build p50 25.55ms -> 9.05ms (-65%),
  p95 28.96ms -> 11.22ms (-61%), reproduced every full-sample run --
  `docs/evidence/card-shell/frame-budget/motion-time-filter-2026-09-28.md`.
  A separate, larger-looking lever (give the live mirror's real opaque
  region to the renderer instead of forcing it empty, so a rounded card's
  opaque interior takes Pixman's SRC fast path) was implemented, measured
  with the same alternating method, found **not** to reproduce a win
  (within host noise, if anything slightly negative), and reverted rather
  than kept on a hoped-for board result -- recorded in the same evidence
  file rather than silently dropped. Visual regression: existing 38-case
  pixel-oracle/scaled-cache/policy unit tests, `tests/card_rounded_clip_qemu.py`
  (`--cache 0` and `--cache 1`) and all 17 native runtime checks all still
  pass on the changed build; new `tests/test_card_shell_motion_filter_runtime.py`
  confirms both filter modes are actually exercised in one session. System
  closure builds (`nixosConfigurations.k230-coherent-shell...toplevel`).
  This is a Build-stage CPU-cost reduction only; it does not by itself prove
  4.2's tracking-presentation p95 passes (see 4.2d below and `analysis.md`'s
  H1 on commit-path serialization) -- board proof required.
- [ ] 4.2d Coordinator decision, informed by 4.2a-c and 4.2e above: accept
  the measured, understood overrun-rate cost as (b) (with the distinction
  from `analysis.md`'s decision table stated explicitly -- an overrun rate,
  not a panel limit), authorize a separately-gated kernel change to attempt
  commit pipelining as (c) pricing in the boot-panic risk above, or -- newly
  possible given 4.2e's large host-side Build-cost reduction -- re-run the
  board capture first to see whether the CPU-side win alone now closes the
  gap before deciding on either (b) or a kernel change. Verify with
  `python3 tools/card-shell-benchmark.py --board --output
  docs/evidence/card-shell/pixman.json` plus
  `docs/evidence/card-shell/frame-budget/board-commands.md`'s
  `tools/measure-panel-refresh.sh` drag capture, against the `perf/deck-draw-less`
  build (a new variable, unlike the ten-plus prior identical-result rounds
  the parent's tasks.md lists).

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
