## ADDED Requirements

### Requirement: The Clock widget marks the minute with the theme accent

<!-- UNVERIFIED: the hour/minute colours are seen in the panel captures under
docs/evidence/clock-restyle/ and approved on glass, but a theme change
re-colouring the minute without a restart has not been observed on the
board. -->

Every Clock widget style SHALL draw the hour in the active theme's foreground
colour and the minute in its accent colour. It SHALL take both colours from
the theme and SHALL keep the existing halo so the time reads over any
wallpaper. It SHALL NOT use the accent for any other element of the Clock
except the analog style's minute hand.

#### Scenario: The Bubble clock on the panel

- **WHEN** Home shows the Bubble Clock on the landscape panel
- **THEN** the hour numerals are the theme's foreground colour
- **AND** the minute numerals below them are the theme's accent colour
- **AND** the date is the foreground colour

#### Scenario: A theme change

- **WHEN** the person activates a theme with a different accent
- **THEN** the minute takes the new accent without a restart

### Requirement: The Clock widget's date is one neutral line of at least 32 px

*Grounding (2026-10-17): host tests `clock_date` check the date's size, width
and clearance at 100/130/160/200%; native panel captures at 100%, 160% and
200% are in `docs/evidence/clock-restyle/board-panel-*-home.png`, and the
operator judged the Clock on glass ("clock lookgs good").*

Every Clock widget style SHALL draw its date as one line of mixed-case text
(for example "Fri, Oct 16") in the foreground colour, at no less than 32 px at
the 100% text step. The size SHALL grow with the Vision text step. The date
SHALL fit the cell without ellipsizing, and the time SHALL NOT overlap it.

#### Scenario: The date at the default step

- **WHEN** Home shows a Clock widget at the 100% text step
- **THEN** its date is shown in full, in mixed case, at 32 px or more

#### Scenario: The date at the largest step

- **WHEN** Home shows a Clock widget at the 200% text step in either
  orientation
- **THEN** neither the date nor the time is clipped or overlapped
