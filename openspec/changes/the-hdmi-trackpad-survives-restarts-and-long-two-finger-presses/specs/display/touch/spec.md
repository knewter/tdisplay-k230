## ADDED Requirements

### Requirement: HDMI trackpad gestures survive a compositor restart and long presses

*Grounding: host tests in `nix/touch-trackpad`; on-board behaviour is
<!-- UNVERIFIED --> until tasks 2.1 and 2.2 are recorded.*

When the compositor has restarted since the last two-finger gesture, the
trackpad relay SHALL reconnect and still deliver the next qualified two-finger
gesture rather than drop it. A multi-finger contact that stays still SHALL
reach libinput only when it moves, changes spread or contact count, or lifts,
so a still two-finger press of any duration is recognized as a two-finger tap
(secondary click).

#### Scenario: First swipe after a shell deployment

- **WHEN** sway has restarted and the operator makes a two-finger swipe on Home
- **THEN** the swipe is delivered to the shell and Home pages

#### Scenario: Long two-finger press

- **WHEN** the operator holds two still fingers on the trackpad for about a
  second and lifts them
- **THEN** a secondary click is delivered at the cursor
