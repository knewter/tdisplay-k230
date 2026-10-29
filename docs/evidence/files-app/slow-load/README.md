# Files never finishes loading a folder while it is visible

Board build `2867v7pm…` (`/nix/store/2867v7pmxsw8gk4w5b07zbhz2v0vrlfd-nixos-system-nixos-26.11.20260919.20b1ddd`),
2026-10-29. Evidence class: the board, with Files launched by the drawer's
launcher (`k230-nautilus`) from SSH, native grim captures, `/proc` sampling,
`perf` and `WAYLAND_DEBUG`. Nobody touched the glass. The operator had
reported that "loading is very slow".

## Symptom

`/home/shell` holds four entries. Files opened it and showed "Loading…" with a
spinner. The main thread then used 71% of the single CPU (about 142 ticks
every 2 s) and never went idle:

| Launch | Ran for | Main-thread CPU | Finished loading |
|---|---|---|---|
| stock launcher | 300 s | ~71% throughout | no |
| no toast shadow (`toast { box-shadow: none; }`) | 300 s | ~71% throughout | no |
| stock, then hidden in the sway scratchpad at ~100 s | — | 0 within 5 s of hiding | yes, while hidden |

Voluntary context switches stayed at 40 while involuntary ones rose by about
400 a second. The main thread never slept in `poll`. Turning animations off
(`gtk-enable-animations=0` and `enable-animations=false`) changed nothing:
libadwaita 1.9.3 creates the spinner animation with
`adw_animation_set_follow_enable_animations_setting (…, FALSE)`
(`src/adw-spinner-paintable.c`).

## Where the time goes

`perf record -e cpu-clock` on the main thread: 50% in pixman
`rvv_composite_over_n_8_8888`. The rest is cairo scan conversion under
`gsk_cairo_renderer_render`, through `gsk_outset_shadow_node_draw` (29%) and
`gsk_border_node_draw` (20%). Uprobes on `gsk_renderer_render` counted 117
renders in 5 s (~23 fps), or about 30 ms of CPU per frame.

`WAYLAND_DEBUG=client` for 20 s: 425 of 427 commits sent
`wl_surface.damage_buffer(0, 0, 1282, 618)`, the whole buffer (the 1232×568
card plus the client-side shadow margin). A minimal window holding only an
`AdwSpinner` behaves the same way: 444 full-buffer damages in 15 s. A
`GtkSpinner` gave 333. With no spinner there was one damage and then nothing.
So any animation in any GTK4 app on this image repaints the whole window in
software on every frame.

## Root cause

The region that reaches `gsk_renderer_render` is empty, and the node diff
finds only the spinner's two nodes (`gsk_render_node_diff_impossible`, twice
per frame). The full region comes from the Wayland cairo context, in
`gdk/wayland/gdkcairocontext-wayland.c`, `gdk_wayland_cairo_context_begin_frame`
(GTK 4.22.4; GTK `main` has the same pattern):

```c
surface_region = gdk_wayland_cairo_context_surface_get_region (self->paint_surface);
if (surface_region)
  cairo_region_union (region, surface_region);   /* new damage ∪ this buffer's backlog */
for (l = self->surfaces; l; l = l->next)
  gdk_wayland_cairo_context_surface_add_region (l->data, region);  /* …onto every buffer */
```

The backlog of the buffer being painted is damage the *other* buffers already
drew, but it is added to them again, so a buffer's backlog never shrinks.
Sway on this board holds a client's shm buffer until the next commit, so GTK
alternates two buffers (`wl_buffer#46` and `#48`, each released only after
the other is attached). The first frame of a new buffer is full-surface, and
from then on that full region ping-pongs between the two buffers on every
frame.

That makes each spinner frame cost a full-window software repaint. GDK's
redraw runs at `GDK_PRIORITY_REDRAW` (120). Nautilus adds the loaded files to
the view from idle callbacks at `G_PRIORITY_DEFAULT_IDLE - 20` (180), so with a
frame always due, the view never fills. Meanwhile "Loading…" keeps the
spinner running.

## Fix under test

`nix/patches/gtk4-wayland-cairo-damage.patch` gives the other buffers only
the frame's new damage, then unions the paint buffer's own backlog into the
region it repaints.
