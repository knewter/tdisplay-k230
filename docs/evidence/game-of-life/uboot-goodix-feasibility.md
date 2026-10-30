# Task 3.2: U-Boot Goodix touch, source and ABI feasibility note

Source reading only (2026-10-30). No U-Boot port was written, no board was
touched, and nothing below is proven on hardware: **everything here is
UNVERIFIED** until a port probes the controller on the board.

## What the hardware is

Per `nix/dts/k230-tdisplay-mainline-drm-common.dtsi`: a Goodix Berlin
controller (`goodix,gt9895`, fallback `goodix,gt9916`) at I2C address `0x5d`
on `i2c3` (`0x91408000`, 400 kHz), reset on `gpio0_ports 24` (active low),
interrupt on `gpio0_ports 23` (level low). Raw X range 0..1079, Y 0..2399
(`docs/evidence/panel-landscape/touch-range.md`), for a 568x1232 panel.

## What the Linux driver does that a port must reproduce

`nix/patches/goodix-berlin/goodix_berlin_core.c` (798 lines) over a
`regmap` with 32-bit register addresses and 8-bit values
(`goodix_berlin_i2c.c`, 76 lines):

1. Power-on and reset sequence: assert reset about 2 ms, release, wait
   `GOODIX_BERLIN_NORMAL_RESET_DELAY_MS` = 100 ms.
2. Device confirm (`GOODIX_BERLIN_DEV_CONFIRM_VAL` 0xAA at the boot-option
   address `0x10000`), firmware version at `0x10014`.
3. Read the IC-info block at `0x10070` (length-prefixed, below 1 KiB,
   checksummed) and parse out `touch_data_addr`. The coordinate format and
   register map are firmware-described, not constants: a port needs this
   parser (the larger part of the work).
4. On each event read the header at `touch_data_addr`: bit 7 = touch event,
   low 4 bits = touch count, more than two contacts need a second read;
   each point carries id (bits 7:4 of status), type, x, y, w (little-endian),
   and a 16-bit checksum protects the frame.

For a "drop a glider on tap" feature only steps 1 to 4 for the first contact
are needed; multi-touch, stylus types, power management and sysfs attributes
are not.

## What U-Boot 2022.10 (this tree) offers

* The device-model I2C controller is present and probes in the existing
  tree: `i2c_designware` for `i2c@91408000` is in the DM tree captured in
  `docs/evidence/uboot-usb-host-coexist-v2.txt` ("probed" column empty until
  used). A port could use `dm_i2c_read`/`dm_i2c_write` with a 4-byte
  big-endian register prefix (the Linux regmap writes `reg_bits = 32`).
* No GPIO controller driver appears in that DM tree, and no pinctrl entry for
  the touch lines is visible. Reset and interrupt would need either a small
  K230 GPIO driver or direct MMIO to the GPIO block, and the pin mux to be
  confirmed. Interrupts are unnecessary: polling the event register once per
  rendered frame (50 ms in the stage-1 loop) is enough, as long as the
  controller is left out of reset by the earlier stage (to be checked: the
  controller may already be held in reset until Linux asserts power).
* U-Boot 2022.10 has keyboard input (`drivers/input`) but no
  touchscreen/pointer uclass, so there is nowhere for the events to land
  except a private polling hook called by `boot_life_stage1_run`. That is
  adequate: the shared engine already exposes `gol_pixel_to_cell` and
  `gol_insert_glider`, which `nix/drm-splash/life.c` uses the same way.

## Estimate and risk

Roughly 250 to 400 lines of U-Boot C (I2C access, reset handling, IC-info
parse, one-contact event read, mapping 1080x2400 to the panel) plus GPIO
bring-up if the reset line is not already released. The risks that make this
a hardware investigation rather than a coding task: the controller's state
after SPL/U-Boot (firmware loaded? reset held?), whether an I2C transaction at
that stage hangs the bus, and mux/reset ownership. A failed probe must leave
the animation running without touch, as the spec's "U-Boot touch is not
available" scenario already requires.

## What would count as proof

Serial output of the probe (address, firmware version string, IC-info
checksum result), coordinates echoed for a real finger or a controlled test,
and a glider appearing in stage-1 frames on camera, all on the board, in a
separate change. None of that exists. Recommendation: do not pursue before
the stage-1 animation itself is verified on glass (task 2.3).
