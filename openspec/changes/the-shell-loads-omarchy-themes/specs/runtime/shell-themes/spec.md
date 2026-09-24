## Purpose

Let a person use unchanged Omarchy theme repositories to give the handheld a coherent appearance, with complete color and background choices and recoverable activation.

## ADDED Requirements

### Requirement: An unchanged theme checkout is a usable source

<!-- UNVERIFIED -->
The system SHALL accept a community theme repository root or a theme within an Omarchy built-in collection without conversion, extra manifests, or edits to source files. Generated output and preferences MUST remain outside that checkout. Refresh SHALL detect changed contents and SHALL NOT execute theme code or alter the source revision. A failed refresh SHALL preserve the last valid generation.

#### Scenario: Clone then select
- **WHEN** a person selects a valid unchanged Quattro theme checkout
- **THEN** the system loads its appearance and assets and leaves its tracked and untracked source files unchanged

#### Scenario: Update the checkout
- **WHEN** a person updates that clone and refreshes the selected theme
- **THEN** changed colors and assets appear together or the previous valid appearance remains with a useful error

#### Scenario: Use the familiar swap command
- **WHEN** a person places an unchanged clone under `~/.config/omarchy/themes/NAME` and runs `omarchy-theme-set NAME`
- **THEN** the handheld adapter applies that theme through the same appearance path used by its touch chooser, without requiring the Omarchy desktop

### Requirement: All theme colors and applicable appearance overrides are honored

<!-- UNVERIFIED -->
The system SHALL preserve authored palette keys and reproduce the pinned Quattro alias, precedence, derived-color, mode, template, full-file, section-replacement, and machine-override behavior. Applicable surface colors, gradients, transparency, border widths, control states, typography and spacing SHALL reach their corresponding handheld surfaces. Touch geometry adaptations MUST be visible in the compatibility report; themes MUST NOT replace gesture navigation.

#### Scenario: A theme supplies more than ANSI colors
- **WHEN** a theme supplies distinct semantic, ANSI, selection, custom, and gradient values plus section overrides
- **THEN** the corresponding shell, drawer, card, Settings, notification, keyboard and app appearance adapters retain their intended distinctions instead of reducing them to a small shared palette

#### Scenario: A section override replaces defaults
- **WHEN** a theme supplies a complete shell file and a partial section file
- **THEN** full-file replacement precedes section replacement, missing section values use documented consumer fallbacks, and machine override keys win last

### Requirement: Theme icons and background choices remain available

<!-- UNVERIFIED -->
The system SHALL resolve `icons.theme` through installed freedesktop themes with explicit missing-theme fallback. It SHALL list all background candidates from the source and user overlay, support upstream still-image formats and bounded supported video playback, and distinguish unavailable codecs from missing assets. Selection SHALL remember each theme's wallpaper across switches and boots. Portrait crop preview, fit options, empty-directory fallback and removed-file recovery SHALL remain usable by touch.

#### Scenario: Choose another background
- **WHEN** a person scrolls the background chooser and taps a different image
- **THEN** the actual portrait preview and shell change to that image, other choices remain available, and the chosen image returns after switching away and back or rebooting

#### Scenario: A video wallpaper is covered by an app
- **WHEN** a supported video background becomes fully covered or reduced motion is enabled
- **THEN** decoding pauses or a still frame is used, and returning to visible playback respects the measured shell interaction budgets

#### Scenario: An icon theme is missing
- **WHEN** a clone names an icon theme that the image does not contain
- **THEN** apps retain recognizable fallback icons and text labels and the missing icon dependency is identified

### Requirement: Theme activation is coordinated and recoverable

<!-- UNVERIFIED -->
The system SHALL validate a new appearance before activation, coordinate its shell surfaces as one generation, and provide touch preview, cancel, apply and rollback. App-specific reload or restart limitations SHALL be reported without closing running work automatically. Invalid assets or appearance settings MUST NOT strand the recovery app or corrupt the active theme. Fresh homes SHALL receive a working pinned default from the Nix image without restored user state.

#### Scenario: Cancel a preview
- **WHEN** a person cancels theme preview or its activation fails
- **THEN** the prior colors, icons and background are restored and the existing app session remains usable

#### Scenario: Boot with no saved preferences
- **WHEN** the image boots with a fresh home or an unavailable user theme source
- **THEN** it displays the declared default theme and exposes a usable chooser and recovery route

### Requirement: Compatibility and physical completion are explicit

<!-- UNVERIFIED -->
The system SHALL classify every palette key, override and asset as applied, adapted, unavailable or unknown with a reason. Existing handheld surface omissions SHALL remain implementation gaps rather than full-compatibility claims. Absent surfaces, hardware and apps SHALL be distinguished from gaps. Completion MUST include unchanged-checkout host fixtures and separate physical screenshots, touch observations, performance measurements, reboot and recovery evidence.

#### Scenario: A theme targets absent desktop features
- **WHEN** a theme includes lock assets, RGB keyboard data, desktop Lua or colors for an app absent from the image
- **THEN** its source remains intact and the compatibility view explains those boundaries while showing which handheld appearance settings were applied

#### Scenario: Only a parser test has passed
- **WHEN** upstream fixture comparisons pass without a device trial
- **THEN** the change continues to identify physical usability and performance as unverified
