## ADDED Requirements

### Requirement: The rest of the shell's text uses the type roles

<!-- UNVERIFIED -->

Home's app and folder labels, the Battery and Weather widget captions, the
volume HUD's expanded rows, the notification banner, the Wi-Fi pages, the Help page, the
theme chooser, the recovery menu and splash, and the card Overview's title
and footer SHALL draw text from the shell's five type
roles with no text below 26 px at the 100% step. Text the shell writes on
these surfaces SHALL reflow without clipping, ellipsizing or overlapping at
all four text steps and in high contrast, in both orientations.

#### Scenario: Home at 100%

- **WHEN** a person looks at Home at the 100% step
- **THEN** each app label is set at 26 px or more and sits inside its own
  cell
- **AND** the page keeps its columns, so a 4-wide widget stays where it was

#### Scenario: The volume HUD with audio playing

- **WHEN** a stream is playing and the person expands the volume HUD at 200%
- **THEN** the stream's name is set in a type role and does not overlap its
  slider
