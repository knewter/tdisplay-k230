# Device tree evidence and corrections

Investigated 2026-09-20 against `ruyisdk/linux-xuantie-kernel` @
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529` and the vendored sources in `repo/`.

Published artifacts built from this:

- Board → DTS map: <https://claude.ai/artifact/82HR7t9NSQq15Y4M6k1QA5>
- SoC dtsi vs board dts overlay mechanics: <https://claude.ai/artifact/PTKTHepqyiYZGRYRCyfY76>
- Panel dtsi anatomy + RM69A10 draft: <https://claude.ai/artifact/FYjeGutLuowSXecVch2zYQ>

## Corrections to `docs/findings.md`

### Wi-Fi is on MMC0/SDIO0, not MMC1

`findings.md` says "RTL8189FTV on SDIO (**MMC1**, GPIO26-31)". That is wrong on
both the controller and the pins.

Evidence:

1. `repo/schematic/T-Display K230_V1.0_NEW.pdf` — nets `WIFI_CLK`, `WIFI_CMD`,
   `WIFI_D0`–`WIFI_D3` land on the SoC's `MMC0_CLK`, `MMC0_CMD`, `MMC0_D0`–`D3`
   balls (A5, D6, D5, C5, B5, C6). These are dedicated pads, not FPIOA pins.
2. `repo/canmv_k230/src/rtsmart/rtsmart/kernel/bsp/maix3/configs/k230_canmv_v3p0_defconfig`:
   ```
   CONFIG_REALTEK_SDIO_DEV0=y
   CONFIG_SDCARD_ON_SDIO_DEV1=y
   CONFIG_SDCARD_ON_SDIO_DEV=1
   ```
3. `repo/canmv_k230/src/uboot/uboot/arch/riscv/dts/k230_canmv_v3p0.dts` muxes
   IO54–59 as `MMC1_*` with the comment `// MMC1 -> TFCARD`, and leaves IO26–31
   at `SEL=0` (plain GPIO) under the comment `// 26-35 ext jp` — they go to the
   expansion header.

So: **Wi-Fi → `&mmc_sd0` (sdhci0@91580000). TF card → `&mmc_sd1`
(sdhci1@91581000).** That also matches U-Boot's `mmc_boot_dev_num = 1`.

GPIO26–31 *can* be muxed to `MMC1_*` (FPIOA function 1) — that is presumably
where the original claim came from — but they are not muxed that way on this
board, and MMC1 is already spoken for by the card.

### `CONFIG_RT_USING_REALTEK` *is* set for this board

`findings.md` says "the board defconfig does not enable it, so it is likely not
compiled into the shipped image at all." The Kconfig default is `n`, but
`k230_canmv_v3p0_defconfig` sets `CONFIG_RT_USING_REALTEK=y` alongside
`CONFIG_REALTEK_SDIO_DEV0=y`.

So the driver is built in. The remaining root cause for the dead radio is the
empty `Set_WLAN_Power_On()` stub — `IO45_WIFI_EN` gates an RT9080-33GJ5 LDO
that produces `WIFI_3V3`, and nothing ever asserts it. That part of
`findings.md` stands.

## The U-Boot DTS is this board's DTS

`repo/canmv_k230/src/uboot/uboot/arch/riscv/dts/k230_canmv_v3p0.dts` has
`model = "kendryte k230 canmv v3.0"`, which is exactly the string U-Boot prints
on our hardware (`findings.md`). It is therefore a primary source for this
board's pin assignments, not a reference-board approximation.

Confirmed from it, cross-checked against the FPIOA alternate-function table in
`repo/canmv_k230/src/canmv/port/machine/machine_fpioa.c`
(`SEL=0` is GPIO, 1–4 are the alternates in column order):

