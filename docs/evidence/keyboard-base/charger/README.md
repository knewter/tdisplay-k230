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

- **Discharging reading:** none was taken with the cable out.
- **Charger:** the `ti,bq25896` node is not added, because the driver
  needs the charger's INT line, whose wiring is unknown (task 5.2a). So
  there is no `online` value and no before/after register record yet.

## Unplug and replug (2026-10-14 22:17–22:32 CDT)

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
