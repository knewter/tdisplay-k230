# Where does the BQ25896 INT go? Public-source search (2026-10-14)

Operator request: "search the web to find the charger signal wire for the
keyboard base, search github for repos that use it". Method: GitHub code and
repository search (`gh`), repository file listings, and LILYGO's wiki and
documentation repository. Result: **not found in any public source.**

- `Xinyuan-LilyGO/T-Display-K230`, `k230_bsp/docs/HARDWARE_PINMAP.md`
  (keyboard-base table, lines 108–133): BQ25896 on I2C4 (GPIO46/47) at 0x6B,
  no INT. The only base interrupt listed is the TCA8418's (GPIO42). The
  XL9555 row names no INT either.
- Same repository, `k230_launcher/k230_phone_ui/src/ui_hardware.c`: no
  charger or XL9555 interrupt code. The launcher polls (`BATTERY_LOW_
  SHUTDOWN_POLL_US 30000000ULL`, line 228) and reads the BQ25896's status and
  ADC registers directly. Its XL9555 use is three LEDs on port 0 (P03–P05).
- LILYGO wiki T-Display-K230 page and `Xinyuan-LilyGO/documentation`
  `cased-version.md` (line 140): the "Schematic" heading is empty. No
  keyboard-base schematic is published in any LILYGO T-Display-K230
  repository. `T-Display-K230_canmv_rt` issue #11 asks LILYGO for the newer
  schematic; no base schematic was posted.
- Community: `caveman99/k230-linux` (`dts/k230-tdisplay.dts` line 102:
  charger and gauge on IIC4, no static nodes, no IRQ) and
  `developing-today/hardware-doc` (same pin map) name no INT. Not fully
  searched (rate limit): `lvzhenhao/T-Display-K230`, `jheidecker/T-Display-K230`,
  `vicliu624/*`.

Consistent with the board result in `README.md` (no GPIO edge on unplug).
The way to settle it is a continuity probe from the BQ25896's INT (pin 1 of
the QFN-24) on the base PCB, or LILYGO's base schematic. Until then the
driver polls every 2 s, which is what LILYGO's firmware does at 30 s.

Evidence class: desk research (web/GitHub), not a board measurement.
