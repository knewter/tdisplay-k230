# Keyboard base read-only probe (tasks 1.2, 1.3)

Evidence class: **board-read**. Commands ran on the second T-Display K230
board, clipped into the LILYGO keyboard base, over the serial console while
the host held `flock /tmp/k230-board.lock`.

## Setup

- Image: `.#sdImage-landscape` built from `master` at `dc2c4dae`, flashed
  over U-Boot `ums` with `tools/ums-session.py --flash` on 2026-10-13.
- Device tree: that image's `mainlineDrmHotplugDeviceTreeNormalName`, rebuilt
  from `impl/keyboard-base` with the I2C4 node and pinctrl states in
  `nix/dts/k230-tdisplay-mainline-drm-common.dtsi`, plus the nRF9151 states
  from `impl/nrf9151`. The image's `/chosen/bootargs` was copied into it with
  `fdtput`, and it was installed with
  `tools/push-file.py --src <dtb> --dest /boot/k230-tdisplay.dtb --reboot`.
- Kernel `7.3.0-rc5`.
- Probe: `tools/keyboard-base-probe.sh`, pushed to `/root` with
  `tools/push-file.py`, run as `bash /root/keyboard-base-probe.sh`.

## Runs

| File | Time (UTC) | Notes |
| --- | --- | --- |
| `probe-2026-10-13T193433Z.log` | 19:34:33 | First version; did not sample IO42/IO43 levels. |
| `probe-2026-10-13T193545Z.log` | 19:35:45 | Current script; samples IO42, IO43 and IO52, which were already inputs. |

Between the runs only the GPIO section and the gauge temperature (0x06 and
0x28, 0x0c0b to 0x0c09) differ.

## Results

Answering addresses on hardware I2C4 (IO46 SCL, IO47 SDA, function 3,
100 kHz, `i2c-1`):

| Address | Chip |
| --- | --- |
| 0x20 | XL9555 expander |
| 0x34 | TCA8418 keypad |
| 0x38 | Not read. LILYGO reads an AHT20 at this address on these pads (`sensor_aht20_iomux_value`) |
| 0x55 | BQ27220 gauge |
| 0x6B | BQ25896 charger |

- **DRV2605 haptics (0x5A): not fitted.** No acknowledgement.
- **IO43 (keypad reset, `gpiochip1` 11): input, level 1**, so the keypad is
  out of reset. IO42 (keypad IRQ, `gpiochip1` 10): input, level 1, inactive.
  IO52 (key backlight, `gpiochip1` 20): input, level 0.

The charger (BQ25896) fields are decoded per the TI datasheet register map:

| Register | Value | Meaning |
| --- | --- | --- |
| REG04 | 0x0b | ICHG 11 × 64 mA = **704 mA** charge current |
| REG05 | 0x13 | IPRECHG 64 + 1 × 64 = **128 mA**; ITERM 64 + 3 × 64 = **256 mA** termination |
| REG06 | 0x72 | VREG 3840 + 28 × 16 = **4288 mV**; BATLOWV 3.0 V; VRECHG 100 mV |
| REG07 | 0x8d | Termination enabled, **watchdog disabled**, safety timer on (12 h) |
| REG0B | 0x5e | CHRG_STAT 11, charge termination done; power good |
| REG0E | 0x63 | BATV 2304 + 99 × 20 = 4284 mV |
| REG11 | 0x97 | VBUS good, VBUSV 2600 + 23 × 100 = 4900 mV |

USB-C was connected to the base.

The gauge (BQ27220) reads, from standard commands:

| Quantity | Value |
| --- | --- |
| Voltage | 4202 mV |
| Current | 0 mA |
| Temperature | 308.3 K (35.2 °C) |
| Remaining capacity | 3000 mAh |
| Full-charge capacity | 3000 mAh |
| State of charge | 100 % |
| State of health | 100 % |
| Cycle count | 0 |
| **Design capacity** | **3000 mAh** |

The keypad and expander read:

- TCA8418 CFG 0x29: key-event interrupt, overflow interrupt and overflow mode
  set.
- XL9555 configuration 0xc7/0xff: port 0 bits 3-5 are outputs. All output
  latches are 1.

## Limits

- **Some register state may be left over from LILYGO's firmware.** The base
  has its own battery and was not power-cycled after LILYGO's firmware last
  ran on this K230 on 2026-10-13. The TCA8418 CFG and XL9555 configuration
  differ from their reset value of 0x00, which suggests prior configuration
  (an inference, not observed). The charger values may also be LILYGO's
  settings rather than power-on defaults.
- **The design capacity may not describe the cell.** 3000 mAh equals the
  BQ27220's factory default, so the gauge may never have been configured for
  this cell. Treat it as unverified until the cell's rating is known.
- **Earlier all-NACK runs were caused by the film.** Earlier attempts on this
  unit, on both the hardware controller and a GPIO bit-bang, saw every
  address NACK. A protective plastic film was still over the base's pogo
  pins; the operator removed it before LILYGO's own firmware detected the base
  (`Detected 6B:yes 55:yes 34:yes 20:yes on I2C4 SDA47/SCL46`). Those runs
  are not evidence about either bus.
- **Not covered here.** This probe does not show that the panel and touch
  still work with the new tree; that is task 2.2.
