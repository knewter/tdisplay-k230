# the-clock-survives-a-reboot: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> launch splash works. mouse nav and hdmi trackpad works. clock works fine don't worry about digging in further i don't think

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-clock-closeout`; branch `closeout/accepted-clock`; base `b06639f7f325b1dd8c73d3712b6589fd7b4a5611`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **4.2:** Preserve full-power-off retention as UNVERIFIED, as the proposal's explicit non-goal. Existing RTC/reboot board proof and the operator's 2026-10-01 clock acceptance close the warm-reboot scope; no power-off-and-wait test is claimed or required for this change.

Warm-reboot/RTC proof: `docs/evidence/rtc/mday-mask-fix.md`. Full main-power-removal retention remains UNVERIFIED and was always an explicit non-goal. The latest report does not distinguish RTC retention from network resynchronization.

## Prior committed evidence

- `docs/evidence/backlight-bluetooth-rtc-board-test-plan.md`
- `docs/evidence/rtc/mday-mask-fix.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
4.2 Leave `UNVERIFIED`: whether the RTC survives a full power-off
      (main power removed, not just a reboot) rather than only a warm
      reboot. Requires a documented backing supply or a separate
      power-off-and-wait board test not performed by this change; do not
      tick this task without that specific evidence.
```

