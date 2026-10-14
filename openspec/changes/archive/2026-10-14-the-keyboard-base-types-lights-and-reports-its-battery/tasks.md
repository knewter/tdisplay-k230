Evidence classes are named per task: **host** (build or unit test), **QEMU**,
**board-read** (a command on the running board), **injected** (synthetic
evdev), **camera**, and **operator** (a person at the real keys or glass). A
host or QEMU result never ticks a board task.

## 1. Read-only probe (board)

- [x] 1.1 Write `tools/keyboard-base-probe.sh`:
  - it reads the mux of IO2, IO28/29, IO42/43, IO46/47, IO50/51 and IO52 from
    pinctrl debugfs (the pinctrl driver owns the IOMUX, so `/dev/mem` is
    refused);
  - it samples IO42, IO43 and IO52 only when they are already inputs;
  - it scans the base's bus with `i2cdetect -r -y` on hardware I2C4
    (IO46/47, function 3; design Decision 2);
  - it reads only identity, status and configuration registers: BQ25896
    0x00–0x14 except the fault register 0x0C, which clears on read; BQ27220
    0x06–0x3C standard commands; TCA8418 CFG 0x01–0x03; XL9555 0x00–0x07;
    DRV2605 status;
  - it makes no register writes, which the script asserts.

  Proof (**host**): `bash -n tools/keyboard-base-probe.sh` and a review of the
  write-free command list.
- [x] 1.2 Run the probe on the board with the base attached, holding
  `flock /tmp/k230-board.lock`, and commit the output to
  `docs/evidence/keyboard-base/probe/`. Record:
  - which addresses answer;
  - IO43's level;
  - the charger's live charge-current, regulation-voltage, termination and
    precharge fields;
  - the gauge's design capacity;
  - whether DRV2605 is fitted.

  Proof (**board-read**): the committed probe log.
- [x] 1.3 If the TCA8418 or XL9555 does not answer, try the hardware
  controller on function 3 once and record the result. Then open the
  enable/power question as an explicit task here, before group 3. The battery
  groups proceed independently. Proof (**board-read**): the committed result.
  Both answered on the hardware controller itself, so no enable task opens.

## 2. Pins and bus (device tree, kernel)

- [x] 2.1 Add the `canaan,k230-pinctrl` node and states for IO42, IO43, IO46,
  IO47 and IO52 only, plus the hardware I2C4 node (design Decision 2), to
  `nix/dts/k230-tdisplay-mainline-drm-common.dtsi`.
  Proof (**host**): `nix build .#deviceTreeMainlineDrm`.
  Done: the pinctrl states and the `i2c@91409000` node are in the dtsi.
  `nix build .#deviceTreeMainlineDrm` built on 2026-10-14
  (`y4j8bwc0…-k230-tdisplay-mainline-drm.dtb`).
- [x] 2.2 Push the DTB with `tools/push-file.py --src <dtb> --dest /boot/k230-tdisplay.dtb --reboot`.
  Record that the console on `/dev/ttyACM0` still logs in, that the panel and
  touch work, and that `i2cdetect -y <bus>` lists the 1.2 addresses.
  Proof (**board-read**): the console log and `i2cdetect` output in
  `docs/evidence/keyboard-base/bus/`.
  Done 2026-10-14 (**board-read**): installed through the boot bundles, not
  `push-file.py`. The serial getty is active, the panel is connected, touch
  and the keypad take interrupts, and `i2cdetect -y -r 1` lists 0x20, 0x34,
  0x55, 0x6b (bound) and 0x38 (`docs/evidence/keyboard-base/bus/README.md`).

## 3. Keys and Caps Lock (kernel, device tree, Nix)

- [x] 3.1 Generate the 7×10 `linux,keymap` from the vendor code table:
  - legends map to ordinary key codes;
  - FN and FN-R are `KEY_RIGHTALT`;
  - LILYGO is `KEY_LEFTMETA`;
  - MIC is `KEY_MICMUTE`.

  Add the `ti,tca8418` node, the IO43 `gpio-hog` at the level 1.2 observed,
  and `KEYBOARD_TCA8418`. Proof (**host**): a generator unit test that
  round-trips every vendor code (the table names 65 of codes 1–68; 4, 30 and
  31 are unused), then `nix build .#deviceTreeMainlineDrm`. Done with
  `tools/keyboard-base-keymap.py` and `tests/test_keyboard_base_keymap.py`.
