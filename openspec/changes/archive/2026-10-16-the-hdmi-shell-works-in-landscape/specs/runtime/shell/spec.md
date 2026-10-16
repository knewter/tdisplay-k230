## ADDED Requirements

### Requirement: The HDMI shell remains usable in landscape

The system SHALL offer a qualified landscape HDMI configuration in which Home,
navigation and Settings remain visible, reachable and correctly hit-tested,
while preserving the existing portrait panel behavior. The shell SHALL derive
coordinate scaling from actual configured output geometry. Reuse the responsive
shell capability's implementation without replacing its existing task owner.

Home and Drawer SHALL keep the panel's native icon and text size on every
output, and a wider output SHALL add grid columns instead of enlarging icons
(operator decision 2026-10-14: "Keep panel size, more columns"). Wi-Fi and
the theme chooser SHALL use a real wide reflow (columns taken from the
surface, theme cards in a grid) instead of a non-uniform stretch. On a wide
output the dock SHALL offer more than four slots, one per grid column, within
the icon budget that keeps a full page plus its dock resident; the extra slots
stay empty until apps are pinned, and returning to a narrower output SHALL NOT
hide a pinned item.

<!-- Grounding (2026-10-16): Home and Drawer columns reflow at native size
(`home_grid::columns_for_width`, `ICON_SIZE` 80), verified by host tests and
board `grim` captures at 1280x800. The Wi-Fi and chooser reflow is in
`docs/evidence/hdmi-hotplug/landscape/wide-reflow/`; operator on the HDMI
monitor: "themes worked in landscape hdmi fine" (operator report). The dock
rule (`home_grid::dock_slots`, `HomeLayout::fit_dock`) has host tests and
renders, plus board evidence, in
`docs/evidence/hdmi-hotplug/landscape/wide-dock/`. Landscape HDMI tasks
5.1–5.4 are complete with board evidence. -->

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

<!-- Grounding (2026-10-14): tasks 8.1–8.7 on the second board's installed
landscape image. The evidence is native `grim` captures of every listed surface,
injected edge gestures, and the operator's real-finger check ("real finger
check worked fine"). HDMI plug and unplug from the landscape profile was checked
by the operator ("yeah it's good to go") with native captures. The camera
photograph was waived by the operator. See
`docs/evidence/panel-landscape/` and
`docs/evidence/hdmi-hotplug/landscape/teardown-crash.md`. -->

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
