# Closeout map, 2026-09-30

Audit base: `6306c1d8df787820c1c74e7808be6d853e343b30`, on master.
Evidence class: repository/source audit only; no new board, camera or physical
acceptance is claimed by this document. The uniform HDMI gesture implementation
is already installed; its implementation and publication records remain separate.

There are **45 active changes**, **263 unchecked tasks**, and **no active change
with all tasks checked**. Eight changes have no checked tasks. Nine changes have
only one unchecked task, but the mainline-kernel trial and performance/probe gates
are materially larger than a single feedback item. OpenSpec artifact completion
or a task percentage is not feature acceptance.

## Recommended first batch

These six have all implementation/build tasks checked and one explicit physical
gate. This is a candidate list, not an archive authorization or a fresh claim
that their old evidence satisfies today's installed image.

| Implementation | Done/total | Exact remaining gate | Best next action |
| --- | ---: | --- | --- |
| [RTC warm-reboot support](../../../../openspec/changes/the-clock-survives-a-reboot/tasks.md) | 5/6 | 4.2: A controlled full-power-removal test, with NTP/RTC write-back excluded before the first post-boot read. A warm reboot is already proved. | See [existing proof](../../rtc/mday-mask-fix.md) and the verbatim task below. |
| [Panel render deadline / bottom-band fix](../../../../openspec/changes/the-compositor-renders-ahead-of-scanout/tasks.md) | 4/5 | 1.4: Real-finger bottom-edge switching and overview on the patch-free panel system, with its installed identity and operator report. HDMI does not test DSI scanout. | See [existing proof](../../card-shell/bottom-band-flicker/max-render-time-fix.md) and the verbatim task below. |
| [Home stays hidden behind overview](../../../../openspec/changes/the-overview-hides-the-home-screen/tasks.md) | 11/12 | 5.1: Actual themed overview entry/drag on the panel, native capture plus physical photograph and real input. | See [existing proof](../../card-shell/overview-home-bleed-through/README.md) and the verbatim task below. |
| [Pinned Home and dock](../../../../openspec/changes/the-shell-presents-a-pinned-home-screen/tasks.md) | 19/20 | 8.1: On the AMOLED in both dark and light themes: page swipe; long-press pin/unpin/rearrange; dock launch; launch-versus-focus. Record a focused capture. | See [existing proof](../../home-screen/navigation/README.md) and the verbatim task below. |
| [Pointer navigation](../../../../openspec/changes/the-shell-is-navigable-with-a-mouse/tasks.md) | 7/8 | 3.3: Panel-touch Home, HDMI glass pointer clicks/edge drags, and four-finger inward/outward recognition. Photo/operator observation; injected IPC is insufficient. | See [existing proof](../../the-shell-is-navigable-with-a-mouse/README.md) and the verbatim task below. |
| [Themed Nautilus and Portfolio](../../../../openspec/changes/the-handheld-has-a-themed-files-app/tasks.md) | 20/21 | 5.3: Launch both real apps on the panel; record launch time, RSS, scroll behavior and resolved icons. Existing host GTK captures are insufficient. | See [existing proof](../../files-app/README.md) and the verbatim task below. |

## Two honest routes to closure

**Verification route:** keep the original six proposals open, perform each
named physical task, commit its evidence, reconcile its spec grounding, validate,
sync and archive it. The short panel session below covers several tasks, but
cannot stand in for both-mode pointer acceptance or the power-off RTC test.

**Proposed scope split (requires user authorization):** create one explicit
successor, `the-landed-shell-passes-physical-acceptance`, with six separately
identified task groups copied from the originals below. Preserve every scenario,
command, photograph, mode/theme combination, measurement, source identity and
UNVERIFIED marker. Then narrow each original to its completed implementation,
record the transferred task ownership, validate/sync/archive each original in
its own branch/worktree, and publish the resulting board. Do not mark transferred
physical tests as passed. Archiving an implementation must not make its still-
unverified user experience appear physically accepted on the public site.

This would reduce the active queue from **45 to 40** (six archives, one successor),
while all six physical gates remain visible in one acceptance queue. The successor
must land on master before any original is closed. This document proposes that
route; no requirement has been moved or original archived yet.

AGENTS.md requires explicit authorization for this ownership change:
> if the user authorizes a scope split, preserve every remaining requirement and task in an explicit successor proposal before closing the finished part.

There is no proposed scope split for unfinished theme consumers, performance
budgets, kernel/SMP work or new UI features.

## Easy operator sessions

1. **Normal panel, one reserved session.** First pin the installed system and
   patch-free kernel, confirm this is the AMOLED rather than the HDMI monitor,
   and arm the camera. Open a real app, perform bottom-edge switching and
   overview entry/drag, then confirm no Home bleed and no bottom-band flicker.
   These are distinct results: record each against its own gate. Then test Home
   swipe/pin/unpin/rearrange/dock/focus in dark and light themes. Launch each Files
   entry, scroll it, inspect icons; the coordinator measures launch time/RSS.
