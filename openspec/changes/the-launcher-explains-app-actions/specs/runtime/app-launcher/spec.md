## Purpose
Provide a refreshable portrait Apps catalog whose cards explain the action a person will take.
## ADDED Requirements
### Requirement: The Apps catalog SHALL explain launch actions
<!-- UNVERIFIED: current native evidence shows generic endpoint cards; implementation is proposed. -->
The shell SHALL present useful desktop applications with an action-oriented name and short description, and SHALL hide or demote known implementation endpoints that do not represent an independent person-facing task. It SHALL retain the existing built-in Terminal, Monitor, New terminal, and Help actions.
#### Scenario: A catalog includes internal Foot endpoints
- **WHEN** Apps refreshes entries including Foot Client or Foot Server
- **THEN** the visible page does not present those endpoints as unexplained peer applications
#### Scenario: An ordinary discovered application is available
- **WHEN** a non-internal desktop entry is visible
- **THEN** it remains launchable through the existing GLib catalog path
### Requirement: Curation SHALL preserve recovery and touch geometry
<!-- UNVERIFIED: requires host and board acceptance. -->
The catalog SHALL preserve page bounds, 56px-or-larger actionable targets, and visible Back/Apps recovery when a launch fails.
#### Scenario: A curated application fails to launch
- **WHEN** launch reports an error
- **THEN** short user-facing text and Back remain visible without exposing a raw path
