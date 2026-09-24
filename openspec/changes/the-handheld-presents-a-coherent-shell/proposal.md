## Why

A person can launch apps and reach shell controls, but the launcher, window deck, system actions, and transient messages do not yet move or respond as one handheld experience. Previous/Next-heavy navigation makes a touch device feel like a menu operated by buttons. The 568×1232 screen needs a direct-manipulation and visual-motion contract so card, catalog, and recovery work meet at predictable boundaries.

## What Changes

- Define an original, Palm/HP phone webOS-inspired visual and motion language for shell, live-card overview, desktop-entry launcher, settings, and notifications. The accompanying SVGs are review mockups, not running UI.
- Make finger-following swipes, kinetic scrolling, tapping, cancellable long press, card snap/expand and recoverable throw-close the main interaction. Visible buttons remain for accessibility and recovery, not routine paging.
- Coordinate app→card, deck selection, app launch/return, launcher, notification, and settings movement as one scene with stable spatial direction, scale, order, and focus. Build this on the selected Sway/wlroots composition boundary if it meets measured limits; do not assume a new compositor.
- Give every accepted touch an immediate visible response. No vibration work is planned on the current board because no actuator/control path is established.
- Give settings truthful controls for capabilities the system can read or change, with unavailable states and explicit action feedback. No battery status is shown or promised.
- Add notification preview, history, dismissal, action, privacy, and interruption rules with recovery routes.
- Keep distinct visible Apps, Windows, Keyboard, System, Back, and Home actions while coordinating gesture ownership, focus, keyboard insets, interruption, empty/loading/error states, reduced motion, and small-screen accessibility.
- Stage implementation behind the existing card-composition, app-card, launcher-curation, and recovery changes; require host checks and separate real-glass proof before declaring physical behavior complete.

**Non-goals:** Palm assets or pixel copying; LG television webOS patterns; an assumed new compositor/GPU renderer; haptic/vibration integration on the current board; a lock screen; telephony, battery, account, or cloud services; replacing the sibling's bounded live-card lifecycle.

## Capabilities

### New Capabilities

- `runtime/handheld-shell-design`: cross-surface direct touch, visual motion, navigation, focus, accessibility, and transition contract.
- `runtime/device-settings`: truthful, recoverable shell settings and system controls.
- `runtime/notification-center`: previews, history, actions, dismissal, privacy, and interruption policy.

### Modified Capabilities

- `runtime/shell`: change the final Home destination from Terminal to the safe Apps landing, with an explicitly labeled Terminal recovery action. Existing app-card, launcher, and recovery behavior remains owned by their changes; this proposal supplies the integration contract they can consume.

## Impact

Planning affects the shell bar, launcher, the selected opt-in Sway card-scene integration, settings surface, notification service/client, and Nix image defaults in later implementation. Host mockups and state/trace fixtures need no board. Finger tracking, motion cadence, readability, touch reach, notification timing, focus, and card continuity require a reserved physical board and are explicitly UNVERIFIED until recorded there. No kernel, device-tree, stage-1, or radio change is presumed.