| Pin | SEL | Function | Use |
| --- | --- | --- | --- |
| IO22 | 0 | GPIO22 | `lcd_rst` — AMOLED reset |
| IO23 | 0 | GPIO23 | commented `hdmi_int`; is our touch INT |
| IO24 | 0 | GPIO24 | commented `hdmi_rset`; is our touch RST |
| IO25 | 0 | GPIO25 | `LCD_EN` |
| IO36/37 | 1 | IIC3_SCL/SDA | touch bus (comment on IO37 says `BT_UART_TXD`; wrong) |
| IO38/39 | 1 | UART0_TXD/RXD | console via CH342 ch0 |
| IO40/41 | 2 | IIC1_SCL/SDA | camera |
| IO45 | 0 | GPIO45 | `IO45_WIFI_EN` |
| IO48/49 | 3 | IIC0_SCL/SDA | — |
| IO7/8 | 2 | IIC4_SCL/SDA | — |
| IO50/51 | 1 | UART3_TXD/RXD | CH342 ch1 |
| IO54–59 | 2 | MMC1_CMD/CLK/D0–D3 | TF card |

Touch is on **i2c3** at **0x5d** — confirmed independently by
`CONFIG_TOUCH_GT9895_I2C_DEV="i2c3"` / `CONFIG_TOUCH_GT9895_I2C_ADDR=0x5d`.

LCD reset and enable pins confirmed by `canmv_k230/include/config/auto.conf`:
`CONFIG_MPP_DSI_LCD_RESET_PIN=22`, `CONFIG_MPP_DSI_LCD_BACKLIGHT_PIN=25`.

## Structural facts about the Linux DTS

- **There is no pinctrl in the Linux device tree.** No `pinctrl`, `pinmux`,
  `pinctrl-names` or regulator of any kind appears in `k230.dtsi`,
  `k230-canmv-v3.dts`, `k230-canmv-v3-lcd.dts` or
  `display-st7701-480x800.dtsi`. FPIOA muxing is done by U-Boot via
  `pinctrl-single` against `0x91105000` and inherited. Our board `.dts` cannot
  set pin functions.
- `k230.dtsi` is 857 lines with 56 hand-written nodes, and its **last line**
  is `#include "k230_clock_provider.dtsi"` — another 3,354 lines that add 133
  children under `sysctl_clock`. Easy to miss when skimming.
- Both board files compile clean at the pinned commit (warnings only). Verified
  locally with `cpp -nostdinc -I include` + `dtc`. The flattened
  `k230-canmv-v3-lcd` tree is **234 nodes, 184 okay, 11 disabled**. The eleven
  left off are `uart1`, `uart2`, `uart4`, `i2c0`, `i2c1`, `i2c2`, `spi0`,
  `spi1`, `spi2`, `mipi1`, `mipi2`.
- Neither `k230-canmv-v3.dtb` nor `k230-canmv-v3-lcd.dtb` is in
  `arch/riscv/boot/dts/canaan/Makefile`. Buildroot builds them by name.
- The whole display chain (`display-subsystem`, `vo@90840000`, `dsi@90850000`)
  is already `status = "okay"` in `k230.dtsi`. A board file never enables the
  display; it only attaches a panel to `&dsi` port 1.
- `compatible = "canaan, k230-sysctl-power"` has a space in it. Do not "fix"
  it — `drivers/soc/canaan/k230-power-domains.c` carries the same string.
- `&mipi0` is re-pointed by the board file, which rewrites `reg`, `interrupts`
  and `resets` on a node that was already `okay`. `dtc` reports this as
  "also defined at k230-canmv-v3.dts:92".
- GPIO bank trap: `gpio0_ports` is pins 0–31 and `gpio1_ports` is 32–63, each
  numbering from zero. Every reference-board GPIO is in bank 0, so this never
  bites upstream. Our Wi-Fi enable is **`<&gpio1_ports 13>`**, not 45.
- Console: the SDK's default env sets `console=ttyS1`, but `uart1` is never
  enabled in any of these device trees, so there is no `ttyS1`. Aliases give
  `serial0 = &uart0` and `serial3 = &uart3`. Try `ttyS0` first, `ttyS3` second.
  (Reasoning from the DTS; not yet observed on hardware.)