- [x] 3.2 Add the `k230-base` xkb symbols file, with the vendor Shift table and
  the Fn layer, and the Sway input stanza for the base only. Proof (**host**):
  `xkbcli compile-keymap` with the layout, plus a test asserting each vendor
  Shift symbol, with its result.
  Done as a complete keymap, `nix/keyboard-base/k230-base.xkb`, loaded with
  Sway's `xkb_file` for `1:1:tca8418`. `xkbcli compile-keymap --keymap` (1.13.2)
  compiles it, and `tests/test_keyboard_base_xkb.py` drives libxkbcommon:
  every Shift symbol, Caps capitals, the digit row and the Fn layer pass;
  changing one symbol makes it fail.
- [x] 3.3 Add the `nxp,pca9555` node at the probed address and the three
  `gpio-leds`. Enable `GPIO_PCA953X` and `LEDS_GPIO`.
  Proof (**host**): `nix build .#kernelMainlineDrm`.
  Board-read (no camera): the LEDs register and switch their lines, in
  `docs/evidence/keyboard-base/leds/`.
- [x] 3.4 Install on the board. Record:
  - `evtest` on the base's device for every key (**board-read**, with an
    operator pressing);
  - `ls -la` typed into foot, shown in a native `grim` capture and a camera
    frame (**operator** + **camera**);
  - a Shift-punctuation line;
  - Caps Lock with its LED lit in a camera frame.

  Store all of it in `docs/evidence/keyboard-base/keys/`.
  Partial evidence: `evtest-2026-10-13T211125Z.log` and the evemu recordings
  in `keys/` (board-read), and the operator typing on the base throughout
  6.2. Closed by the operator: "keyboard seems good to me dont worry about
  recording" and "waive the camera pics" (2026-10-14). There is no
  `ls -la` capture, Shift line or Caps Lock frame.

## 4. Key backlight (device tree, then kernel)

- [x] 4.1 Add IO52 as a `gpio-leds` `k230::kbd_backlight`. Proof (**host**):
  `nix build .#deviceTreeMainlineDrm`. Then (**camera**) a frame with it on
  and a frame with it off, written through sysfs, in
  `docs/evidence/keyboard-base/backlight/`. The line itself switches
  (`docs/evidence/keyboard-base/leds/`, board-read); the camera frames remain.
  Closed 2026-10-14: the line switches (board-read), Settings' Key backlight
  row toggles the LED (injected tap), and the operator waived the camera
  frames ("waive the camera pics").
- [x] 4.2 Port the vendor K230 PWM driver and switch IO52 to PWM4 with a
  `pwm-leds` entry of the same name. Proof (**host**):
  `nix build .#kernelMainlineDrm`. Then (**camera**) three distinct
  brightness levels.
  Done 2026-10-14: `nix/patches/mainline/pwm-k230.c` (forward-port with
  prescale, disabled-output and polarity fixes), `pwm@9140a040`, and IO52 on
  function 2 as a 0–255 `pwm-leds` at 20 kHz. Built as part of
  `.#kernelMainlineDrmShellLandscapeBootFiles`. On the board (**board-read**),
  the PWM registers track 255, 128, 32, 4 and 0. **Operator**, camera waived:
  "it dims fine, off is dark" (`docs/evidence/keyboard-base/backlight/`).

## 5. Battery and charger (kernel, device tree)

- [x] 5.1 Write the forward-port patch adding BQ27220 to `bq27xxx`. It is
  read-only, with no data-memory writes. Enable `BATTERY_BQ27XXX_I2C`.
  Proof (**host**): `nix build .#kernelMainlineDrm`.
- [x] 5.2 Add the `ti,bq25896` node with the 1.2 register values and
  `CHARGER_BQ25890`. Document any field the driver would rewrite. Proof
  (**host**): `nix build .#deviceTreeMainlineDrm` and a reviewed
  field-by-field table in `docs/evidence/keyboard-base/charger/`.
  Done 2026-10-14: `charger@6b` with `linux,skip-reset` and
  `linux,read-back-settings`, every `ti,*` value equal to the register it
  names; `nix build .#deviceTreeMainlineDrm` built. The table and the one
  rewritten field (REG02 CONV_RATE) are in the charger README. On the board
  only REG02 changed on bind.
