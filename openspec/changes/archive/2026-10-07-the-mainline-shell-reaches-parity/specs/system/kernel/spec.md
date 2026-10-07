## ADDED Requirements

### Requirement: Every mainline kernel variant carries the proven clock and firewall fixes
Each mainline kernel the repository builds (console and DRM) SHALL keep running the
clocks that physical bisection showed the SoC needs (`spi2axi`, the display DDR port
`vpu_ddrcp2`) and SHALL carry the same firewall kernel configuration as the vendor
kernel. The protected normal system is not changed by this.

#### Scenario: Console mainline boot survives unused-clock cleanup
- **WHEN** an operator boots the console mainline variant through the guarded trial with ordinary clock cleanup
- **THEN** the serial console reaches a qualified root login, as the DRM variant already does
<!-- Observed 2026-10-06 (docs/evidence/mainline-shell-parity-2026-10-06/README.md): console variant qualified login with cleanup, then rebooted itself to normal. -->

#### Scenario: Firewall unit starts on mainline
- **WHEN** the full mainline shell boots
- **THEN** `systemctl is-active firewall` reports active on the serial console
<!-- Observed 2026-10-06 (docs/evidence/mainline-shell-parity-2026-10-06/README.md): firewall active on the full mainline shell. -->

### Requirement: The K230 clock gates match the vendor register map
Every mainline gate SHALL use the register bit the vendor clock tree uses, and
any deliberate difference (a bit the vendor shares between clocks, or a vendor
gate mainline leaves unmodelled) SHALL be recorded with the reason, so a driver
claiming one clock cannot silently change another device.

#### Scenario: Comparison is committed
- **WHEN** a reader opens the committed vendor-versus-mainline gate comparison
- **THEN** every gate shows matching register and bit, or a recorded reason: `usb_480m`/`usb_100m` share 0x100 bit 0 exactly as the vendor `usb_clk480`/`usb_clk100` do; the display `clkext` gate (0x74 bit 5) stays unmodelled because no Linux consumer exists and modelling it would expose it to unused-clock cleanup

### Requirement: SoC temperature is readable under mainline
The mainline kernel SHALL expose the K230 thermal sensor so that a person at the
console can read the SoC temperature, matching the vendor kernel's reading within
the sensor's resolution.

#### Scenario: Temperature reads back
- **WHEN** an operator reads the thermal zone on the mainline shell
- **THEN** a plausible SoC temperature is reported and it changes under load
<!-- Observed 2026-10-06 (docs/evidence/mainline-shell-parity-2026-10-06/README.md): 52.4 °C idle, 54.5 °C after 60 s load (vendor driver reports raw codes). -->

### Requirement: Remaining vendor-only drivers have a recorded disposition
ADC, PWM and crypto SHALL each be recorded as forward-ported, or as an explicit
non-goal naming which shipped service would need them; none may be silently absent.

#### Scenario: Inventory lists each driver's disposition
- **WHEN** a reader opens the mainline driver inventory
- **THEN** ADC, PWM and crypto each show ported or non-goal with a reason and date
