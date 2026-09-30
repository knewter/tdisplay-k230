# Proposal closeout campaign — 2026-09-30

Audited `master` at `647c8d3e`: **45 open changes, 37 with checked tasks,
8 with no checked tasks, and none with every task complete**. Counts describe
the audit baseline, not concurrent agents. No proposal was archived by this
inventory. A high checkbox count does not mean only user feedback remains.

The installed checkpoint is recorded in
[navigation installation](../the-shell-is-navigable-with-a-mouse/installed.json).
It uses HDMI with the built-in display inactive and its glass acting as a
trackpad. HDMI observations do not satisfy explicitly AMOLED-only checks.

## Make feedback easy

Use one small checklist at a time. The coordinator prepares the screen,
records identity, console/native state and required camera evidence, and asks
the operator only to perform the gesture and say what happened. A response
can simply be `all pass`, or a step number and its failure. Never ask the
operator to run the tooling, inspect journals, or repeat an already-grounded
observation without a specific source/configuration change that requires it.

Start on the current HDMI setup:

1. With an app open, pinch four fingers inward on the built-in glass: overview.
2. Click the overview's Home footer: Home, with apps retained.
3. From Home, pinch four fingers inward again: overview.
4. Spread four fingers outward: the centered app opens.

Swiping upward from Home opens the app drawer, not overview. The operator's
question about returning to overview demonstrates a discoverability gap;
record it in the design review rather than treating that question as a
failed pinch test or as acceptance. Ordinary app clicks and pointer routes
already have [18 injected board checks](../the-shell-is-navigable-with-a-mouse/README.md).

This batch supplies portions of navigation task 3.3 and trackpad tasks
3.5/3.6. It does **not** complete panel-touch restoration, ordinary two-finger
scroll/right-click/zoom, edge-drag acceptance, or required photographs.

Then schedule one panel session, with a matched recoverable boot selection,
for these batches. Do not change output or reboot while the operator is
performing the HDMI batch.

| Batch | Operator actions | What the coordinator supplies | Potential closures |
| --- | --- | --- | --- |
| Panel navigation | Open overview, drag/switch cards, tap Home; report bottom-strip flicker or Home showing through the deck. | Installed kernel identity, native captures, photograph/video, correct panel mode. | Render deadline, Home bleed-through; navigation after its HDMI checks also pass. |
| Home | In dark then light theme: page, pin, rearrange/remove, dock launch and focus a running app. | Camera, persistence/focus checks; then separate folder/widget scenarios and unfinished host harness cases. | Pinned Home. Folder/widget proposals need additional cases, not automatic closure. |
| Apps and keyboard | Search/filter an app; reverse drawer scroll; show/type/slow-hide/reverse the keyboard; launch both Files entries and scroll them. | Frame timing, Files startup/RSS and icons, keyboard motion budgets, launch timeout/failure fixtures and captures. | Drawer, Files, keyboard, launch splash, subject to their measured gates. |
| Themes and Settings | Drag both picker rows, reverse/hold/release; dark/light/community selection; overlay escape. | Safe captures, attribution and matched profiling, token/icon coverage and reboot tooling where still missing. | Coherent-system A/E slice; individual theme interaction gates. Whole theme proposals still have engineering work. |
| Wi-Fi and audio | Use the normal network setup UI; later confirm headphone output and mute if headphones are available. | Protected credentials, failure/cancel/Forget cases, reboot reconnect checks; sink/node checks and tone setup. | Wi-Fi and volume after every named case; speaker outcome can honestly be “add-on absent.” |

The RTC power-off check is a separate prepared trial: capture the RTC before
power removal and before network time can overwrite its post-boot value.
There is no battery attached. A reset while offline is a useful negative
finding, not proof of clock retention. Reconcile the result against the
actual requirement before archive; preserve unresolved scope explicitly.

## Five changes whose remaining task is physical acceptance

These have no identified remaining source task. They are **candidates**, not
pre-approved archives: the task's exact evidence and spec sync still apply.

