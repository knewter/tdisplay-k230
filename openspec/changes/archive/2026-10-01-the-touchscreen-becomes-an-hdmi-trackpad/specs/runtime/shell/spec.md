## ADDED Requirements

### Requirement: Four-finger trackpad pinch opens app overview

<!-- UNVERIFIED: normal Sway binding syntax and routing are read in the pinned source; individual physical four-finger recognition is not separately documented; overall acceptance and waived exhaustive recheck are recorded in docs/evidence/proposal-closeout/2026-10-01/trackpad.md. -->

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

*Grounding: operator acceptance in `docs/evidence/proposal-closeout/2026-10-01/trackpad.md`, with prior source and board/QEMU evidence retaining their original classes and limits.*

<!-- Grounding: installed uniform-gesture trial/source evidence and overall operator acceptance in docs/evidence/proposal-closeout/2026-10-01/trackpad.md. No new camera/contact-count measurement is claimed. -->

In HDMI trackpad mode, two-contact shell gestures SHALL use the same navigation,
card manipulation, sheet scrolling/dismissal and release policies as one-contact
direct touch gestures. Three-contact upward bottom gestures SHALL use the existing
two-contact direct touch keyboard policy. Motion SHALL follow the contact centroid,
reverse while held, and settle with the shared release physics. The shell SHALL
preserve ordinary application center scroll/pinch and one-contact pointer/tap.
Transport loss and cancellation SHALL restore recoverable state without a stale
contact, and translated pan release SHALL NOT activate an app as a tap.
Direct-touch behavior SHALL retain its existing gesture configuration.

#### Scenario: Open shell surfaces without positioning the cursor

- **WHEN** two fingers swipe down from the glass's top edge or up from its bottom edge in HDMI mode
- **THEN** Shade or the existing app/overview/Home/drawer navigation follows that movement, independent of where the pointer is

#### Scenario: Browse cards without stepping

- **WHEN** two fingers move horizontally while overview is showing
- **THEN** live cards move continuously, reverse with the fingers and settle from release velocity without discrete card jumps

#### Scenario: Ordinary input retains its owner

- **WHEN** a center two-finger scroll/pinch, one-finger pointer/tap, incompatible movement or an unqualified additional-contact sequence occurs
- **THEN** the compatible ordinary sequence remains libinput-owned; a canceled owned shell gesture cannot generate a stray app click

#### Scenario: Dismiss, reverse or lose a controller

- **WHEN** an owned sheet gesture reverses, cancels or loses its transport
- **THEN** the current sheet settles to a recoverable state without a stale owned contact, half-visible sheet or unrelated route

#### Scenario: Dismiss a drawer using its native content rules

- **WHEN** a two-finger downward drag begins in an open app drawer at the top of its scrollable content
- **THEN** it closes with the same tracking, reversal and release as a one-finger direct-touch drag
- **AND** a gesture that began while the list was scrolled retains scrolling ownership

#### Scenario: Keyboard uses the next contact count

- **WHEN** three fingers swipe upward from the bottom in HDMI trackpad mode
- **THEN** the existing keyboard show/drag/settle policy handles the gesture as the corresponding direct-touch two-finger chord
- **AND** a two-finger navigation gesture does not accidentally show the keyboard

<!-- Closeout evidence: docs/evidence/proposal-closeout/2026-10-01/trackpad.md. Operator report is physical
feedback; retained host/QEMU/injected evidence keeps its original class.
No additional capture, quantitative measurement or fault injection claimed. -->
