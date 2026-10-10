## Why

A person can launch apps, but the current permanent top bar and Back/Home footers make the 568×1232 touch screen feel like a button menu. The intended handheld uses a live card deck as Home, an installed-app drawer rising from it, and a notification shade descending from the top. Those surfaces need one direct-touch and motion contract before their implementations meet.

## Current accepted scope — 2026-10-10

The production Rust shell is implemented and installed in the daily mainline
system; exact acceptance, source/bundle/runtime identity, ordinary boot and
limits are committed in `docs/evidence/coherent-shell/operator-closeout-2026-10-10/README.md`.
The operator explicitly waived further camera, per-case physical and comparative
probe evidence. Numerical motion measurement remains deferred to the existing
`the-shell-gets-side-edge-back-and-motion-trace` successor, which also owns
unimplemented side-edge Back and general at-down arbitration. These are not
implemented features of this archive. Existing host/QEMU/native/operator
results retain their evidence classes; missing quantitative and individual-case
observations remain UNVERIFIED rather than being invented for closeout.

The accepted navigation is app → Overview → pinned Home → All apps, per
`runtime/home-screen`’s landed gesture topology. This supersedes the historical
deck-as-Home/direct-deck-to-drawer wording wherever it remains below.
Acceptance and rollback retention replace the old capture-only default-promotion
prerequisites; no new probe benchmark or six-surface dark/light trial is claimed.

## What Changes

- Polish the implemented Home, drawer, Settings, shade and theme picker with exposed app artwork, restrained surfaces, consistent type and faithful authored Omarchy colors/brushes. Remove routine icon/row/frame borders while retaining selected/focused and safety affordances; preserve existing targets and gesture mapping. Record before/after host renders separately from real-glass proof.
- Define an original, Palm/HP phone webOS-inspired visual and motion language for shell, live-card overview, desktop-entry launcher, settings, and notifications. The accompanying SVGs are review mockups, not running UI.
- Make a bottom-edge swipe shrink the current app into Overview; a new bottom-area upward gesture reveals pinned Home, and a new upward gesture from Home reveals the installed-app drawer. Use horizontal card swipes, tap expand, recoverable upward throw-close, kinetic list scroll, and cancellable long press as normal interaction.
- Extend the bottom app gesture to two axes: drag up then sideways without lifting to choose an adjacent running app, or swipe horizontally from the bottom-center gesture region for a direct app switch. Preserve one-to-one finger tracking, stable deck order, reversible cancellation, and focus only after release. Pure upward release still reaches Home; no hold-to-enter mode or second home grid is added.
- Open a notification shade with a top-edge downward gesture; place truthful Settings entry inside it. Bottom-edge escape and explicit close controls dismiss shell surfaces; qualified side-edge Back and general touch arbitration remain in the authorized successor. The final shell has no permanent navigation rail or Back/Home footer.
- Coordinate app→card, deck selection, app launch/return, launcher, notification, and settings movement as one scene with stable spatial direction, scale, order, and focus. Build this on the selected Sway/wlroots composition boundary if it meets measured limits; do not assume a new compositor.
- Give every accepted touch an immediate visible response. No vibration work is planned on the current board because no actuator/control path is established.
- Give settings truthful controls for capabilities the system can read or change, with unavailable states and explicit action feedback. No battery status is shown or promised.
- Add notification preview, history, dismissal, action, privacy, and interruption rules with recovery routes.
- Give the empty Overview a stable landing and route to pinned Home and its drawer cue, with optional accessibility controls in a deliberately opened aid view. Keep the installed bar only as the reversible development fallback alongside the operator-accepted gesture session.
- Stage implementation behind the existing card-composition, app-card, launcher-curation, and recovery changes; retain host checks and distinct native-board/operator evidence; the user accepts the installed result and waives further physical recordings.
- Target a Rust implementation of the final launcher/drawer/shade/Settings UI client while retaining Sway as the live-deck compositor and the existing C launcher as a development reference and rollback. Retain the cross-built Rust probe as a feasibility artifact; production Rust runtime identity and native rendering are recorded separately. The user waives the historical comparative probe benchmark.

**Non-goals:** A second competing Home destination or hold-for-recents model; permanent Apps/Windows/System/Back/Home controls in the final shell; synthetic universal Back keypresses into arbitrary Wayland apps; Palm assets or pixel copying; LG television webOS patterns; an assumed new compositor/GPU renderer; haptic/vibration integration on this board; a lock screen; telephony, battery, account, or cloud services; replacing the sibling's bounded live-card lifecycle.

## Capabilities

### New Capabilities

- `runtime/device-settings`: truthful, recoverable shell settings and system controls.
- `runtime/notification-center`: previews, history, actions, dismissal, privacy, and interruption policy.

### Modified Capabilities

- `runtime/handheld-shell-design`: add the accepted portrait appearance, navigation, direct manipulation, scene, accessibility and feedback contract while retaining its existing overlay requirements.

- `runtime/shell`: replace the final persistent-bar navigation requirement with accepted Overview → pinned Home → drawer and shade/Settings behavior, retaining the separate rollback session. The installed bar remains only as a rollout/rollback session; Terminal remains a named recovery app in the drawer.

## Impact

Planning affects the replacement of the shell bar in the final session, a Rust UI client for the launcher drawer/shade/Settings, the selected opt-in Sway card-scene integration, notification service, and Nix image defaults in later implementation. Host mockups and state/trace fixtures need no board. Operator acceptance covers the installed behavior with an explicit further-proof waiver. Numerical motion cadence and unrecorded individual physical cases remain UNVERIFIED; existing observations keep their original classes. No kernel, device-tree, stage-1, or radio change is presumed.
