## ADDED Requirements

### Requirement: The BootROM's USB recovery path is characterised, not assumed

Whether this board can be recovered over USB with no bootloader on the card
SHALL be established by observation and written down, including no-card entry,
SW3/BOOT0 entry, host enumeration, and the tool or explicit reason recovery is
unavailable. The result SHALL distinguish BootROM recovery from U-Boot UMS and
shall not claim success from UMS evidence alone.

<!-- UNVERIFIED: no-card and SW3 BootROM entry have not yet been observed. -->

*Grounding for the test target: `docs/uboot-ums.md` §5 describes Canaan's
`do_k230_dfu()` path and the `kendryte/k230_flash_py` host tool; the schematic
places SW3 between BOOT0 and ground. These sources identify what must be tested
but do not establish that this board enters BootROM recovery.*

#### Scenario: No bootable card is present

- **WHEN** the TF card is removed and the board is powered through the data USB-C
- **THEN** the evidence records the serial state, host USB result, VID/PID if any, and a reproducible pass or negative result

#### Scenario: The BOOT0 button is held

- **WHEN** SW3 is held while the board with its card is powered on
- **THEN** the evidence records the button state, serial state, host USB result, VID/PID if any, and a reproducible pass or negative result

#### Scenario: A BootROM device is observed

- **WHEN** either entry test enumerates a BootROM device
- **THEN** the documented `k230_flash` procedure writes a disposable deliberately nonbootable-stage1 card and a later boot verifies the result; an unsafe or unattempted write leaves this scenario incomplete and is recorded as such

#### Scenario: BootROM entry does not work

- **WHEN** both entry tests produce no BootROM device
- **THEN** the documented recovery answer says so explicitly and points to the tested card-reader recovery and U-Boot UMS paths
