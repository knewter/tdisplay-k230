## ADDED Requirements

### Requirement: The shell uses one visual language across its surfaces

<!-- UNVERIFIED -->

Home widgets, the dock, the drawer, the Shade, Settings and the Vision page
SHALL draw text from one type scale of five roles (Display, Title, Body,
Label and Caption) with no text below 26 px at the 100% step, spaced on an 8
px rhythm. They SHALL use three card treatments by job (group, control and
chosen) and one icon style. They SHALL take every colour from the active
theme, and SHALL reflow without clipping, ellipsizing or overlapping at all
four text steps and in high contrast, in both orientations.

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
  clipped, ellipsized or overlapping text
