# the-compositor-renders-ahead-of-scanout: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> **Render-ahead / bottom flicker** <-- this is done it's been fixed for ages. **App drawer redesign** <-- this seems fine idk why we would focus on perf for it right now versus find slow sutff to spend energy on when it arises. **Keyboard gestures** <-- these seem fine to me. **Coherent shell behavior** <-- this seems fine just close them out ask me for any details you need but trust me and no need for captures if they're hard at all

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-flicker-closeout`; branch `closeout/accepted-flicker`; base `792098bc77e4c6336496f07a5550b93f9a221a8b`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **1.4:** Accept the operator's 2026-10-01 report that render-ahead/bottom flicker has been fixed for ages. Commit the report alongside the prior patch-free board proof. No new capture or kernel test is claimed.

The earlier patch-free board identity and camera proof is recorded in `docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`. Current report is continued user acceptance, not a fresh kernel identification or boot test.

## Prior committed evidence

- `docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md`
- `docs/evidence/card-shell/bottom-band-flicker/max-render-time-fix.md`
- `docs/evidence/dsi-burst-headroom.md`
- `docs/evidence/flicker-after-headroom-revert.md`
- `docs/evidence/panel-lit.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
1.4 **Board, real finger.** Operator confirms on a patch-free system
  that bottom-edge app switching and the card overview show no bottom-band
  flicker. Record the report, with the system path, in
  `docs/evidence/card-shell/bottom-band-flicker/` (operator report).
```

