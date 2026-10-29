## Why

Opening a folder in Files can take minutes, and while the window is on screen
it may never finish. On 2026-10-29, build `2867v7pm…` showed "Loading…" for
more than 300 s on a home folder of four entries, with one CPU 71% busy. The
same folder loaded as soon as the window was hidden. The operator reported:
"loading is very slow".

The cause is in GTK, not Nautilus. While any GTK4 window animates, even a
lone spinner, it repaints its whole surface in software on every frame,
because GTK's Wayland cairo context never lets damage shrink once two buffers
alternate. On this board that costs about 30 ms a frame. A redraw is always
due, so Nautilus's idle-priority work that fills the view never runs, and the
"Loading…" spinner never stops. See `docs/evidence/files-app/slow-load/README.md`.

## What Changes

- Patch GTK 4.22.4 for the board closure. In
  `gdk/wayland/gdkcairocontext-wayland.c`, each frame's new damage goes to the
  other buffers, and only the buffer being painted takes its own backlog.
  The board overlay that already rebuilds pixman carries the patch, so every
  GTK4 app on the image (Files, Portfolio, libadwaita) uses it.
- No Nautilus change, and no theme or CSS change. Removing the toast's
  shadow, and turning GTK animations off, were both measured and changed
  nothing.

Non-goals:

- Making full-window software repaints cheaper (pixman, a GL renderer).
- Changing Nautilus's loading priorities, or hiding its loading bar.
- GTK3 apps (Net). They use a separate code path and were not measured here.
- Sending the fix upstream. It is worth doing, but it is not this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `runtime/files`: Files finishes loading a folder while its window is
  visible. An animating GTK4 window damages only what changed.

## Impact

- `nix/hardware.nix` (board overlay) and
  `nix/patches/gtk4-wayland-cairo-damage.patch`.
- Rebuilds gtk4 and its dependents in the board closure: libadwaita,
  gnome-desktop, libglycin-gtk4, libportal-gtk4, Nautilus and Portfolio. QEMU
  keeps its package graph.
- Needs the physical board: the failure only appears with this compositor's
  buffer release timing and this CPU. A host build proves only that the
  patch applies.
