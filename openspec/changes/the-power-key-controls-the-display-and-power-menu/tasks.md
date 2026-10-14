## 1. Button identity and safe input path

- [x] 1.1 Identify the user's lower physical button against the board marking and PMU INT0/RESET wiring; record operator observation and cited schematic/vendor source under `docs/evidence/power-key/identity/README.md`, and verify the record names which switch can be intercepted by Linux.
  Done 2026-10-14 (operator + board-read): the operator's button is the top
  right one with the board in the keyboard case; each press logs `INT0 press`
  and `INT0 release` and arrives as `KEY_POWER` on "K230 PMU Power Key" with
  no reset, so it is SW2 (PMU INT0). `docs/evidence/power-key/identity/README.md`.
- [x] 1.2 Port the vendor PMU edge-input path without its long-hold auto-poweroff or system-off callback, enable its DT and Kconfig bindings, and verify `nix build .#kernel` and `nix build .#deviceTree` succeed.
- [x] 1.3 Stage the candidate kernel/DTB with the guarded `/boot` update path, boot with the reserved console, and record `python3 tools/console.py /dev/ttyACM0 --wait=3 'cat /proc/bus/input/devices'` plus a real short press/release event log; verify that the same system stays running. Keep this hardware task unchecked if the press still resets or release never arrives.
  Done 2026-10-14 (board-read over SSH, on the installed mainline landscape
  image rather than a staged candidate): `/proc/bus/input/devices` lists the
  key, and `evemu-record` logged two taps as press/release pairs (195 ms and
  160 ms) with the boot ID unchanged. Limit: read over SSH, not
  `tools/console.py`, because `/dev/ttyACM0` on this bench is another device.
  `docs/evidence/power-key/mainline-events/`.

## 2. Press timing and display

- [x] 2.1 Add a single named-device power-key handler and configure logind to leave `KEY_POWER` to it; verify host state-machine tests cover a short press, hold, repeats, bounce, disconnect and one action per gesture, then build its narrow Nix derivation.
- [x] 2.2 Use the proven `output DSI-1 power off/on` route for short presses and reconcile state after service restart; verify a host fake-command test does not turn a hold into a short press or wake into an app action.
- [x] 2.3 On the physical board, record camera and serial evidence of a real tap turning the panel off, a second real tap restoring the same session and brightness, and no reset; verify the panel result against the named `tools/console.py` system/uptime command and store it in `docs/evidence/power-key/display/`.
  Done 2026-10-14 (board-read + operator): the board logged `DSI-1` power
  false at 16:24:12 and true at 16:24:16 with continuous uptime and one boot
  ID; operator: "it worked". Camera waived by the operator; no serial log
  (`/dev/ttyACM0` is another device). `docs/evidence/power-key/display/`.

## 3. Power sheet and confirmation

- [x] 3.1 Add the Rust shell `power` route with themed sheet, large touch targets, dismiss/Cancel, Power off and Restart; verify `cargo test` in `nix/rust-shell-client` and `nix build .#handheld-shell-rust`.
  Done 2026-10-14 (host): the `power` route paints the themed sheet with
  68 px Restart…, Power off… and Cancel rows, and a named two-button
  confirmation; `cargo test` passes (511 + 22) and `nix build
  .#handheld-shell-rust` built at master `339fb0f6` (`jj55fw9i…`). Board
  captures: `docs/evidence/power-key/sheet/`.
- [x] 3.2 Route a held physical key to that sheet and use the existing bounded Settings power request path for a second confirmation; verify host tests cover hold-open, duplicate suppression, cancel, outside dismissal, denied action and no command before confirmation.
- [ ] 3.3 Verify the integrated NixOS closure with `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`, then record real-button/glass proof of hold → sheet → Cancel and hold → named confirmation without execution under `docs/evidence/power-key/sheet/`.
  Partial 2026-10-14 (operator + native captures,
  `docs/evidence/power-key/sheet/`): hold opened the sheet, Cancel closed it,
  and Restart… showed the named confirmation with nothing run (boot ID
  unchanged). The trial found the confirmation's split bar easy to mis-tap and
  the sheet not closing on a swipe; the revised sheet (two named buttons,
  larger tap area, swipe to close) has host tests only. Open: the revised
  sheet on the board, and the named `k230-coherent-shell` toplevel build.
- [x] 3.4 With an explicit physical trial, verify confirmed Restart and Power off independently, including return on power-on; capture serial/camera evidence and any recovery limitation. Keep this task open until both are observed.
  Operator decision 2026-10-14 ("we want the power-off code back"): the
  mainline driver now restores the vendor's system-off callback
  (`devm_register_power_off_handler`, the patch 0064 register sequence:
  long-press wake source, `PMU_STATUS` normal power-down, PMU system-control
  pulse). The vendor's automatic 5 s `orderly_poweroff()` stays out, as task
  1.2 decided. Reason: keyboard-base 6.6 showed `systemctl poweroff` only
  halted with the board powered (no SBI SRST), draining the battery.
  Power-on afterwards is by a ~3 s hold of the power key (96000 PMU ticks).
  Partial 2026-10-14 (`docs/evidence/power-key/power-off/`): with the handler,
  `systemctl poweroff` cut power (operator: "it shut off this time") and a
  ~3 s power-key hold started the board again with USB-C still connected; a
  reboot returned on its own (board-read). Open: Restart and Power off
  confirmed from the shell's sheet, with serial or camera evidence.
  Done 2026-10-14 (board-read + operator, `docs/evidence/power-key/sheet/`):
  Restart confirmed from the sheet ran `systemctl reboot` and the board came
  back on its own (boots `ccd3f704…` to `c988db76…`); Power off confirmed from
  the sheet ran `systemctl poweroff`, the board stayed dark until a ~3 s key
  hold (operator: "it did"), then booted `dadc6e5c…`. Limit: no serial or
  camera capture (camera waived; `/dev/ttyACM0` is another device).

## 4. Reconcile and publish

- [ ] 4.1 Run `openspec validate the-power-key-controls-the-display-and-power-menu --strict`, commit the physical evidence with exact commands and limits, and archive only when every task and named proof above is complete. Verify merged `master`, pushed revision, CI and the published capability page.
