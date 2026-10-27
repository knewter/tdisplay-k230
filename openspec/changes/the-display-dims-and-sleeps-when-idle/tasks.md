Every board command needs the sole board reservation and the flock on
`/dev/ttyACM0`. `D=$(readlink -f /sys/class/backlight/*)`; `SM="swaymsg -s /run/shell/sway-ipc.sock"`
(run as the `shell` user). Host tests and a host build are not board proof.

## 1. Host-testable logic

- [x] 1.1 Add the idle dimmer (`nix/idle-dimmer/idle_dimmer.py`) and its tests.
  Verify: `python3 -m unittest tests.test_idle_dimmer` (host only).
- [x] 1.2 Make power_keyd restore idle dimming when it lights the display.
  Verify: `python3 -m unittest tests.test_power_keyd` (host only).
- [x] 1.3 Add the touch wake gate (`nix/card-shell/wake-gate.h`) and its rules test.
  Verify: `python3 -m unittest tests.test_card_wake_gate` (host only).
- [x] 1.4 Wire `shell-idle` (swayidle 30 s dim / 60 s off), the `inhibit_idle`
  rules, and the power_keyd `--idle-wake` argument in `nix/shell.nix`.
  Verify: `nix-instantiate --parse nix/shell.nix` (parse only; not a system build).

## 2. Build gates (host or QEMU, no board)

- [x] 2.1 Build the card-shell compositor with the adapter change.
  Verify: `nix build .#card-shell --out-link "$SCRATCH/card-shell"` (build only; adapter.c
  has not been compiled yet). Take the build slot first.
  Done 2026-10-27: the landscape system build compiled the patched Sway after `2cc67965` fixed a declaration-order error (`wake_gate` was used before its declaration).
- [x] 2.2 Build the system closure with `shell-idle` and read the unit.
  Verify: `nix build .#nixosConfigurations.k230.config.system.build.toplevel --out-link "$SCRATCH/top"`
  then `cat "$SCRATCH/top/etc/systemd/system/shell-idle.service"` shows the swayidle arguments.
  Done 2026-10-27 with the landscape system (`kllh24ww…`): `shell-idle.service` runs `k230-swayidle`, which execs `swayidle -w timeout 30 "… dim …" resume "… resume …" timeout 60 "… off …"`.
- [ ] 2.3 QEMU or headless smoke: on a headless Sway run `swaymsg output '*' power off`,
  inject a touch with the existing card-shell test input, and show the swallowed
  sequence never reaches a probe client. Record the evidence class as QEMU/headless.

## 3. Board proof (UNVERIFIED until run)

- [x] 3.1 Deploy to the board (operator action). Idle 30 s: `cat $D/brightness` is a quarter of the
  value read before; `systemctl status shell-idle` is active.
  Done 2026-10-27T03:42:33Z (build `prk64sjw…`, read over SSH): brightness 148 dimmed to 37, power still true, `shell-idle` active. `docs/evidence/idle-dim/`.
- [x] 3.2 Idle 60 s: `$SM -t get_outputs -r | jq '.[].power'` prints `false`; `cat /run/shell/idle-dimmer.json`
  shows `"off": true`; the session and open apps survive.
  Done 2026-10-27T03:43:03Z: `"power": false`, `idle-dimmer.json` `{"saved": 148, "dimmed": 37, "off": true}`, and the terminal survived. `docs/evidence/idle-dim/`.
- [ ] 3.3 Wake by power key: the display lights, `cat $D/brightness` equals the prior value, and a
  further 30 s idle dims again (proves the `seat * cursor move 0 0` re-arm).
- [ ] 3.4 Wake by touch with an app open whose button sits under the finger: the display lights,
  the app does not act on the tap (check the app's log or state), `cat $D/brightness` is restored,
  and a lone `journalctl -u shell` shows no touch delivery. Use the webcam, not a user report.
  First confirm Sway still receives touch on the off output; if not, record that and design a
  libinput-level wake instead.
- [x] 3.5 Video inhibit: start the video app, leave it 90 s with no input; brightness stays and
  `get_outputs` power stays true. Return Home and confirm dim at 30 s and off at 60 s.
  Repeat with the Timer app.
  Done 2026-10-27 (injected): Timer focused held 148 for 103 s; Video focused held it ~98 s; at Home with Video playing behind, build `zs05li2k…` (commit `be58ff02`) dimmed to 37 at 15:46:55Z and turned the output off at 15:47:17Z. Two earlier builds failed the Home part (unfocused video kept inhibiting). `docs/evidence/idle-dim/`.
- [ ] 3.6 Slider while dim: dim, set brightness through the shade, then wake; `cat $D/brightness`
  keeps the slider value.
- [ ] 3.7 Base-keyboard key on a dark panel lights the display (accepted to reach the app).

## 4. Follow-ups, not part of this slice

- [ ] 4.1 Settings row for the timeout (Off / 1 min / 5 min), persisted beside the existing
  settings and read by `shell-idle` at start. Needs its own Rust service request and a
  `runtime/shell` or `display/backlight` delta.
- [ ] 4.2 The HDMI-unplug wake in `nix/touch-trackpad/src/shell_ipc.rs` powers the display on
  without reporting activity; make it run `k230-idle-dimmer wake` so the panel does not stay dim.
- [ ] 4.3 Decide whether charging should defer idle off, and whether the wallpaper video should
  stop decoding while the display is off.
