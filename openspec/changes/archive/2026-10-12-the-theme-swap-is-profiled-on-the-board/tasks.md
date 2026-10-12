**Withdrawn by the operator, 2026-10-12** (after being offered this change as the next to land): "can we just close it or at least dont give me a before this is all fine i dont want to spend time on it". None of the measurements below was performed for this change, and none is claimed. The tasks stay unticked. No requirement from this change enters `openspec/specs/`; it was archived with `--skip-specs`. The closest existing board figures are the parent's warm apply trials in `docs/evidence/theme-picker/board-session-2026-10-12b/README.md` (tap-up to shown frame 27.5-42.2 ms, injected taps). They were not produced by `tools/analyze-theme-swap-jank.py` and do not stand in for tasks 1.1-2.2.

## 1. Theme-swap jank and tap-to-visible latency (parent 2.3 and 3.4, hardware-only)

- [ ] 1.1 (parent 2.3, verbatim) Run the capture tool on the reserved board across a
  representative swap (a bundled dark theme, a bundled light theme, and one
  community theme with a still background), before and after this change's
  `theme-helper.service` lands on an installed system. Record
  `docs/evidence/omarchy-themes/theme-swap-jank/README.md` with the exact
  `journalctl`/board commands and both reports. **Needs the reserved
  board; not run by this change.**
- [ ] 1.2 (parent 3.4, verbatim) Re-run `tools/analyze-theme-swap-jank.py`'s tap-to-visible metric
  against the board once 3.1b/3.2/3.3 land, and report against the ~100 ms
  target. Needs the reserved board; 3.1b/3.2/3.3 now have source/package
  proof. The named measurement remains unperformed and was deferred by the user.

## 2. Compositor stages and CPU flamegraph (parent 15.2 and 15.3)

- [ ] 2.1 (parent 15.2, verbatim) Extend verified coverage through compositor render/commit/present
  and scheduling; probe perf/kernel support and capture a bounded CPU stack
  profile with matching symbols. Produce a CPU flamegraph separately from
  the span timeline, or document the precise unsupported sampling/unwinding
  gate. Do not label elapsed spans CPU samples.
- [ ] 2.2 (parent 15.3, verbatim) On the reserved board, capture matching picker runs with tracing
  disabled/enabled and sampling separately. Publish reviewed timeline,
  frame-stall report and supported flamegraphs with runtime identities,
  commands, coverage gaps and observer cost. Use the same tools for at least
  one other interaction; host tests alone leave this physical gate open.

## 3. Review and publish

- [ ] 3.1 Validate with `openspec validate the-theme-swap-is-profiled-on-the-board --strict`,
  commit the reviewed reports, push and inspect the matching CI/Pages run.
  Archive only when every measurement above, or its documented unsupported
  gate, is committed.
