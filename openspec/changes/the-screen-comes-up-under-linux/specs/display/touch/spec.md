## Purpose

Defines what the board does when a person touches the screen.

## ADDED Requirements

### Requirement: Touches are reported as input events

<!-- UNVERIFIED: the GT9895 has not been probed under Linux on this board. -->

The GT9895 controller SHALL be probed and SHALL report touches as standard
Linux input events, with coordinates in the panel's own 568x1232 space so that
a touch lands where it is seen.

*Grounding for the hardware: the schematic gives the controller as a GT9895 on
I2C, with reset on GPIO24, SCL on GPIO36, SDA on GPIO37 and interrupt on
GPIO23. The shipped RT-Smart firmware drives it.*

#### Scenario: A person touches the screen

- **WHEN** the panel is touched
- **THEN** an input event is emitted whose coordinates correspond to where it was touched

#### Scenario: Touch is verified

- **WHEN** touch support is claimed to work
- **THEN** the evidence is a recorded `evtest` session showing coordinates that track a deliberate movement, not only that a device node exists

### Requirement: Touch support is a recorded divergence from upstream

The GT9895 is not supported by the pinned kernel and its support SHALL be
carried as an explicit patch, recorded with what was backported and from where,
so the cost of the pin is visible when the kernel is next moved.

*Grounding: the pinned Xuantie kernel carries `drivers/input/touchscreen/goodix.c`,
which serves the older GT9xx generation. No `goodix_berlin` source is present in
that tree. GT9895 is a Berlin-generation part, supported in mainline from
approximately 6.7; the pinned tree is 6.6-based.*

#### Scenario: The kernel pin is moved

- **WHEN** someone updates the kernel revision
- **THEN** the repository states which patches must be carried forward and why
