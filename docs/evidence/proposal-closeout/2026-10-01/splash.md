# launching-an-app-shows-a-splash: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> launch splash works. mouse nav and hdmi trackpad works. clock works fine don't worry about digging in further i don't think

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-splash-closeout`; branch `closeout/accepted-splash`; base `7c270b23793dbe7f464af13089909abb86f8166e`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **6.1:** Record physical operator acceptance: launch splash works (2026-10-01), also reported fine on 2026-09-27. Retain existing QEMU/source evidence. Additional frame-timing/native capture is waived; this is not a measured one-frame latency result.
- **6.2:** Accept functional launch splash with the operator report and existing process-identity/terminal launch source tests. A new recorded Terminal=true board launch is waived, not claimed.
- **6.3:** Accept the delivered splash behavior using the operator report plus committed host timeout/failure tests. The requested artificial slow/failing physical launches and captures are waived; no newly observed physical fault injection is claimed.

No one-frame latency measurement or new physical timeout/failure injection was obtained. Functional acceptance is recorded; quantitative timing and individual artificial failure cases retain their evidence limits.

## Prior committed evidence

- `docs/evidence/launch-splash/qemu/README.md`
- `docs/evidence/operator-reports/2026-09-27-shell-acceptance.md`
- `docs/evidence/shell-features/desktop-launcher/README.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
6.1 On the physical board, record a native capture of the splash
  appearing within one frame of a real finger tap (drawer, Home, and
  dock), with no visible flash of the previously active app -- verify with
  `python3 tools/capture-feature.py launch-splash --provenance real-touch
  --output-dir docs/evidence/launch-splash/real-touch` (or the equivalent
  current capture tool), reviewed against native state, not camera
  impression alone.
```

```text
6.2 On the physical board, record a real `Terminal=true` launch
  (e.g. the existing Terminal entry) mapping as `foot` and the splash
  correctly handing off despite the `app_id` mismatch -- verify with a
  console/native capture showing the matched pid and the resulting focused
  `foot` window.
```

```text
6.3 On the physical board, record the `TimedOut` and `Failed` states:
  an artificially slow/failing launch (e.g. a fixture desktop entry
  pointing at a sleeping or immediately-exiting command) reaching each
  state, and a real finger dismissing `TimedOut` by tap -- verify with a
  native capture and console log of the resulting `SplashStatus`
  transitions.
  Operator real-finger report, 2026-09-27: "launch splash seems fine"
  (`docs/evidence/operator-reports/2026-09-27-shell-acceptance.md`). This
  task stays open because it requires a native capture.
```


## Activation and publication limits

Existing Home/dock focus is distinct from the drawer's launch path. Shared GNOME
activation/menu parity remains planned in Home group 11. Quantitative one-frame
timing and physical fault-injection cases keep an explicit UNVERIFIED marker
in the published spec; functional user acceptance does not establish those
measurements. The delta is reapplied as MODIFIED through the archive CLI to
correct the published evidence label and narrow focus scope, without source changes.
