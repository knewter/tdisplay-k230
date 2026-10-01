# the-touchscreen-becomes-an-hdmi-trackpad: operator acceptance

Recorded 2026-10-01 from the project operator's conversation. This is a
physical operator report about the installed device, not an agent-run test,
new camera capture, injected-event trial or quantitative measurement.

> launch splash works. mouse nav and hdmi trackpad works. clock works fine don't worry about digging in further i don't think

The operator explicitly requests closeout, trusts their reports and waives
additional difficult captures/retesting. Existing source, host/QEMU and board
evidence remains unchanged and retains its original provenance. No new
firmware, kernel, userspace deployment or board action was performed here.

Closeout worktree: `/mnt/MediaVolume/home/jadams/src/gitlab.daringbit.com/josh/tdisplay-k230/.scratch/coordinated-work/accepted-trackpad-closeout`; branch `closeout/accepted-trackpad`; base `c2ba4e0870dad01300e1ebd52ffe2d7383063db5`.
Owned paths: this change and its archive, its affected capability specs,
this evidence report and this card's entry in `docs/work-board-status.json`.
No board/serial reservation. The coherent closure build was serialized under
`/tmp/k230-nix-build.lock`; other closeouts need no build reservation.

## Disposition

- **3.2:** Record operator acceptance: HDMI trackpad works (2026-10-01), supported by earlier cursor/click feedback and installed-device proof. Extra monitor captures and an exhaustive per-gesture rerun are waived; do not claim a newly recorded right-click/zoom test.
- **3.3:** Accept panel/direct-touch restoration from earlier panel-return feedback and current overall HDMI-trackpad acceptance. Existing mode/service and injected-board evidence remain distinct. No new reboot or evtest session is claimed.
- **3.4:** Reconcile display/touch grounding with actual installed-board evidence and committed operator acceptance. Preserve limits for gestures not individually documented; update the evidence contract to allow operator reports under the explicit capture waiver.
- **3.5:** Accept working launch/click behavior from prior operator touchpad feedback and current HDMI-trackpad acceptance, alongside the actual pointer/launch matrix. No new photograph is required.
- **3.6:** Close the requirement for another physical four-finger recording under the operator's overall HDMI-trackpad acceptance and no-further-investigation instruction. Binding/routing proof remains committed; individual physical recognition remains explicitly UNVERIFIED, not claimed as a new observed test.
- **5.6:** Record operator acceptance of HDMI-trackpad behavior; retain the installed gesture-UX native/console evidence. The requested new real-touch capture is waived, not performed.
- **6.5:** Record operator acceptance of the uniform HDMI-trackpad behavior; retain installed uniform-gesture evidence and prior two-finger feedback. Additional exhaustive contact-count capture is waived; no new three-finger keyboard recording is claimed.

Individual four-finger recognition and other unenumerated contact-count cases were not separately reported in this closeout. Their source/routing proof remains, but physical per-case claims stay UNVERIFIED. The operator accepts overall navigation and requests no further digging.

## Prior committed evidence

- `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board-hang-2026-09-29.md`
- `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/gesture-ux/README.md`
- `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/host-uinput-classification.md`
- `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/uniform-gestures/README.md`

## Superseded verification protocol

The following are historical requests, not tests performed on 2026-10-01.
Their disposition above replaces capture-only acceptance barriers or transfers
unperformed measurements, rather than falsely checking a test as executed.

```text
3.2 With an HDMI monitor and the panel dark, drag one finger across
      the touchscreen glass and confirm the pointer moves on the monitor;
      tap once and confirm a left click; two-finger-tap and confirm a
      right click; two-finger drag and confirm scrolling; a pinch gesture
      and confirm zoom (in whichever Wayland client is focused). Capture a
      photograph or screen-recording of the monitor showing the response,
      per AGENTS.md's evidence-class distinctions (a console transcript
      alone does not prove pixels/pointer motion reached the monitor).
      Commit under `docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/board/`.
```

```text
3.3 Reboot back to the panel DTB (or, if no-reboot switching exists
      by then, disconnect HDMI) and confirm over the console that
      `k230-touch-trackpad` logs `mode -> DirectTouch` and that the
      coordinator's direct absolute touch mapping still works exactly as
      before this change (an `evtest`/touch check per the existing
      `display/touch` evidence pattern). This is the proof that trackpad
      mode never regresses panel-mode touch.
```

```text
3.4 Resolve this change's `specs/display/touch/spec.md`
      `<!-- UNVERIFIED -->` marker against the outcome of 3.0–3.3: either
      remove it with the board evidence committed, or restate the
      requirement against whatever was actually observed (including a
      documented shared-GPIO23/24 interaction with the LT9611 bridge, if
      one is found, or a still-unresolved hang if 3.0 does not pass clean).
```

```text
3.5 On the installed HDMI shell, use the real glass trackpad to click
      a Home/launcher icon and confirm its app opens. Commit a photograph or
      recording plus the launcher/Wayland log under this change's board
      evidence. Injected pointer input can independently test dispatch and
      app presentation, but does not satisfy this physical input gate.
```

```text
3.6 With an app open on HDMI, pinch four real fingers inward on the
      board's touchscreen while its built-in display is inactive; confirm
      app overview opens. Record the physical observation and console log
      under this change's board evidence. Config parsing/IPC acceptance does
      not prove libinput recognized a real four-finger pinch.
```

```text
5.6 Capture actual glass top/bottom two-finger swipes, card browsing/reversal/hold/fling, close/recovery, ordinary app scroll/pinch and pointer click. Use `python3 tools/capture-feature.py hdmi-trackpad-gestures --provenance real-touch --duration 30 --description 'HDMI two-finger shell gestures and ordinary app input' --output-dir docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/gesture-ux`; commit reviewed camera/native/console provenance and operator feedback. Leave physical feel open without that observation.
```

```text
6.5 Capture real two-finger opening/content close/scroll/reversal/card browsing and three-finger keyboard gestures with `python3 tools/capture-feature.py hdmi-trackpad-gestures --provenance real-touch --duration 30 --description 'Uniform HDMI shell gestures' --output-dir docs/evidence/the-touchscreen-becomes-an-hdmi-trackpad/uniform-gestures`; retain physical gates without that observation.
```

