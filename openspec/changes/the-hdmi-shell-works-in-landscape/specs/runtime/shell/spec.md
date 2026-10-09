## ADDED Requirements

### Requirement: The HDMI shell remains usable in landscape

The system SHALL offer a qualified landscape HDMI configuration in which Home,
navigation and Settings remain visible, reachable and correctly hit-tested,
while preserving the existing portrait panel behavior. The shell SHALL derive
coordinate scaling from actual configured output geometry. Reuse the responsive
shell capability's implementation without replacing its existing task owner.

<!-- UNVERIFIED: host responsive fixtures exist, but the original HDMI
landscape tasks 5.1–5.4 and separate physical Home/Settings proof remain open.
Portrait HDMI acceptance is not landscape evidence. -->

#### Scenario: A person uses Home and Settings on a landscape monitor

- **WHEN** the board runs the qualified landscape HDMI profile
- **THEN** Home and navigation have no overlapping, off-screen or unreachable
  controls, and Settings rendering and input use the same output geometry

#### Scenario: The person returns to the portrait panel

- **WHEN** the active output returns to the 568×1232 panel
- **THEN** the established portrait rendering and input behavior remain intact
