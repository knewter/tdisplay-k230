# runtime/shell-themes Specification

## Purpose
The userspace shell applies resolved theme roles to Settings and notification
Shade surfaces, reports unsupported roles explicitly, and restores their colors
when a shared appearance transaction rolls back.

## Requirements

### Requirement: Settings and notifications honor the active theme

Grounding: `docs/evidence/omarchy-themes/settings-notifications-themed/board/README.md` records the physical dark/light Settings and Shade presentation, named compatibility reports and forced rollback on the same Rust renderer.

The system SHALL make the Rust shell's Settings and notification Shade surfaces read
the active generation's resolved colors the same way the shell, drawer, and
card renderers already do, and repaint on the existing commit/rollback
signal `theme_transaction.py`'s receiver fan-out already sends. It SHALL
report their coverage in the existing `applied`/`adapted`/`unavailable`/
`unknown` compatibility view by name, rather than silently inheriting
hardcoded defaults, per `the-shell-loads-omarchy-themes`'s own
"Compatibility and physical completion are explicit" requirement. This
requirement adds no new palette role: it wires up `theme_tokens.py`'s
existing `sections["controls"]`/`sections["notifications"]` output.

#### Scenario: A theme with an explicit notifications section activates
- **WHEN** a person activates a theme whose source supplies a
  `notifications` section (or relies on documented fallback) and a
  notification is shown
- **THEN** the notification surface's colors match the active generation's
  resolved `notifications` section, and the compatibility report names it
  `applied` or `adapted` rather than silently defaulting

#### Scenario: Settings reflects the active theme after a swap
- **WHEN** a person opens Settings after switching themes
- **THEN** its rendered surface shows the newly active generation's colors without a restart, and a
  subsequent rollback restores the previous generation's colors on the
  same surface

#### Scenario: A surface has no themeable equivalent
- **WHEN** Settings or notifications turns out to have no rendered surface
  for a given palette role
- **THEN** the compatibility report names that role `unavailable` rather
  than omitting it or claiming coverage

#### Scenario: `--surface system` is exercised
- **WHEN** `python3 tests/test_handheld_theme_rendering.py --surface
  system` runs against a built package
- **THEN** it asserts every Settings/notifications role named above and
  fails rather than skips on an unimplemented one

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
- **THEN** the corresponding shell, drawer, card, keyboard and app appearance adapters retain their intended distinctions instead of reducing them to a small shared palette

<!-- Settings/notifications adapters moved 2026-09-28 (user-authorized scope
split, "yes a-d and f"): that portion of this scenario is now
`the-settings-and-notifications-surfaces-are-themed`'s own "Settings and
notifications honor the active theme" requirement, not this change's. -->

#### Scenario: A section override replaces defaults
- **WHEN** a theme supplies a complete shell file and a partial section file
- **THEN** full-file replacement precedes section replacement, missing section values use documented consumer fallbacks, and machine override keys win last

### Requirement: Theme icons and background choices remain available

<!-- UNVERIFIED -->
<!-- Narrowed 2026-09-28 (user-authorized scope split, "yes a-d and f"):
user-supplied overlays, non-crop fit modes (fill/solid), and bounded video
playback moved to `the-background-chooser-supports-fill-solid-and-video`'s
own "Every promised background fit mode exists" and "A video-suffixed
background plays, muted and bounded" requirements. This requirement keeps
only what this change itself still owns: icon fallback and the still-image,
crop-only background carousel with selection memory (implemented; see task
4.2.r/4.2.r2). -->
The system SHALL resolve `icons.theme` through installed freedesktop themes with explicit missing-theme fallback. It SHALL list all background candidates from the theme's own source, and support upstream still-image formats. Selection SHALL remember each theme's wallpaper across switches and boots. Portrait crop preview, empty-directory fallback and removed-file recovery SHALL remain usable by touch.

#### Scenario: Choose another background
- **WHEN** a person browses the background carousel (by drag or a side-slice tap) and confirms a different image (by tapping the centred slice or Apply)
- **THEN** the actual portrait preview and shell change to that image, other choices remain available, and the chosen image returns after switching away and back or rebooting

#### Scenario: An icon theme is missing
- **WHEN** a clone names an icon theme that the image does not contain
- **THEN** apps retain recognizable fallback icons and text labels and the missing icon dependency is identified

