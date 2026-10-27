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

## Touch-only terminal apps (build `iw96wr9d…`, commit `93dc4efb`)

On build `kllh24ww…` focusing the Timer raised the keyboard over its
buttons. With `focusKeyboardIgnoreAppIds`, `board/timer-focus-keyboard-down.png`
(2026-10-27 ~15:19:55Z) shows the Timer focused and running with the
keyboard down, and a terminal launched the same way still raised it.

## GTK4 entry did not raise the keyboard (task 3.3, failed on `zs05li2k…`)

Tapping the Files search entry focused it ("Search everywhere") but the
keyboard stayed down (`board/gtk-search-no-keyboard.png`, 2026-10-27
~16:55Z). A `WAYLAND_DEBUG=1` trace of Nautilus
(`board/gtk-late-text-input-trace.txt`) shows the cause: GTK4 creates its
`zwp_text_input_v3` only after the first touch has already moved keyboard
focus to it, Sway sends `enter` only on focus changes, so GTK's `enable`
arrives for a text input with no focused surface and wlroots ignores it.
Foot creates its text input at startup, which is why the terminal works.
`nix/patches/sway-k230-text-input-late-enter.patch` sends `enter` when a text
input is created for the client that already holds keyboard focus. Task 3.3
stays open until a build with the patch raises the keyboard for the entry.
