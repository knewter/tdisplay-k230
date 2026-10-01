# the-keyboard-follows-touch-gestures: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> **Render-ahead / bottom flicker** <-- this is done it's been fixed for ages. **App drawer redesign** <-- this seems fine idk why we would focus on perf for it right now versus find slow sutff to spend energy on when it arises. **Keyboard gestures** <-- these seem fine to me. **Coherent shell behavior** <-- this seems fine just close them out ask me for any details you need but trust me and no need for captures if they're hard at all

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-keyboard-closeout`; branch `closeout/accepted-keyboard`; base `42fb9f55fb7eb08feab76dff0016a0f64a3a4571`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **3.2:** Record operator acceptance of keyboard gestures (2026-10-01), together with the earlier standalone Foot keyboard confirmation. The operator waives additional capture; this is physical operator feedback, not a new recorded show/hold/reverse sequence.
- **3.3:** Transfer the unperformed installed-board visibility/gesture budget measurement intact to `the-shell-profiles-reported-interaction-jank` task 3.1, on the operator-authorized performance deferral. This checks scope transfer, not a measured budget pass.
- **4.1:** Retain already-published keyboard feature media and add the committed operator report to the dashboard evidence; validate the working-tree work snapshot. Additional real-touch video is waived, not fabricated.
- **4.2:** Reconcile accepted functional scope and the explicit measurement successor; validate and archive/sync runtime/shell through the OpenSpec CLI. Source and prior media are already landed; the closeout is pushed and its publication checked separately.

## Prior committed evidence

- `docs/evidence/keyboard-gestures/installed-preview/README.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
3.2 Run a documented real-finger show, type, slow hide/hold/reverse, committed hide and app-navigation sequence. Capture focused feature video with `python3 tools/capture-feature.py keyboard-gestures --duration 15 --provenance real-touch --description "Two-finger show, typing, handle dismissal and reversal"`, record the actual camera and output directory plus camera/native provenance, and keep user acceptance open until explicitly confirmed.
```

```text
3.3 Measure keyboard visibility and gesture workload against the existing shell responsiveness budgets using the installed compositor instrumentation; commit the exact workload/operator invocation and observed results. Do not infer motion quality from static captures.

Proof: exact build and console identity above, committed concrete camera/workload commands and real-glass observations. No routine flash readback is required.
```

```text
4.1 Publish feature media and updated dashboard evidence as it arrives; run `python3 scripts/build_site.py`, push master and inspect exact-revision Pages deployment.
```

```text
4.2 After all source and physical gates pass, run `openspec validate the-keyboard-follows-touch-gestures --strict`, archive/sync the runtime/shell delta, commit and push. Leave incomplete tasks open.

Proof: `python3 scripts/build_site.py` and `openspec validate the-keyboard-follows-touch-gestures --strict`, followed by exact deployed revision inspection.

Installed checkpoint: [native board identity and captures](../../../docs/evidence/keyboard-gestures/installed-preview/README.md). Tasks 2.2 and 3.1 have their named build/identity proof; real-finger and output-change recovery gates stay open; the later native Foot text proof completes task 2.3.
```