2. **HDMI/panel pointer session.** Complete the panel Home tap and HDMI click/edge
   drag and four-finger inward/outward pinch. Two-finger shell translation already
   has strict injected-board proof, but physical recognition and feel still need
   their own observations. Do not ask the operator to re-prove a dispatched IPC.
3. **Separate RTC session.** Capture an RTC value, control synchronization and
   write-back, physically remove main power, wait, then capture the first RTC
   reading before network correction. This is not a reboot test. Restore all
   transient test settings. Keep full-power survival unknown without that proof.

Start each session with the board/serial reservation and an exact system identity.
Use the original task's capture command and retain the difference between native
pixels, optical evidence, physical fingers and an operator report.

## The next batch is actual remaining work

- **Home widgets/folders and fluid paging:** each still needs a paired real-
  compositor QEMU run and physical acceptance. The earlier harness was terminated
  repeatedly; resolve that failure before claiming folder rename, drag-out, dock
  folders, widget placement or cross-page drag are verified.
- **Generic video/card path:** functionality has board evidence, but real-input
  entry/touch timing targets and the existing performance budget remain unresolved.
- **Omarchy theme loading and theme-swap performance:** audit token coverage,
  icons and control states; reconcile removed preview/cancel semantics; re-check
  matched-content traces and the reboot/background workloads. Do not treat the
  existence of a theme picker as full theme compatibility.
- **Keyboard gestures, trackpad and responsive HDMI shell:** group their physical
  acceptance journeys where possible, but retain keyboard workload measurements,
  panel restoration, real four-finger recognition and resolution/density work.
- **Mainline kernel and CPU0/SMP:** keep separate reservations and recoverable boot
  trials. These are substantive hardware bring-up, not quick acceptance checks.

Hold a small implementation set until this queue closes. Eight proposals have no checked tasks; that does not rule out partial research
(such as the interrupted Qt build). No new feature is started by this audit.

## All active proposals at the audit revision

