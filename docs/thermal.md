# Thermal protection on the K230: what exists, and what does not

Prompted by a direct question — whether it is safe to leave the board powered
unattended. Short answer: **the temperature is readable, and nothing acts on
it.** No throttling, no shutdown. That is a property of the vendor kernel and
device tree, not of anything we configured.

All symbol evidence below is from `System.map` of our own build,
`linux-riscv64-unknown-linux-gnu-6.6.36-xuantie`.

## What works

**The sensor has a driver, and it is built in.**

```
t canaan_thermal_probe
t canaan_thermal_init
d __initcall__kmod_canaan_thermal__258_122_canaan_thermal_init6
d of_canaan_thermal_match
```

`drivers/thermal/canaan_thermal.c`, enabled by `CONFIG_CANAAN_THERMAL`, which
is `default ARCH_CANAAN` and so comes in without being named in
`k230_defconfig`. It matches `tsensor@91107000`, `compatible =
"canaan,k230-tsensor"`, which is `status = "okay"` in `k230.dtsi:850`.

**The thermal core is built in** — 306 `thermal*` symbols, including
`thermal_zone_device_register_with_trips` and `thermal_zone_device_critical`,
the emergency-shutdown path.

So `/sys/class/thermal/thermal_zone0/temp` should exist on the booted board.
**Unverified** — the board was powered down before this was checked, and it is
the first thing to run next session.

## What does not work, and why

**1. The driver registers a zone with no trip points, deliberately.**

`canaan_thermal.c:86`:

```c
data->tz = thermal_tripless_zone_device_register(
```

`thermal_tripless_*` is exactly what it says. A zone with no trips never
crosses a trip, so the thermal core never invokes a governor and never calls
`thermal_zone_device_critical()`. The driver is a thermometer.

**2. No device tree supplies trips either.** There is no `thermal-zones` node
in any K230 device tree in the Xuantie tree — the usual place a board declares
`trip-point` / `critical` and binds a cooling device. So the gap is not closed
from the DT side.

**3. There is no cooling device to bind even if a trip existed.** The only
cpufreq symbol in the kernel is `cpufreq_add_device`; there is no
`cpufreq_register_driver`, so no cpufreq driver is present and the CPU has no
DVFS states Linux can select. The conventional response to a passive trip —
throttle the CPU — has nothing to act on.

That leaves a critical trip forcing an orderly poweroff as the only meaningful
protection available, and it is not configured.

## What this means in practice

- Nothing in software will stop this board getting hot. Any protection is
  whatever the silicon does on its own, which we have not characterised.
- The RT-Smart core is still running its own firmware on the second C908
  (see `hardware-userspace.md`), and whether *it* implements a thermal
  response is unknown and outside our kernel.
- Powering the board down when leaving it unattended is, on this evidence,
  the correct instinct rather than excessive caution.

## Proposed next steps

Cheap, in order:

1. **Read the sensor.** `cat /sys/class/thermal/thermal_zone*/temp` at idle,
   then after a sustained load, and write both down. This costs one boot and
   tells us whether the part even runs warm. It may make the rest moot.
2. **Find the hardware limit.** The K230 datasheet's operating range, and
   whether the TSENSOR block has its own hardware trip independent of Linux.
   `canaan_thermal.c` and the `hardlock = <2>` property in the DT node are the
   places to look.
3. **Add a critical trip.** A `thermal-zones` node with a `critical` trip
   referencing the tsensor, which gives `thermal_zone_device_critical()`
   something to fire. This needs step 2 first — a made-up threshold is worse
   than none, because it either never fires or shuts the board down during
   normal work.
4. **Only then consider throttling**, which means a cpufreq driver and OPP
   table, and is a substantially larger piece of work for a board that may
   simply never get hot enough to need it.

Steps 1 and 2 are research. Step 3 is a small change. Step 4 should not be
started until 1 and 2 say it is needed.
