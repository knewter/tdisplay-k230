# Findings

Investigated 2026-09-20 against firmware
`CanMV-K230-V3P0_rtsmart_localnncase_v2.9.0_20260130` (LilyGO V1.3).

## Hardware

Read out of `schematic/T-Display K230_V1.0_NEW.pdf` in the upstream repo.

| Function | Detail |
| --- | --- |
| SoC | Kendryte K230D, 2x RISC-V C908 (1.6 GHz + 800 MHz), KPU NPU, 1 GiB LPDDR |
| Panel | RM69A10 MIPI-DSI, 568x1232 AMOLED, reset on **GPIO22** |
| Touch | GT9895 (Goodix Berlin family) on I2C — RST GPIO24, SCL GPIO36, SDA GPIO37, INT GPIO23 |
| Wi-Fi | RTL8189FTV on SDIO (**MMC0** — see correction below); enable line `IO45_WIFI_EN` on **GPIO45** |
| Serial | CH342 dual UART bridge on the charge USB-C (`J2`); ch0<->UART0, ch1<->UART3 |
| Power | BQ25896 charger + BQ27220 fuel gauge |
| LoRa | SX1262 (V1.1+) / LR2021 (V1.3) |
| SD | TF card on GPIO54-59, muxed as **MMC1** |

U-Boot identifies the board as `Model: kendryte k230 canmv v3.0`.

## Wi-Fi is broken in the shipped firmware

`wifi scan` returns an empty table. `wifi ap <ssid>` reports
`start ap successs!` and brings `w1` up with an IP, but the BSSID stays
`00:00:00:00:00:00` at `0Mbps` and **no phone, laptop, or other receiver can
see the SSID**. The radio never transmits.

Root cause is in LilyGO's BSP, at
`canmv_k230/src/rtsmart/rtsmart/kernel/bsp/maix3/drivers/extdrv/realtek/platform/rtwlan_bsp/rtwlan_bsp.c`:

```c
void Set_WLAN_Power_On(void)
{
}

void Set_WLAN_Power_Off(void)
{
}
```

The power-on hook is an empty stub, so `GPIO45` / `IO45_WIFI_EN` is never
asserted and the RTL8189 stays powered down. `realtek_init()` registers the
SDIO driver and triggers a rescan, but with no chip powered the probe never
fires. The RT-Thread WLAN framework registers `w0`/`w1`/`sta`/`ap`
unconditionally, which is why they appear in `ifconfig` with nothing behind
them.

Compounding this, in `canmv_k230/src/rtsmart/rtsmart/kernel/bsp/maix3/drivers/Kconfig`:

```
menuconfig RT_USING_REALTEK
    bool "Enable Realtek WiFi Driver"
    default n
```

The driver is off by default and the board defconfig does not enable it, so it
is likely not compiled into the shipped image at all. The boot log contains no
RTL8189 probe of any kind — the only SDIO device found is the TF card.

Both need fixing to get Wi-Fi under RT-Smart:

1. `RT_USING_REALTEK=y` plus `REALTEK_SDIO_DEV1` (SDIO1 = `mmc1@91581000`)
2. Implement `Set_WLAN_Power_On()` using `kd_pin_mode()` / `kd_pin_write()`
   from `drv_gpio.h` to drive GPIO45 high, and call it from `realtek_init()`
   before the SDIO rescan

The driver itself is otherwise complete — `wlan_lib/libwlan_v1_1.a`, the SDIO
glue in `platform/sdio/`, and correct SDIO IDs (`0x024c`/`0xf179`) are all
present.

**Under Linux this is likely moot**: `k230_canmv_v3_defconfig` in
`kendryte/k230_linux_sdk` sets `BR2_PACKAGE_RTL8189FS=y`.

## No Ethernet

U-Boot reports `Net: No ethernet found.` The `u0` interface visible in
RT-Smart's `ifconfig` (MAC `00:e0:4c:…`, Realtek) is not the RJ45.

## Linux support

`kendryte/k230_linux_sdk` (`dev` branch) has **`k230_canmv_v3_defconfig`**,
matching this board's U-Boot board name (`k230_canmv_v3`):

- Kernel: `ruyisdk/linux-xuantie-kernel` @ `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`, defconfig `k230`
- `BR2_PACKAGE_RTL8189FS=y` — the Wi-Fi chip on this board
- DTS: `canaan/k230-canmv-v3-lcd`, `canaan/k230-canmv-v3`

Gaps for *this* board:

- The v3 reference DTS uses `display-st7701-480x800.dtsi` — an ST7701 480x800
  LCD, **not** the RM69A10 AMOLED. However `drivers/gpu/drm/panel/panel-canaan-universal.c`
  is a 395-line generic DSI panel driver configured entirely from the device
  tree (init command sequence, videomode, reset/power GPIOs, lane count). So
  the AMOLED should be a **new dtsi**, not a new driver — transcribe the init
  sequence from LilyGO's `mpp/kernel/connector/src/rm69a10.c`.
- No GT9895 / `goodix_berlin` in that kernel (it carries the older GT9xx
  `goodix.c`). GT9895 is in mainline since ~6.7, so this is a backport onto a
  6.6-based tree.