### Requirement: The theme chooser shows each theme's own imagery

<!-- UNVERIFIED -->
The touch chooser SHALL present each catalog entry as a full-image carousel slice, matching the horizontal Cover Flow layout of Omarchy's own picker (`shell/plugins/image-picker/ImagePicker.qml`, shared by `omarchy-theme-switcher` and `omarchy-theme-bg-switcher`): one large expanded centre slice with skewed side slices either side, browsed by drag or a side-slice tap and confirmed by tapping the centred slice or an explicit Apply. Each slice's imagery SHALL be sourced from that theme's own preview image when the source provides one, and otherwise a representative background image chosen by the same fallback rule Omarchy's picker uses (its first background asset, not a fabricated substitute). A theme with neither a preview image nor a background asset SHALL show a plain placeholder slice rather than an invented image. The background chooser SHALL show the same carousel treatment for each background candidate.

#### Scenario: A theme ships its own preview image
- **WHEN** a theme's source directory contains a supported preview image
- **THEN** that theme's carousel slice shows imagery decoded from that exact file, whether the slice is centred or a side slice

#### Scenario: A theme ships no preview image
- **WHEN** a theme has no preview file but does have background images
- **THEN** that theme's carousel slice shows imagery derived from that theme's first background image, sorted the same way Omarchy's own picker selects one

#### Scenario: A theme ships neither
- **WHEN** a theme has no preview image and no background image
- **THEN** its carousel slice shows a plain placeholder instead of imagery, and remains fully usable by touch (browsable and confirmable) all the same

### Requirement: Theme activation is coordinated and recoverable

<!-- UNVERIFIED -->
The system SHALL validate a new appearance before activation, coordinate its shell surfaces as one generation, and provide touch preview, cancel, apply and rollback. App-specific reload or restart limitations SHALL be reported without closing running work automatically. Invalid assets or appearance settings MUST NOT strand the recovery app or corrupt the active theme. Fresh homes SHALL receive a working pinned default from the Nix image without restored user state.

#### Scenario: Cancel a preview
- **WHEN** a person cancels theme preview or its activation fails
- **THEN** the prior colors, icons and background are restored and the existing app session remains usable

#### Scenario: Boot with no saved preferences
- **WHEN** the image boots with a fresh home and no valid saved theme generation
- **THEN** it displays the declared default theme and exposes a usable chooser and recovery route

#### Scenario: Boot after a selected source is removed
- **WHEN** the selected user theme source is unavailable but its saved generation remains valid
- **THEN** the system retains that generation and its selected wallpaper, exposes a usable chooser and recovery route, and does not require the source checkout to restore the appearance

### Requirement: Compatibility and physical completion are explicit

<!-- UNVERIFIED -->
The system SHALL classify every palette key, override and asset as applied, adapted, unavailable or unknown with a reason. Existing handheld surface omissions SHALL remain implementation gaps rather than full-compatibility claims. Absent surfaces, hardware and apps SHALL be distinguished from gaps. Completion MUST include unchanged-checkout host fixtures and an explicit disposition of physical screenshots, touch observations, performance measurements, reboot and recovery evidence. Existing device evidence and recorded operator acceptance MAY satisfy implemented-behavior acceptance when the operator explicitly waives additional collection. Waived recordings, unmeasured costs and unobserved individual boot cases MUST remain identified as UNVERIFIED; a waiver MUST NOT close missing consumer implementation.

Evidence and limits: `docs/evidence/omarchy-themes/compatibility-closeout-2026-10-10.md`, `docs/evidence/omarchy-themes/consumer-closeout-2026-10-10/README.md` and `docs/evidence/omarchy-themes/accepted-closeout-2026-10-10/README.md` retain the field inventory, source/license attribution, distinct host/board classes and explicit waiver. Individual unobserved physical cases and unmeasured costs remain UNVERIFIED.

#### Scenario: A theme targets absent desktop features
- **WHEN** a theme includes lock assets, RGB keyboard data, desktop Lua or colors for an app absent from the image
- **THEN** its source remains intact and the compatibility view explains those boundaries while showing which handheld appearance settings were applied

#### Scenario: Only a parser test has passed
- **WHEN** upstream fixture comparisons pass without a device trial
- **THEN** the change continues to identify physical usability and performance as unverified
