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

## 3. Board (UNVERIFIED until performed; one operator holds the board)

Take the flock on `/dev/ttyACM0` first; deploy with `switch-to-configuration test`.

- [x] 3.1 Protocols advertised: `WAYLAND_DISPLAY=wayland-1 XDG_RUNTIME_DIR=/run/shell wayland-info | grep -E 'text_input|input_method'` lists `zwp_text_input_manager_v3` and `zwp_input_method_manager_v2`.
  Done 2026-10-27 (build `kllh24ww…`): `wayland-info` lists `zwp_input_method_manager_v2` and `zwp_text_input_manager_v3`.
- [x] 3.2 Client bound: `systemctl status shell-osk-focus` is active and `journalctl -u shell-osk-focus -b` has no `unavailable` line. If it does, retry with wvkbd's `--auto` as described in design.md and record the outcome.
  Done 2026-10-27: `shell-osk-focus` active, no `unavailable` line in this boot's journal, without wvkbd's `--auto`.
- [x] 3.3 GTK entry: open a GTK app with a text entry (for example the files app search), tap the entry; the on-screen keyboard rises; tap a non-text area or switch card; it hides. If it does not and the app is GTK3, set `GTK_IM_MODULE=wayland` for the session and repeat. Capture with `grim` (native capture, not QEMU) before and after, plus the journal.
- [x] 3.4 foot: `k230-foot terminal`, focus it; the keyboard rises, then hides on switching away. Watch `journalctl -u shell-osk-focus -f` for repeated show/hide while typing (flapping).
- [ ] 3.5 Suppression: with the base attached, press a key on the base, then within 10 s focus a text field by touch; the keyboard stays down. Wait over 10 s and re-focus; it rises. Inject keys with the camera on the panel; do not assume the operator is touching.
- [ ] 3.6 Keys unaffected: type on the base and on the on-screen keyboard into the focused field; characters arrive intact.
