## MODIFIED Requirements

### Requirement: The system boots to a console prompt

<!-- UNVERIFIED: the emulated half is grounded by
docs/evidence/qemu-boot.txt, but nothing of ours has booted on the board
yet. Grounded once docs/evidence/hardware-boot.txt exists. -->

The system SHALL boot to an interactive console prompt on the serial console
without a display, a keyboard, or a network.

The console SHALL be the serial console at 115200 8N1, matching the board's
CH342 bridge, so that one transcript format serves both QEMU and hardware.

**This SHALL hold on the physical board, not only under emulation.** A boot
under QEMU's `k230` machine is not evidence for this requirement, because that
machine models neither the vendored boot chain nor the SD card the board loads
from.

#### Scenario: The system boots under emulation

- **WHEN** the system is booted under QEMU's `k230` machine
- **THEN** a console prompt is reached, and the transcript is committed as evidence

#### Scenario: The system boots on the board

- **WHEN** the board is powered on with a flashed card and a data cable attached
- **THEN** a console prompt is reached on `/dev/ttyACM0`, and that transcript is committed as evidence