- `k230.dtsi` declares a single `cpu@0`. The second C908 is not in the Linux
  device tree.

## Upstream nodes that conflict with our board

`k230-canmv-v3.dts` declares an LT9611 HDMI bridge on `&i2c3` with
`reset-gpios = <&gpio0_ports 24>` and `interrupts = <23 ...>`. On our board
those two GPIOs are the GT9895's RST and INT. The I2C addresses do not collide
(0x3b vs 0x5d); the GPIOs do. Our board file must not carry the LT9611 node as
written.

Whether HDMI and the AMOLED touch are physically mutually exclusive on this
board has **not** been established — the schematic around that section has not
been read. Treat it as a DT-level constraint for now.

## Panel notes for change 3

Full detail is in the third artifact. The load-bearing points:

- `panel-canaan-universal.c` is fully DT-driven, so the RM69A10 is a new
  `.dtsi`, not a new driver — **with two exceptions**, both hardcoded in
  `probe()` and not expressible in the device tree:
  - `dsi->mode_flags = MIPI_DSI_MODE_VIDEO_SYNC_PULSE`. The vendor runs this
    panel in `K_BURST_MODE`.
  - `dsi->format = MIPI_DSI_FMT_RGB888`.
- **The reset line is only pulsed in `probe`.** The equivalent block in
  `canaan_panel_prepare()` is present but entirely commented out, while
  `canaan_panel_unprepare()` drives both the reset and enable GPIOs low. Any
  modeset or suspend cycle therefore leaves the panel in reset and `prepare`
  will DCS into a dead panel. This may be a prerequisite patch, not a polish
  item.
- `panel-init-sequence` framing is `data_type, delay_ms, payload_length,
  payload…` repeated. `delay` is a `u8`, so 255 ms is the longest expressible
  wait. `payload_length` includes the DCS command byte. The `data_type` byte is
  effectively decorative — 0x05, 0x15 and 0x39 all route to
  `mipi_dsi_dcs_write_buffer`, which picks the real packet type from the length;
  anything else aborts the probe.
- `panel-width-mm`/`panel-height-mm` in the reference contain **pixel counts**
  (480, 800), not millimetres. The driver feeds them to
  `connector->display_info.width_mm`. For a 4.1" 568x1232 panel the real figures
  are about 44 x 95 mm (computed from the stated diagonal, not measured).
- RM69A10 timings, from `connector_info_list[]` in
  `repo/canmv_k230/src/rtsmart/mpp/userapps/src/connector/mpi_connector.c`:
  ```
  { 39600, 475200, 788, 568, 40, 140, 40, 1268, 1232, 4, 16, 16 }
     pclk  phyclk  htot hact hsl hbp hfp vtot vact vsl vbp vfp   (kHz / pixels)
  ```
  2 lanes, `K_BURST_MODE`, `intr_line = 9` (so `&vo { vth_line = <9>; }`).
- **The enum name says 60FPS; the numbers say 39.6 Hz.**
  39.6 MHz / (788 x 1268) = 39.63 Hz. The numbers are self-consistent —
  39.6 MHz x 24 bpp / 2 lanes = 475.2 Mbps/lane, exactly the `phyclk` in the
  same row — so the pixel clock is real and the name is wrong. 60 Hz would need
  roughly 60 MHz; the shipped firmware does not attempt it.
- The transcribed `panel-init-sequence` for the RM69A10 (13 commands, 75 bytes,
  parses cleanly under the driver's own framing algorithm) is in the third
  artifact.

## Not established — do not assume

- Which I2C bus carries the BQ25896 charger and BQ27220 fuel gauge.
- Which SPI controller and chip-select the SX1262 / LR2021 uses.
- Whether IO25 (`LCD_EN`) gates a supply rail or is a logic-level enable.
- Whether the HDMI connector and the AMOLED touch are electrically exclusive.
- Whether the RM69A10 tolerates non-burst sync-pulse video mode at these
  timings.
