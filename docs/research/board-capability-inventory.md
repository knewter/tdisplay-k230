# Board capability inventory

Compiled 2026-09-25. Answers one question per hardware feature the
LILYGO T-Display-K230 (main board, optional nRF52840 base, optional
nRF9151/keyboard base) is documented to carry: what it is, where it lives,
whether our pinned kernel and device tree can drive it, whether userspace
can use it, and what full support would cost.

## How to read this document

**Grounding tiers**, from `.skills/k230-spec-change/SKILL.md`, strongest
first:

1. **An observation on the board** — a boot log, console transcript,
   photograph committed under `docs/evidence/`.
2. **Vendor source that has been read** — a driver, defconfig or device
   tree, cited by path (ours, or LILYGO's/Canaan's).
3. **Nothing else** — marked `UNVERIFIED` inline.

A datasheet or marketing page is never grounding by itself.

**Support-level column**, one of:

- **Working-and-evidenced** — proven on this physical board; evidence
  file cited.
- **Enabled-but-unverified** — driver built, device tree node `okay`,
  never exercised on hardware.
- **Present-but-not-enabled** — driver exists in our pinned kernel source
  (or a ready reference patch exists) but is off in our defconfig/DT.
- **Missing-driver** — no driver for this exact part in our pinned kernel
  source tree; would need porting or writing.
- **Not-applicable/vendor-RTOS-only** — only usable from the RT-Smart
  core/KPU stack, not from the Linux side we ship.

**Two source trees underpin the driver/config claims below.** Our pinned
kernel is `ruyisdk/linux-xuantie-kernel` @ `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`
(`nix/kernel-src.nix`; unpacked locally at
`/nix/store/bjgv1xn5b66gbz2kxv2aqzr1szp7dk7c-linux-xuantie-k230-src` at the
time of writing, so every "our tree has/lacks X" claim below was checked
by reading that exact checkout's `arch/riscv/configs/k230_defconfig`,
`arch/riscv/boot/dts/canaan/k230.dtsi` and `drivers/`, not inferred).
LILYGO publishes a separate, genuinely detailed BSP,
`Xinyuan-LilyGO/T-Display-K230:k230_bsp/`, as a patch set against
`kendryte/k230_linux_sdk` (`k230_bsp/metadata/upstream_sdk_url.txt` =
`https://github.com/kendryte/k230_linux_sdk.git`, `upstream_sdk_commit.txt`
= `22d02c6b6783a57a3aca7eb3160e313e772cb710`) — that SDK's own buildroot
config vendors the *same* `ruyisdk/linux-xuantie-kernel` tree ours is
pinned to (`docs/findings.md`), and one spot-checked patch
(`0064-input-k230-pmu-pwrkey.patch`) diffs cleanly against context that
matches our tree's `k230.dtsi` verbatim (the `tsensor@91107000` /
`hardlock = <2>` block immediately preceding `security: security {`), so
these patches are very likely a near-direct fit, not merely a similar
board. Treat every LILYGO-patch citation below as **grounding tier 2**
(vendor source read, cited by path/URL) and every "our tree already has
this" claim as **tier 2 from our own checkout** — both stronger than a
datasheet, per the SKILL.md ordering. Nothing in this document is tier-1
(board-observed) unless it cites a `docs/evidence/` file.

---

## Summary: what the board can do

