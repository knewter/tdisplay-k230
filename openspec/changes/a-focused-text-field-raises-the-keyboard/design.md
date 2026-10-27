## Context

Layer: userspace (Nix-built Rust client, one systemd unit, one Python
companion tweak). No compositor, kernel or device-tree change.

Today `wvkbd-mobintl` is shown by SIGUSR2 and hidden by SIGUSR1, both sent by
`k230-keyboard-gesture-signal` (`nix/shell.nix`), which also records
`$XDG_RUNTIME_DIR/k230-keyboard-visible`. Callers: the compositor's gesture
code (`SWAY_K230_KEYBOARD_SIGNAL`, `nix/card-shell/adapter.c`
`keyboard_signal()`), the Rust shell (`K230_KEYBOARD_SIGNAL`, Wi-Fi password,
home and drawer search) and `k230-keyboard-base` (`--osk-signal`, on every key
press).

## Findings (read from the repository and the built store paths, 2026-10-26)

1. **Sway exposes both managers.** The image uses nixpkgs `sway-unwrapped`
   1.12 (plus `sway-k230-card-shell.patch` and `sway-k230-trackpad-ipc.patch`
   under `nix/card-shell.nix`). `strings` on its binary shows
   `wlr_text_input_manager_v3_create` and `wlr_input_method_manager_v2_create`;
   Sway's `input_method_relay` is unpatched by the card-shell patches
   (`grep` of the patch finds neither protocol). So `zwp_text_input_manager_v3`
   (for applications) and `zwp_input_method_manager_v2` (for us) are both
   advertised. Not yet observed with `wayland-info` on the board.
   <!-- UNVERIFIED -->
2. **wvkbd 0.20 does bind input-method-v2, but only as an opt-in.** The
   riscv64 build of `wvkbd-mobintl` contains `zwp_input_method_manager_v2`,
   `get_input_method`, `text_input_rectangle` and an `--auto` option ("Automatically
   toggle visibility based on focus"). The image launches it without `--auto`
   (`nix/shell.nix`, both launch sites), so the lead's assumption that it uses
   only virtual-keyboard holds *as configured*. Whether wvkbd binds the input
   method at registry time regardless of `--auto` is not provable from the
   binary alone (no source in the store); if it does, `k230-osk-focus` receives
   `unavailable` and does nothing, which the board task 3.2 detects.
   <!-- UNVERIFIED -->
3. **foot 1.27.0** contains `zwp_text_input_manager_v3` and
   `zwp_text_input_v3` (`strings`): it enables text input while focused.
4. **GTK4 4.22.4** contains `zwp_text_input_v3` and uses it natively.
5. **GTK3 3.24.52** ships `immodules/im-wayland.so`, which speaks text-input-v3,
   but GTK3 only loads it when `GTK_IM_MODULE=wayland` (or the
   `gtk-im-module` setting) names it. Nothing in `nix/` sets either
   (`grep -rn "GTK_IM_MODULE\|im-wayland" nix` finds nothing), so GTK3 entries
   will not raise the keyboard until the session sets it. This change leaves
   that to board task 3.3: set `GTK_IM_MODULE=wayland` for the session only if
   a GTK3 app on the image needs it. <!-- UNVERIFIED -->
6. The Rust shell client's own text fields (Wi-Fi password, drawer search) use
   `wl_keyboard`, not text-input, so they never emit `activate` and keep their
   explicit signalling; the two paths do not collide.

## Decisions

**A separate client, not `wvkbd --auto`.** `--auto` would be zero code, but
wvkbd would then show and hide itself without writing the
`k230-keyboard-visible` marker that theme restarts and `keyboard-base` rely
on, could not honour the key-press suppression, and would fight the gesture's
state. Rejected, kept as the fallback if finding 2 shows the input method is
unavailable to a second client.

**Observe `activate`/`deactivate`/`done` only.** The client binds the seat's
input method and ignores surrounding text, content type and change cause. It
never calls `commit_string`, `set_preedit_string` or `grab_keyboard`.
Grabbing would route every key through this process on a single CPU and break
the "shell does not grab input" requirement; not acceptable.

**State applies at `done`.** The protocol double-buffers; `Focus` in
`nix/rust-shell-client/src/osk_focus.rs` flips only at `done` and acts only on a
change, so a field-to-field focus move inside one batch is quiet and a
spurious `done` does nothing. Show happens only on inactive to active; hide on
active to inactive. Moving from one field to another with the keyboard
dismissed by gesture leaves it dismissed (rejected: re-raising on every
`activate`, because Sway does not repeat `activate` for a field change within
the same client and the repeat would also fire for content-type updates).

**Key-press suppression through an mtime stamp.** Options: (a) the shell's
own `libinput`/evdev read (second reader, extra wakeups), (b) the input
method keyboard grab (rejected above), (c) a file the base service already
could write. `k230-keyboard-base` already sees every base key press (it reads
the evdev node without grabbing) and calls `hide_osk()` on each, so `hide_osk`
now also touches `$XDG_RUNTIME_DIR/k230-keyboard-base-last-key`. The client
`stat`s it only when a `show` is possible, so there is no polling and no
inotify. Both services run as `shell` with `XDG_RUNTIME_DIR=/run/shell`.
The window is `K230_OSK_SUPPRESS_SECONDS` (default 10, option
`focusKeyboardSuppressSeconds`). A stamp more than a minute in the future (clock
step) is ignored. Touching the on-screen keyboard does not count: only the
base's keys do.

**Hide is unconditional on deactivate.** The helper is idempotent and
`hide` while already hidden only rewrites the marker. Rejected: tracking
"did we show it", which would leave a gesture-raised keyboard up over a
non-text window.

**Service shape.** `shell-osk-focus.service` follows `shell-keyboard-base`
(bound to `shell.service`, user `shell`, restart on failure). A wrapper
script finds the session's single `wayland-*` socket as `k230-shell-rust`'s
wrapper does. It is gated by `k230.shell.focusKeyboard` so it can be turned
off without a rebuild of anything else.

**One CPU.** The process blocks in `wl_display` dispatch; it is idle between
focus changes and each action is one short `pkill` helper spawn.

## Risks

- A second input-method client is refused (`unavailable`): see finding 2.
- Apps that toggle text-input on every cursor move could flap the keyboard;
  the state machine only acts on active-to-inactive transitions, but an app
  that disables and re-enables per keystroke would hide and show repeatedly.
  Board task 3.4 watches for it. <!-- UNVERIFIED -->

## Added after the first board run

- **The overview lowers the keyboard.** A focused terminal keeps its text
  input enabled while the card overview is shown, so the keyboard stayed up
  over the deck and squeezed the card into a sliver above it (build
  `vzizj58r…`). The compositor now sends `hide` when the overview opens
  (`CS_SHRINK` in `adapter.c`). Returning to the app does not raise it again,
  because no new `activate` arrives; the two-finger gesture still does.
- **Touch-only terminal apps are skipped.** foot enables text input for
  every window, so the Timer rose the keyboard over its own buttons (board,
  build `kllh24ww…`, 2026-10-27). Before a show, `k230-osk-focus` reads the
  focused window's `app_id` with one `get_tree` and skips ids in
  `K230_OSK_FOCUS_IGNORE` (`focusKeyboardIgnoreAppIds`: Timer, Clock,
  Weather, Monitor, btop). The terminal, NetHack and 2048 take keys and
  still raise it.
