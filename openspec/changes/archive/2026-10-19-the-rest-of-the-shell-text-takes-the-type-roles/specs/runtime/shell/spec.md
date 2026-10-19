## ADDED Requirements

### Requirement: The rest of the shell's text uses the type roles

Home's app and folder labels, the Battery and Weather widget captions, the
volume HUD's expanded rows, the notification banner, the Wi-Fi pages, the Help page, the
theme chooser, the recovery menu and splash, and the card Overview's title
and footer SHALL draw text from the shell's five type
roles with no text below 26 px at the 100% step. Text the shell writes on
these surfaces SHALL reflow without clipping, ellipsizing or overlapping at
all four text steps and in high contrast, in both orientations.

*Grounding (2026-10-19): host renders at four steps in both orientations
and unit tests (`docs/evidence/rest-of-text/host-*.png`); native `grim`
captures of every named surface at 100% and 200% on the landscape panel
(`docs/evidence/rest-of-text/board-panel-{100,200}.png`, closures
e6cfec6a and 2a7a86ba); the operator looked on glass: "it all seems
fine", "it's good to go". Network and app names that are longer than
their line may still be shortened.*

#### Scenario: Home at 100%

- **WHEN** a person looks at Home at the 100% step
- **THEN** each app label is set at 26 px or more and sits inside its own
  cell
- **AND** the page keeps its columns, so a 4-wide widget stays where it was

#### Scenario: The volume HUD with audio playing

- **WHEN** a stream is playing and the person expands the volume HUD at 200%
- **THEN** the stream's name is set in a type role and does not overlap its
  slider

## MODIFIED Requirements

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
surface) instead of a non-uniform stretch. On every output the theme
chooser SHALL show its themes and backgrounds as the omarchy-style
carousels, never as a grid of cards (operator decision 2026-10-19: "even
the larger displays should show the omarchy-style theme switcher"). On a wide
output the dock SHALL offer more than four slots, one per grid column, within
the icon budget that keeps a full page plus its dock resident; the extra slots
stay empty until apps are pinned, and returning to a narrower output SHALL NOT
hide a pinned item.

<!-- UNVERIFIED: the carousel-only chooser on a landscape monitor has host tests only; it needs a board capture on HDMI. -->

*Grounding (2026-10-16): Home and Drawer columns reflow at native size
(`home_grid::columns_for_width`, `ICON_SIZE` 80), verified by host tests and
board `grim` captures at 1280x800. The Wi-Fi and chooser reflow is in
`docs/evidence/hdmi-hotplug/landscape/wide-reflow/`; operator on the HDMI
monitor: "themes worked in landscape hdmi fine" (operator report). The dock
rule (`home_grid::dock_slots`, `HomeLayout::fit_dock`) has host tests and
renders, plus board evidence, in
`docs/evidence/hdmi-hotplug/landscape/wide-dock/`. Landscape HDMI tasks
5.1–5.4 are complete with board evidence.*

#### Scenario: A person uses Home and Settings on a landscape monitor

- **WHEN** the board runs the qualified landscape HDMI profile
- **THEN** Home and navigation have no overlapping, off-screen or unreachable
  controls, and Settings rendering and input use the same output geometry

#### Scenario: The person returns to the portrait panel

- **WHEN** the active output returns to the 568×1232 panel
- **THEN** the established portrait rendering and input behavior remain intact
