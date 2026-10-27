## Why

Tapping a text field does nothing to the on-screen keyboard. A person who
touches a search box, a GTK entry or the terminal has to know the two-finger
gesture, perform it, and then perform it again to put the keyboard away.
Firefox OS raised its keyboard when a field took focus and lowered it when
focus left; people expect that from a touch handheld. The one exception today
is the shell's own Wi-Fi password field, which signals the keyboard itself.

The inverse already exists: pressing a key on the keyboard base hides the
on-screen keyboard. Raising it on focus must not undo that, so a field that
takes focus while a person is typing on the base leaves the keyboard down.

## What Changes

- Add `k230-osk-focus`, a small Wayland input-method client in
  `nix/rust-shell-client`. When a focused text field becomes active it runs
  the existing keyboard signal helper with `show`; when focus leaves the
  field it runs `hide`. It never commits text, sets preedit or grabs the
  keyboard.
- Suppress `show` for 10 s after the last physical key press from the
  keyboard base. `nix/keyboard-base/keyboard_based.py` records each press as
  the mtime of `$XDG_RUNTIME_DIR/k230-keyboard-base-last-key`.
- Start it as `shell-osk-focus.service` with the coherent shell
  (`k230.shell.focusKeyboard`, default on; `focusKeyboardSuppressSeconds`).
- Add a requirement to `runtime/shell`.

## Non-goals

- No text-input state other than focus: no surrounding text, content-type
  layouts (numeric, email), autocorrect or candidate lists.
- No change to the two-finger gesture, its animation or `wvkbd` itself.
- No second keyboard path: the helper and its `k230-keyboard-visible` marker
  stay the only way the keyboard is shown or hidden.
- Applications that never speak text-input-v3 (GTK3 without the Wayland input
  module, Qt without its plugin) are not made to; they keep the gesture.

## Needs the physical board

Host unit tests cover the decision logic. Whether Sway delivers `activate` for
a focused foot terminal and GTK entry on this image, and whether the keyboard
rises, is board work and stays `UNVERIFIED` until observed. Not provable under
QEMU, which runs solid backdrops and no touch/OSK interaction.
