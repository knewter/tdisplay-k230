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

## Patched GTK, loaded by hand (task 2.1)

Evidence class: the board with injected launches. This is not yet a system
build. The patched gtk4 (`/nix/store/44233ralwykx4v001h9i07dcm8wpa4k6-gtk4-riscv64-unknown-linux-gnu-4.22.4`,
derivation `kdn7aa7w…`, the same one the overlay in `nix/hardware.nix`
evaluates to) was copied to the board. Each test process's
`/proc/<pid>/maps` showed it mapping that `libgtk-4.so.1.2200.4`. For the
Python probe, `GI_TYPELIB_PATH` needed the patched typelib first, because
the typelib names its library by absolute store path.

| Window | GTK | Commits | Full-buffer damages | Typical damage |
|---|---|---|---|---|
| lone `AdwSpinner`, 15 s | stock | 444 | 444 | `(0, 0, 1282, 618)` |
| lone `AdwSpinner`, 15 s | patched | 794 | 2 | about 25×26 px at the spinner, e.g. `(631, 315, 26, 25)` |
| Files on `/home/shell`, 20 s | stock | 427 | 425 | `(0, 0, 1282, 618)` |
| Files on `/home/shell`, 20 s | patched | 10 | 2 (at startup) | the file view `(325, 141, 932, 452)` once loaded, then small header regions |

Files on `/home/shell` through the stock launcher plus
`LD_LIBRARY_PATH=<patched gtk4>/lib`: the main thread went idle 8.4 s after
launch (`IDLE at t=8.4 main_ticks=264`). Two stock launches were still busy
after 300 s. `patched-loaded.png` is a grim capture about 12 s after a
patched launch: all four entries, no loading bar, and no stale pixels where
the spinner was. `stock-loading.png` is the stock launch stuck on
"Loading…".

Scripts (copied to `scripts/`, run from `/var/tmp` on the board): `files_probe.py` (launch, then sample
per-thread CPU every 2 s until two quiet samples or 300 s),
`files_ab.sh`, `spin_probe.py` and `spin_probe.sh`. `spin_probe.sh` reads the typelib path from `/var/tmp/gi_typelib_path`, which was taken from Portfolio's wrapper.

## System build, opened from the drawer (task 2.2)

Evidence class: the board with injected touch. Nobody touched the glass.
Build `/nix/store/1lpsniwgxxz9bqk83261lbb0k8q6hpqz-nixos-system-nixos-26.11.20260919.20b1ddd`,
activated with `switch-to-configuration test` on 2026-10-29. The Files
process (pid 14670) mapped
`/nix/store/44233ralwykx4v001h9i07dcm8wpa4k6-gtk4-riscv64-unknown-linux-gnu-4.22.4/lib/libgtk-4.so.1.2200.4`.

At 18:55:27 UTC, `ui.py` opened the drawer and tapped the Files icon at
(917, 150). `scripts/files_idle.py` was already running. It waits for the
`.nautilus-wrapp` process, then samples the main thread's CPU ticks every
2 s:

```
t=2.0 dticks=56 total=73
t=4.0 dticks=53 total=126
t=6.0 dticks=138 total=264
t=8.0 dticks=47 total=311
t=10.0 dticks=0 total=311
t=12.0 dticks=0 total=311
IDLE by t=10.0 main_ticks=311
```

The main thread went idle within 10 s of the process appearing. A grim
capture 4 s after the tap still showed the shell's "Files" launch
placeholder. `system-build-drawer-loaded.png`, captured 12 s after the
tap, shows the home folder's four entries with no loading bar and no stale
pixels.
It is byte-identical to `patched-loaded.png` from task 2.1 (SHA-256
`ee884d51…`), so the system build draws the loaded folder exactly as the
hand-loaded library did.

## Glass report (task 2.3)

Evidence class: real glass interaction by the operator, reported in chat.
Build `1lpsniwg…` test-activated, as in task 2.2. After being asked to open
Files from the drawer, the operator reported at 2026-10-29T20:27Z, verbatim:

> opened fast, folder showed

## Boot default and ordinary boot (task 2.4)

With the charger online, `init=` in `/boot/bootargs.txt` was changed from
`2867v7pm…` to `1lpsniwg…` (backup at
`/var/tmp/bootargs.txt.before-1lpsniwgxxz9bqk83261lbb0k8q6hpqz`), and
`/nix/var/nix/profiles/system` was set to the new build. Both builds use the
same kernel, initrd and device tree. The board rebooted at about 20:28 UTC.
Afterwards `/run/booted-system` and `/run/current-system` were both `1lpsniwg…`,
`shell.service` and `shell-ui.service` were active, and no units had failed.

Evidence class: the board with injected touch. At 20:31:57 UTC `ui.py` opened
the drawer and tapped Files. `ordinary-boot-loaded.png`, captured 12 s after
the tap, shows the loaded home folder; it is byte-identical to the two earlier
captures (`ee884d51…`). Files (pid 1273) mapped the patched
`libgtk-4.so.1.2200.4` from `44233ral…`, and its main thread used 8 ticks in
the 10 s after 20:32:24 UTC. `files_idle.py` had been started just before the
tap but printed `NO FILES PROCESS`, so it did not time this launch. The cause
was not investigated.