| Proposal | Done at baseline | Exact remaining gate |
| --- | --- | --- |
| `the-compositor-renders-ahead-of-scanout` | 4/5 | 1.4: real-finger panel switching/overview, no bottom-band flicker on patch-free kernel; report with installed system path. HDMI-only feedback is insufficient. |
| `the-overview-hides-the-home-screen` | 11/12 | 5.1: actual theme/wallpaper, focused app, real input, native capture and physical photograph without Home bleed-through. |
| `the-shell-is-navigable-with-a-mouse` | 7/8 | 3.3: panel tap, HDMI click/edge drags, real inward/outward four-finger pinch, physical observation and photograph. |
| `the-shell-presents-a-pinned-home-screen` | 19/20 | 8.1: photographed AMOLED dark/light real-finger page/pin/remove/rearrange/dock/launch-versus-focus. |
| `the-shell-has-a-card-composition-plan` | 10/11 | 3.2: continuous real-finger tracking in the separate two-app probe, collection and verified normal-shell restoration. Reserve separately; it stops the normal shell. |

## Seven further candidates needing prepared checks or reconciliation

| Proposal | Done at baseline | What remains |
| --- | --- | --- |
| `launching-an-app-shows-a-splash` | 15/18 | Native/finger launch from drawer/Home/dock, Terminal app-id handoff, timeout dismiss and failed launch states. Informal “seems fine” already exists but does not replace these captures. |
| `the-card-shell-has-no-video-special-case` | 9/10 | Real-finger video and busy non-video entry/ack timing (<400ms/<100ms). Before archive, reconcile the older canonical video-specific close requirement with the new general rule. |
| `the-clock-survives-a-reboot` | 5/6 | Isolated full-power-off RTC test; warm-reboot proof is already committed. No request for a battery. |
| `the-handheld-has-a-themed-files-app` | 20/21 | Physical launch time/RSS, scroll and Wayland icon check for Portfolio and Nautilus. The decision to keep both is already made. |
| `the-keyboard-follows-touch-gestures` | 7/11 | Finger show/type/hide/hold/reverse/navigation, measured motion workload, publish and deliberate archive. |
| `the-launcher-explains-app-actions` | 2/4 | Narrow launcher build and physical curated catalog/failed-launch recovery; verify the legacy launcher's actual session rather than assuming Rust coverage substitutes. |
| `the-shell-behaves-as-one-coherent-system` | 16/20 | A.4 fan-card legibility/momentum and E.4 overlay escape on glass; integrated closure and archive gate. Quick toggles/accessibility already belong to an authorized successor. |

## Twenty-five started changes with genuine engineering or substantial trials

Do not request “does it look OK?” feedback as if that could close these.