| Feature | Part | Location |
| --- | --- | --- |
| AMOLED panel | RM69A10, 568×1232, MIPI-DSI 2-lane | Main board |
| Touch | GT9895 (Goodix "Berlin" family) | Main board |
| Wi-Fi | RTL8189FTV/RTL8189FS, SDIO | Main board |
| Bluetooth | Generic USB dongle (bundled unit enumerates as a CSR8510 clone, `0a12:0001`) | Accessory over USB host |
| Camera | GC2093, MIPI-CSI2 | Main board |
| HDMI out | Lontium LT9611 bridge, I2C | Main board (diagnostic; shares GPIO23/24 with touch — mutually exclusive) |
| USB Ethernet/modem | Generic USB-class (CDC-ECM/NCM/MBIM/RNDIS/QMI) | Accessory over USB host |
| SD card | TF slot, 4-bit SDIO | Main board |
| LoRa | SX1262 (v1.1+) / LR2021 (v1.3), SPI | Main board |
| I2S amplifier | MAX98357A | Main board (per `feat/speaker`; LILYGO's split docs it on the nRF52840 base) |
| Temp/humidity sensor | AHT20, I2C | nRF52840 base board |
| Charger | BQ25896, I2C | Keyboard/nRF9151 base board |
| Fuel gauge | BQ27220, I2C | Keyboard/nRF9151 base board |
| GPIO expander | XL9555 (PCA9555-compatible) | Keyboard/nRF9151 base board |
| Keyboard controller | TCA8418, I2C matrix scanner | Keyboard/nRF9151 base board |
| Keyboard backlight | PWM4 / GPIO52 | Keyboard/nRF9151 base board |
| Power key | PMU INT0 channel (not a plain GPIO) | Main board |
| BLE/cellular co-processor | nRF52840 (BLE+audio+sensors) / nRF9151 (LTE/NTN/DECT) | Optional base boards, each its own UART link |
| On-chip thermal sensor | K230 `tsensor` | SoC |
| On-chip RTC | K230 `rtc` | SoC |
| On-chip watchdog | Synopsys DesignWare WDT ×2 | SoC |
| On-chip ADC | K230 `adc` | SoC |
| On-chip PWM | K230 `pwm0`/`pwm1` (+ `pwm3_5` group for PWM4) | SoC |
| Video decode/encode | Arm/Canaan MVX (H.264, HEVC, JPEG) | SoC |
| 2D GPU | VG-Lite (Vivante) | SoC |
| NPU/KPU | Canaan KPU + nncase runtime | SoC (closed userspace runtime; see `docs/blob-inventory.md` B1/B2) |
| Crypto engine + TRNG | AES/hash/RSA/RNG/OTP block | SoC |
| Second RISC-V C908 core | 800 MHz hart | SoC |
| USB OTG ×2 | DWC2 dual-role | SoC |

## Summary: what we support today

| Capability | Level | Evidence / spec |
| --- | --- | --- |
| Panel (RM69A10) | Working-and-evidenced | `docs/evidence/panel-lit.md`, `openspec/specs/display/panel/spec.md` |
| Touch (GT9895) | Working-and-evidenced | `docs/evidence/touch-reports.md`, `openspec/specs/display/touch/spec.md` |
| Wi-Fi (RTL8189) | Working-and-evidenced | `openspec/specs/radio/wifi/spec.md` |
| SD card | Working-and-evidenced | `docs/evidence/sd-image.txt`, `openspec/specs/image/sd-layout/spec.md` |
| USB mass-storage host/gadget (UMS) | Working-and-evidenced | `docs/evidence/usb-host-validation.md` |
| USB Ethernet (r8152) | Enabled-but-unverified | `docs/evidence/ethernet-readiness.txt` (interface exists, no cable tested) |
| Software video playback | Working-and-evidenced | `openspec/specs/runtime/video/spec.md` |
| MVX hardware video decode | Enabled-but-unverified (experiment-gated) | `openspec/specs/runtime/video/spec.md`, `docs/evidence/mvx-v4l2-audit.md` |
| VG-Lite 2D GPU (private buffer only) | Enabled-but-unverified | `openspec/specs/runtime/gpu-validation/spec.md` |
| Second core (SMP release) | Not attempted; readiness-only | `openspec/specs/system/second-core-readiness/spec.md` |
| Thermal sensor | Enabled-but-unverified, uncalibrated | `docs/thermal.md` |
| GPIO, on-chip PWM/ADC | Enabled-but-unverified | driver `default ARCH_CANAAN`, DT `okay`, never read from userspace on this board |
| Audio (I2S) | Present-but-not-enabled correctly | board `sound` node describes the on-chip Inno codec, not this board's MAX98357A — see Overlaps |
| Backlight brightness control | Missing (fixed value baked into panel init) | see row below |
| Bluetooth | Missing (kernel config off) | see row below |
| Camera | Missing-driver | see row below |
| Charger / fuel gauge / power key / keyboard base | Missing-DT-node (drivers mostly present in-tree) | see rows below |
| LoRa | Missing-DT-node (SPI disabled) | see row below |
| RTC | Present-but-not-enabled (one Kconfig line) | see row below |
| NPU/KPU | Not-applicable under Linux | `docs/blob-inventory.md` B1/B2 |

## Summary: gaps ordered by value to a handheld user, vs. effort

| Rank | Gap | Value | Effort | Risk |
| --- | --- | --- | --- | --- |
| 1 | Battery %, charge state (BQ25896 + BQ27220) | Very high — no battery UI today | M | Charger register writes are risky; read-only first |
| 2 | Adjustable screen brightness (backlight class) | Very high — brightness is currently fixed | S/M | Low — DSI command writes only |
| 3 | Power key press/long-press → shutdown/wake | Very high — no clean shutdown today | M | Medium — new driver, wakeup path |
| 4 | Bluetooth (generic USB dongle) | High | S | Low — Kconfig only, no DT/patch |
| 5 | RTC (wall-clock across reboots) | Medium-high | S | Low — one Kconfig line, DT already enabled |
| 6 | Keyboard base (TCA8418 + XL9555 + backlight) | High, but only if that accessory is bought | M | Low; watch the shared UART3 conflict (see row) |
| 7 | LoRa (SX1262/LR2021 over spidev) | Medium — niche but a headline feature | M | Medium — RF transmit correctness/regulatory |
| 8 | Camera (GC2093 + ISP) | Medium | L | Low physical risk, largest engineering lift |
| 9 | Audio (MAX98357A route) | High | — owned by `feat/speaker`, not duplicated here | — |
| 10 | Ethernet-over-USB verified link | Low-medium | S | Low — needs only a cable and a test |
| 11 | Watchdog exercised | Low | S | Low |
| 12 | Second C908 core | Speculative/long-term | L | Gated by its own OpenSpec change |
| 13 | HDMI | Low (diagnostic only; conflicts with touch) | M | Low |
| 14 | NPU/KPU | Low today (nothing needs on-device inference) | L, blocked on vendor | closed runtime, see blob inventory |

---

## Detailed inventory

### Display and input

#### RM69A10 AMOLED panel

- **Part / location**: RM69A10, 568×1232 AMOLED, MIPI-DSI 2-lane. Main board.
- **Bus/pins**: DSI; reset `GPIO22` (`GPIO_ACTIVE_HIGH`), enable/backlight-gate
  `GPIO25` (`GPIO_ACTIVE_HIGH`). Cited from `k230-canmv-v3-lcd.dts` via
  `docs/dts-evidence.md` and independently from LILYGO's own
  `k230_bsp/docs/HARDWARE_PINMAP.md` ("RM69A10 AMOLED | `GPIO22` | Output |
  Reset", "... `GPIO25` | Output | Panel enable").
- **Linux driver**: `drivers/gpu/drm/panel/panel-canaan-universal.c`, fully
  DT-driven (compatible `canaan,universal`). Present and patched in our
  kernel (`nix/kernel.nix`: DCS-read backport, reset-timing fix, PHY-wait
  bound, `pm_runtime_get_sync` pin, DT-settable `hsfreqrange`).
- **DT**: `nix/dts/display-rm69a10-568x1232.dtsi` + `nix/dts/k230-tdisplay.dts`,
  `status = "okay"`.
- **Userspace**: DRM/KMS via `libdrm`/`modetest`; `fbset` for the fbdev path.
- **Support level**: **Working-and-evidenced** —
  `docs/evidence/panel-lit.md`, `docs/evidence/sway-first-light.jpg`,
  `openspec/specs/display/panel/spec.md`.
- **Known defect, not yet fixed**: `canaan_panel_prepare()` has its reset
  pulses commented out by the vendor; only `probe()` resets the panel, so
  any later modeset or suspend/resume cycle re-enters `prepare()` without
  a reset and would DCS into a dead panel (`docs/dts-evidence.md`). This
  blocks any future suspend/power-key work on the display side. Effort S
  (already diagnosed, needs the same reset block moved into `prepare()`),
  risk low.
- **Gap — no adjustable brightness**: `SET_DISPLAY_BRIGHTNESS 0xFE` is
  baked into `panel-init-sequence` as a fixed value; there is no
  `/sys/class/backlight` device. LILYGO's own BSP later added exactly this
  (`0049-drm-panel-canaan-universal-add-rm69a10-dsi-backlight.patch`):
  `canaan,dsi-command-backlight`, `default-brightness`, `max-brightness`
  properties and a Linux `backlight_device` driven by
  `MIPI_DCS_SET_DISPLAY_BRIGHTNESS`. Adopting/adapting that patch is the
  direct path. **Effort S/M, risk low** (DSI command writes only). This
  is also the missing `display/backlight` capability in the taxonomy
  (`.skills/k230-spec-change/SKILL.md` names it; no spec file exists yet).

#### GT9895 touch (Goodix "Berlin" family)

- **Part / location**: GT9895. Main board, on `&i2c3`, address `0x5d`.
- **Bus/pins**: I2C3; RST `GPIO24`, INT `GPIO23`, SCL `GPIO36`, SDA `GPIO37`.
  Confirmed three ways: our own schematic read (`docs/findings.md`), the
  U-Boot board DTS FPIOA table (`docs/dts-evidence.md`), and LILYGO's
  `HARDWARE_PINMAP.md`.
- **Linux driver**: our tree backports `goodix_berlin` from v6.12
  (`nix/patches/goodix-berlin/`), matched via a two-compatible fallback
  (`"goodix,gt9895", "goodix,gt9916"`) since the backport only binds the
  gt9916 string (`nix/dts/k230-tdisplay.dts`). LILYGO's own BSP instead
  vendors a distinct driver tree, `goodix_berlin/goodix_brl_*.o`
  (`CONFIG_TOUCHSCREEN_GOODIX_BRL`, patch `0034-gt9895-touch.patch`),
  under `compatible = "goodix,nottingham"` — a second, independent
  reference for the same silicon if the mainline backport ever regresses.
- **DT**: `nix/dts/k230-tdisplay.dts`, `status = "okay"`, `IRQ_TYPE_LEVEL_LOW`
  (the level-vs-edge fix that made touch report at all).
- **Userspace**: `evtest`/standard `evdev`.
- **Support level**: **Working-and-evidenced** — `docs/evidence/touch-reports.md`,
  `docs/evidence/touch-evtest.txt`, `openspec/specs/display/touch/spec.md`.

#### GC2093 camera

- **Part / location**: GC2093, MIPI-CSI2. Main board. LILYGO:
  I2C `&i2c4` address `0x37`; reset `GPIO21`; MCLK on `IO13`
  (`k230_bsp` patch `0036-add-gc2093-camera.patch`, cross-checked against
  `T-Display-K230_canmv_rt`'s `autoconf.h`:
  `CONFIG_MPP_CSI_DEV2_RESET 21`, `CONFIG_MPP_ENABLE_SENSOR_GC2093 1`).
- **Linux driver**: **none** in our pinned kernel tree — no
  `drivers/media/i2c/gc2093*` file, and no CSI-capture/ISP driver of any
  kind (`drivers/media/platform/canaan/` contains only the `vpu/`
  video-codec directory; verified by direct listing). Under RT-Smart the
  entire ISP/VICAP path is closed-source `.a` blobs
  (`docs/blob-inventory.md` C1/C2: `lib3a.a`, `libcam_engine.a`).
  LILYGO's BSP adds the sensor node plus a `BR2_PACKAGE_VVCAM`/`v4l2isp`
  package (a Verisilicon "vvcam" ISP stack port, source vendored at
  `k230_bsp/overlay/buildroot-overlay/package/vvcam/src/gc2093.c`) — a
  real, adoptable reference, not a from-scratch job, but still the
  largest single porting effort in this document.
- **DT**: our board's `&mipi0` is already re-pointed to the CSI2 instance
  (`nix/dts/k230-tdisplay.dts`, `id = <2>`), but carries no sensor i2c
  node and no ISP node.
- **Userspace**: would need `libcamera` or plain V4L2 + the vvcam
  userspace pieces.
- **Support level**: **Missing-driver**. **Effort L, risk low**
  (register/GPIO writes only, no PMIC).

#### HDMI (Lontium LT9611)

- **Part / location**: LT9611 DSI-to-HDMI bridge, I2C `0x3b` on `&i2c3`.
  Main board, documented as a diagnostic path only
  (LILYGO README: "HDMI support is kept as a diagnostic feature. AMOLED
  remains the default display path.").
- **Conflict**: shares reset (`GPIO24`) and interrupt (`GPIO23`) with the
  GT9895 touch controller (`docs/dts-evidence.md`; LILYGO's own DTS
  snapshot confirms the reset-GPIO24 sharing, though its prose table and
  literal DTS disagree on which GPIO carries the bridge's own IRQ line —
  flagged as a minor inconsistency in the vendor source itself). **HDMI
  and the AMOLED+touch panel are mutually exclusive on this board.**
- **Linux driver**: `CONFIG_DRM_LONTIUM_LT9611=y` is already set in our
  pinned kernel's `k230_defconfig`, and `k230.dtsi`'s upstream
  `k230-canmv-v3.dts` carries an LT9611 node — but with the exact GPIO
  collision our board's touch controller uses, so our board file
  deliberately omits it (`docs/dts-evidence.md`).
- **Support level**: **Present-but-not-enabled** (driver built, no
  conflict-free DT node for our board). **Effort M** (needs a
  touch/HDMI-select mechanism, not just a node), **risk low**, **value
  low** given it is explicitly a fallback/diagnostic path, and would cost
  the working touchscreen while active.

### Radio

#### Wi-Fi (RTL8189FTV / RTL8189FS)

One row only — this is already fully specified and evidenced; see
`openspec/specs/radio/wifi/spec.md` and `docs/evidence/wifi-driver-audit.md`
(driver selection, `8189fs.ko`, firmware-blob boundary) and
`docs/findings.md`/`docs/dts-evidence.md` (SDIO0 vs SDIO1 correction,
`&gpio1_ports 13` enable line). **Working-and-evidenced.**

#### Bluetooth (generic USB dongle)

- **Part / location**: not on-board silicon — a USB dongle over USB
  host. LILYGO's bundled test unit enumerates as a CSR8510 clone
  (`0a12:0001`, `bcdDevice=0x8891`); their BSP carries two patches to
  paper over that specific dongle's `HCI_QUIRK_RESET_ON_CLOSE`/init
  quirks (`0056`, `0057-bluetooth-btusb-*.patch`) plus
  `CONFIG_BT=m CONFIG_BT_HCIBTUSB=m CONFIG_BT_HCIBTUSB_RTL=y` and BlueZ
  (`BR2_PACKAGE_BLUEZ5_UTILS=y`, `k230_bsp` `linux.fragment`).
- **Linux driver**: mainline `drivers/bluetooth/btusb.c` — present in our
  pinned tree (it is standard upstream code, not a K230-specific patch),
  simply never turned on: our defconfig and `nix/kernel.nix`'s
  `structuredExtraConfig` set **no** `CONFIG_BT*` symbol at all (checked
  directly against `k230_defconfig`).
- **DT**: none needed — USB Bluetooth needs no device-tree node beyond
  the already-`okay` USB host controllers.
- **Userspace**: BlueZ (`bluez5`), none of which is in
  `environment.systemPackages` today.
- **Support level**: **Present-but-not-enabled**. **Effort S** (pure
  Kconfig + a NixOS package addition, no DT, no patch), **risk low**.
  Genuinely one of the cheapest, highest-value gaps in this document —
  ranked accordingly.

#### LoRa (SX1262 v1.1+ / LR2021 v1.3)

- **Part / location**: main board, `&spi0`. Pins (LILYGO
  `HARDWARE_PINMAP.md`, `0054-riscv-dts-rm69a10-enable-lora-spidev.patch`):
  MOSI `GPIO16`, MISO `GPIO17`, SCLK `GPIO15`, CS `GPIO14`, reset `GPIO5`,
  BUSY `GPIO19` (input), IRQ/DIO `GPIO20` (SX1262 DIO1 / LR2021 DIO11,
  same physical pin), power-enable `GPIO44`.
- **Linux driver**: none needed by design — LILYGO exposes the radio to
  userspace as a plain `spidev` (`compatible = "rohm,dh2228fv"`, a
  standard "generic SPI device" placeholder used purely to bind
  `spidev`), controlled by **RadioLib** in userspace over
  `/dev/spidevX.Y`. `CONFIG_SPI_SPIDEV=y` is already set in our pinned
  `k230_defconfig` (checked directly), and the on-chip SPI controller
  driver (`canaan,k230-spi`, `CONFIG_SPI_DESIGNWARE=y` +
  `CONFIG_SPI_DW_MMIO=y`) is likewise already in our defconfig.
- **DT**: **all three SPI controllers are `status = "disabled"` in our
  board's inherited tree** (`k230.dtsi` read directly: `spi0`, `spi1`,
  `spi2` each carry an explicit `status = "disabled";`), and our board
  `.dts` never re-enables any of them.
- **Userspace**: RadioLib (or an equivalent SX126x/LR20xx userspace
  stack) over spidev; plus reset/busy/power-enable as plain `gpiod`
  from userspace, or DT'd as GPIO consumers.
- **Support level**: **Missing-DT-node** (driver-side is entirely already
  present). **Effort M** (enable `&spi0`, add the `spidev@0` node plus
  four GPIO lines, then a userspace radio stack), **risk medium** — this
  is a transmitter; wrong frequency/power/region settings are a
  regulatory risk, not just a software one, and should be reviewed before
  first transmit.

#### MAX98357A I2S amplifier — overlap only

Owned by another agent on `feat/speaker`; not duplicated here beyond one
row. Current state as of this inventory: `nix/dts/k230-tdisplay.dts`'s
`sound` node describes `compatible = "canaan,k230-audio-inno"` driving
the **on-chip Inno codec** (`CONFIG_SND_SOC_CANAAN_K230_INNO=y`, already
in our defconfig) — inherited from the reference board, and **not** this
board's actual MAX98357A external I2S DAC/amp. The mainline
`sound/soc/codecs/max98357a.c` codec driver already exists in our pinned
tree (confirmed by direct file listing) with no DT node wired to it.
LILYGO's own BSP does not add a second ALSA card either; instead it adds
an ALSA mixer switch (`"External I2S Output Switch"`,
`sound/soc/canaan/canaan_k230_inno.c`, patch
`0059-asoc-canaan-add-external-i2s-output-switch.patch`) that gates the
same I2S stream to the external amp via `GPIO34` from userspace, plus
pinmux for BCLK `GPIO32`/LRCK `GPIO33`/DATA `GPIO35`. **Present-but-wrong
node today; effort and risk are `feat/speaker`'s to size.**

### Sensors, power, and the keyboard base

#### BQ25896 charger + BQ27220 fuel gauge — "the handheld reports its battery"

- **Part / location**: both on the keyboard/nRF9151 base board, I2C,
  addresses `0x6b` (charger) and `0x55` (fuel gauge). LILYGO documents
  them on the **same physical bus as the AHT20/XL9555/TCA8418** — SCL
  `GPIO46`, SDA `GPIO47` ("I2C4-alt" pin group, `k230_bsp` patch `0058`) —
  and states plainly that **neither chip has a kernel device-tree node in
  their BSP at all**; both are read purely from userspace over
  `/dev/i2c-0` in the LILYGO launcher's `ui_hardware.c`, which hardcodes
  the full BQ25896 (`INPUT 0x00`, `STATUS 0x0B`, `ADC_BATV 0x0E`, …) and
  BQ27220 (`VOLTAGE 0x08`, `SOC 0x2C`, …) register maps.
- **Linux driver**: **present in our pinned kernel already** —
  `drivers/power/supply/bq25890_charger.c` explicitly enumerates
  `BQ25896` as one of its four supported chip IDs (`BQ25890_ID`,
  `BQ25892_ID`, `BQ25895_ID`, **`BQ25896_ID = 0`**, checked directly in
  the source). The fuel-gauge side is **not** as complete: our tree's
  `bq27xxx_battery.h` chip enum (`BQ27000` … `BQ78Z100`) has **no
  `BQ27220`/`BQ27Z561`-adjacent entry that matches the BQ27220 command
  set** — checked directly, and the string does not appear anywhere in
  `bq27xxx_battery.c`. The fuel gauge is a genuine **Missing-driver** even
  though the charger is not.
- **DT**: no node exists in our tree today for either chip.
- **Not established / UNVERIFIED**: whether our board's existing `&i2c4`
  (Linux alias `i2c0`, already `status = "okay"`) is physically wired to
  the same GPIO46/47 pin group LILYGO's keyboard base uses, or to the
  IO7/8 group our own U-Boot FPIOA table currently selects for the SoC's
  I2C4 controller (`docs/dts-evidence.md`) — pin muxing is entirely
  U-Boot's job and is inherited, not something the Linux DT controls.
  This is exactly what `tools/board-inventory-probe.sh`'s per-bus
  `i2cdetect -y -r` is for: if `0x6b`/`0x55` answer on the live `i2c4`
  bus with the keyboard base attached, the wiring question is settled in
  one boot.
- **Support level**: **Missing-DT-node** for both (charger driver
  in-tree; fuel-gauge driver absent). **Effort M** (charger: add DT
  node + `power_supply` wiring, verify against the live board before any
  register *write* — charge-current/voltage-limit writes are the
  textbook "risky PMIC register" case named in the working agreements;
  fuel gauge: port/adapt a BQ27220-capable driver, no upstream one is
  known to exist in this tree). **Risk: charger writes are flagged
  explicitly — read-only (`power_supply` `POWER_SUPPLY_PROP_*` reads,
  `i2cget`) before any write path is attempted.** **Value: very high** —
  this is the single most-requested handheld capability (battery
  percentage, charging state) and currently has zero Linux-side support.

#### AHT20 temperature/humidity sensor

- **Part / location**: nRF52840 base board (per LILYGO's split; also
  reachable from the same I2C4-alt bus as the keyboard-base chips).
  I2C address `0x38`.
- **Linux driver**: `drivers/hwmon/aht10.c` is present in our pinned tree
  and explicitly supports both variants (`enum aht10_variant { aht10,
  aht20 }`, `i2c_device_id` entry `"aht20"` — checked directly).
- **DT**: no node in our tree.
- **Support level**: **Present-but-not-enabled** (driver ready, just needs
  a DT node once the physical bus is confirmed by probe). **Effort S**,
  **risk low**, **value low-medium** (a "cabin weather" widget, not a
  core handheld need — ranked low on the value table above).

#### XL9555 GPIO expander

- **Part / location**: keyboard/nRF9151 base board, I2C, address range
  `0x20`–`0x27` (LILYGO scans and caches the address rather than
  hardcoding one).
- **Linux driver**: `drivers/gpio/gpio-pca953x.c` is present in our
  pinned tree and its OF match table includes `"nxp,pca9555"` (checked
  directly) — XL9555 is a register-compatible PCA9555 clone, the same
  "close enough, dual-compatible-string" situation as the GT9895/gt9916
  touch backport.
- **Support level**: **Present-but-not-enabled**. **Effort S** (DT node
  with a `"xlsemi,xl9555", "nxp,pca9555"` compatible pair once the
  address is confirmed by probe), **risk low**.

#### TCA8418 keyboard-matrix controller

- **Part / location**: keyboard/nRF9151 base board, I2C address `0x34`.
  Reset `GPIO43` (output), IRQ `GPIO42` (input). LILYGO's own BSP only
  wires the IRQ pinmux in DT (`keyboard_irq_gpio42_pins`,
  `0058-...patch`) and drives the device itself from userspace — it does
  **not** register a kernel keypad node either.
- **Linux driver**: `drivers/input/keyboard/tca8418_keypad.c` is present
  in our pinned tree (checked directly) — a real, mainline, DT-drivable
  keypad driver, distinct from LILYGO's own userspace-only approach.
- **Support level**: **Present-but-not-enabled**. **Effort M** (DT node —
  reset GPIO, IRQ, `keypad,num-rows`/`num-columns`, a `linux,keymap` —
  plus deciding row/column wiring, which is not in the citations above
  and would need the keyboard base's own schematic or a probe/scan).
  **Risk low. Value high, but conditioned on owning the keyboard base
  accessory.**

#### Keyboard backlight (PWM4 / GPIO52)

- **Part / location**: keyboard/nRF9151 base board. LILYGO:
  `keyboard_backlight_pwm4_pins { pins = K230_IO52; function =
  K230_IO52_PWM4; }`, then `&pwm3_5 { status = "okay"; };` — PWM4 lives
  in the SoC's second PWM controller group.
- **Linux driver**: **`CONFIG_PWM_K230` defaults to `y` whenever
  `ARCH_CANAAN` is set** (`drivers/pwm/Kconfig`, checked directly) — it
  is already built into our kernel today, without our having asked for
  it. Our board `.dts` has no PWM node reference at all, and we have not
  confirmed a `pwm3_5`-equivalent group exists identically in our exact
  `k230.dtsi` (only `pwm0`/`pwm1` were directly inspected).
- **Support level**: **Enabled-but-unverified** for the driver/subsystem
  in general; **Missing-DT-node** for this specific pin. **Effort S**
  once the keyboard base's PWM group is confirmed, **risk low**.

#### Power key (PMU INT0 channel)

- **Part / location**: main board. **Not a plain GPIO** — LILYGO:
  "PMU INT0 / power key | `GPIO64` | PMU input | PMU input channel 0 |
  Not a normal GPIO line. Idle low, pressed high."
- **Linux driver**: **absent from our pinned tree** (checked directly:
  no `k230-pmu-pwrkey` anywhere under `drivers/input/misc/`). LILYGO adds
  a complete 647-line driver plus DT node from scratch
  (`0064-input-k230-pmu-pwrkey.patch`, spot-checked against the raw
  patch: it edits our exact `k230.dtsi` context around
  `tsensor@91107000`/`security: security {`, adds
  `pmu_pwrkey: pmu-pwrkey@91000000` with
  `compatible = "canaan,k230-pmu-pwrkey"`, `interrupts = <175
  IRQ_TYPE_LEVEL_HIGH>`, `wakeup-source;`, and
  `CONFIG_INPUT_K230_PMU_PWRKEY`). The driver edge-detects press/release,
  treats a long press as an orderly-shutdown request, and registers a
  `sys-off` power-off handler that reprograms INT0 for long-press wake
  and asserts a PMU shutdown register.
- **Support level**: **Missing-driver**, but with a ready, spot-checked
  reference patch to adapt rather than a from-scratch design. **Effort M**
  (porting a full new driver + DT node, plus board-side wake testing),
  **risk medium** — it directly programs the PMU/power-cutoff path, so a
  mistake here can hang or hard-power-off the board; test the read-only
  edge-detection and `KEY_POWER` event path thoroughly under real
  hardware before wiring the shutdown/wake side. **Value: very high** —
  currently there is no clean shutdown path at all on this handheld.

#### nRF52840 (optional BLE/audio/sensor base) and nRF9151 (optional cellular/GNSS/keyboard base)

- **Not-applicable/vendor-RTOS-only from our side in the sense that these
  are separate MCUs with their own firmware** — Linux only sees a UART.
  nRF52840: UART1, TX `GPIO3`→its RX, RX `GPIO4`←its TX, `/dev/ttyS1`.
  nRF9151: enable `GPIO2`, UART3 alt-group TX `GPIO28`/RX `GPIO29`,
  `/dev/ttyS3`.
- **Conflict worth flagging**: our board's **existing debug console
  already uses UART3** — aliased `serial3`, physically on `IO50/51` via
  the CH342 bridge (`docs/dts-evidence.md`). LILYGO's own nRF9151 patch
  (`0061-riscv-dts-rm69a10-enable-uart3-nrf9151.patch`) has to force
  `IO50`/`IO51` back to plain GPIO specifically *because* they are
  "another UART3 mux group" that would otherwise collide with the
  nRF9151's `IO28`/`IO29` group on the **same hardware UART3
  controller**. In other words: **the nRF9151 link and this project's
  serial debug console are the same physical peripheral on two different
  pin groups, and can't both be live.** Any change that wires up the
  nRF9151 must say explicitly whether it is trading away the console.
- **Support level**: enabling either link needs only a DT pinmux/uart-enable
  change (no kernel driver gap — both are plain `ttyS*` UARTs); the
  RF/cellular/GNSS/BLE functionality itself lives entirely in the
  co-processor's own firmware and is out of scope for this Linux-side
  inventory. **Effort S for the UART link itself; not sized here for
  what runs on the far end.** **Value: low for this project's current
  goal** (a touchscreen handheld shell) — flagged mainly for the UART3
  conflict, which future work must not rediscover by losing the console.

### SoC-internal blocks

#### On-chip RTC

- **DT**: `rtc@0x91000c00`, `compatible = "canaan,k230-rtc"` — **no
  `status` property, so it is enabled by default** (checked directly in
  `k230.dtsi`).
- **Linux driver**: `drivers/rtc/rtc-k230.c` exists in our pinned tree,
  but its Kconfig (`RTC_DRV_K230`) is **`default n`**, and our
  `k230_defconfig`/`structuredExtraConfig` set only the unrelated
  `CONFIG_RTC_DRV_SUN6I=y` (checked directly) — the K230-specific RTC
  driver is simply never turned on.
- **Support level**: **Present-but-not-enabled**. **Effort S** (one
  `structuredExtraConfig` line, `RTC_DRV_K230 = yes`, in
  `nix/kernel.nix`), **risk low**. Cheap, real value (a wall clock that
  survives reboot without NTP).

#### On-chip watchdog

- **DT**: `watchdog1: wdt1@91106800`, `compatible = "snps,dw-wdt"`, no
  `status` override → enabled by default.
- **Linux driver**: generic `drivers/watchdog/dw_wdt.c`,
  `CONFIG_DW_WATCHDOG=y` **already set** in our pinned `k230_defconfig`.
- **Support level**: **Enabled-but-unverified** — nobody has opened
  `/dev/watchdog` on this board yet. **Effort S** (a systemd
  `RuntimeWatchdogSec=` or a one-line pet-the-dog test), **risk low**,
  value low (nice hardening, not user-visible).

#### On-chip ADC

- **DT**: `adc: adc@9140d000`, `compatible = "canaan,k230-adc"`, no
  `status` override → enabled by default.
- **Linux driver**: `drivers/iio/adc/k230-adc.c`, Kconfig `K230_ADC`
  **`default ARCH_CANAAN`** — already built into our kernel, unasked.
- **Support level**: **Enabled-but-unverified**. No confirmed use for
  this board's ADC channels is documented anywhere in this repo or in
  LILYGO's pin map beyond the header's generic `ADC0-2` expansion pins —
  **value low** unless a future feature (e.g. an analog battery-voltage
  fallback) needs it.

#### On-chip PWM

See "Keyboard backlight" above for the concrete consumer. The controller
itself (`pwm0`/`pwm1`, `compatible = "canaan,k230-pwm"`, Kconfig
`PWM_K230` **`default ARCH_CANAAN`**) is enabled by default and already
built. **Enabled-but-unverified** at the controller level.

#### On-chip GPIO

`gpio0`/`gpio1`, `compatible = "canaan,k230-apb-gpio"`, driver
`gpio-k230.c`, Kconfig `GPIO_K230` `default ARCH_CANAAN`. **Working-and-
evidenced** — already the mechanism behind the panel reset/backlight,
touch reset/IRQ, and Wi-Fi enable lines documented above and in
`docs/dts-evidence.md`.

#### Crypto engine (AES/hash/RSA), TRNG, OTP

- **DT**: `security { compatible = "simple-bus"; ... aes@91210200
  (canaan,k230-crypto); hash@91210800 (canaan,k230-hash); rsa@91211000
  (canaan,k230-rsa); trng@91213000 (canaan,k230-rng); otp@91213500
  (canaan,k230-otp); }` — every child `status = "okay"` by default
  (checked directly).
- **Linux driver**: all five are present in our pinned tree, checked
  directly: `drivers/crypto/canaan/kendryte-aes.c`
  (`CONFIG_CRYPTO_DEV_KENDRYTE_CRYP`), `kendryte-hash.c`
  (`CONFIG_CRYPTO_DEV_KENDRYTE_HASH`), `kendryte-rsa.c`
  (`CONFIG_CRYPTO_DEV_KENDRYTE_RSA`, `default ARCH_CANAAN`),
  `drivers/char/hw_random/k230-rng.c`
  (`CONFIG_HW_RANDOM_K230`, `default ARCH_CANAAN`), and
  `drivers/nvmem/kendryte_k230_otp.c` (NVMEM-class OTP driver — not
  independently confirmed which Kconfig symbol gates it). None of these
  symbols appear as explicit `=y` lines in `k230_defconfig`; they build
  in only because `default ARCH_CANAAN` and `ARCH_CANAAN=y` is set —
  worth remembering the one exception to that pattern is the RTC driver
  above (`RTC_DRV_K230` is `default n`), so "default ARCH_CANAAN" should
  not be assumed without checking each symbol.
- **Support level**: **Enabled-but-unverified** — likely built in by
  default, never exercised from userspace on this board (no `/dev/hwrng`
  read, no AF_ALG crypto offload use, recorded anywhere in this repo).
  **Value low** for the current handheld goal.

#### Video decode/encode (MVX: H.264, HEVC, JPEG)

One row only — see `openspec/specs/runtime/video/spec.md` and
`docs/evidence/mvx-v4l2-audit.md` for the full picture, including the
compiled-in microcode/blob boundary (`docs/blob-inventory.md` A11).
**Enabled-but-unverified as a general decoder; proven for one bounded
30-fps H.264 experiment.**

#### 2D GPU (VG-Lite)

One row only — see `openspec/specs/runtime/gpu-validation/spec.md` and
`docs/research/vglite-validation.md`. `/dev/vg_lite` is registered by our
pinned kernel; `libvg_lite.so` builds from the vendor SDK's Vivante
MIT-licensed source. Private-buffer RGB565/alpha probes have physically
passed; DRM dma-buf import, a real wlroots renderer, and scanout remain
open. **Enabled-but-unverified** as an integrated renderer,
**Working-and-evidenced** for the narrow private-buffer probes cited
above.

#### NPU/KPU

More nuanced than a flat "RTOS-only": there **is** a genuine, thin Linux
kernel driver layer, already enabled in our pinned defconfig —
`CONFIG_K230_GNNE_DRIVER=y`, `CONFIG_K230_AI2D_DRIVER=y`,
`CONFIG_K230_MMZ=y` (checked directly), matching DT nodes `gnne@80400000`
(compatible `k230-gnne`) and `ai2d@80400c00` (compatible `k230-ai2d`).
These are register/IRQ/reserved-memory shims (char devices), not a
scheduler. The actual model-loading and inference intelligence needed to
use them lives entirely in Canaan's closed **nncase** userspace runtime,
shipped only as a binary tarball/wheel with no public K230 module on any
nncase branch (`docs/blob-inventory.md` B1/B2: "we do not use the
NPU... it becomes a hard blocker the moment anything wants on-device
inference"). So: **Enabled-but-unverified for the kernel shim,
Not-applicable in practice for on-device inference** without adopting
that closed runtime. Nothing in this project's current goal needs it;
flagged here only because the user asked for "everything the board can
do."

#### Second RISC-V C908 core

One row only — this already has its own OpenSpec change and capability,
`system/second-core-readiness`
(`openspec/specs/system/second-core-readiness/spec.md`,
`openspec/changes/the-system-runs-on-both-cores/`). Current state:
read-only readiness tooling exists (`tools/second-core-readiness.sh`);
the live device tree and firmware handoff describe one hart; SMP release
is explicitly gated behind further evidence, not attempted.

#### USB (DWC2 ×2, host/gadget/UVC)

- **DT**: `usb0`/`usb1`, both `status = "okay"` in our board `.dts`.
- **Linux driver**: `CONFIG_USB_DWC2=y`, `CONFIG_USB_DWC2_DUAL_ROLE=y`,
  `CONFIG_USB_GADGET=y`, plus gadget UVC function support
  (`CONFIG_USB_F_UVC=y`) and `CONFIG_USB_STORAGE=y` — all already in our
  pinned `k230_defconfig`.
- **Support level**: **Working-and-evidenced** for host mode and UMS
  (`docs/evidence/usb-host-validation.md`, `docs/uboot-ums.md`).
  Ethernet-class USB networking is enabled (`CONFIG_USB_RTL8152=y`) and
  an `enu1` interface exists but is untested with a cable
  (`docs/evidence/ethernet-readiness.txt`) — **Enabled-but-unverified**.

#### Bus controllers and interrupt/pinmux infrastructure (not separate rows above)

A second research pass, against `kendryte/k230_linux_sdk`'s own copy of
the same pinned commit, cross-checked the remaining bus-level blocks
without turning up any that change this document's conclusions; two
details are worth recording:

- **UART**: 5 instances (`uart0`–`uart4`), compatible
  `snps,dw-apb-uart` — mainline 8250-family, `uart0` is the Linux
  console (`serial0`). Already Working-and-evidenced via the console
  itself.
- **I2C**: 5 controllers (`i2c0`–`i2c4`), compatible
  `snps,designware-i2c` — fully mainline, matching
  `CONFIG_I2C_DESIGNWARE_PLATFORM=y` confirmed directly above.
- **SPI**: 3 controllers, compatible `canaan,k230-spi` — mainline
  `spi-dw-mmio.c` plus a small vendor init hook
  (`dw_spi_canaan_k230_init()`); matches this document's LoRa row.
- **Pinctrl/IOMUX**: the SoC has a real Linux pinctrl driver,
  `drivers/pinctrl/canaan/pinctrl-k230-iomux.c`, compatible
  `canaan,k230-iomux`, citing "K230 Technical Reference Manual V0.3.1,
  Section 12.9.2" in its binding doc — **but it ships only via a
  buildroot `linux.fragment` patch, not the base `k230_defconfig`**,
  which is exactly why `docs/dts-evidence.md` found "no pinctrl in the
  Linux device tree at all" on our build: the driver exists upstream of
  us, we simply never pulled its enabling fragment in. Any future work
  that wants Linux (rather than U-Boot's inherited FPIOA table) to
  control pin muxing has a named, concrete starting point.
- **PLIC/CLINT**: `canaan,k230-plic`+`thead,c900-plic` (208 IRQ sources,
  one context per hart) and `canaan,k230-clint`+`thead,c900-clint` —
  relevant context for `system/second-core-readiness`, not a gap of its
  own.

#### Thermal sensor

One row only — see `docs/thermal.md` in full: the sensor reads, but the
value is an **uncalibrated raw ADC code, not millidegrees**, there are no
trip points in the driver or device tree, and there is no cpufreq driver
to throttle against even if one existed. **Enabled-but-unverified is
generous; functionally there is no thermal protection at all today.**
LILYGO's own BSP separately fixes exactly this
(`0063-thermal-canaan-convert-k230-tsensor-raw.patch`: a degree-4
polynomial raw-to-millicelsius conversion matching RT-Thread's own
formula) — a concrete, adoptable reference for closing this gap.
**Effort S/M, risk low, value medium** (safety-adjacent, not
user-visible day to day).

---

## Overlaps with other in-flight work

- **Audio (MAX98357A)**: owned by another agent on branch `feat/speaker`.
  Covered above in exactly one row; do not duplicate further here.
- **Second C908 core**: has its own OpenSpec change,
  `the-system-runs-on-both-cores`, and its own capability,
  `system/second-core-readiness`. Covered above in one row.
- **Wi-Fi**: already has a change lineage and full spec/evidence
  (`radio/wifi`); cited above, not re-researched.
- **Video decode**: already has a spec and evidence
  (`runtime/video`, `docs/evidence/mvx-v4l2-audit.md`); cited above, not
  re-researched.

---

## Proposed sequence of OpenSpec changes

Grouped by what becomes true for the person holding the handheld, in the
same rough order as the value/effort table above. Names are sentences
per `.skills/k230-spec-change/SKILL.md`; none of these directories exist
yet.

1. **`the-handheld-reports-its-battery`** — `system/power` (new
   capability, or `display`/`system` per taxonomy discussion): read-only
   BQ25896 + BQ27220 access over the existing `&i2c4` bus once probe
   confirms wiring; expose charge percent, charging/discharging state,
   and a upower-compatible `power_supply` sysfs node. No register writes
   in the first pass.
2. **`the-panel-brightness-is-adjustable`** — `display/backlight`
   (the taxonomy already names this capability; no spec exists yet):
   port LILYGO's DSI-command backlight patch, wire a real
   `/sys/class/backlight` device, and fix `canaan_panel_prepare()`'s
   missing reset pulses as a prerequisite so brightness changes survive
   a modeset.
3. **`the-power-key-suspends-and-wakes`** — `system/power`: port the
   PMU INT0 power-key driver, land `KEY_POWER` events first
   (read-only/observable), then wire orderly shutdown, and only then the
   long-press wake path. Each stage gets its own board proof before the
   next.
4. **`the-handheld-talks-bluetooth`** — `radio/bluetooth` (new
   capability): flip the Kconfig symbols, add BlueZ, prove pairing with
   a real USB dongle. No device tree or kernel patch required.
5. **`the-clock-survives-a-reboot`** — `system/kernel` or a new
   `system/rtc` capability: enable `RTC_DRV_K230`, confirm
   `/dev/rtc0`, confirm the SoC RTC itself has a backing supply that
   survives a full power-off (UNVERIFIED today).
6. **`the-keyboard-base-types`** — `runtime/shell` + a new
   `input/keyboard-base` capability: TCA8418 keypad DT node, XL9555
   expander DT node, keyboard backlight PWM, explicitly documenting the
   UART3/nRF9151 conflict so it is not silently traded away.
7. **`the-handheld-transmits-lora`** — `radio/lora`: enable `&spi0`,
   add the `spidev` + GPIO nodes, bring up a userspace RadioLib path,
   and get a regulatory/frequency-plan review before first transmit.
8. **`the-camera-captures-a-frame`** — new `media/camera` capability:
   port the GC2093 sensor driver and vvcam ISP path, land a single
   `v4l2-ctl --stream` capture as the proof before any libcamera/app
   integration.
9. **`the-thermal-sensor-reads-real-degrees`** — `system/kernel`
   or a new `system/thermal` capability: port LILYGO's raw-to-millidegree
   conversion, then add a critical trip point tied to `orderly_poweroff`
   even without a cpufreq cooling device.
10. **`the-usb-ethernet-link-is-verified`** — `system/console` or
    `radio/*`: plug a cable into the existing `enu1` r8152 interface and
    record the missing evidence class (DHCP, route, DNS, ping) that
    `docs/evidence/ethernet-readiness.txt` stopped short of.

---

## `tools/board-inventory-probe.sh`

A strictly read-only inventory probe, in the same style as
`tools/second-core-readiness.sh`: POSIX `sh`, parameterized by
`BOARD_INVENTORY_ROOT` (default `/`) so the file-based parts can be
tested against a synthetic tree on a host with no board attached
(`tools/test-board-inventory-probe.sh`, mirroring
`tools/test-second-core-readiness.sh`'s fixture pattern).

**Run on the board** (it reads local `/proc`, `/sys`, and runs local
commands — it is not a serial-console wrapper like
`tools/probe-display.sh`, though the coordinator can paste its one-liner
into a `tools/console.py --send` invocation over `/dev/ttyACM0` exactly
the way `tools/probe-display.sh` already does for the display/touch
checks):

```
sh tools/board-inventory-probe.sh
```

It collects, in order, and only ever reads:

1. Every `/proc/device-tree` node it can walk, with each node's `status`
   property (or `(default okay)` when the property is absent, per the
   devicetree spec).
2. Every `/dev/i2c-*` bus found, named from
   `/sys/class/i2c-dev/i2c-N/name`, then `i2cdetect -y -r` on it —
   **`-r` only**, the SMBus "receive byte" read, never the default
   "quick write" probe; that choice (plus i2cdetect's own reserved-range
   skip, `0x00`–`0x02`/`0x78`–`0x7f`) is what makes every scan safe.
   `BOARD_INVENTORY_I2C_SKIP` (space-separated hex addresses) is recorded
   against each bus in the output as a reviewer note when a coordinator
   already knows a specific chip on this board is read-sensitive — it
   annotates the output, it does not change what gets scanned
   (`i2cdetect` has no such exclude option).
3. `ls` on `/sys/class/{power_supply,backlight,input,sound,video4linux,
   bluetooth,net,thermal,pwm,gpio}`.
4. `lsusb`.
5. `dmesg`, filtered to driver-probe-shaped lines (`probe`, `bound`,
   `ready`, `okay`, `error`, `fail`, case-insensitive).
6. `lsmod`.

It never loads/unloads a module, never writes a sysfs attribute, never
opens `/dev/ttyACM0` itself (it runs on the board, not over the console
link), and never issues an I2C/SPI write. Any command that is not found
on the running image is reported as `<unavailable>` rather than failing
the whole probe.

`tools/test-board-inventory-probe.sh` builds a small synthetic
`/proc/device-tree` and `/sys/class/*` tree under a temp directory (the
same pattern as `tools/test-second-core-readiness.sh`), runs the probe
against it with `BOARD_INVENTORY_ROOT` set, and asserts on specific
output lines. The command-based sections (`i2cdetect`, `lsusb`, `dmesg`,
`lsmod`) are exercised only for their "tool not present" fallback in the
host fixture, since faking their real output would test the fixture, not
the probe.
