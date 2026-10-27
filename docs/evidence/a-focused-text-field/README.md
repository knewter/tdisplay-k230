# A focused text field raises the keyboard: board evidence

Change: `a-focused-text-field-raises-the-keyboard`. Evidence class: board,
injected touch and keys through `/var/tmp/ui.py`, native `grim`. Not glass,
and not the real base, so suppression (3.5) is not exercised: injected keys
come from a uinput keyboard, not `keyboard-base`.

Build `/nix/store/kllh24ww1vhybcdf6z9z6jz859584jsb-nixos-system-nixos-26.11.20260919.20b1ddd`
(commit `b351d40a`), test-activated, 2026-10-27 ~03:50Z.

- `board/terminal-focus-keyboard-up.png`: the terminal took focus and wvkbd
  rose. Cropped to the keyboard; the terminal text is left out.
- `board/overview-keyboard-lowered.png`: LILYGO+Tab (injected) with the
  terminal focused. The keyboard is down and the card is full size. On build
  `vzizj58r…`, before the compositor lowered it, the same step left the
  keyboard up and the card crushed above it.
- `wayland-info` lists `zwp_input_method_manager_v2` and
  `zwp_text_input_manager_v3`; `shell-osk-focus` is active, and its journal
  has no `unavailable` line.

Not yet run: a GTK entry (3.3), flapping while typing (3.4), suppression after
a base key (3.5) and key integrity (3.6).