| Proposal | Done at baseline | Next concrete work |
| --- | --- | --- |
| `plugging-in-hdmi-moves-the-display` | 8/21 | Settings-controlled recoverable DTB switch, actual hotplug feasibility and panel restoration; reconcile implemented responsive-shell scope. Current HDMI output does not prove hotplug. |
| `the-app-drawer-is-redesigned` | 24/28 | Finger reversal and search/keyboard acceptance plus board frame timing; a failed budget requires the explicitly named follow-up. Included in the Apps batch, but not merely an approval question. |
| `the-board-runs-a-mainline-kernel` | 24/25 | A compatible usable root path and recoverable manual candidate boot with panel/touch proof. Image/DTB-only host build is insufficient. |
| `the-card-deck-still-misses-its-frame-budget` | 5/8 | Decide from the measured overrun evidence/new CPU win, then integrated non-fixture QEMU proof. Parent scope split is still unapproved; avoid double ownership. |
| `the-handheld-configures-wifi-from-settings` | 8/12 | Reconcile stale broker/build checks, then real keyboard/scan/connect/failure/cancel/Forget and reboot persistence. |
| `the-handheld-controls-volume` | 19/27 | Prove real codec sink rather than Dummy Output, node identity, sliders/mute, headphone audio and HUD/per-app streams. Conditional keyboard/add-on cases only when hardware exists. |
| `the-handheld-plays-through-its-speaker` | 8/17 | Matching kernel boot, controls/script compatibility and internal audio regression; record add-on presence/absence honestly. |
| `the-handheld-presents-a-coherent-shell` | 22/35 | Missing accessibility aid and named motion fixture/trace coverage, integrated physical journey/motion metrics and persistent boot. Historical partial evidence is not the named complete harness. |
| `the-home-screen-has-widgets-and-folders` | 19/21 | Finish paired compositor harness: rename, drag out, dock folders and widget picker; then actual panel gestures/photo. |
| `the-home-screen-pages-fluidly-and-widgets-look-designed` | 17/19 | Finish paired compositor/widget cross-page harness and photographed real-finger panel/readability/network check; battery only if one is attached. |
| `the-portrait-hdmi-shell-keeps-up-with-touch` | 3/12 | Profile/select rotation path, implement correctness tests, matched performance/input proof and panel restoration. |
| `the-power-key-controls-the-display-and-power-menu` | 4/11 | Identify interceptable switch, prove tap without reset, finish themed power route and distinct confirm/restart/off physical cases. |
| `the-screen-lights-before-linux` | 20/27 | Remaining stage-1/handoff measurements and full boot capture, initrd/console-option implementation. Existing no-dark-frame clips do not close every task. |
| `the-shell-adapts-to-output-resolution` | 16/22 | Cross-link HDMI ownership; actual HDMI configure/photo/hit testing; remaining density scale, Wi-Fi/theme layout and dock design. |
| `the-shell-gets-side-edge-back-and-motion-trace` | 1/7 | Implement qualified side-edge ownership and missing motion trace/test tooling before physical trials. |
| `the-shell-loads-omarchy-themes` | 17/25 | Complete token/control/font coverage, drawer/card icon captures, reconcile tap-to-apply flow, write reboot workload, then physical/theme/background trials. Fill/video and Settings/notification source scope already moved to successors. |
| `the-shell-manages-apps-as-cards` | 11/14 | Outstanding budget decision, integrated non-fixture QEMU smoke and real-finger card capture. Do not silently transfer its budget scope to the staged successor. |
| `the-shell-offers-quick-toggles-and-vision-options` | 1/12 | Shade controls/targets and persistent text-scale/high-contrast across Rust/C renderers, then board proof. |
| `the-shell-swaps-themes-without-a-python-stall` | 61/74 | Unwritten profiling/admission harness, Foot deferral, compositor tracing and several measured board gates. Finger tracking feedback closes only 14.4. |
| `the-shell-trials-vglite-composition` | 5/13 | Renderer format/texture/blend/cache/completion correctness and privileged device access, then GPU/Pixman board comparison. |
| `the-small-core-runs-a-recoverable-heartbeat` | 5/9 | Separate bounded CPU0 execution trial, grounded reserved-memory/cache protocol and Linux coexistence proof. |
| `the-small-core-runs-as-a-coprocessor` | 1/15 | Mailbox/reset/QEMU grounding, echo firmware, remoteproc and repeated physical start/stop/liveness trials. |
| `the-system-enables-proven-c908-extensions` | 5/11 | Additional-extension targeting plus exact candidate emulation, vector/pixel/card/recovery and persistent-boot gates. Existing RVV trials are partial grounding, not blanket completion. |
| `the-system-runs-on-both-cores` | 8/12 | Hart/SBI/interrupt identity and pre-Linux coherency proof before an experimental scalar SMP boot/migration test. Not a configuration checkbox. |
| `the-touchscreen-becomes-an-hdmi-trackpad` | 15/20 | Real pointer/click/right-click/scroll/zoom and four-finger app overview, required media/logs, then panel direct-touch restoration and spec grounding. Current injected click proof is reusable but cannot replace fingers. |

## Eight changes with no checked tasks

