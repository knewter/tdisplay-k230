# How our board DTS diverges from the reference

`nix/dts/k230-tdisplay.dts` derives from `canaan/k230-canmv-v3-lcd.dts`,
which is the right base: U-Boot on this hardware prints
`Model: kendryte k230 canmv v3.0`.

Compiled against the real `k230.dtsi` from the pinned Xuantie tree —
**55,156 byte DTB**, and every node verified present in the output rather
than assumed.

| | reference | this board |
| --- | --- | --- |
| `model` | `Canaan CanMV-K230` | `LILYGO T-Display-K230` |
| `compatible` | `canaan,canmv-k230` | `lilygo,t-display-k230`, then the Canaan strings |
| panel | ST7701, 480×800 | **RM69A10, 568×1232** |
| touch | `edt,edt-ft5306` @ 0x38 | **`goodix,gt9895` @ 0x5d** |
| panel dtsi | `display-st7701-480x800.dtsi` | `display-rm69a10-568x1232.dtsi` |
| `vth_line` | 10 | **9** |

Everything else is carried over unchanged: `&uart0`, `&uart3`, `&usb0`,
`&usb1`, `&i2c3`, `&i2c4`, `&mipi0`, and both MMC controllers with the
reference's delay-line values.

## What is NOT diverged, and why that is worth saying

**GPIO22 reset and GPIO25 backlight are the reference's values**, not ours.
`&lcd { dsi_reset-gpios = <&gpio0_ports 22 GPIO_ACTIVE_HIGH>;
backlight_gpio-gpios = <&gpio0_ports 25 GPIO_ACTIVE_HIGH>; }` is copied
verbatim. Before reading that file, `docs/dts-evidence.md` listed "whether
IO25 gates a rail" as unestablished and we had no polarity for the reset at
all.

**The touch GPIOs are unchanged too** — RST 24, INT 23 — even though the
chip differs. Confirmed against the schematic.

**No pinctrl.** There is none in the Linux device tree for this SoC at all;
FPIOA muxing is inherited from U-Boot's own DTS. A board `.dts` here cannot
set pin functions.

## Known-unverified

- The GT9895 node **will not probe** until the `goodix_berlin` backport
  lands. Until then it is inert; the panel is unaffected.
- The upstream non-LCD `k230-canmv-v3.dts` gives its LT9611 HDMI bridge
  `reset-gpios = <&gpio0_ports 24>` and `interrupts = <23 …>` — the touch
  controller's pins. We derive from the **LCD** variant, which has no
  LT9611, so there is no collision. Anyone merging HDMI support back in
  must resolve it.
- Nothing here has been booted.
