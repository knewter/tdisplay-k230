## Context

`nix/rust-shell-client/src/main.rs` already launches installed desktop
entries: `launch_app` (drawer taps) called `self.hide()` before spawning
`launch_selected`, which re-parses the `.desktop` file with
`gio::DesktopAppInfo::from_filename` and calls `app.launch(&[], None)`.
`launch_home_app` (Home/dock taps) calls `focus_or_launch`, which looks up
`running_con_id` over `swaymsg -r -t get_tree` and focuses it, or falls
through to the same `launch_selected`. `hide()` drops the shared
`Layer::Overlay` `LayerSurface` (`self.layer`) entirely, unmapping it, which
is what let whatever card was already focused show through, unstyled and
unresponsive, until the new app's window happened to map. Neither path knew
when a launch actually finished; a Home-only `launch_started`/`launching`
pair drove a blind 3-second "reopen the drawer" fallback that fired whether
or not the app was about to succeed.

`icon.rs`'s `IconCache::paint(cr, icon, size, x, y)` already resolves a
desktop entry's `Icon=` key (through the installed freedesktop icon theme,
including scalable SVG via librsvg) and paints it into any Cairo context at
any size, with its own bounded per-size decode cache; it needed only a
raised size cap (128px -> 192px) to admit a "large" 176px splash icon.
`render.rs` already has a proven pattern for a cached, geometry-keyed
bitmap repainted cheaply every frame (`RendererCache::draw`'s
`static_pixels`) and an eased-alpha convention for a full-screen dim
(`tray_backdrop_alpha`). Nothing in this client had ever spoken sway's own
IPC protocol directly before this change -- every existing use
(`running_con_id`, `focus_con`, `swaymsg_back`) shells out to the `swaymsg`
binary. `tests/card_shell_runtime.py`'s own `ipc()` helper proves the wire
format this change's `sway_ipc.rs` reimplements in Rust: `i3-ipc` magic,
then a native-endian `u32` length and `u32` type, matching `sway-ipc(7)`'s
documented framing exactly; `sway-ipc(7)` also documents that a `window`
event's `container.pid` is "the PID of the application that owns the
window", and a `window`/`new` event's `container` already carries it.

## Goals / Non-Goals

**Goals:** a full-screen splash within one frame of a tap, in every launch
entry point (drawer, Home, dock); the theme's real background colour and
the app's own icon/name, never a placeholder; the previously active app
never visible in between, even for one frame; a real hand-off the instant
the launched window maps, detected without relying on `app_id` (which a
`Terminal=true` entry defeats, since it maps as its terminal, not the
launched entry); explicit, recoverable timeout and process-exit states;
cheap on a single slow RISC-V core running a software (Pixman) compositor.

**Non-Goals:** a grow-from-the-tapped-icon-rect scale animation (see
Decision 3); a compositor-side (`adapter.c`) placeholder card (Decision 1);
any change to which apps exist, how the drawer/Home/dock lay them out, or
how window switching/gestures behave once an app is showing; a generic
sway-IPC client library (only `window`/`SUBSCRIBE` are implemented, and
only as much of each as the splash needs).

## Decisions

