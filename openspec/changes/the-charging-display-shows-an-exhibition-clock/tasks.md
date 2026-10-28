Every board command needs the sole board reservation and the flock on
`/dev/ttyACM0` (or the SSH session the idle-dim evidence used). `D=$(readlink -f
/sys/class/backlight/*)`; `SM="swaymsg -s /run/shell/sway-ipc.sock"` (as the
`shell` user). Evidence classes are kept apart: host build, host test, injected
board input, camera recording, and glass (a person touching the panel). A host
test or build never closes a board task. Depends on
`the-display-dims-and-sleeps-when-idle` for the idle hooks.

## 1. Package ttfx (build only)

- [x] 1.1 Pin `ttfx` v0.5.1 (commit `14ed274`) for riscv64 with its committed
  `Cargo.lock`, licence and notice (`nix/ttfx.nix`, `nix/ttfx/`), exposed as the
  flake package `ttfx`. Proof (build, not boot): `flock /tmp/k230-nix-build.lock
  nix build .#ttfx --max-jobs 1 --cores 4 --out-link "$SCRATCH/ttfx"` then
  `file -L "$SCRATCH/ttfx/bin/ttfx"` reports RISC-V and `share/doc/ttfx/LICENSE`
  exists.
  Done 2026-10-27 (build only): store path `/nix/store/9cnvvxgivs46vwxx43ba0ld28381my0d-ttfx-riscv64-unknown-linux-gnu-0.5.1`; `file -L` reports `ELF 64-bit LSB pie executable, UCB RISC-V`; `share/doc/ttfx/{LICENSE,NOTICE}` present.

## 2. Host logic

- [x] 2.1 The exhibition card (`nix/term-apps/k230_exhibition.py`,
  `nix/exhibition/K230.txt`): minute schedule, effect rotation and timeline,
  drift, frame layout, dismissal reading. Proof (host test):
  `python3 -m unittest tests.test_exhibition`.
  Done 2026-10-27 (host): 19 tests.
- [x] 2.2 The idle decision (`idle_dimmer.py`): charger read, preference read,
  dim launches the card, off is skipped while it is up and charging, resume
  ends it only after a dark wake, `exhibit-end` closes and blanks. Proof (host
  test): `python3 -m unittest tests.test_idle_dimmer`.
  Done 2026-10-27 (host): 27 tests.
- [x] 2.3 Wire `nix/shell.nix` (the card's command line into the dimmer, the
  term-apps install, the `k230-exhibition` command). Proof (parse only, not a
  system build): `nix-instantiate --parse nix/shell.nix` and
  `nix-instantiate --parse nix/term-apps/default.nix`.
  Done 2026-10-27 (parse only); `nix build --dry-run` of the toplevel also evaluated.
- [x] 2.4 The Settings row and preference (`shell_prefs.rs`, `service_ui.rs`,
  `render.rs`, `main.rs`): tap regions meet the 99 px floor at 100% and 200%
  text, in wide and portrait, with and without the modem rows and key
  backlight. Proof (host test): `cargo test --offline --lib` in
  `nix/rust-shell-client`.
  Done 2026-10-27 (host): 650 passed; `cargo check --offline --bins` compiled `main.rs`.
- [x] 2.5 Host renders of the Settings row (Clock and Sleep, 100% and 200%) under
  `docs/evidence/clock-display/host/`, with `tools/blob-scan.py` run and
  `docs/blob-inventory.md` updated. Proof (host render, not glass).
  Done 2026-10-27 (host render): `docs/evidence/clock-display/host/`; `tools/blob-scan.py --no-vendor` ok.
- [x] 2.6 Run the card on the host in a pty with a host `ttfx` and record the
  effect timings and the exit behaviour under `docs/evidence/clock-display/host/`.
  Proof (host pty, not Foot, not glass).
  Done 2026-10-27: `docs/evidence/clock-display/host/README.md`.

## 3. Build gates (no board)