| Change | Checked/total | Classification by task count |
| --- | ---: | --- |
| [the-board-runs-a-mainline-kernel](../../../../openspec/changes/archive/2026-10-06-the-board-runs-a-mainline-kernel/tasks.md) | 24/25 | One remaining task |
| [the-card-shell-has-no-video-special-case](../../../../openspec/changes/the-card-shell-has-no-video-special-case/tasks.md) | 9/10 | One remaining task |
| [the-clock-survives-a-reboot](../../../../openspec/changes/the-clock-survives-a-reboot/tasks.md) | 5/6 | One remaining task |
| [the-compositor-renders-ahead-of-scanout](../../../../openspec/changes/the-compositor-renders-ahead-of-scanout/tasks.md) | 4/5 | One remaining task |
| [the-handheld-has-a-themed-files-app](../../../../openspec/changes/the-handheld-has-a-themed-files-app/tasks.md) | 20/21 | One remaining task |
| [the-overview-hides-the-home-screen](../../../../openspec/changes/the-overview-hides-the-home-screen/tasks.md) | 11/12 | One remaining task |
| [the-shell-has-a-card-composition-plan](../../../../openspec/changes/the-shell-has-a-card-composition-plan/tasks.md) | 10/11 | One remaining task |
| [the-shell-is-navigable-with-a-mouse](../../../../openspec/changes/the-shell-is-navigable-with-a-mouse/tasks.md) | 7/8 | One remaining task |
| [the-shell-presents-a-pinned-home-screen](../../../../openspec/changes/the-shell-presents-a-pinned-home-screen/tasks.md) | 19/20 | One remaining task |
| [the-handheld-configures-wifi-from-settings](../../../../openspec/changes/the-handheld-configures-wifi-from-settings/tasks.md) | 10/12 | Remaining implementation and/or proof |
| [the-home-screen-has-widgets-and-folders](../../../../openspec/changes/the-home-screen-has-widgets-and-folders/tasks.md) | 19/21 | Remaining implementation and/or proof |
| [the-home-screen-pages-fluidly-and-widgets-look-designed](../../../../openspec/changes/the-home-screen-pages-fluidly-and-widgets-look-designed/tasks.md) | 17/19 | Remaining implementation and/or proof |
| [the-launcher-explains-app-actions](../../../../openspec/changes/the-launcher-explains-app-actions/tasks.md) | 2/4 | Remaining implementation and/or proof |
| [launching-an-app-shows-a-splash](../../../../openspec/changes/launching-an-app-shows-a-splash/tasks.md) | 15/18 | Remaining implementation and/or proof |
| [the-card-deck-still-misses-its-frame-budget](../../../../openspec/changes/the-card-deck-still-misses-its-frame-budget/tasks.md) | 5/8 | Remaining implementation and/or proof |
| [the-shell-manages-apps-as-cards](../../../../openspec/changes/the-shell-manages-apps-as-cards/tasks.md) | 11/14 | Remaining implementation and/or proof |
| [the-app-drawer-is-redesigned](../../../../openspec/changes/the-app-drawer-is-redesigned/tasks.md) | 24/28 | Remaining implementation and/or proof |
| [the-keyboard-follows-touch-gestures](../../../../openspec/changes/the-keyboard-follows-touch-gestures/tasks.md) | 7/11 | Remaining implementation and/or proof |
| [the-shell-behaves-as-one-coherent-system](../../../../openspec/changes/the-shell-behaves-as-one-coherent-system/tasks.md) | 16/20 | Remaining implementation and/or proof |
| [the-shell-makes-recovery-routes-legible](../../../../openspec/changes/the-shell-makes-recovery-routes-legible/tasks.md) | 0/4 | No checked tasks |
| [the-small-core-runs-a-recoverable-heartbeat](../../../../openspec/changes/the-small-core-runs-a-recoverable-heartbeat/tasks.md) | 5/9 | Remaining implementation and/or proof |
| [the-system-runs-on-both-cores](../../../../openspec/changes/the-system-runs-on-both-cores/tasks.md) | 8/12 | Remaining implementation and/or proof |
| [the-handheld-pairs-over-a-usb-bluetooth-dongle](../../../../openspec/changes/the-handheld-pairs-over-a-usb-bluetooth-dongle/tasks.md) | 0/5 | No checked tasks |
| [the-shell-adapts-to-output-resolution](../../../../openspec/changes/the-shell-adapts-to-output-resolution/tasks.md) | 16/22 | Remaining implementation and/or proof |
| [the-shell-gets-side-edge-back-and-motion-trace](../../../../openspec/changes/the-shell-gets-side-edge-back-and-motion-trace/tasks.md) | 1/7 | Remaining implementation and/or proof |
| [the-system-enables-proven-c908-extensions](../../../../openspec/changes/the-system-enables-proven-c908-extensions/tasks.md) | 5/11 | Remaining implementation and/or proof |
| [the-power-key-controls-the-display-and-power-menu](../../../../openspec/changes/the-power-key-controls-the-display-and-power-menu/tasks.md) | 4/11 | Remaining implementation and/or proof |
| [the-screen-lights-before-linux](../../../../openspec/changes/the-screen-lights-before-linux/tasks.md) | 20/27 | Remaining implementation and/or proof |
| [the-touchscreen-becomes-an-hdmi-trackpad](../../../../openspec/changes/the-touchscreen-becomes-an-hdmi-trackpad/tasks.md) | 26/33 | Remaining implementation and/or proof |
| [the-handheld-controls-volume](../../../../openspec/changes/the-handheld-controls-volume/tasks.md) | 19/27 | Remaining implementation and/or proof |
| [the-settings-and-notifications-surfaces-are-themed](../../../../openspec/changes/the-settings-and-notifications-surfaces-are-themed/tasks.md) | 0/8 | No checked tasks |
| [the-shell-loads-omarchy-themes](../../../../openspec/changes/the-shell-loads-omarchy-themes/tasks.md) | 17/25 | Remaining implementation and/or proof |
| [the-shell-trials-vglite-composition](../../../../openspec/changes/the-shell-trials-vglite-composition/tasks.md) | 5/13 | Remaining implementation and/or proof |
| [the-handheld-gets-a-design-and-ux-review](../../../../openspec/changes/the-handheld-gets-a-design-and-ux-review/tasks.md) | 0/9 | No checked tasks |
| [the-handheld-plays-through-its-speaker](../../../../openspec/changes/the-handheld-plays-through-its-speaker/tasks.md) | 8/17 | Remaining implementation and/or proof |
| [the-portrait-hdmi-shell-keeps-up-with-touch](../../../../openspec/changes/the-portrait-hdmi-shell-keeps-up-with-touch/tasks.md) | 3/12 | Remaining implementation and/or proof |
| [the-boot-shows-a-computational-game-of-life](../../../../openspec/changes/the-boot-shows-a-computational-game-of-life/tasks.md) | 0/10 | No checked tasks |
| [characterise-bootrom-usb-recovery](../../../../openspec/changes/characterise-bootrom-usb-recovery/tasks.md) | 0/11 | No checked tasks |
| [the-shell-offers-quick-toggles-and-vision-options](../../../../openspec/changes/the-shell-offers-quick-toggles-and-vision-options/tasks.md) | 1/12 | Remaining implementation and/or proof |
| [the-background-chooser-supports-fill-solid-and-video](../../../../openspec/changes/the-background-chooser-supports-fill-solid-and-video/tasks.md) | 0/12 | No checked tasks |
| [plugging-in-hdmi-moves-the-display](../../../../openspec/changes/plugging-in-hdmi-moves-the-display/tasks.md) | 8/21 | Remaining implementation and/or proof |
| [the-handheld-evaluates-qtquick-and-quickshell](../../../../openspec/changes/the-handheld-evaluates-qtquick-and-quickshell/tasks.md) | 0/13 | No checked tasks |
| [the-handheld-presents-a-coherent-shell](../../../../openspec/changes/the-handheld-presents-a-coherent-shell/tasks.md) | 22/35 | Remaining implementation and/or proof |
| [the-shell-swaps-themes-without-a-python-stall](../../../../openspec/changes/the-shell-swaps-themes-without-a-python-stall/tasks.md) | 61/74 | Remaining implementation and/or proof |
| [the-small-core-runs-as-a-coprocessor](../../../../openspec/changes/the-small-core-runs-as-a-coprocessor/tasks.md) | 1/15 | Remaining implementation and/or proof |

