## Purpose

The userspace shell applies resolved theme roles to Settings and notification
Shade surfaces, reports unsupported roles explicitly, and restores their colors
when a shared appearance transaction rolls back.

## ADDED Requirements

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
