## ADDED Requirements

### Requirement: Every mainline kernel variant carries the proven clock and firewall fixes
Each mainline kernel the repository builds (console and DRM) SHALL keep running the
clocks that physical bisection showed the SoC needs (`spi2axi`, the display DDR port
`vpu_ddrcp2`) and SHALL carry the same firewall kernel configuration as the vendor
kernel. The protected normal system is not changed by this.

#### Scenario: Console mainline boot survives unused-clock cleanup
- **WHEN** an operator boots the console mainline variant through the guarded trial with ordinary clock cleanup
- **THEN** the serial console reaches a qualified root login, as the DRM variant already does
<!-- UNVERIFIED: console variant not yet rebuilt or booted with these fixes -->

#### Scenario: Firewall unit starts on mainline
- **WHEN** the full mainline shell boots
- **THEN** `systemctl is-active firewall` reports active on the serial console
<!-- UNVERIFIED: firewall.service failed on the 2026-10-06 full-shell boot -->

### Requirement: The K230 clock table matches the vendor tree for gates the board uses
No two mainline gates SHALL toggle the same register bit, and display gates the
vendor tree defines SHALL be modelled, so a driver claiming one clock cannot
silently change another device.

#### Scenario: USB still enumerates after the USB test-clock gates are separated
- **WHEN** the corrected clock table boots with a USB device attached
- **THEN** the device enumerates as before and `clk_summary` lists distinct register bits for each USB gate
<!-- UNVERIFIED: usb_480m and usb_100m currently share 0x100 bit 0 -->

### Requirement: SoC temperature is readable under mainline
The mainline kernel SHALL expose the K230 thermal sensor so that a person at the
console can read the SoC temperature, matching the vendor kernel's reading within
the sensor's resolution.

#### Scenario: Temperature reads back
- **WHEN** an operator reads the thermal zone on the mainline shell
- **THEN** a plausible SoC temperature is reported and it changes under load
<!-- UNVERIFIED: no thermal driver exists in mainline yet -->

### Requirement: Remaining vendor-only drivers have a recorded disposition
ADC, PWM and crypto SHALL each be recorded as forward-ported, or as an explicit
non-goal naming which shipped service would need them; none may be silently absent.

#### Scenario: Inventory lists each driver's disposition
- **WHEN** a reader opens the mainline driver inventory
- **THEN** ADC, PWM and crypto each show ported or non-goal with a reason and date
