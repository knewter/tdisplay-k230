# runtime/app-launcher Specification

## Purpose
Provide a refreshable portrait Apps catalog whose cards explain the action a person will take.

## Requirements

### Requirement: The Apps catalog SHALL explain launch actions
The shell SHALL present useful desktop applications with an action-oriented name and short description, and SHALL hide or demote known implementation endpoints that do not represent an independent person-facing task. It SHALL retain the existing built-in Terminal, Monitor, New terminal, and Help actions.

*Grounding: observed on hardware 2026-10-08 (`docs/evidence/launcher-curation/operator-board-2026-10-08.md`): the coherent shell's drawer omits Foot Client/Foot Server and shows Foot as Terminal and Htop as Monitor (native capture plus operator report); the bar-session `touch-launcher` policy is host-tested (`docs/evidence/launcher-curation/host.md`).*
<!-- UNVERIFIED: the coherent shell's drawer tiles show names only; the "short description" clause is met only by the bar-session launcher. -->

#### Scenario: A catalog includes internal Foot endpoints
- **WHEN** Apps refreshes entries including Foot Client or Foot Server
- **THEN** the visible page does not present those endpoints as unexplained peer applications

#### Scenario: An ordinary discovered application is available
- **WHEN** a non-internal desktop entry is visible
- **THEN** it remains launchable through the existing GLib catalog path

### Requirement: Curation SHALL preserve recovery and touch geometry
The catalog SHALL preserve page bounds, 56px-or-larger actionable targets, and visible Back/Apps recovery when a launch fails.

*Grounding: observed on hardware 2026-10-08 (`docs/evidence/launcher-curation/operator-board-2026-10-08.md`): a deliberately failing entry took the shell's failure path (`app-launch-process-exited`) and the operator confirmed human text and Back recovery.*

#### Scenario: A curated application fails to launch
- **WHEN** launch reports an error
- **THEN** short user-facing text and Back remain visible without exposing a raw path