## Exact gates preserved by the proposed split

These are verbatim task blocks at the audit revision, not rewritten or waived
acceptance criteria. Their linked proposal/spec contracts remain authoritative.

### RTC warm-reboot support: the-clock-survives-a-reboot, task 4.2

- [ ] 4.2 Leave `UNVERIFIED`: whether the RTC survives a full power-off
      (main power removed, not just a reboot) rather than only a warm
      reboot. Requires a documented backing supply or a separate
      power-off-and-wait board test not performed by this change; do not
      tick this task without that specific evidence.

### Panel render deadline / bottom-band fix: the-compositor-renders-ahead-of-scanout, task 1.4

- [ ] 1.4 **Board, real finger.** Operator confirms on a patch-free system
  that bottom-edge app switching and the card overview show no bottom-band
  flicker. Record the report, with the system path, in
  `docs/evidence/card-shell/bottom-band-flicker/` (operator report).

### Home stays hidden behind overview: the-overview-hides-the-home-screen, task 5.1

- [ ] 5.1 Board re-check: repeat the coordinator's original native capture
  (`swaymsg card_shell enter`, a real focused app, the board's actual theme
  and wallpaper configured) on the installed system once this change lands,
  confirming Home no longer bleeds through with a real (not synthetic)
  theme canvas and real finger input. Operator command:
  `./tools/console.py /dev/ttyACM0 --wait=3 "swaymsg card_shell enter"`
  plus a photograph of the panel; requires the board and its serial port
  reserved by one operator, per `AGENTS.md`. Not performed by this task
  (QEMU-only scope, no board/`/dev/ttyACM0` access).

### Pinned Home and dock: the-shell-presents-a-pinned-home-screen, task 8.1

- [ ] 8.1 **Hardware, not claimed by this change.** Real-finger Home page
  swipe, long-press pin/unpin/rearrange, dock taps, and launch-vs-focus,
  photographed on the physical AMOLED in both a dark and a light theme;
  verify on hardware with `python3 tools/capture-feature.py home-screen
  --provenance real-touch --duration 30 --description 'Real-finger Home
  page swipe, pin, rearrange, dock, launch-or-focus' --output-dir
  docs/evidence/home-screen/real-touch`. Left open per the coordinator's
  explicit instruction that this implementation does not touch the board
  or `/dev/ttyACM0`.

### Pointer navigation: the-shell-is-navigable-with-a-mouse, task 3.3

- [ ] 3.3 Physical operator acceptance: tap Home in panel-touch mode, click/edge-drag in HDMI trackpad mode and four-finger inward/outward pinch. Record physical observation and photograph. Keep unchecked until actually performed.

### Themed Nautilus and Portfolio: the-handheld-has-a-themed-files-app, task 5.3

- [ ] 5.3 Board evidence: real launch time, RSS and scroll behavior for both
  candidates on the physical panel, plus confirmation that icons resolve
  correctly with the `GDK_BACKEND=wayland`/`adwaita-icon-theme`/
  `hicolor-icon-theme` fix (task 6.2) applied. **Which entry(ies) to keep
  is no longer blocked on this**: the operator has already decided (task
  6.1) to keep both by default; this task now covers only the physical
  performance/appearance observation itself. Operator command once a
  flashed image exists: launch each "Files (…)" drawer entry and observe; no
  narrow `tools/msh.py`/`console.py` invocation is prescribed here because
  the observation itself (does it come up, how fast, how smooth, do icons
  render) is the point, not a scripted check. UNVERIFIED until performed;
  this change does not claim board behavior.
