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

## GTK4 entry with the Sway patch (task 3.3), build `gpgh1vx6…` (commit `e8056ece`)

Board, injected touch and keys, native `grim`, 2026-10-27. Files launched
from the Home dock as usual (no tracing). `board/gtk-search-keyboard-up.png`:
Home, Files open, the search button tapped at 17:01:46Z with the entry focused and
the keyboard up, then a tap meant for the file area that landed on the raised
keyboard's "h" key and typed "h" into the entry. `board/gtk-search-closed-keyboard-down.png`:
Backspace emptied the entry, GTK closed the search bar and the keyboard went
down; Starred then opened by touch at 17:02:15Z with the keyboard still down.
`shell-osk-focus` logs nothing on show/hide, so its journal only shows the
restart; the captures are the record. A GTK3 entry was not tried.

## foot while typing: no flapping (task 3.4), build `gpgh1vx6…`

`shell-osk-focus` writes nothing per show/hide, so the journal cannot show
flapping. Instead `board/kbwatch.py.txt` (run as `/var/tmp/kbwatch.py 100`)
blocks on inotify and prints each replacement of
`/run/shell/k230-keyboard-visible`, which `k230-keyboard-gesture-signal`
rewrites on every show and hide call, from any caller. Log:
`board/foot-typing-kbwatch.log`; captures: `board/foot-typing-no-flap.png`.

From Home the dock's terminal was tapped at 17:06:13Z: one `show`. Then 26
keys ("echo flap test one two three") typed through the injected uinput
keyboard between 17:06:17Z and 17:06:23Z, plus Enter: no events, and the
line echoed intact. Switching to the overview at 17:06:25Z gave `hide`, and
tapping Home at 17:06:28Z a second `hide`. The keys came from the injected
uinput device, not the base or the on-screen keyboard, so 3.5 and 3.6 remain.

## Base attached: no keyboard on focus (task 3.5), 2026-10-28 23:02–23:04

Build `vf91pbq6…`, test-activated, with the shell restarted and `shell-idle`
stopped. Evidence class: **injected** (`ui.py` uinput touch, plus a uinput
keyboard that is not the base) with native `grim` captures. The base's
`tca8418` was listed in `/proc/bus/input/devices`. No base key was pressed
after the shell restart: `k230-keyboard-base-last-key` did not exist, so the
10 s rule could not be what kept the keyboard down. The visibility marker
`/run/shell/k230-keyboard-visible` was read after each step.

| Step | Result | Capture |
| --- | --- | --- |
| Drawer, tap the search field | Cursor in the field, no keyboard; injected F, I, L typed "fil" and listed Files | [`drawer-tap.png`](board/base-attached/drawer-tap.png), [`drawer-typed.png`](board/base-attached/drawer-typed.png) |
| Terminal opened from the drawer, tapped | foot focused, no keyboard; marker still `hide` from 23:02:34 | [`terminal.png`](board/base-attached/terminal.png) |
| Two-finger swipe up from the bottom edge | Keyboard rose; marker `show` at 23:03:38 | [`gesture.png`](board/base-attached/gesture.png) |
| Files, tap the search button (GTK4 entry) | Entry focused, "fil" typed, no keyboard; marker still `hide` from the handle swipe at 23:04:02 | [`gtk-typed.png`](board/base-attached/gtk-typed.png) |

**Limits.** The keys came from an injected keyboard, not from the base's
matrix. There is no same-build control without the base, because the base
cannot be detached in software. Before this rule, 3.3 and 3.4 showed the
same fields raising the keyboard.

**Operator report.** After this deploy the operator, who had first reported
the keyboard rising over the drawer search with the base attached, tried it
again on the glass and replied "worked great" (2026-10-28). That is a glass
report without detail: it records no field list and no typed text.

**On-screen keyboard typing (task 3.6, glass half), injected.** On the same
build with the base attached, a terminal was opened from the drawer and the
keyboard raised with the two-finger swipe. Injected taps on its `l`, `s` and
Enter keys ran `ls`, which listed the home directory, and the keyboard stayed
up throughout ([`osk-typed-ls.png`](board/base-attached/osk-typed-ls.png)).
