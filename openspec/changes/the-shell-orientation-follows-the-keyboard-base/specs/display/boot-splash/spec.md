## ADDED Requirements

### Requirement: The boot animation and the shell's first frame share one orientation

*Grounding: the boot animation's orientation rule is the boot text-effects change's design D15. The shared decision with the shell is <!-- UNVERIFIED: no boot with this change has run. -->*

The boot animation and the shell's first frame SHALL be in the same orientation, decided by whether the keyboard base is attached: portrait without it, the keyboard-case landscape with it. When the stage 1 animation and the Linux decision agree there SHALL be no rotation at the hand-off. When they disagree, the Linux decision SHALL win and the disagreement SHALL be logged.

#### Scenario: Both agree

- **WHEN** the board boots in the base (or out of it) and stage 1 and Linux see the same state
- **THEN** the animation, the hand-off and the shell's first frame are all in that orientation

#### Scenario: They disagree

- **WHEN** the base is attached or removed between stage 1's probe and Linux's
- **THEN** the shell's first frame follows Linux and the log records both values