No checked tasks does not mean zero source work: the Qt probe packaging and
informal UX critiques exist. These are backlog/research, not ready archives.

| Proposal | Baseline | Next work |
| --- | --- | --- |
| `characterise-bootrom-usb-recovery` | 0/11 | Ground recovery setup and actual pre-U-Boot enumeration; disposable-card write only under its prerequisites. Working UMS is already proven separately. |
| `the-background-chooser-supports-fill-solid-and-video` | 0/12 | Implement fill/solid persistence, user overlay and isolated video lifecycle, then measured board acceptance. Current enum supports crop/fit/center only. |
| `the-boot-shows-a-computational-game-of-life` | 0/10 | Consume splash prerequisite, implement engine/RAM handoff and Linux touch before staged boot proof. |
| `the-handheld-evaluates-qtquick-and-quickshell` | 0/13 | Finish paused Qt probe build, baseline and trial tools; gate Quickshell on the Qt result. |
| `the-handheld-gets-a-design-and-ux-review` | 0/9 | Consolidate existing critiques into named round-2 artifacts, reconcile current journeys and recheck critical findings. Include Home-to-overview discoverability. |
| `the-handheld-pairs-over-a-usb-bluetooth-dongle` | 0/5 | Actual dongle pairing/session proof when hardware is available; BlueZ/kernel preparation was archived separately. |
| `the-settings-and-notifications-surfaces-are-themed` | 0/8 | Cross-surface theme consumer/control/icon mapping and notification motion, host captures and physical/reboot proof. Existing palette colors alone do not satisfy the full scope. |
| `the-shell-makes-recovery-routes-legible` | 0/4 | Implement/test visible recovery explanations and failed-launch presentation before physical readability check. |

## Results landed during this campaign

[Wi-Fi host closeout](../wifi-settings/closeout-host-2026-09-30/README.md)
records successful broker/configuration and integrated Rust/system builds.
Tasks 1.4 and 2.5 are now complete: Wi-Fi advances from 8/12 to **10/12**.
Only physical tasks 3.1 and 3.2 remain. This does not install the newly built
system or prove connection/reboot behavior.

The dashboard now puts the five physical-only candidates in verification
and corrects stale HDMI-trackpad, card, Omarchy and CPU-extension next steps.
Responsive-output and CPU-extension proposals move out of verification
because their remaining source/emulation work is substantive. No completed
capability is claimed from these status edits, and no change is archived
without its required physical proof.

## Reconciliation and archive rules

- Correct stale dashboard “next” steps against the installed checkpoint.
  Mark a whole proposal as verification only when its remaining engineering
  is actually complete. Keep optional investigations visible without starting
  more work just to reduce a checkbox count.
- Share a capture/check across proposals only when it satisfies each named
  scenario and source/output configuration. Cite the shared artifact from
  each task; do not claim that one short navigation run proves every journey.
- Before any archive, complete its tasks, commit required proof, validate
  strictly, compare deltas with canonical specs, sync/archive, merge/push and
  inspect exact-revision deployment. Keep rejected/negative results visible.
- Do not silently drop requirements or create automatic successor proposals.
  Existing authorized splits are honored; further splits/cancellations need
  an explicit user decision. The staged card-budget split remains unapproved.
- Older [system](../../closeout/board-checklist-system.md),
  [shell](../../closeout/board-checklist-shell.md),
  [umbrella](../../closeout/board-checklist-umbrella.md) and
  [theme](../../closeout/board-checklist-themes.md) checklists preserve exact
  commands, but contain historical configurations and flash-first assumptions.
  Resolve current build/boot identities before using them; no routine full
  flash readback or unnecessary fresh flash is part of this campaign.

Audit method: cached `tools/work-status.py`, current OpenSpec task blocks,
existing closeout audits, committed evidence and relevant source inspection.
This inventory used no board/serial reservation and performed no physical
test. New narrow build/task reconciliation is recorded separately under the
owning proposal; this report never substitutes for that evidence.
