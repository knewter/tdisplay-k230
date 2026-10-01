## 1. Preserve deferred scope (planning; no hardware claim)

- [ ] 1.1 When a slow interaction is reported, record route/workload and installed system/Rust/compositor identities under `docs/evidence/interaction-jank/`. Proof: the named report and `python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system'` under the board reservation. Do not start solely to reconfirm accepted UX.

## 2. Drawer measurement (parent 5.2 and 5.4, hardware-only)

- [ ] 2.1 While scrolling on the installed board, read `K230_DRAWER_FRAME ms=` with `python3 tools/console.py /dev/ttyACM0 --wait=3 'journalctl -u shell-ui --since "2 minutes ago" --no-pager | rg K230_DRAWER_FRAME'`; commit the sustained workload and samples, compare the 17.3–34.6 ms estimate and ~20 ms target. This is render-cost measurement, not inferred presentation timing.
- [ ] 2.2 If 2.1 shows a relevant shortfall, propose the scroll-direction damage-limited blitting follow-up in `docs/design/app-drawer-review.md` section 6; otherwise record why it is unnecessary. Proof: the recorded measured decision and `openspec validate --all --strict`. This preserves parent 5.4 without claiming an optimization already happened.

## 3. Keyboard measurement (parent 3.3, hardware-only)

- [ ] 3.1 Measure keyboard visibility and gesture workload against existing shell responsiveness budgets using installed compositor instrumentation. Commit exact show/type/hold/reverse/hide workload, concrete instrumentation invocation, identities and observed results under `docs/evidence/interaction-jank/`. Use `python3 tools/console.py /dev/ttyACM0 --wait=3` for the documented installed probe; static images cannot establish timing. Keep open until actual measurements exist.

## 4. Ordinary-card measurement (parent 5.1, hardware-only)

- [ ] 4.1 Measure entry-animation duration and touch acknowledgement with a live video and a separate busy non-video app on the installed board. Preserve the sub-400ms entry and sub-100ms touch-ack targets. Use real contact or a persistent uinput-holding injector rather than per-sample `evemu-event` process spawns; record concrete instrumentation command, exact identities and samples under `docs/evidence/interaction-jank/`. Existing qualitative acceptance is not measured performance. Keep both targets UNVERIFIED until actual samples establish them.

## 5. Review and publish

- [ ] 5.1 Validate `openspec validate the-shell-profiles-reported-interaction-jank --strict`, commit measured results/decision, push and inspect matching CI/Pages; archive only once performed measurements and conditional disposition are committed. Parent UX acceptance is not this proposal's performance proof.
