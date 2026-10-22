## 1. Preserve deferred scope (planning; no hardware claim)

- [x] 1.1 Record the reported landscape panel notification-shade pull workload and installed system/Rust/compositor identities in `docs/evidence/interaction-jank/notification-shade/README.md`. Hardware proof under the board reservation: protected-SSH Python current-system/profile/process/hash/output queries and the exact installed-client capture commands in that report, replayed with `python3 docs/evidence/interaction-jank/notification-shade/analyze.py.txt docs/evidence/interaction-jank/notification-shade/trial-f` (and `trial-g`). SSH follows the operator's explicit preference; no UART or physical performance acceptance is claimed. The settings-priority comparison diagnoses a contributor and does not ship a fix. Do not start unrelated measurements solely to reconfirm accepted UX.

## 2. Drawer measurement (parent 5.2 and 5.4, hardware-only)

- [x] 2.1 While scrolling on the installed board, read `K230_DRAWER_FRAME ms=` with `python3 tools/console.py /dev/ttyACM0 --wait=3 'journalctl -u shell-ui --since "2 minutes ago" --no-pager | rg K230_DRAWER_FRAME'`; commit the sustained workload and samples, compare the 17.3–34.6 ms estimate and ~20 ms target. This is render-cost measurement, not inferred presentation timing.
  Done 2026-10-22 on installed system `8xkkpma4…` (landscape, 12 ms
  allowance, one CPU, 19 apps), with injected native touch at the 8.14 ms
  real-finger rate. The same `journalctl -u shell-ui` read was made over SSH
  (the operator's preference) instead of the UART `console.py` wrapper.
  Three 60 s runs give contact `K230_DRAWER_FRAME` medians of 38.9, 39.5
  and 39.1 ms, with p95 53.4/53.4/52.9 ms. All 216 samples exceed both the
  ~20 ms target and the 34.6 ms top of the estimate. Presented frame rate
  during contact is 8.3 frames per second. A traced run (one `shell-ui`
  restart with the opt-in recorder) shows a full `scene_rebuild` on every
  scroll frame. No real glass or camera was used. A busy-waiting first
  injector (run1) and a trace-permission failure (run5) are preserved, and
  their data is not used:
  `docs/evidence/interaction-jank/drawer-scroll/README.md`.
- [x] 2.2 If 2.1 shows a relevant shortfall, propose the scroll-direction damage-limited blitting follow-up in `docs/design/app-drawer-review.md` section 6; otherwise record why it is unnecessary. Proof: the recorded measured decision and `openspec validate --all --strict`. This preserves parent 5.4 without claiming an optimization already happened.
  Done 2026-10-22: the shortfall is relevant. `docs/design/app-drawer-review.md`
  §6 now records the measurement and proposes a two-part follow-up, in order
  of measured cost: stop the per-scroll full scene rebuild (a cached chrome
  layer plus a grid-slice copy, then scroll-direction blitting if still
  needed), and bound per-touch-event work and logging. Nothing has been
  implemented, and no optimization is claimed.

## 3. Keyboard measurement (parent 3.3, hardware-only)

- [x] 3.1 Measure keyboard visibility and gesture workload against existing shell responsiveness budgets using installed compositor instrumentation. Commit exact show/type/hold/reverse/hide workload, concrete instrumentation invocation, identities and observed results under `docs/evidence/interaction-jank/`. Use `python3 tools/console.py /dev/ttyACM0 --wait=3` for the documented installed probe; static images cannot establish timing. Keep open until actual measurements exist.
  Done 2026-10-22 with a measured miss. Two 8-cycle runs used injected
  native touch at the real-finger rate on installed `8xkkpma4…` (landscape,
  12 ms allowance, one CPU). The installed compositor benchmark (`card_shell
  benchmark injected`) logged presentation and repaint timing for every frame.
  The workload was show, type, hold and reverse, and hide. Presented
  intervals: grip drag and hide median 38.3 ms (p95 38.3–57.5 ms), show
  swipe median 76.7 ms (p95 172 ms). All miss the 33.334 ms card frame
  budget. Render wall time is 21–42 ms against the 12 ms allowance. The show
  motion repaints the full output, and every keyboard frame rearranges the
  workspace. Sway runs with `-d` (about 90 DEBUG journal lines per second).
  Per-input latency is not available for keyboard motion. The functional
  probe and its captures were taken via SSH; no real glass or camera was
  used, and nothing was optimized or waived:
  `docs/evidence/interaction-jank/keyboard/README.md`.

## 4. Ordinary-card measurement (parent 5.1, hardware-only)

- [ ] 4.1 Measure entry-animation duration and touch acknowledgement with a live video and a separate busy non-video app on the installed board. Preserve the sub-400ms entry and sub-100ms touch-ack targets. Use real contact or a persistent uinput-holding injector rather than per-sample `evemu-event` process spawns; record concrete instrumentation command, exact identities and samples under `docs/evidence/interaction-jank/`. Existing qualitative acceptance is not measured performance. Keep both targets UNVERIFIED until actual samples establish them.

## 5. Review and publish

- [ ] 5.1 Validate `openspec validate the-shell-profiles-reported-interaction-jank --strict`, commit measured results/decision, push and inspect matching CI/Pages; archive only once performed measurements and conditional disposition are committed. Parent UX acceptance is not this proposal's performance proof.