- [x] 5.2a Find the BQ25896 INT line. `bq25890_charger` will not bind
  without an interrupt (`No irq resource found`), and neither LILYGO's code
  nor its pin map names where INT goes; the XL9555's INT is equally
  unknown. Until this is found, 5.2 adds no charger node. When it binds,
  use `linux,skip-reset` and `linux,read-back-settings`, so the driver reads
  the charge parameters instead of writing them. It still writes
  CHG_CONFIG=1 and WATCHDOG=0 (both already set) and CONV_RATE. Proof
  (**board-read**): the line identified on the board, with the method
  recorded.
  Partial 2026-10-14: not identified. INT reaches no GPIO-muxed K230 line:
  `gpiomon -e both` on every unclaimed line of both GPIO chips during a
  USB-C unplug and replug saw no edge, and LILYGO's pin map names no INT.
  Pads muxed away from GPIO are not covered (the IOMUX readout is a
  placeholder). The charger no longer needs it to bind:
  `bq25890-poll-without-irq.patch` polls the IRQ handler every 2 s when no
  interrupt is given, and the board logs `no interrupt; polling every 2000 ms`.
  Closing this without the line needs the operator's scope decision.
  Public-source search 2026-10-14 (operator asked; `docs/evidence/
  keyboard-base/charger/int-line-search.md`): no keyboard-base schematic is
  published, LILYGO's pin map names no INT for the BQ25896 or XL9555, and
  LILYGO's own launcher polls the charger over I2C every 30 s. Finding the
  net now needs a continuity probe of BQ25896 pin 1 on the base PCB, or
  LILYGO's schematic.
  Closed by operator scope decision 2026-10-14, with the line still
  unidentified: "yeah close charger interrupt line do what lilygo does i
  guess". The charger stays on polling: LILYGO polls over I2C every 30 s, and
  this kernel polls every 2 s. Nothing here claims the line was found.
- [x] 5.3 On the board, record:
  - `power_supply` `capacity`, `status`, `voltage_now` and `current_now`;
  - the charger's `online` value, cable in and cable out;
  - the charger registers before and after binding, unchanged except for the
    named fields.

  Proof (**board-read**): the logs in `docs/evidence/keyboard-base/charger/`.
  Partial 2026-10-14: gauge capacity, status, voltage and current on USB, on
  battery (cable out, about -405 mA) and in charger Hi-Z (`Discharging`, then
  `Charging` once restored); charger `online` 1 with the cable in and 0 in
  Hi-Z; registers before and after bind, only REG02 CONV_RATE changed.
  Done 2026-10-14: with the cable physically out (operator), the charger read
  `online` 0, `Discharging`, no VBUS, EN_HIZ clear; the gauge `Discharging`
  at about -400 mA (`cable-out-2026-10-14.log`).
- [x] 5.4 If 1.2 found a DRV2605, add its node and `INPUT_DRV260X_HAPTICS`,
  and record its input device appearing (**board-read**). Otherwise record
  "not fitted" and close the task. Not fitted: 0x5A did not answer
  (`docs/evidence/keyboard-base/probe/`).

## 6. Shell use (Nix, Rust shell client)

- [x] 6.1 Add the `k230-keyboard-base` user service. It reads evdev without
  grabbing it and handles:
  - hiding wvkbd;
  - the backlight following typing, with the idle timeout and panel-off;
  - the Caps Lock LED from xkb state.

  Proof (**host**): unit tests with a fake evdev stream, and
  `nix build` of its derivation.
- [x] 6.2 Add the Sway bindings:
  - Super for the drawer;
  - Super+Tab for the overview;
  - Fn+LILYGO for a `grim` screenshot;
  - Esc as back only when nothing has focus.

  Proof (**host**):
  `nix build .#nixosConfigurations.k230-mainline-drm-shell-landscape.config.system.build.toplevel`.
  Built as part of `.#kernelMainlineDrmShellLandscapeBootFiles` (system
  `w3isqi2b…`). Esc-as-back is in the keyboard-base service rather than a
  Sway binding, because a binding would take Esc from focused apps. It
  calls `card_shell back` only when no app has focus, with unit tests.
  Board follow-up 2026-10-14 (**operator** + **board-read**): LILYGO opens
  the drawer. Of five real LILYGO+Tab presses, two reported Shift 23–46 ms
  before Tab, so Sway saw Super+Shift+Tab and the terminal got it; the
  overview binding now also takes Super+Shift+Tab. Fn+LILYGO "did nothing"
  because the screenshot gave no sign; it now blinks the key backlight and
  adds a "Screenshot saved" notification. Fn reaches the board as
  `KEY_RIGHTALT` (`fn-evemu-record-2026-10-14T0237Z.txt`). The operator then saw the overview
  open but Tab also reach the terminal: Sway delivers the key for an
  `--input-device` binding, so the chord bindings are now global (injected
  experiment in the keys README). Recording:
  `docs/evidence/keyboard-base/keys/shortcuts-evemu-record-2026-10-14T0112Z.txt`
  and `shortcuts-sway-bindings-2026-10-14T0112Z.json`.
