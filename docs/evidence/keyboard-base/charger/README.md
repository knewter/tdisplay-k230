# Fuel gauge under Linux (task 5.3, partial; board-read)

`gauge-2026-10-13.log` is from system `l002j7bg…` (the first build with
`nix/patches/mainline/bq27xxx-bq27220.patch`) at 22:48 UTC. It records:

- the `bq27xxx` driver binding the `ti,bq27220` node at
  `/soc/i2c@91409000/fuel-gauge@55`;
- `bq27220-0` reporting Full, 100 %, 4.207 V, 0 A, 36.6 °C and 3000 mAh
  design capacity.

USB-C was connected and the cell was full, so the current was 0. That
matches the probe's raw registers.

## Not yet covered

Nothing for task 5.3; the cable-out `online` reading is at the end.

## Unplug and replug (2026-10-13 22:17–22:32 CDT)

Evidence class: **board-read** (operator unplugged and replugged USB-C on
request). `unplug-replug-2026-10-14.log` samples the gauge's `power_supply`
and the charger's REG0B (status) and REG11 (VBUS) once a second, read-only
(`i2cget -y 1 0x6b`, no driver bound to 0x6B).

| Time | Event | Gauge | Charger |
| --- | --- | --- | --- |
| 22:17–22:26 | on USB, charge done | 100 %, 4.209 V, 0 mA, `Full` | REG0B 0x5e (adapter, charge termination done, power good), REG11 0x97 (VBUS 4.9 V) |
| 22:26:1x | USB-C unplugged | -400 to -411 mA steady, `Full` | REG0B 0x02 (no input), REG11 0x17 |
| 22:30:51 | after ~4.6 min | 99 %, ~4.04 V | |
| 22:31:3x | USB-C replugged | +719 mA, later +672 mA, `Full` | REG0B 0x56 (fast charging, power good), REG11 0x98 |

Discharge reading: about 405 mA for 5.3 min, roughly 36 mAh, which moved the
gauge one percent of its 3000 mAh. The gauge said `Full` throughout,
including while discharging and charging: bq27xxx reports Full whenever the
BQ27220's FC flag is set, and that flag stays set after termination until the
charge falls below its clear threshold. `nix/patches/mainline/
bq27xxx-bq27220-status.patch` makes a nonzero current decide.

## Where the charger's INT goes (task 5.2a)

LILYGO's pin map (`Xinyuan-LilyGO/T-Display-K230`,
`k230_bsp/docs/HARDWARE_PINMAP.md`) lists the BQ25896's I2C lines only. During
the same unplug and replug, `gpiomon -e both` watched every K230 GPIO line not
already claimed (gpiochip0 all but 2, 22, 23, 24, 25; gpiochip1 all but 10,
11, 20; every one already an input, so requesting it changed nothing). Neither
event produced an edge on any line (`mon0.txt` and `mon1.txt` were empty).

Limit: a pad muxed to a non-GPIO function would not show an edge either, and
this kernel's pinctrl debugfs prints the same placeholder for every pad, so
the mux of unclaimed pads is not shown here. The XL9555 has no interrupt
output wired either, so a charger INT routed to an expander input could not
be caught by polling a 256 µs pulse. Result: INT reaches no GPIO-muxed K230
line. The charger driver therefore polls (`bq25890-poll-without-irq.patch`).

## The charger node (task 5.2)

`nix/dts/k230-tdisplay-mainline-drm-common.dtsi` adds `charger@6b`,
`compatible = "ti,bq25896"`, with `linux,skip-reset` and
`linux,read-back-settings`. The driver therefore reads the charge parameters
from the chip; the `ti,*` values are still required by the binding and are set
to what the registers already hold, so nothing changes if read-back is ever
dropped. Host proof: `nix build .#deviceTreeMainlineDrm` (2026-10-14, built
`k230-tdisplay-mainline-drm.dtb`; `dtc` shows the node).

Decoded from the probe's registers (`../probe/probe-2026-10-13T193545Z.log`)
against the BQ25896 datasheet:

