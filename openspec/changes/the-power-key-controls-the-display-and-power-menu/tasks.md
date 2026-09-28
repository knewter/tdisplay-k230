## 1. Button identity and safe input path

- [ ] 1.1 Identify the user's lower physical button against the board marking and PMU INT0/RESET wiring; record operator observation and cited schematic/vendor source under `docs/evidence/power-key/identity/README.md`, and verify the record names which switch can be intercepted by Linux.
- [x] 1.2 Port the vendor PMU edge-input path without its long-hold auto-poweroff or system-off callback, enable its DT and Kconfig bindings, and verify `nix build .#kernel` and `nix build .#deviceTree` succeed.
- [ ] 1.3 Stage the candidate kernel/DTB with the guarded `/boot` update path, boot with the reserved console, and record `python3 tools/console.py /dev/ttyACM0 --wait=3 'cat /proc/bus/input/devices'` plus a real short press/release event log; verify that the same system stays running. Keep this hardware task unchecked if the press still resets or release never arrives.

## 2. Press timing and display

- [x] 2.1 Add a single named-device power-key handler and configure logind to leave `KEY_POWER` to it; verify host state-machine tests cover a short press, hold, repeats, bounce, disconnect and one action per gesture, then build its narrow Nix derivation.
- [x] 2.2 Use the proven `output DSI-1 power off/on` route for short presses and reconcile state after service restart; verify a host fake-command test does not turn a hold into a short press or wake into an app action.
- [ ] 2.3 On the physical board, record camera and serial evidence of a real tap turning the panel off, a second real tap restoring the same session and brightness, and no reset; verify the panel result against the named `tools/console.py` system/uptime command and store it in `docs/evidence/power-key/display/`.

## 3. Power sheet and confirmation

- [ ] 3.1 Add the Rust shell `power` route with themed sheet, large touch targets, dismiss/Cancel, Power off and Restart; verify `cargo test` in `nix/rust-shell-client` and `nix build .#handheld-shell-rust`.
- [x] 3.2 Route a held physical key to that sheet and use the existing bounded Settings power request path for a second confirmation; verify host tests cover hold-open, duplicate suppression, cancel, outside dismissal, denied action and no command before confirmation.
- [ ] 3.3 Verify the integrated NixOS closure with `nix build .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel`, then record real-button/glass proof of hold → sheet → Cancel and hold → named confirmation without execution under `docs/evidence/power-key/sheet/`.
- [ ] 3.4 With an explicit physical trial, verify confirmed Restart and Power off independently, including return on power-on; capture serial/camera evidence and any recovery limitation. Keep this task open until both are observed.

## 4. Reconcile and publish

- [ ] 4.1 Run `openspec validate the-power-key-controls-the-display-and-power-menu --strict`, commit the physical evidence with exact commands and limits, and archive only when every task and named proof above is complete. Verify merged `master`, pushed revision, CI and the published capability page.
