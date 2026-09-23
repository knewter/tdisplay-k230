## Why

A person can launch apps and reach shell controls, but the launcher, window deck, system actions, and transient messages do not yet read as one handheld experience. The 568×1232 screen needs a single visual and navigation contract so later card, catalog, and recovery work can meet at predictable boundaries.

## What Changes

- Define an original, phone webOS-inspired visual language and surface map for the shell, card overview, desktop-entry launcher, settings, and notifications. The accompanying SVGs are review mockups, not running UI.
- Give settings truthful controls for capabilities the system can read or change, with unavailable states and explicit action feedback. No battery status is shown or promised.
- Add notification preview, history, dismissal, action, privacy, and interruption rules with recovery routes.
- Keep distinct visible Apps, Windows, Keyboard, System, Back, and Home actions while coordinating gestures, focus, keyboard insets, empty/loading/error states, motion, and small-screen accessibility.
- Stage implementation behind the existing card-composition, app-card, launcher-curation, and recovery changes; require host checks and separate real-glass proof before declaring physical behavior complete.

**Non-goals:** Palm assets or pixel copying; LG television webOS patterns; a new compositor or GPU renderer; a lock screen; telephony, battery, account, or cloud services; redefining the existing live-card implementation contract.

## Capabilities

### New Capabilities

- `runtime/handheld-shell-design`: cross-surface visual, navigation, focus, accessibility, and transition contract.
- `runtime/device-settings`: truthful, recoverable shell settings and system controls.
- `runtime/notification-center`: previews, history, actions, dismissal, privacy, and interruption policy.

### Modified Capabilities

- `runtime/shell`: change the final Home destination from Terminal to the safe Apps landing, with an explicitly labeled Terminal recovery action. Existing app-card, launcher, and recovery behavior remains owned by their changes; this proposal supplies the integration contract they can consume.

## Impact

Planning affects the shell bar, launcher, settings surface, notification service/client, and their Nix image defaults in later implementation. Host mockups and contract tests need no board. Readability, touch reach, notification timing, app focus, and card continuity require a reserved physical board and are explicitly unverified until recorded there. No kernel, device-tree, stage-1, or radio change is proposed.
