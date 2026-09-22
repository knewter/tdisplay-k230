## Purpose

Provides a bounded set of useful offline applications and an on-device guide for
the portrait shell, so a person can learn and use the image without a network,
installer, or physical keyboard.

## ADDED Requirements

### Requirement: The shell exposes a bounded offline application set

The shell SHALL expose Help and the existing Terminal action through the portrait
Apps flow. It SHALL add only a small, explicitly reviewed set of portrait-usable
desktop entries selected from packages that build for the pinned riscv64 image and
fit the measured closure and startup budgets. An editor and a file browser are
preferred candidates when an existing dependency satisfies those constraints;
the image SHALL not gain a network installer, package manager UI, AtomVM, Dozer,
or a general desktop suite for this capability. <!-- UNVERIFIED: candidate package availability and final closure cost require host evaluation. -->

#### Scenario: A user opens the offline app set

- **WHEN** the user opens Apps with no network connection
- **THEN** Help, Terminal, and every selected offline application appear as
  readable touch targets and do not require network access to launch

#### Scenario: A candidate fails the image checks

- **WHEN** a proposed editor or file browser fails the pinned riscv64 build,
  closure, startup, or portrait usability check
- **THEN** it is omitted and the remaining Apps and Help flow remain usable

### Requirement: Help explains the keyboard-free shell

The shell SHALL provide an offline Help surface reachable from Apps and SHALL
describe the purpose and action of Apps, Keyboard, Windows/Home, System, Back,
paging, and the terminal and monitor actions. Help SHALL be readable at
568x1232 in portrait mode, support touch navigation back to Apps, and avoid
requiring a network, physical keyboard, or text entry. <!-- UNVERIFIED: final
font size and physical-finger readability require board evidence. -->

#### Scenario: A new user reads the controls

- **WHEN** the user taps Help and pages through its content
- **THEN** each persistent control and launcher navigation action has a concise
  visible explanation

#### Scenario: A user leaves Help

- **WHEN** the user taps Back from Help
- **THEN** Help closes and the user returns to the launcher or persistent shell
  controls without losing the existing touch actions

### Requirement: Offline app additions are checked before image integration

Before an app is added to the image, the project SHALL record its desktop ID,
package source, riscv64 build result, closure delta, startup result, and injected
portrait touch result. Physical finger accuracy, reboot persistence, and final
glass readability SHALL remain separately labelled evidence rather than inferred
from host or injected checks.

#### Scenario: A reviewer checks an app addition

- **WHEN** a reviewer examines the app evidence
- **THEN** the record distinguishes package/build and injected workflow checks
  from physical-touch, reboot, and final-panel checks, and names any failed or
  unverified check

