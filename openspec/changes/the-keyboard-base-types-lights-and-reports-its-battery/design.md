## Context

Sources read for this design:

- LILYGO `Xinyuan-LilyGO/T-Display-K230` at tree `4a87c53c`:
  - `k230_bsp/docs/HARDWARE_PINMAP.md`, the pin map of the nRF9151 base.
  - `k230_launcher/k230_phone_ui/src/ui_hardware.c`, the LVGL launcher's
    driver for the base.
- `docs/dts-evidence.md`, for the FPIOA and the fact that our Linux tree has
  no pinctrl.
- `docs/research/board-capability-inventory.md`, for the nRF9151/UART3 conflict.
- The mainline sources and bindings in the pinned kernel:
  - `tca8418_keypad.c` and `ti,tca8418.yaml`;
  - `gpio-pca953x.c`;
  - `bq25890_charger.c`;
  - `bq27xxx_battery_i2c.c` and `bq27xxx.yaml`;
  - `drv260x.c`.

### What the vendor code does

The vendor does not use a Linux driver for any chip on the base. Its vendor
device tree has no nodes for them.

**Bus.** `keyboard_i2c_begin()` uses `/dev/mem` to switch IO46 and IO47 to FPIOA
function 0 (GPIO). It then bit-bangs I2C on `/dev/gpiochip1` lines 14 and 15
(open-drain, pull-up, 8 µs half-period), and afterwards restores function 3.

**Probe.** Its probe looks for:

| Chip | Address |
| --- | --- |
| BQ25896 | 0x6B |
| BQ27220 | 0x55 |
| TCA8418 | 0x34 |
| XL9555 | first answer in 0x20–0x27 |

It reports `Keyboard base not detected` when none answers.

