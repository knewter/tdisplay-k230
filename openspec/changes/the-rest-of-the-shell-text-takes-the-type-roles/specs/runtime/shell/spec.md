## ADDED Requirements

### Requirement: The rest of the shell's text uses the type roles

<!-- UNVERIFIED -->

Home's app and folder labels, the Battery and Weather widget captions, the
Shade's audio and notification rows, the Wi-Fi pages, the Help page, the
theme grid and the recovery menu SHALL draw text from the shell's five type
roles with no text below 26 px at the 100% step. Text the shell writes on
these surfaces SHALL reflow without clipping, ellipsizing or overlapping at
all four text steps and in high contrast, in both orientations.

#### Scenario: Home at 100%

- **WHEN** a person looks at Home at the 100% step
- **THEN** each app label is at least 26 px tall and sits inside its own cell

#### Scenario: The Shade with audio playing

- **WHEN** a stream is playing and the person opens the Shade at 200%
- **THEN** the stream's row text is set in a type role and does not overlap
  its slider