## Boot chain

```
BootROM -> U-Boot SPL (+ DDR PMU training firmware) -> U-Boot 2022.10 -> OpenSBI v0.9 -> payload
```

Canaan packages these with a custom header and compression
(`image: uboot load to 20000000 compress =1`). For a NixOS port, treat stage 1
as a prebuilt binary input and let Nix own the kernel, initrd, and rootfs.

Shipped image layout (608 MB, MBR):

| Region | Contents |
| --- | --- |
| sectors 0-102399 | raw boot firmware |
| part 1 @ 102400, 30 MB, FAT32 `BIN` | camera sensor tuning (gc2093/gc2053/imx335 xml+json) |
| part 2 @ 163840, 500 MB, FAT32 `SDCARD` | `app.elf`, sample ELFs, `*.kmodel` |

`app.elf` is the default boot application; the fast iteration loop is to build
a new one and copy it onto part 2, no reflash needed.

## Toolchain notes for the NixOS port

- QEMU 11.1.0 has a **`k230` machine** ("RISC-V Board compatible with Kendryte
  K230 SDK") — iterate without hardware.
- `riscv64-linux` is community-tier in nixpkgs with **no binary cache**; cross
  compile from `x86_64-linux` rather than emulating.
- Closest precedent is `nixos-licheepi4a` (T-Head Xuantie C910, vendor kernel).
- **Compose Desktop on riscv64 is unproven but not ruled out.** Skiko
  publishes 32 Maven artifacts and none are riscv64 (Linux natives are
  arm64/x64 only). However **Skia itself supports riscv64** — SkiaSharp added
  riscv64 builds (PR #3192) and skia-python ships riscv64 wheels — so the gap
  is Skiko's build matrix and JNI glue, not a Skia port. Needs a riscv64
  OpenJDK (upstream since ~JDK 19) and `SKIKO_RENDER_API=SOFTWARE`, since the
  K230's 2.5D GPU has no Mesa/Vulkan driver. The open question is whether
  software Skia + a JVM performs acceptably at 568x1232 in 1 GiB of RAM.
  Measure it on hardware before committing either way.
- Kotlin/Native has no riscv64 target at all, so a KMP-native shell is out
  regardless; any Kotlin path is Kotlin/JVM.


## Corrections

Two claims above were wrong when first written. Recording the correction
rather than quietly editing, because both were used to reason about other
things.

### Wi-Fi is on MMC0, not MMC1

Originally recorded as "RTL8189FTV on SDIO (MMC1, GPIO26-31)". The two
controllers were swapped. Three independent sources agree:

- The schematic ties `WIFI_CLK/CMD/D0–D3` to the SoC's dedicated **MMC0**
  balls, not to IO26–31.
- `k230_canmv_v3p0_defconfig` sets `CONFIG_REALTEK_SDIO_DEV0=y` and
  `CONFIG_SDCARD_ON_SDIO_DEV=1`.
- U-Boot's pinmux muxes IO54–59 as MMC1 with the comment
  `// MMC1 -> TFCARD`, and leaves IO26–31 as plain GPIO to the expansion
  header.

So Wi-Fi is `&mmc_sd0` and the TF card is `&mmc_sd1`. This matters directly:
the U-Boot environment loads the kernel from `mmc ${mmc_boot_dev_num}:1`
with `mmc_boot_dev_num=1`, which is consistent with the card being MMC1 and
would have been confusing under the old, wrong mapping.

### The Realtek driver IS compiled in

Originally recorded that `RT_USING_REALTEK` "defaults to n and the board
defconfig does not enable it, so it is likely not compiled into the shipped
image at all". The Kconfig default is indeed `n` — but
`k230_canmv_v3p0_defconfig` sets `CONFIG_RT_USING_REALTEK=y`. The driver is
built.

That strengthens rather than weakens the diagnosis: the radio is silent with
the driver present, so the empty `Set_WLAN_Power_On()` stub is the whole
cause, not one of two.

### Other device-tree findings

From `docs/dts-evidence.md`:

- **There is no pinctrl in the Linux device tree at all.** FPIOA muxing
  lives in U-Boot's `k230_canmv_v3p0.dts` and is inherited. A board `.dts`
  cannot set pin functions.
- **The upstream LT9611 HDMI node collides with our touch controller.**
  `k230-canmv-v3.dts` gives it `reset-gpios = <&gpio0_ports 24>` and
  `interrupts = <23 …>` — GT9895's RST and INT. The I2C addresses do not
  collide (0x3b vs 0x5d); the GPIOs do.
- **`panel-canaan-universal` only pulses reset in `probe()`.** The reset
  block in `prepare()` is commented out while `unprepare()` drives reset and
  enable low, so any modeset or suspend cycle leaves the panel held in
  reset. Likely a prerequisite patch rather than polish.
- **The RM69A10 runs at ~39.6 Hz**, not the 60 its enum name suggests —
  39.6 MHz over 788×1268, consistent with the vendor's own 475.2 Mbps/lane
  figure.
