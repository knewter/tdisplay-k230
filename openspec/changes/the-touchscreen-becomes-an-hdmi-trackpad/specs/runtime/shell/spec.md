## ADDED Requirements

### Requirement: Four-finger trackpad pinch opens app overview

<!-- UNVERIFIED: normal Sway binding syntax and routing are read in the pinned source; physical four-finger recognition and overview presentation remain task 3.6. -->

While the board's built-in display is inactive and its touchscreen is a
virtual touchpad for HDMI, the shell SHALL open app overview after a
four-finger inward pinch on that touchscreen. The Sway configuration SHALL
scope this binding to the virtual touchpad and leave two-finger application
scroll/zoom gestures available. Direct-touch panel-mode gestures SHALL retain
their existing configuration.

#### Scenario: Navigate from a running app

- **WHEN** an app is open on HDMI and the operator pinches four fingers inward
  on the board's touchscreen glass
- **THEN** app overview appears without a keyboard or edge-touch gesture

#### Scenario: Ordinary app gestures remain available

- **WHEN** the operator uses two-finger scrolling or pinch in an app
- **THEN** the four-finger shell binding does not consume that gesture