- [x] 6.3 Add the battery to the shade, and the keyboard backlight control to
  Settings, persisted under `/var/lib/k230`. Both are hidden when their device
  is absent. Proof (**host**): `cargo test` in `nix/rust-shell-client`, plus
  host renders with and without a fake `power_supply`/LED tree.
  The shade reuses `home_widgets::battery`; Settings' "Key backlight" row is an
  on/off preference that `keyboard_based.py` re-reads, so Off keeps the keys
  dark. The preference is `/var/lib/k230-keyboard-base/key-backlight`, a
  shell-owned directory beside `/var/lib/k230` (a child of the root-only 0700
  directory would be unreachable to the `shell` user). Tests:
  `keyboard_base::tests`, `render::tests::the_shade_shows_a_battery_line_only_when_a_battery_exists`,
  `render::tests::settings_shows_the_key_backlight_row_only_when_the_led_exists`,
  `service_ui::tests::the_key_backlight_row_is_tappable_only_when_the_led_exists`,
  and `tests/test_keyboard_based.py` (preference off keeps the LED dark). Host
  renders: `docs/evidence/keyboard-base/shell/host-renders/`. Not glass or board
  evidence; 6.5 records that.
  Board (**board-read**, native `grim`, 2026-10-14): the landscape shade shows
  "100% - Full" from the real gauge, in
  `docs/evidence/keyboard-base/shell/board/`. In landscape the Key backlight row
  sits below the panel edge and Settings does not scroll (injected drag); that
  predates this task and is tracked by landscape task 8.3.
- [x] 6.4 Add the `k230-battery-policy` service and its Nix options. Proof
  (**host**): state-machine tests covering 15%/5% once each, two readings at
  3%, the countdown, a cancel on charge, and disabled. `tests/test_battery_policy.py`
  (7 tests, including the `/run/k230-battery-policy.json` override used by
  6.6); options `k230.shell.batteryPolicy.*`. Installed on the board as
  system `iw5x7hn5…`, where the service is active with 15/5/3.
- [x] 6.5 On the board, record:
  - a key press hiding the on-screen keyboard, and the LILYGO-key launch flow
    (**operator** + **camera**);
  - the shade's battery and the Settings control, in native captures;
  - Home's Battery widget leaving its "no battery info" state.

  Store all of it in `docs/evidence/keyboard-base/shell/`.
  Partial 2026-10-14: the shade's battery line and the Settings Key backlight
  row (native captures; the row toggled by injected taps, preference file
  `off` then `on`) in `docs/evidence/keyboard-base/shell/board/`. The operator
  reports LILYGO opens the drawer. Open: camera frames, the key press hiding
  the on-screen keyboard, and Home's widget.
  2026-10-14: Home's Battery widget reads 100 % on the board (native
  capture `home-battery-widget.png`, widget added to a test layout).
  Camera frames waived by the operator (Operator, 2026-10-14: "waive the camera pics".). Still open: a key
  press hiding the on-screen keyboard.
  Done 2026-10-14: the operator reports "pressing a key hides the osk"
  (**operator**; camera waived).
- [x] 6.6 Exercise the low-battery policy on the board with the thresholds
  raised temporarily through a `/run` override, so a real discharge crosses
  them. Record the notifications, the countdown, the cable cancel, and one
  clean shutdown in the journal.
  Proof (**board-read** + **camera**): `docs/evidence/keyboard-base/battery-policy/`.
  Partial 2026-10-14 (board-read): with a `/run` override of 100/99/98 % and
  the charger in Hi-Z for a real ~400 mA discharge, the journal records the
  low and very-low notifications, the critical countdown, a cancel when the
  charger came back, a second countdown and logind's orderly poweroff through
  `systemd-shutdown`. The board then halted with the panel lit instead of
  powering off: no SBI SRST and no PMU power-off handler, so a shutdown on
  battery keeps draining it. Open: a real power-off (power-key task 3.4's
  handler), then one clean shutdown that actually removes power, and the
  camera frame.
  2026-10-14: the PMU power-off handler is restored and the same
  `systemctl poweroff` now removes power (`docs/evidence/power-key/power-off/`).
  Rerun 02:18–02:31 CDT on that kernel: same notifications, countdown and
  cancel, then the policy's poweroff cut power (operator: "it went fully
  dark"); the power key started it again, charger reconnected by the test's
  cleanup. Native capture of the countdown in the shade. The camera frame
  this task names is waived by the operator (Operator, 2026-10-14: "waive the camera pics".).

## 7. Close

- [x] 7.1 Run `openspec validate the-keyboard-base-types-lights-and-reports-its-battery --strict`
  and `python3 tools/blob-scan.py --no-vendor`. Merge, push, and check CI and
  the published spec pages. Archive only when every task above has its named
  proof committed.
  Done 2026-10-14: validate --strict and blob-scan pass at 9ba70f63; master
  pushed, Spec site run 38623895514 built and deployed, and the published
  backlight evidence page carries the live-slider record. Every task above has
  its proof committed; the charger cold start and base-absent boot keep their
  UNVERIFIED grounding markers in the specs.
