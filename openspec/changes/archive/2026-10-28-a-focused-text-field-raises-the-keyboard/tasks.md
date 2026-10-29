Host build and unit tests are one evidence class; a board observation of the
panel is another. Nothing below claims the second from the first. Store board
evidence under `docs/evidence/focus-keyboard/` with commands, timestamps and
limits.

## 1. Findings

- [x] 1.1 Record in design.md whether Sway, wvkbd, foot, GTK3 and GTK4 on this image speak input-method-v2 / text-input-v3. Proof: `strings` of the store paths named in design.md.

## 2. Client, wiring and host tests

- [x] 2.1 Pure focus/suppression state in `nix/rust-shell-client/src/osk_focus.rs` and the `k230-osk-focus` binary (`src/bin/k230-osk-focus.rs`) using the already-locked `wayland-protocols-misc 0.3.9`. Proof: `cd nix/rust-shell-client && cargo test --offline` (all pass, including `osk_focus::tests`).
- [x] 2.2 `keyboard_based.py` stamps `k230-keyboard-base-last-key` on each base key press. Proof: `python3 -m unittest tests.test_keyboard_based`.
- [x] 2.3 `shell-osk-focus.service` and the `focusKeyboard` options in `nix/shell.nix`. Proof: `nix-instantiate --parse nix/shell.nix` (syntax only; evaluation and the package build are not run here).
- [x] 2.4 Build the package: `flock /tmp/k230-nix-build.lock nix build .#packages.riscv64-linux.k230-shell-rust --max-jobs 1 --cores 4 --out-link $SCRATCH/osk` (confirm the exact attribute with `nix flake show`) and check `ls $SCRATCH/osk/bin/k230-osk-focus`. Host cross-build proof only.
  Done 2026-10-27 as part of the landscape system build: `shell-osk-focus.service` execs `…-k230-shell-rust-…/bin/k230-osk-focus` through `k230-osk-focus-session`.
- [x] 2.5 `openspec validate a-focused-text-field-raises-the-keyboard --strict`.
- [x] 2.6 While the base's keys (`tca8418` under /sys/class/input) are present, no focus shows the on-screen keyboard: `keyboard_base::keys_present`, checked by `k230-osk-focus` before a show and by the drawer search's tap. Proof: `cd nix/rust-shell-client && cargo test --offline --lib keyboard_base` (7 passed on the host, 2026-10-28; host only). The full `cargo test --offline` also fails `settings_568x1232_matches_the_committed_evidence_exactly` in `tests/responsive_pixel_identity.rs`, and that test fails the same way on unmodified master.

## 3. Board (UNVERIFIED until performed; one operator holds the board)

Take the flock on `/dev/ttyACM0` first; deploy with `switch-to-configuration test`.

- [x] 3.1 Protocols advertised: `WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/shell wayland-info | grep -E 'text_input|input_method'` lists `zwp_text_input_manager_v3` and `zwp_input_method_manager_v2`.
  Done 2026-10-27 (build `kllh24ww…`): `wayland-info` lists `zwp_input_method_manager_v2` and `zwp_text_input_manager_v3`.
- [x] 3.2 Client bound: `systemctl status shell-osk-focus` is active and `journalctl -u shell-osk-focus -b` has no `unavailable` line. If it does, retry with wvkbd's `--auto` as described in design.md and record the outcome.
  Done 2026-10-27: `shell-osk-focus` active, no `unavailable` line in this boot's journal, without wvkbd's `--auto`.
- [x] 3.3 GTK entry: open a GTK app with a text entry (for example the files app search), tap the entry; the on-screen keyboard rises; tap a non-text area or switch card; it hides. If it does not and the app is GTK3, set `GTK_IM_MODULE=wayland` for the session and repeat. Capture with `grim` (native capture, not QEMU) before and after, plus the journal.
- [x] 3.4 foot: `k230-foot terminal`, focus it; the keyboard rises, then hides on switching away. Watch `journalctl -u shell-osk-focus -f` for repeated show/hide while typing (flapping).
- [x] 3.5 Base attached (rule changed 2026-10-28 at the operator's request; 3.3 and 3.4 were proved before it, so they show the mechanism, not the current rule): with the base attached, tap a GTK entry, a foot terminal and the app drawer's search field, more than 10 s after the last base key. The keyboard stays down and the keyboard's gesture still raises it. Typing on the base itself belongs to 3.6. Without the base, a 10 s suppression after a base key still applies, but it needs the base detached and is not required here. Use injected touch and keys with native `grim` captures (the webcam was reassigned), and do not assume the operator is touching.
  *Done 2026-10-28, injected, build `vf91pbq6…` (docs/evidence/a-focused-text-field/README.md § Base attached): with `tca8418` present and no base key pressed since the shell restart, tapping the drawer search, a foot terminal and the Files GTK4 search entry raised no keyboard, and injected keys typed into each. A two-finger swipe from the bottom edge raised it.*
- [x] 3.6 Keys unaffected: type on the base and on the on-screen keyboard into the focused field; characters arrive intact. This includes the drawer search, a foot terminal and a GTK entry with the base attached and the keyboard down (moved here from 3.5 on 2026-10-28).
  *Operator, 2026-10-28, build `vf91pbq6…`, after being asked to try the drawer search with the base: "worked great". That covers the base part only, in general terms and without per-field detail. Typing on the on-screen keyboard was done by injection the same day: `ls` typed on it ran in foot (docs/evidence/a-focused-text-field/README.md). Operator at the glass, 2026-10-28, same build, base attached: typed `echo base ok` on the base in Terminal, pressed Enter, and confirmed it printed `base ok` exactly ("yup").*
