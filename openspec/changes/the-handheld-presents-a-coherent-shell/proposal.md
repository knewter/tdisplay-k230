## Why

A person can launch apps, but the current permanent top bar and Back/Home footers make the 568×1232 touch screen feel like a button menu. The intended handheld uses a live card deck as Home, an installed-app drawer rising from it, and a notification shade descending from the top. Those surfaces need one direct-touch and motion contract before their implementations meet.

## What Changes

- Define an original, Palm/HP phone webOS-inspired visual and motion language for shell, live-card overview, desktop-entry launcher, settings, and notifications. The accompanying SVGs are review mockups, not running UI.
- Make a bottom-edge Home swipe shrink the current app into the live-card deck; continue a deck pull upward to reveal the installed-app drawer. Use horizontal card swipes, tap expand, recoverable upward throw-close, kinetic list scroll, and cancellable long press as normal interaction.
- Extend the bottom app gesture to two axes: drag up then sideways without lifting to choose an adjacent running app, or swipe horizontally from the bottom-center gesture region for a direct app switch. Preserve one-to-one finger tracking, stable deck order, reversible cancellation, and focus only after release. Pure upward release still reaches Home; no hold-to-enter mode or second home grid is added.
- Open a notification shade with a top-edge downward gesture; place truthful Settings entry inside it. A contextual edge Back gesture dismisses shell surfaces or keyboard first but does not pretend every Wayland app has a universal Back action. The final shell has no permanent navigation rail or Back/Home footer.
- Coordinate app→card, deck selection, app launch/return, launcher, notification, and settings movement as one scene with stable spatial direction, scale, order, and focus. Build this on the selected Sway/wlroots composition boundary if it meets measured limits; do not assume a new compositor.
- Give every accepted touch an immediate visible response. No vibration work is planned on the current board because no actuator/control path is established.
- Give settings truthful controls for capabilities the system can read or change, with unavailable states and explicit action feedback. No battery status is shown or promised.
- Add notification preview, history, dismissal, action, privacy, and interruption rules with recovery routes.
- Give the empty deck a stable landing and drawer cue, with optional accessibility controls in a deliberately opened aid view. Keep the installed bar only as the reversible development fallback until the full gesture route passes real-glass recovery tests.
- Stage implementation behind the existing card-composition, app-card, launcher-curation, and recovery changes; require host checks and separate real-glass proof before declaring physical behavior complete.
- Target a Rust implementation of the final launcher/drawer/shade/Settings UI client while retaining Sway as the live-deck compositor and the existing C launcher as a development reference and rollback. First prove a pinned Rust layer-shell/software-buffer client can cross-build, map, render, and receive touch on this RISC-V board; the probe does not select a final UI toolkit or complete a shell route.

**Non-goals:** A separate Android home grid or hold-for-recents model; permanent Apps/Windows/System/Back/Home controls in the final shell; synthetic universal Back keypresses into arbitrary Wayland apps; Palm assets or pixel copying; LG television webOS patterns; an assumed new compositor/GPU renderer; haptic/vibration integration on this board; a lock screen; telephony, battery, account, or cloud services; replacing the sibling's bounded live-card lifecycle.

## Capabilities

### New Capabilities

- `runtime/handheld-shell-design`: cross-surface direct touch, visual motion, navigation, focus, accessibility, and transition contract.
- `runtime/device-settings`: truthful, recoverable shell settings and system controls.
- `runtime/notification-center`: previews, history, actions, dismissal, privacy, and interruption policy.

### Modified Capabilities

- `runtime/shell`: replace the final persistent-bar navigation requirement with gesture-led Home-as-cards, drawer, shade, and contextual Back behavior. The installed bar remains only as a rollout/rollback session; Terminal remains a named recovery app in the drawer.

## Impact

Planning affects the replacement of the shell bar in the final session, a Rust UI client for the launcher drawer/shade/Settings, the selected opt-in Sway card-scene integration, notification service, and Nix image defaults in later implementation. Host mockups and state/trace fixtures need no board. Finger tracking, motion cadence, readability, touch reach, notification timing, focus, and card continuity require a reserved physical board and are explicitly UNVERIFIED until recorded there. No kernel, device-tree, stage-1, or radio change is presumed.
