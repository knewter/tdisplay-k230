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
