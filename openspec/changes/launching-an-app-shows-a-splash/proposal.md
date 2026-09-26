## Why

Tapping an app in the drawer, on Home, or in the dock today leaves whatever
was already on screen visible while the process starts. On this hardware
that gap is not instant: icon/catalog work, process exec, and the new
client's own Wayland handshake all take real time, so a person sees the
previous app sit there, unresponsive to their tap, before the one they
asked for finally appears. Nothing tells them the tap registered.

## What Changes

- The moment a person taps an app (drawer, Home, or dock), show a
  full-screen splash within one frame: the theme's background colour, the
  app's icon large and centred (from the `.desktop` `Icon=` key, via the
  existing `icon.rs`/librsvg path), and the app name below it. The backdrop
  paints fully opaque on its very first frame; only the icon/name ease in
  over ~220ms, so the previously active app is never uncovered even
  momentarily.
- Keep the splash up until the launched app's window actually maps, then
  hand off to it as an ordinary card. Detect the map through a new, minimal
  hand-rolled sway IPC `window` event subscription (no `swayipc` crate
  existed in this client before), matched against the spawned process's pid
  (captured via `gio::AppLaunchContext`) or its bounded `/proc` ancestry --
  covering `Terminal=true` entries and other one-hop indirection, which map
  as their terminal's own `app_id`, not the launched entry's.
- If the app is already running, keep the existing focus-or-launch path;
  the splash is shown for at most one IPC round trip before the real window
  is focused, never a fabricated full one.
- Add two recoverable failure states: `Pending` becomes `TimedOut` ("Taking
  longer than usual...", tap to dismiss or return Home) after about 10s with
  no matching window, and a spawned process exiting before any window maps
  shows "Couldn't open <Name>" and dismisses itself shortly after (or on a
  tap).
- Keep the splash on the client's own existing overlay surface rather than
  a compositor-side placeholder card: `nix/card-shell/adapter.c` needs no
  change, because the overlay already composites above every ordinary
  toplevel, and never unmapping it during the transition is what removes
  the flash. `design.md` records why this was chosen over a card-shell
  placeholder.

**Non-goals:** a grow-from-the-tapped-icon-rect scale animation (considered
and rejected for this hardware's cost budget -- see `design.md`); a
notification/toast system; any change to the drawer/Home/dock catalog,
gesture, or window-switching behavior beyond what a launch's own splash
needs; a compositor-side placeholder-card implementation.

## Capabilities

### Modified Capabilities

- `runtime/shell`: launching a desktop entry now shows an instant splash
  with icon/name, hands off on the real window mapping, and exposes
  explicit timeout/failure states, superseding the previous "leave a
  visible explanation" wording for a launch failure with the concrete
  splash-based one.

## Impact

Affects `nix/rust-shell-client` (`splash.rs`, `sway_ipc.rs` are new;
`main.rs`, `render.rs`, `icon.rs` are modified) and its own test suite. No
device tree, kernel, boot, or card-shell/adapter.c change. Host build and
`cargo test`/`cargo clippy` can (and did) complete without the board; a
QEMU harness proves the splash paints and hands off under the headless
Pixman backend, but only the physical board proves real-glass timing,
touch-dismiss feel, and that the previous app is never perceptibly
uncovered on real hardware. Both remain open until that evidence exists.
