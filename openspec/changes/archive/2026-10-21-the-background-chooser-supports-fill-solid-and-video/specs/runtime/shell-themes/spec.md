## ADDED Requirements

### Requirement: Every promised background fit mode exists

*Grounding (2026-10-16): host tests in `tests/background_decode_module.rs`, `tests/test_theme_preferences.py` and `tests/test_omarchy_theme_activation.py`; native board `grim` captures of all five modes on one dark and one light theme, and a user overlay staged, applied and kept across a shell/helper restart, in `docs/evidence/omarchy-themes/background-fit-modes-board/README.md`. Taps were injected over HDMI. The over-256 MiB overlay rejection is host-only.*
The system SHALL support `crop`, `fit`, `center`, `fill`, and `solid`
background placement modes, selectable the same way the existing modes
already are. `fill` SHALL stretch the image to exactly cover the panel, ignoring its
aspect ratio, with no letterbox and no crop (`crop` is the
aspect-preserving cover). `solid` SHALL show a plain fill color drawn from the active
generation's resolved background/base palette role for a theme that ships
no background asset. A person SHALL be able to choose a background image
from outside the active theme's own asset set, bounded the same way an
in-theme background already is (size limit, supported-format check, no path
escape).

#### Scenario: Fill mode covers the panel without letterboxing
- **WHEN** a person selects `fill` for a background whose aspect ratio does
  not match the panel
- **THEN** the image is stretched to cover the whole panel, with no visible
  letterbox and nothing cropped away

#### Scenario: Solid mode with no background asset
- **WHEN** a theme ships no background asset and a person selects `solid`
- **THEN** the panel shows a plain fill color drawn from that generation's
  resolved palette, not a decode error or a blank surface

#### Scenario: A user overlay image is chosen
- **WHEN** a person selects a background image from outside the active
  theme's own asset set
- **THEN** the system applies the same size/format/path bounds an in-theme
  background already has, and rejects an oversized or unsupported file
  without crashing

### Requirement: A video-suffixed background plays, muted and bounded

*Grounding (2026-10-22): board playback, cover pause/resume, reduced-motion startup and restoration in `docs/evidence/omarchy-themes/background-video-board-2026-10-21/README.md`. The paired still/video, one/three-card budget trial passes every frozen numeric metric at the shipped 12 ms panel allowance with injected drags at the measured real-finger rate, in `docs/evidence/omarchy-themes/background-video-board-2026-10-21/installed-12ms-trial/README.md`. The operator reported no flicker on real glass. Landscape only.*

<!-- UNVERIFIED: the budget trial's portrait 568x1232 session (the board runs
landscape by operator decision); unsupported-codec diagnostics and fallback
on the board (host proof only, docs/evidence/omarchy-themes/background-video-audit.md);
a live reduced-motion toggle (only the startup setting was tested). -->
The system SHALL play a video-suffixed background from a theme's own
`backgrounds/` directory, muted, bounded, and reusing the same decode path
already justified for another wallpaper surface. It SHALL distinguish an
unsupported codec from a missing or corrupt asset, pause decoding when the
background is fully covered or reduced motion is enabled, and show a still
fallback (the theme's own preview image, or its first still background)
in either case rather than a blank surface. This inherits the existing
card CPU/frame budgets as a physical performance gate; it is not claimed
closed by a host test alone.

#### Scenario: A supported video background plays
- **WHEN** a person selects a theme whose `backgrounds/` directory contains
  a supported video-suffixed file
- **THEN** the panel plays it muted and bounded, respecting the existing
  card CPU/frame budgets

#### Scenario: An unsupported codec is reported honestly
- **WHEN** a selected video background's codec is not supported
- **THEN** the system reports the specific unsupported-codec condition and
  shows a still fallback, rather than reporting a generic missing-asset
  error

#### Scenario: Covered or reduced-motion playback pauses
- **WHEN** a playing video background becomes fully covered by another
  surface, or reduced motion is enabled
- **THEN** decoding pauses and a still frame is shown, resuming visible
  playback only when uncovered and reduced motion is off, within the
  measured shell interaction budgets