**Keys.**
- The matrix is 7×10, with 68 key codes named in `tca8418_key_name()`.
- There is no punctuation row. `extension_keyboard_shift_symbol_for_code()`
  puts punctuation on Shift of the letter and number keys, for example
  Shift+Q is `` ` `` and Shift+E is `-`.
- FN and FN-R are layer keys.
- FN+LILYGO takes a screenshot, and FN+Space toggles pinyin.

**IRQ and reset.**
- IO42 is set to a GPIO input (IOMUX value `0x344`) and read as the TCA8418
  interrupt.
- IO43, named the TCA8418 reset in the pin map, is never touched by this file.

**Backlight.** IO52 is muxed to PWM4 (IOMUX value `0x1191`) and driven through
`/sys/class/pwm`. The vendor kernel has a PWM driver. Our kernel has none: PWM
is a recorded non-goal in `docs/research/mainline-kernel-inventory.md`.

**LEDs.** The XL9555's P0.3, P0.4 and P0.5 drive three LEDs. LED 0 follows
Caps Lock.

**Charger.** The BQ25896 is used with a 704 mA charge current and a 4288 mV
regulation voltage, both defaults, and its watchdog disabled.

**Fuel gauge.** The BQ27220 is read with standard commands at the following
registers:

| Register | Quantity |
| --- | --- |
| 0x06 | temperature |
| 0x08 | voltage |
| 0x0A | flags |
| 0x0C | current |
| 0x10 | remaining capacity |
| 0x12 | full-charge capacity |
| 0x16 | time to empty |
| 0x18 | time to full |
| 0x2A | cycle count |
| 0x2C | state of charge |
| 0x2E | state of health |

Mainline `bq27xxx` at our pin has no BQ27220 entry.

### GPIO bank arithmetic

`gpio0_ports` is IO0–31 and `gpio1_ports` is IO32–63. So:

| Pad | Bank line |
| --- | --- |
| IO42 | `gpio1 10` |
| IO43 | `gpio1 11` |
| IO46 | `gpio1 14` |
| IO47 | `gpio1 15` |
| IO52 | `gpio1 20` |

## Goals / Non-Goals

**Goals:**
- The base's keys arrive as an ordinary Linux keyboard.
- Caps Lock and the key backlight are Linux LED devices.
- Battery and charger are `power_supply` devices.
- The shell behaves well with a hardware keyboard.
- Low-battery policy.

**Non-goals:** see the proposal. In particular, no charge-parameter changes
and no modem.

## Decisions

### 1. Probe before binding (userspace, read-only)

The first group is a read-only probe on the board. The pinctrl and driver
choices below depend on its answers, and the vendor issue
(T-Display-K230_canmv_rt#11: TCA8418 and XL9555 not ACKing under Linux) means
a guess could cost a boot.

The probe:
- reads the IOMUX words for IO2, IO28, IO29, IO42, IO43, IO46, IO47, IO50,
  IO51 and IO52 through `/dev/mem`, read-only;
- runs `i2cdetect -r` on an `i2c-gpio` bus created at runtime, or, failing
  that, the vendor's bit-bang sequence driven through `gpioset`/`gpioget`;
- reads only identity and status registers.

It writes nothing to any chip.

### 2. Bus: `i2c-gpio` on IO46/IO47 (device tree)

A device-tree `i2c-gpio` node with SCL on `gpio1 14` (IO46) and SDA on
`gpio1 15` (IO47), both open-drain. This is what the vendor actually does.

The hardware controller, function 3 on those pads, is tried once in the probe
group. If it ACKs at 100 kHz, it is preferred, because it costs no CPU per
bit. The decision is recorded in evidence either way.

**Rejected:**
- `/dev/mem` IOMUX pokes from userspace, as the vendor does. They need root,
  race any kernel owner of the pads, and leave the pads in whatever state a
  crash left them.
- Assuming the hardware controller works. The vendor's own code deliberately
  avoids it.

### 3. Pins: Linux pinctrl, not stage 1 (device tree)

`PINCTRL_K230` is already built (`nix/kernel-mainline.nix:499`), but our
device tree has no pinctrl node. Every pad today keeps U-Boot's FPIOA setting
(`docs/dts-evidence.md`). This change adds a `canaan,k230-pinctrl` node at
`0x91105000` with states only for the base's pads:

| Pad | Function |
| --- | --- |
| IO42 | GPIO input, pull-up |
| IO43 | GPIO |
| IO46/47 | GPIO, open-drain-capable, pull-up |
| IO52 | GPIO now, PWM4 once the PWM port lands |

The driver applies only states that consumers reference, so pads such as the
console's IO38/39 stay as U-Boot left them. The first boot of this device tree
must show the console still working. That is checked in the probe-to-bind
group before any key work.

**Rejected:**
- An FPIOA patch in our U-Boot board file. It would need a stage 1 reflash to
  change a peripheral's pins, and it would hide board policy in the
  bootloader.

### 4. Drivers (kernel, Kconfig, device tree)

**TCA8418.**
- `ti,tca8418` at 0x34, IRQ on `gpio1 10` falling edge, 7 rows by 10 columns.
- `linux,keymap` is generated from the vendor's code-to-name table:
  code `n` is row `(n-1)/10`, column `(n-1)%10`.

**Reset (IO43).** The binding has no reset property, so IO43 is a `gpio-hog`.
Its polarity and level must come from the probe. The vendor code never drives
it, so its pad state at probe time is the only grounding.

**XL9555.**
- `nxp,pca9555` at the probed address.
- `gpio-leds` on P0.3/4/5 named `k230:green:capslock`, `k230:status-1` and
  `k230:status-2`. The colors are UNVERIFIED until a camera frame shows them.

**BQ25896.**
- `ti,bq25896` at 0x6B. The binding requires charge parameters.
- The values are copied from the charger's own registers as read in the
  probe, so binding the driver does not change how the battery charges.
- If the driver would write any register to a different value, that field is
  named in the evidence before the change boots.

**BQ27220.**
- A forward-port patch adds a `BQ27220` chip entry to `bq27xxx_battery.c` and
  `bq27xxx_battery_i2c.c`, using the vendor's register list above. It is
  read-only: no data-memory or configuration writes.
- **Rejected:** a userspace gauge daemon. Home's Battery widget, logind and
  any later UPower all read `/sys/class/power_supply`, and userspace cannot
  create a `power_supply`. A second, private battery API would mean every
  consumer reads two sources.
- **Also rejected:** estimating charge from the BQ25896's VBAT ADC, which gives
  voltage only, with no coulomb counting.

**DRV2605.** `ti,drv2605` at 0x5A if the probe finds it, with the default
library. No consumer is added.

### 5. Key backlight: on/off now, dimmable later (kernel)

**First step.** IO52 stays a GPIO (`gpio1 20`) driven by a `gpio-leds` entry
named `k230::kbd_backlight`. The `::kbd_backlight` suffix is the name
convention desktop tools look for. This needs no new driver.

**Second step.** A port of the vendor K230 PWM driver turns it into a
`pwm-leds` entry with the same name and a brightness range.

**Rejected:**
- Toggling it from userspace through `/dev/mem`, as the vendor does.

### 6. Typing (Nix, xkb, Sway)

- **Layout.** A custom xkb symbols file, `k230-base`, reproduces the vendor's
  Shift-symbol table. The kernel keymap emits ordinary key codes for each
  legend, for example `KEY_Q`, and xkb puts `` ` `` on Shift+Q.
