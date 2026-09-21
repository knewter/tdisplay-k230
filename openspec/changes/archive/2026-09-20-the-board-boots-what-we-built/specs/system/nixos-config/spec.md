## MODIFIED Requirements

### Requirement: The system boots to a console prompt

*Grounded on both halves. QEMU: `docs/evidence/qemu-boot.txt`. Hardware: a
root prompt was reached on the board over the CH342 serial console at 115200
8N1, with no display, no keyboard and no network, and commands were run at it
(`docs/evidence/hardware-userspace.md`). The transcript format is shared, as
the requirement intends.*

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

#### Scenario: Someone reads an emulated boot as a claim about the board

- **WHEN** an emulated boot succeeds
- **THEN** the evidence records which machine was emulated and what it does not model, so the claim cannot be over-read
