## ADDED Requirements

### Requirement: Touch follows the active panel orientation

*Grounding: the fixed landscape mapping (logical (x, y) is panel (y, 1232 - x)) is grounded by `docs/evidence/panel-landscape/` (injected and operator-confirmed). A mapping that survives a live rotation is <!-- UNVERIFIED: not yet observed. -->*

In each panel orientation the shell uses, a touch SHALL land under the finger, including after the orientation changes at run time, without a reboot and without a calibration step. The edge gestures SHALL follow the edges of the active orientation. While HDMI is the active output the existing HDMI touch behaviour SHALL be unchanged.

#### Scenario: Corners before and after a rotation

- **WHEN** a touch is injected at each corner of the glass in portrait, the shell rotates to landscape, and the same panel positions are touched again
- **THEN** each touch is delivered at the logical position the active orientation maps that panel point to

#### Scenario: HDMI is active during a rotation

- **WHEN** the base is attached or detached while HDMI is the active output
- **THEN** the HDMI touchpad relay is not disturbed, and direct panel touch is correct when HDMI is unplugged