- [x] 3.1 Build the system closure and read the units and the wrapper. Proof:
  `nix build .#nixosConfigurations.k230.config.system.build.toplevel --out-link
  "$SCRATCH/top"` (long; the coordinator owns the slot), then `cat
  "$SCRATCH/top/sw/bin/k230-exhibition"` execs `k230_exhibition.py`, the
  `k230-swayidle` script named in `etc/systemd/system/shell-idle.service`
  contains `--exhibit-exec /nix/store/...-k230-exhibition-card`, and that script
  names the `ttfx` store path from task 1.1.

## 4. Board (hardware-only; one operator holds the board)

Charger operations need the operator at the cable; say so before asking.

- [x] 4.1 Injected board: with the charger connected, read the charger supply:
  `grep -H . /sys/class/power_supply/*/{type,online}`. Record which supply
  reports `online`, on charger and off, under `docs/evidence/clock-display/board/`.
  This grounds or corrects the "non-Battery supply with `online` 1" rule.
- [x] 4.2 Injected board: charger connected, preference Clock
  (`cat /var/lib/k230-shell-prefs/idle-on-charger` absent or `clock`), no input
  for 70 s; `$SM -t get_outputs -r | jq '.[].power'` prints `true`, `cat
  $D/brightness` is a quarter of the prior value, `$SM -t get_tree` lists
  `k230-exhibition`, and a `grim` capture shows the clock. Injected-board proof.
- [x] 4.3 Injected board: the same on battery (charger out) shows no
  `k230-exhibition` and power `false` at 62 s; with `sleep` written to the
  preference file and the charger in, the same. Injected-board proof.
- [ ] 4.4 Injected board: tap the exhibition at a point over an app button (a
  Timer button, with the app's state read before and after) with `ui.py` or
  `tools/board-pointer.py`; the card closes, brightness is restored, the button
  did not act, and `get_tree` shows which card is in front. Repeat with a key
  from the keyboard base if present. Record the in-front card, which settles
  "prior card or Home". Injected-board proof; not glass.
- [ ] 4.5 Injected board: unplug (operator) while exhibiting; the card closes and
  power is `false` within 15 s. Power-key blank while exhibiting, then wake: no
  card, prior card in front.
  Unplug half done 2026-10-27 (9–11.5 s, `docs/evidence/clock-display/board/README.md`);
  the power-key half remains.
- [x] 4.6 CPU: with the exhibition up and the effect interval left at its default,
  sample `/proc/stat` for 60 s in the clock-only phase and again across one
  effect: `awk '/^cpu /{print $2+$3+$4+$7+$8, $2+$3+$4+$5+$6+$7+$8}' /proc/stat`
  at the start and the end, busy/total delta as a percent, plus `ps -o pid,pcpu,comm`
  for `foot`, `sway`, `ttfx`, `python3`. Write the numbers and the command under
  `docs/evidence/clock-display/board/`. Take the same 60 s sample with no card
  (before and after) as the baseline. Pass: the clock-only phase is under 1%
  above the baseline (criterion changed from a whole-system 1% at the
  operator's direction on 2026-10-28). If the
  effect phase pins the CPU, lower `--frame-rate` or cut effects and rerun. Take
  samples with a sleep-paced shell loop, never a busy wait.
- [x] 4.8 Glass: the operator taps and presses a key on the exhibition and reports
  that the app beneath did not react and the prior card returned. Physical proof:
  a timestamped operator report tied to the installed build in the same
  directory. Keep open until it exists.

## 5. Follow-ups, not part of this slice

- [ ] 5.1 Notification-count dot on the card (needs the broker count).
- [ ] 5.2 A separate Exhibition brightness, and a setting for the two-hour cap
  and the effect interval.
- [ ] 5.3 Close the card on pointer-only activity (HDMI mouse) as well.
- [ ] 5.4 A shade tile or a Home action to start the exhibition on demand.
- [ ] 5.5 Camera (moved from 4.7 on 2026-10-28: the operator took the webcam
  for other work and said not to record; not a gate for this slice): the
  webcam on the panel records a clock minute change, one
  position drift and one effect. Look at consecutive raw frames first. Camera
  evidence, not glass, not injected.

## 6. Closeout

- [ ] 6.1 Archive after 4.8, once `the-display-dims-and-sleeps-when-idle` has
  archived; re-check the ADDED requirements against the merged `system/power`.
  Proof: `openspec validate the-charging-display-shows-an-exhibition-clock --strict`.
