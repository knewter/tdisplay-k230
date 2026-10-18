## ADDED Requirements

### Requirement: The shell uses one visual language across its surfaces

<!-- UNVERIFIED -->

Settings, the Vision page, the Shade's header and controls, the drawer, the
Clock widget and the Battery details widget SHALL draw text from one type
scale of five roles (Display, Title, Body, Label and Caption) with no text
below 26 px at the 100% step, spaced on an 8 px rhythm. Settings, the Shade,
the drawer search and the dock SHALL use three card treatments by job
(group, control and chosen), and Settings and the Shade SHALL use one icon
style. These surfaces SHALL take every colour from the active theme. The
text the shell writes itself SHALL reflow without clipping, ellipsizing or
overlapping at all four text steps and in high contrast, in both
orientations. Text that comes from elsewhere -- an app's name, a sender's
notification text -- MAY be cut short after it fills its space: a drawer
app name wraps onto a second line and is shortened only beyond that.

#### Scenario: A person scans Settings

- **WHEN** the person opens Settings at the 100% step
- **THEN** section labels, row names and values each use one consistent size
  and case
- **AND** the accent appears only on the current choice and one primary action

#### Scenario: The Vision page shows the chosen step

- **WHEN** the person opens the Vision page
- **THEN** the chosen text size is distinguished from the other three by the
  accent fill and rim, not only by text colour

#### Scenario: The largest step

- **WHEN** the person selects 200% text
- **THEN** every restyled surface reflows in both orientations with no
  clipped, ellipsized or overlapping shell text

#### Scenario: A long app name in the drawer

- **WHEN** the drawer shows an app named "System Monitor" at any text step
- **THEN** the name wraps onto two lines in the 26 px Caption role (scaled
  by the step) instead of being shortened
