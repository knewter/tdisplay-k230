# the-shell-is-navigable-with-a-mouse: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> launch splash works. mouse nav and hdmi trackpad works. clock works fine don't worry about digging in further i don't think

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-mouse-closeout`; branch `closeout/accepted-mouse`; base `22a867da54a1cc77d95e2772fbdfb270db278fc1`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **3.3:** Record the operator's 2026-10-01 mouse-navigation acceptance. Prior actual-board/headless pointer matrix remains committed. Additional photographs and exhaustive gesture rechecks are waived; this does not claim an individually observed four-finger pinch sequence.
- **4.3:** Record the earlier real-finger acceptance of the edge-tap/Search correction and Home handle, plus current mouse-navigation acceptance. Retain installed-board edge-control evidence. No additional photograph or repeated glass test is required.

Individual four-finger recognition and other unenumerated contact-count cases were not separately reported in this closeout. Their source/routing proof remains, but physical per-case claims stay UNVERIFIED. The operator accepts overall navigation and requests no further digging.

## Prior committed evidence

- `docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-board/README.md`
- `docs/evidence/the-shell-is-navigable-with-a-mouse/edge-controls-host/README.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
3.3 Physical operator acceptance: tap Home in panel-touch mode, click/edge-drag in HDMI trackpad mode and four-finger inward/outward pinch. Record physical observation and photograph. Keep unchecked until actually performed.
```

```text
4.3 Real-finger panel acceptance on that installed correction: app header controls, drawer-search Backspace, Home handle to overview, and the preserved top-down/bottom-up drags. Commit operator observations and physical photograph; keep open until collected.
```

