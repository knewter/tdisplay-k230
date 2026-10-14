## Why

With the handheld clipped into its keyboard base, a person cannot type on the
keys in front of them. Pressing them does nothing. Typing still means summoning
the on-screen keyboard, which covers almost half of the landscape panel. The
keyboard's backlight stays dark, and its Caps Lock light never lights. The base
also carries a battery and a charger, but nothing on screen shows the charge or
whether the battery is charging. Home's Battery widget reports "no battery
info", so the first warning is the board switching off.

The keyboard base is the LILYGO "nRF9151 cellular / GNSS / keyboard base"
(`k230_bsp/docs/HARDWARE_PINMAP.md` in `Xinyuan-LilyGO/T-Display-K230`). Its
modem is a separate proposal,
`the-nrf9151-gives-the-handheld-cellular-sms-and-location`. This change covers
everything else on the base that Linux can use:

- the key matrix (TCA8418);
- the key backlight (PWM on IO52);
- three status LEDs on an XL9555 expander;
- the charger (BQ25896);
- the fuel gauge (BQ27220);
- an optional haptic driver (DRV2605) on some variants.

## What Changes

- **Probe first, read-only.** Establish on the board which of these chips
  answer, at which addresses, over which bus, and whether anything must be
  enabled first. LILYGO bit-bangs the base's I2C bus through GPIO46/47 rather
  than using a hardware I2C controller, and an open LILYGO issue reports the
  keypad not ACKing under Linux. Every later group depends on what this probe
  finds.
- **Kernel and device tree.**
  - Mux the base's pins in the Linux device tree.
  - Give the base an I2C bus.
  - Bind the existing mainline drivers for the keypad, GPIO expander, charger
    and haptics.
  - Add BQ27220 support to the kernel's `bq27xxx` fuel-gauge driver.
  - Drive the key backlight, first as on/off, then dimmable once a K230 PWM
    driver is ported.
- **Typing.** The base's keys type into the focused application through Sway,
  with an xkb layout that matches the printed legends, punctuation included.
  Caps Lock lights its LED.
- **Shell use.**
  - Typing on the base hides an open on-screen keyboard.
  - The LILYGO key opens the app drawer, and Esc goes back.
  - The key backlight follows typing, goes dark with the panel, and has a
    control in Settings.
  - The battery's charge and charging state appear in Home's existing Battery
    widget and in the shade.
  - A low battery raises a notification. A critically low battery shuts the
    system down cleanly instead of letting it brown out.

## Non-goals

- The nRF9151 modem, its UART and its power enable (see the companion
  proposal).
- The separate nRF52840/AHT20 base.
- Changing how the battery charges. The charger keeps the limits it already
  runs with. There is no charge-current or charge-voltage control in Settings.
- Haptic feedback as a user-facing feature. DRV2605 is probed and bound if
  present, but no shell feature uses it in this change.
- Suspend-to-RAM, and waking from suspend on a key press.
- Assigning the two XL9555 LEDs other than Caps Lock to a purpose.
- An input-method editor, including LILYGO's Fn+Space pinyin toggle.

## Capabilities

### New Capabilities

- `display/keyboard`: the keyboard base's keys, Caps Lock light and key
  backlight, as Linux input and LED devices with a layout matching the legends.
- `system/battery`: the base's battery and charger reported as Linux
  power-supply devices, with low and critical battery policy.

### Modified Capabilities

- `runtime/shell`: hardware-keyboard behavior (hiding the on-screen keyboard,
  shell keys, backlight follows typing) and battery state in the shade.
- `runtime/device-settings`: a keyboard backlight control. Battery status
  appears only once battery hardware is observed, as the existing requirement
  already demands.

## Impact

- **Kernel:**
  - Kconfig for `KEYBOARD_TCA8418`, `GPIO_PCA953X`,
    `CHARGER_BQ25890`, `BATTERY_BQ27XXX_I2C`, `INPUT_DRV260X_HAPTICS`,
    `LEDS_GPIO` and `LEDS_PWM`.
  - A forward-port patch adding BQ27220 to `bq27xxx`.
  - Later, a K230 PWM driver port.
- **Device tree:** the mainline DRM device tree (`k230-tdisplay-mainline-drm-common.dtsi`)
  gains a pinctrl node and the base's devices.
- **Nix:** an xkb layout, the Sway input stanza, a small keyboard-base service,
  and the battery policy unit.
- **Rust shell client:** the shade and Settings.
- **Needs the board.** Every claim about keys, lights or the battery needs the
  physical board with the keyboard base attached. Host builds, host unit tests
  and QEMU can check the device tree, the kernel build, the xkb layout and the
  shell's state handling, but not one key press.
- **Stage 1 is untouched.**
