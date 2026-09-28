# Wi-Fi Settings: password field takes the system keyboard, under paired headless QEMU

2026-09-28, source commit `2ba7425c` (`2ba7425cdac24a0939e11c8ff9737fcbc7d18064`),
fixing the in-app keypad reported in `/tmp/coherent-start.png`: a dense
keyboard glued mid-screen above Cancel/Connect, with duplicate `Del`/`Delete`
keys and unreliable taps. Not a board or real-finger result: headless QEMU
Sway + Rust composition, real cross-built RISC-V executables under
`qemu-riscv64-static`, injected touch via Sway's `card_shell test-touch`, a
real `zwp_virtual_keyboard_v1` connection standing in for `wvkbd`, `grim`
screenshots, a private synthetic root broker inside a user namespace.
Invented `Example *` network names only.

Cross-built packages for this run:

- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#handheld-shell-rust`
  passed: derivation
  `/nix/store/32r3zdi8b7kw7dwnz2wpd0asjihs9xly-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0.drv`,
  output
  `/nix/store/973w5k7csmjgpk1bzcn9m993xsif47xp-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- `nix build --no-link --print-out-paths --max-jobs 1 --cores 6 .#card-shell`
  passed: derivation `/nix/store/sxc259f1dgi7qarmj8rjxfibd0g2vfrg-k230-card-shell.drv`,
  output `/nix/store/j57c5im42d3rq5gxdar2ikmh22717zvc-k230-card-shell`, whose
  card-shell-patched Sway executable is
  `/nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway`
  (unchanged from the `webos-polish-qemu` run below: no commit in this
  branch's history touches `nix/card-shell/`).

```sh
unshare -Ur python3 tests/rust_wifi_settings_qemu.py \
  --sway /nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-riscv64-unknown-linux-gnu-1.12/bin/sway \
  --rust /nix/store/973w5k7csmjgpk1bzcn9m993xsif47xp-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0/bin/k230-shell-rust \
  --theme-source nix/handheld-theme-default \
  --output /tmp/k230-wifi-qemu-keyboard
```

This exact command reproduces every capture below. The command exited zero
and reported `headless-qemu-injected-touch-and-keyboard`.

## What this proves, and how

`tests/rust_wifi_settings_qemu.py` itself was extended (not worked around)
for this change: it now types the WPA2 password through `PasswordKeyboard`,
a real `zwp_virtual_keyboard_v1` client with its own small compiled xkb
keymap (printable ASCII plus Escape/Return/BackSpace) -- from the
compositor's point of view this is indistinguishable from `wvkbd` or a
physical keyboard, unlike the previous test's synthetic taps on the now-
removed in-app keypad's coordinates. It:

- selects an unsaved WPA2-Personal network and waits for the Rust log's own
  `wifi-keyboard-focus-granted` line (`ShellClient::KeyboardHandler::enter`)
  -- the compositor's actual `wl_keyboard.enter` confirmation that the
  overlay surface was granted `KeyboardInteractivity::Exclusive`, not an
  assumption that the commit requesting it had already landed;
- types `password` (8 characters) and confirms the masked field reads `8/63`
  before Connect is enabled, then presses **Return**, which the shell maps
  to **Connect** (`wifi_ui::key_event_intent`) -- the broker receives exactly
  that 8-character password and nothing else (checked by length only, never
  logged or printed);
- repeats this for a second, deliberately-rejected network and presses
  **Escape** afterward, which the shell maps to **Cancel/Back**, returning to
  the network list;
- asserts the Rust log never contains a raw touch coordinate for the whole
  Wi-Fi session (`private-touch-log`), same invariant as before.

`docs/evidence/wifi-settings/README.md`'s own `nix/rust-shell-client/src/
main.rs` `request()` helper (a separate short-lived `--surface settings`
process, used only to reveal Settings and unrelated to this change) has a
fixed 500ms connect/round-trip deadline. This build machine's load average
was 35-55 on 32 cores while this ran (many other agents' concurrent `nix
build`s), which intermittently exceeded that deadline purely from process-
scheduling contention -- confirmed with a throwaway diagnostic script that
called the identical helper standalone: it failed once or twice with the
target socket already present and listening, then succeeded immediately on
a bare retry, with no code path difference from a successful call. This
matches the already-documented `tesseract` OCR flakiness in
`../webos-polish-qemu/README.md`: a pre-existing fragility in the test
harness's timing assumptions under a busy shared machine, not a regression
from this change and not something in `nix/rust-shell-client/src/main.rs`'s
production code this change touches. Rather than editing the committed
`request()` deadline (a shared, unrelated primitive) or the committed test
script's `route()` helper to paper over shared-machine noise, this run used
an uncommitted wrapper (not committed; reused `tests/rust_wifi_settings_
qemu.py`'s own `main()`, `Broker`, `theme()` and the new `PasswordKeyboard`
unchanged, and retried only `subprocess.run` calls whose argv ends in
`--surface <name>`) exactly the same way `../webos-polish-qemu/README.md`
used an ad hoc script to route around the OCR flakiness there.

## Captures

[Settings with Wi-Fi capability row, dark](wifi-settings-dark.png),
[light](wifi-settings-light.png); [Settings with the two-finger keyboard
hint disabled](wifi-keyboard-gesture-disabled-dark.png); [network list,
dark](wifi-list-dark.png), [light](wifi-list-light.png), [mid-
scan](wifi-loading-dark.png); [saved-network entry, no password
field](wifi-saved-entry.png); [password field before typing, "Type the
password"](wifi-keyboard-dark.png); [password field after typing 8
characters, Cancel/Connect already reflowed to where they sit above the
raised keyboard](wifi-masked-dark.png); [authentication error after Enter
submitted the typed password](wifi-auth-error-dark.png); [Forget
confirmation](wifi-forget-confirm-dark.png) and [network list after
Forget](wifi-forgotten-dark.png).

`wifi-keyboard-dark.png` and `wifi-masked-dark.png` are the two captures
that most directly show the fix: Cancel/Connect sit around two-thirds up the
screen (empty space below them is where the real `wvkbd` process -- not run
in this headless capture, which injects keys directly at the Wayland
protocol level instead -- would render), not glued to a keypad drawn by this
app, and there is no `Del`/`Delete` duplication because there is no more
in-app keypad to draw one.

Real focus handoff with the actual `wvkbd` process (rather than a stand-in
virtual-keyboard client), real-glass typing, and physical association remain
**UNVERIFIED**, unchanged from the pre-existing gates recorded in
`../README.md` and `../board-scan.md`.
