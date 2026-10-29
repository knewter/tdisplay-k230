## Context

The layer is userspace: GTK 4.22.4's GDK Wayland backend, built from source
in the board closure. The board overlay in `nix/hardware.nix` already
replaces pixman for riscv64, so the whole GTK stack is built locally.
Measurements and the code reading are in
`docs/evidence/files-app/slow-load/README.md`.

`gdk_wayland_cairo_context_begin_frame` keeps a damage backlog on each shm
buffer. It unions the paint buffer's backlog into the frame's region and then
adds that union to every buffer. The backlog is damage the other buffers
have already drawn, so adding it to them means no backlog ever shrinks.
Sway on this board releases a client buffer only after the next commit, so
GTK always alternates two buffers, and a full-surface first frame repeats
forever.

## Goals / Non-Goals

**Goals:** per-frame damage equal to what changed, for every GTK4 app on the
board, without changing app code.

**Non-Goals:** faster full repaints, Nautilus or theme changes, GTK3.

## Decisions

- **Patch GDK, not the apps.** Every GTK4 app, and every animation in it,
  has the defect. A Nautilus-only workaround, such as hiding its loading bar
  or raising its idle priority, would leave Portfolio's spinners, hover
  transitions and libadwaita animations repainting the whole window.
- **The fix.** Add the frame's *new* damage to every buffer other than the
  one being painted, then union the paint buffer's own backlog into the
  region it repaints. That way each buffer's backlog is exactly what was
  drawn since it was last painted. It is still correct with one buffer
  (nothing else to update) and with three or more (each gets every frame it
  missed, once).
- **Carry it in the board overlay** next to pixman, for riscv64 only. QEMU
  keeps its package graph, as it does for pixman.

Rejected, after measurement on the board:

- `toast { box-shadow: none; }` in the generated `gtk.css`: the same 71% CPU,
  and the folder still did not load in 300 s.
- `gtk-enable-animations=0` and `enable-animations=false`: libadwaita's
  spinner opts out of that setting, so nothing changed.
- An empty user `gtk.css`: the damage was still full-window, so the theme is
  not the cause.
- A GL renderer: the board has no GL driver, and llvmpipe on one CPU would
  cost more.

## Risks / Trade-offs

- [The patch is wrong and leaves stale pixels when buffers alternate] →
  check grim captures of an animating window and the Files folder view on
  the board, and compare damage logs. Rolling back is a revert of one
  overlay entry.
- [Rebuilding gtk4 dependents lengthens the next system build] → it happens
  once. The host keeps the board closure.
- [Carrying a GTK patch] → it is small and local. Upstream `main` has the
  same code, so the patch should apply to later versions until upstream
  fixes it.

## Migration Plan

Build the board system, `nix copy`, `switch-to-configuration test`, verify,
then promote through `/boot/bootargs.txt` as for any build.