1. **The splash lives in the Rust client, on its existing overlay surface
   -- not a compositor-side placeholder card in `nix/card-shell/adapter.c`.**
   The client already owns one `Layer::Overlay` `LayerSurface` shared by the
   drawer/shade/Settings/theme-chooser (`self.layer`), and `Layer::Overlay`
   already composites above every ordinary toplevel by construction. That
   means the flash was never a compositor ordering problem -- it was this
   client tearing its own surface down (`hide()`) before the replacement was
   ready. Keeping that same surface mapped and simply repainting it as the
   splash (`start_splash`, replacing the old `self.hide()` call in
   `launch_app`) removes the flash with no `adapter.c`/`card-shell-policy.c`
   change at all: nothing about focus handoff, view mapping, or z-order
   needed to move, because the overlay already sat on top of the view that
   would otherwise flash. A card-shell placeholder was considered and
   rejected: it would duplicate icon/name rendering in C
   (`nix/card-shell/render.c`/`icon.c` have their own separate Cairo-less
   drawing path), need a new IPC message from the Rust client to the
   compositor naming which card is "the splash", and still leave the Rust
   client needing its *own* window-map detection to know when to ask the
   compositor to remove that placeholder -- strictly more moving parts for
   the same outcome. The trade-off: a Home/dock-triggered splash must call
   `ensure_layer`, which is not free (an `xdg_surface`-style `configure`
   round trip before the very first attach), so that path's first frame is
   one Wayland round trip later than a drawer tap's (whose overlay is
   already mapped and configured). That is still well under one visible
   frame on a local Wayland connection and nowhere near what it replaces
   (an uncontrolled, multi-hundred-millisecond process-start gap).

2. **Window-map detection subscribes to sway's own `window` IPC event and
   matches by pid/`/proc` ancestry, not `app_id`.** `gio::AppLaunchContext`
   emits its `launched` signal synchronously inside `app.launch(...)` itself
   (a direct `g_signal_emit`, not scheduled through a `GMainContext`) --
   proven against the real `glib`/`gio` runtime in
   `route_tests::launch_selected_captures_the_real_spawned_pid_with_no_glib_main_loop_running`,
   not just reasoned about, since this client runs no glib main loop at all.
   `platform_data`'s `pid` key (present since glib 2.72, for a launch GIO
   itself spawned) is captured into a `Cell` the closure can reach, with no
   `Mutex`/thread-safety needed since it never leaves the launch call.
   `sway_ipc.rs` is a from-scratch, minimal client (`write_message`/
   `try_parse_frame`/`watch_window_events`) matching the wire format
   `tests/card_shell_runtime.py`'s Python helper already proves against a
   live sway; adding the `swayipc` crate was rejected as unnecessary weight
   for "subscribe to one event type and read `change`/`container.pid`".
   Matching walks a bounded (4-hop) `/proc/<pid>/stat` ppid chain
   (`splash::pid_or_ancestor`) rather than only exact-pid equality, covering
   a `Terminal=true` entry (which GIO/the desktop file's own Exec spawns as
   the configured terminal directly -- that terminal process *is* the
   window's owner, so an exact pid match already covers the common case)
   and any one-hop shell-wrapper indirection a quoted `Exec=` can add. When
   GIO reports no pid at all (a launch whose `platform_data` never carried
   one), the target degrades to `SplashTarget::LaunchOrder`: match the next
   `window`/`new` event, full stop -- sound only because `launch_in_flight`
   already serializes this client to one launch at a time, so there is
   never a second candidate to confuse it with. A process-liveness check
   (`sway_ipc::process_alive`, a plain `/proc/<pid>` existence check) runs
   alongside the IPC watch so a process that exits before mapping anything
   is detected without waiting for `SPLASH_TIMEOUT`.

3. **Motion is an opaque-backdrop-first icon/name fade-in, not a
   grow-from-the-tapped-icon-rect scale.** The task's own preference was
   "ideally grows from the tapped icon's rect ... at minimum fades in
   quickly". A grow animation needs the tapped icon's exact on-screen rect
   threaded out of whichever grid computed it (drawer or Home/dock, two
   different layout modules), a per-frame scaled/clipped repaint of the
   whole composed splash bitmap, and touches this hardware's one slow
   RISC-V core doing everything through Pixman software rasterization was
   explicitly asked to keep cheap. Instead: `render.rs`'s
   `ensure_splash_bake` paints the theme background colour plus every line
   of text into a `(name, width, height, status)`-keyed bitmap exactly
   once (rebuilt only when one of those four actually changes, e.g. a
   `Pending` -> `TimedOut` status transition); this bake is unconditionally
   *opaque*, so the previously active app cannot show through even during
   the fade. `draw_splash` then composites only the icon on top each frame,
   through `IconCache`'s own existing per-size decode cache (so re-painting
   it every frame is already a cheap cached blit, not a redecode), ramped
   through an ease-out cubic alpha (`splash::fade_alpha`, mirroring the
   existing `tray_backdrop_alpha` convention) over 220ms -- inside the
   requested 200-250ms band. This is one `memcpy`-sized backdrop copy plus
   one small cached-surface composite per frame, an explicit, bounded cost
   this hardware can sustain, versus an unbounded-resolution scale/clip
   operation repeated every frame of the transition.