| Register | Value | Field | Decoded | Node property / driver |
| --- | --- | --- | --- | --- |
| REG00 | 0x7f | EN_HIZ, EN_ILIM, IINLIM | 0, 1, 3250 mA | read back (`input_current_limit` 3250000) |
| REG02 | 0x11 | CONV_RATE, ICO_EN, AUTO_DPDM | 0, 1, 1 | **driver writes CONV_RATE=1** (continuous ADC) |
| REG03 | 0x1a | OTG_CONFIG, CHG_CONFIG, SYS_MIN | 0, 1, 3500 mV | `ti,minimum-sys-voltage` 3500000; driver writes CHG_CONFIG=1 (already 1) |
| REG04 | 0x0b | ICHG | 704 mA | `ti,charge-current` 704000 |
| REG05 | 0x13 | IPRECHG, ITERM | 128 mA, 256 mA | `ti,precharge-current` 128000, `ti,termination-current` 256000 |
| REG06 | 0x72 | VREG, BATLOWV, VRECHG | 4288 mV, 3.0 V, 100 mV | `ti,battery-regulation-voltage` 4288000 |
| REG07 | 0x8d | EN_TERM, WATCHDOG, EN_TIMER, CHG_TIMER | 1, disabled, 1, 12 h | driver writes WATCHDOG=0 (already 0) |
| REG08 | 0x03 | BAT_COMP, VCLAMP, TREG | 0, 0, 120 °C | `ti,thermal-regulation-threshold` 120 |
| REG0A | 0x73 | BOOSTV, BOOST_LIM | 4998 mV, 1.4 A | `ti,boost-voltage` 4998000, `ti,boost-max-current` 1400000 |

## Bound on the board (tasks 5.2, 5.2a, 5.3; board-read)

System `9lp7f072…` (kernel 7.3.0-rc5, `bq25890-poll-without-irq.patch` and
`bq27xxx-bq27220-status.patch`). `dmesg`: `bq25890-charger 1-006b: no
interrupt; polling every 2000 ms`. `registers-bound-2026-10-14.log`
(05:02:48 UTC, `i2cget -f`, read-only) against the probe:

- REG02 0x11 → 0x51: CONV_RATE, the one field named above. No other
  configuration register (0x00–0x0A, 0x0D, 0x14) changed.
- REG0B and 0x0E–0x13 are status and ADC readings and move with the
  charge state (REG0B 0x56 here: fast charging, power good).

`bq25890-charger-0` reports type USB, `online` 1, BQ25896, constant charge
current 704000, voltage 4288000, input limit 3250000.

`devmem` is installed on this image (`STRICT_DEVMEM`, `IO_STRICT_DEVMEM`
off, `I2C_CHARDEV`). Reading the IOMUX block at `0x91105000 + 4 * pin`
returned 0x800019d1 for all 64 pads, so it does not reveal the pad mux either;
the 5.2a limit stands.

## Charger Hi-Z: gauge status follows the current (2026-10-14; board-read)

`hiz-2026-10-14.log`, 05:01:07–05:02:25 UTC. Writing `0` to the charger's
`online` sets EN_HIZ (REG00 0x7f → 0xff): the input is disconnected and the
battery carries the system, as with the cable out, but from software. Writing
`1` clears it. Sampled every 5 s:

| Phase | Charger | Gauge |
| --- | --- | --- |
| before | online 1, Full | `Full`, 0 mA, 4.201 V, 100 % |
| Hi-Z, 45 s | online 0, Discharging | `Discharging`, -394 to -417 mA, 4.121 → 4.096 V |
| restored, 30 s | online 1, Charging | `Charging`, +574 mA tapering to +396 mA, 4.284 V |

Before `bq27xxx-bq27220-status.patch` the gauge said `Full` in both
directions (unplug log above). This run used Hi-Z, not a pulled cable, so it
proves the status mapping and the charger's `online` reporting, not the
cable-out `online` reading.

## Cable out with the charger bound (2026-10-14; board-read)

`cable-out-2026-10-14.log`, 05:11:14–05:11:19 UTC, system `9lp7f072…`. The
operator pulled USB-C and reported it; the samples were read over SSH
afterwards.

- Charger: `online` 0, `Discharging`; REG00 0x7f (EN_HIZ clear, so this is
  the cable, not Hi-Z), REG0B 0x02 (no input), REG11 0x00 (no VBUS).
- Gauge: `Discharging`, -394 to -491 mA, 4.118 → 4.093 V, 100 %.
