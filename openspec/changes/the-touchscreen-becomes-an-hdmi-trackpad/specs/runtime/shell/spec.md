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

### Requirement: HDMI two-finger gestures have explicit ownership and direct motion

<!-- UNVERIFIED: operator requested the gesture UX pass on 2026-09-30; source,
compositor and physical acceptance for the new edge/motion policy are tasks 5.1-5.7. -->

In HDMI trackpad mode, the shell SHALL offer two-finger vertical swipes from
the built-in glass's top and bottom edges for shell navigation, independent
of cursor position. It SHALL move overview cards continuously under a
horizontal two-finger swipe and settle with the release momentum. It SHALL
preserve center application scroll/pinch and one-finger pointer/tap input.
Drawer/shade dismissal SHALL follow current visible geometry and support
reversal, cancellation and transport-loss recovery. This policy SHALL not
change direct-touch panel input.

#### Scenario: Open shell surfaces without positioning the cursor

- **WHEN** two fingers swipe down from the glass's top edge or up from its bottom edge in HDMI mode
- **THEN** Shade or the existing app/overview/Home/drawer navigation follows that movement, independent of where the pointer is

#### Scenario: Browse cards without stepping

- **WHEN** two fingers move horizontally while overview is showing
- **THEN** live cards move continuously, reverse with the fingers and settle from release velocity without discrete card jumps

#### Scenario: Ordinary input retains its owner

- **WHEN** a center two-finger scroll/pinch, one-finger pointer/tap, incompatible edge movement or additional-contact sequence occurs
- **THEN** the compatible ordinary sequence remains libinput-owned; a canceled owned shell gesture cannot generate a stray app click

#### Scenario: Dismiss, reverse or lose a controller

- **WHEN** an owned sheet gesture reverses, cancels or loses its transport
- **THEN** the current sheet settles to a recoverable state without a stale owned contact, half-visible sheet or unrelated route
