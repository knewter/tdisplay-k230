## ADDED Requirements

### Requirement: The HDMI shell remains usable in landscape

The system SHALL offer a qualified landscape HDMI configuration in which Home,
navigation and Settings remain visible, reachable and correctly hit-tested,
while preserving the existing portrait panel behavior. The shell SHALL derive
coordinate scaling from actual configured output geometry. Reuse the responsive
shell capability's implementation without replacing its existing task owner.

Home and Drawer icon/text density SHALL have an actual-output sizing policy
beyond column-count reflow, while preserving native portrait behavior. Wi-Fi
and the theme chooser SHALL use a real reflow or uniform centered scale.
The dock’s slot-count/reflow policy SHALL be explicitly decided and qualified
against the corresponding physical layout and input evidence. These transferred
requirements remain UNVERIFIED until tasks 7.1–7.3 and their named proof pass.

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

### Requirement: The panel shell works in landscape with the keyboard case

The system SHALL offer a build-time panel orientation for the built-in
568×1232 DSI panel. Portrait (`transform normal`) SHALL remain the default.
A landscape profile SHALL rotate the panel output 90 degrees counterclockwise
as seen by a person typing on the attached keyboard case (Sway
`transform 270`), giving a 1232×568 logical output. In that profile the
shell's own surfaces (wallpaper, Home and dock, Drawer, shade, Settings
including Wi-Fi and the theme chooser, the on-screen keyboard, notifications
and the power sheet) SHALL accept the whole-output configure, lay out without
overlapping, off-screen or unreachable controls, and hit-test against the
same rotated geometry. Touch input SHALL map to the rotated output, and the
edge gestures SHALL follow the rotated edges. The HDMI output behavior SHALL
be unchanged by the panel orientation.

<!-- UNVERIFIED: operator request 2026-10-13 with camera observation of the
keyboard-case bench; tasks 8.1–8.7 and their named proof are open. A runtime
`swaymsg output DSI-1 transform 270` trial on the second board on 2026-10-13
showed the terminal correctly oriented, but shell-ui rejected the 1232×568
home and wallpaper configures after a restart (`home-configure-rejected`). -->

#### Scenario: A person uses the shell in the keyboard case

- **WHEN** the board runs the landscape panel profile in the keyboard case
- **THEN** text reads upright from the keyboard side, and Home, Drawer,
  shade, Settings and the power sheet are fully visible and respond where
  they are drawn

#### Scenario: The default panel profile stays portrait

- **WHEN** a board runs the default profile
- **THEN** the panel stays 568×1232 portrait with the established rendering
  and input behavior

#### Scenario: HDMI still works from the landscape profile

- **WHEN** an HDMI monitor is connected to a board running the landscape panel
  profile
- **THEN** the HDMI output, its transform and its touchpad relay behave as
  in the portrait profile
