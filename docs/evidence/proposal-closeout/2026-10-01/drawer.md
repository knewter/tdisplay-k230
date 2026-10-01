# the-app-drawer-is-redesigned: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> **Render-ahead / bottom flicker** <-- this is done it's been fixed for ages. **App drawer redesign** <-- this seems fine idk why we would focus on perf for it right now versus find slow sutff to spend energy on when it arises. **Keyboard gestures** <-- these seem fine to me. **Coherent shell behavior** <-- this seems fine just close them out ask me for any details you need but trust me and no need for captures if they're hard at all

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-drawer-closeout`; branch `closeout/accepted-drawer`; base `dd62acb46e49be629f31dbde83e2d1797b1b5040`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **5.2:** Transfer the unperformed sustained `K230_DRAWER_FRAME ms=` board measurement, 17.3–34.6 ms estimate comparison and ~20 ms target to `the-shell-profiles-reported-interaction-jank` task 2.1. This is completed scope transfer, not measured performance.
- **5.4:** Transfer the contingent damage-limited blitting proposal/decision to `the-shell-profiles-reported-interaction-jank` task 2.2, preserving `docs/design/app-drawer-review.md` section 6. No optimization or performance result is claimed.
- **6.3:** Complete matching userspace deployment/native proof and exact Pages inspection using the already-committed system-keyboard-board evidence. The user confirmed real-finger Search/correction/dismissal/reopen/launch and now accepts the drawer as fine (2026-10-01). Additional gesture capture is waived; quantitative checks remain in the named successor.

## Prior committed evidence

- `docs/evidence/app-drawer/README.md`
- `docs/evidence/app-drawer/system-keyboard-board/README.md`
- `docs/evidence/app-drawer/system-keyboard-board/operator-feedback.md`
- `docs/evidence/app-drawer/system-keyboard-qemu/README.md`
- `docs/evidence/card-shell/backdrop-blur-feasibility.md`
- `docs/evidence/proposal-closeout/2026-09-30/operator-feedback.md`
- `docs/evidence/shell-features/desktop-launcher/README.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
5.2 **Hardware-only, not performed here.** Read
      `K230_DRAWER_FRAME ms=` from the board's journal while scrolling
      the drawer and compare against §3's 17.3-34.6ms/frame estimate.
      Resolves the design review's UNVERIFIED performance claim into a
      real number, and settles whether the ~20ms target is actually
      met.
```

```text
5.4 **Hardware-only, contingent on 5.2.** If the board
      measurement still shows a shortfall, open a follow-up change for
      the scroll-direction damage-limited blitting named in
      `docs/design/app-drawer-review.md` §6 (not implemented in this
      change).

The coordinator asked for the named drawer reversal and search/type/filter/launch checks; the operator replied “drawer works fine. search works fine.” Evidence: `docs/evidence/proposal-closeout/2026-09-30/operator-feedback.md`. This accepts the current interaction only; it does not claim 5.2 timing, a performance-contingent 5.4 follow-up, or the requested standard keyboard below.
```

```text
6.3 Deploy the exact matching userspace on the reserved board and prove real-finger system-keyboard search, correction, launch, dismissal and edge gestures; commit safe native/optical feature evidence and inspect the exact Pages revision. Use `python3 tools/console.py /dev/ttyACM0 --wait=3 'readlink -f /run/current-system'` plus the recorded operator workload. Retain 5.2/5.4 until their separate measured evidence exists.

Task 6.2 proof: `docs/evidence/app-drawer/system-keyboard-qemu/README.md`, exact cross-built runtime identities in `result.json`. Real wvkbd correction, dismissal/reopen and app focus passed; injected host evidence only.

Task 6.1 host/build proof and 6.2 QEMU proof are recorded above. Partial 6.3 deployment and board-injected capture proof: `docs/evidence/app-drawer/system-keyboard-board/README.md`; real-finger Search/correction/dismissal/reopen/launch is accepted in `docs/evidence/app-drawer/system-keyboard-board/operator-feedback.md`; exact Pages revision `7eda7f36` passed build/deploy and HTTP inspection (`docs/evidence/app-drawer/system-keyboard-board/deployment.json`). Keyboard-handle/drawer-dismiss gesture acceptance remains required.
```