4. **The pre-existing blind 3-second "reopen the drawer" timeout is
   removed, not layered underneath the splash.** It existed only because a
   failed/stuck drawer launch had no other way to recover
   (`launching`/`launch_started` existed for exactly this). The splash now
   owns that whole story with real signals (`LaunchOutcome`, `SplashSignal`)
   instead of a blind clock: `TimedOut` after `SPLASH_TIMEOUT` (10s, chosen
   to clear an ordinary cold start -- icon decode, catalog re-parse, process
   exec, first frame -- with room to spare) with an explicit tap-to-dismiss/
   Home affordance, and `Failed` (immediately, from the real `Err` this
   launch's own thread already reports, or from `SplashSignal::
   ProcessExited`) auto-dismissing after `FAILED_AUTO_DISMISS` (1.6s, long
   enough to read "Couldn't open <Name>", short enough that "dismiss" reads
   as automatic). Keeping the old 3-second clock running underneath would
   have raced the new one and reopened the drawer mid-splash for a launch
   that was about to succeed.

## Risks / Trade-offs

- [A Home/dock tap's first splash frame is one Wayland round trip later
  than a drawer tap's] -> accepted (Decision 1); still far below the
  gap it replaces, and unlike a drawer tap there is no pre-existing overlay
  content that could flash in the meantime (Home has none).
- [A quoted `Exec=` that GIO spawns through an intermediate shell puts the
  window's owner more than one hop below the captured pid] -> the bounded
  4-hop `/proc` walk covers this for any launch this client actually ships
  (a hand-authored NixOS desktop entry, not an attacker-controlled one);
  `splash::pid_or_ancestor`'s own tests cover exact, one-hop, and
  bounded-multi-hop ancestry, plus a ppid cycle terminating instead of
  looping.
- [The `sway_ipc` watcher thread's own socket/IO failure leaves a `Pending`
  splash with no further signal] -> deliberately degrades to
  `SPLASH_TIMEOUT` rather than guessing at a false "process exited"; a
  live process is never misreported as failed.
- [No card-shell/`adapter.c` change means this fix is entirely dependent on
  the client's own overlay always compositing above every toplevel] ->
  already a load-bearing invariant of the existing shell (the drawer/shade/
  Settings would all have the same flash risk otherwise), not a new
  assumption this change introduces.
- [QEMU's headless Pixman backend proves wiring/timing under synthetic
  touch and a fixture window, not real-glass readability, touch-dismiss
  feel, or that the previous app is imperceptible on the physical panel] ->
  both remain explicit open board tasks; QEMU evidence is recorded as
  exactly that evidence class, never inferred as hardware proof.

## Migration Plan

No data/format migration: this only changes what the Rust client paints
during a launch and how it decides a launch finished. Existing desktop
entries, icon themes, and the Home/drawer/dock layouts are unaffected.
Land the source change, host tests, and (if the QEMU harness proves
practical for a synthetic mapped window) a QEMU splash-and-handoff capture,
then hand off to the board for the real-glass acceptance this design
cannot itself provide: splash timing/readability, touch-dismiss on
`TimedOut`/`Failed`, a real `Terminal=true` launch mapping and handing off
correctly, and confirmation that the previously active app is never
perceptibly visible during a real launch.