- **Fn and Fn-R.** Both map to `KEY_RIGHTALT`, and xkb treats that as
  `ISO_Level3_Shift`. The Fn layer:

  | Fn + | Gives |
  | --- | --- |
  | Up / Down | PgUp / PgDn |
  | Left / Right | Home / End |
  | Del | Insert |

- **Shell keys.**
  - LILYGO is `KEY_LEFTMETA` (Super).
  - MIC is `KEY_MICMUTE`, with no action in this change.
- **Sway** applies the layout only to the base's input identifier, so a USB
  or Bluetooth keyboard keeps `us`.
- **Rejected:**
  - Kernel keymap layers. `tca8418` has no Fn layer support.
  - `keyd` or `interception-tools`. They add a daemon that grabs the device
    and re-emits it, and the layout belongs in xkb, where Sway already reads
    it.

### 7. Shell behavior (userspace)

**On-screen keyboard.** Any key from the base's input device while wvkbd is
shown hides wvkbd, through the existing visibility signal path in
`nix/shell.nix`. A Sway `bindsym --no-repeat` cannot see every key without
consuming it, so this uses a small `k230-keyboard-base` user service that reads
the evdev device without grabbing it. The same service drives:

- **Backlight follows typing.** On at the user's level on a key press. Off
  after 30 s without keys, and off while the panel is off.
- **Caps Lock LED.** From the Sway/xkb lock state. The kernel `kbd-capslock`
  trigger follows the VT keyboard, which Sway does not drive, so it is not
  used.

**Shell keys** are Sway bindings to existing shell commands:

| Key | Action |
| --- | --- |
| Super (LILYGO) | the app drawer |
| Super + Tab | the card overview |
| Esc on Home, with no app focused | the existing back action |
| Fn + LILYGO | a `grim` screenshot, matching the vendor |

**Battery policy.** A `k230-battery-policy` system service watches
`power_supply` uevents and the gauge's `capacity` while discharging:

- At 15% and again at 5% it raises a shell notification.
- At 3% it raises a 60-second "shutting down" notification, then requests a
  clean poweroff.
- Charging cancels the countdown.

The levels are Nix options. **Rejected:** UPower, which is a heavier
dependency than this single-battery device needs, and which has no K230
packaging precedent here.

### 8. Ownership

| Layer | Owns |
| --- | --- |
| Kernel and device tree | Devices exist and report truthfully. |
| Nix | Layout, services and options. |
| Rust shell client | The shade and Settings. |

Stage 1 owns nothing new.

## Risks / Trade-offs

- **Charger takeover.** The BQ25890 driver configures the charger at probe, so
  wrong device-tree values could change how the battery charges. Mitigation:
  the values come from the board's live registers, and the probe checks this
  before boot.
- **The keypad still does not ACK.** If neither bus sees the TCA8418 or the
  XL9555, the vendor issue's power or enable question becomes the next task,
  and the battery groups proceed on their own. The groups are deliberately
  independent.
- **Bit-bang CPU cost** on the one Linux core. Keypad traffic is
  interrupt-driven and small, and gauge polling is slow. The probe records the
  CPU cost of a key burst.
- **The pinctrl node** could disturb pads it does not name. The console check
  in group 2 guards this.
- **Low-battery shutdown** is destructive if the gauge reads wrongly.
  Mitigation: shutdown requires two consecutive readings at or below the
  level, both while discharging, and the threshold can be disabled in Nix.

## Open Questions

- Does the keyboard base need anything powered or enabled before the
  TCA8418/XL9555 answer? This is the vendor's open issue.
- IO43's reset polarity.
- The XL9555 address on this unit.
- The battery's design capacity: the gauge's own `0x3C` register versus a
  label.
- Whether DRV2605 is fitted on this unit.
