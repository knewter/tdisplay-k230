# Drawer scroll: CPU profile, fixes and re-measurement

**Evidence class: board, injected native touch.** All captures were taken on
2026-10-22 on the board's DSI panel in landscape: 1232x568 logical pixels,
52.19 Hz (19.16 ms per refresh), `max_render_time 12`, one online CPU, 19 apps
installed. A persistent uinput touchscreen drove the drawer, sending one report
every 8.14 ms. There was no real glass and no camera.

The workload is the committed
[`drawer-scroll.py`](../drawer-scroll/drawer-scroll.py.txt). It alternates
flicks, slow drags and reversals, with sleep pacing. Builds are named by store
prefix (`nixos-system-nixos-26.11.20260919.20b1ddd`):

| Build | Contents | How it ran |
| --- | --- | --- |
| `8xkkpma4` | baseline (`master` 582dcc60) | installed |
| `c702z5mz` | text-measure cache, whole-pixel grid blit, band repaint, one `touch-move` per contact | `switch-to-configuration test` |
| `z1basiwi` | as above, plus drawer motion drawn on the frame callback, cached sheet and band-only surface damage | `switch-to-configuration test` |

## CPU flamegraphs

Captured with [`tools/board-profile.py`](../../../../tools/board-profile.py).
The tool records 30 s of `perf record -e cpu-clock -F 199 --call-graph
dwarf,65528` on the main processes of `shell-ui` and `shell`, while the
workload runs. Stacks resolve from `_start` through Rust, pango, cairo and
pixman. Each directory holds `flamegraph.svg` (open the file directly to zoom),
`folded.txt`, `summary.json` and `capture.log`. The capture log has the PIDs
and start times; no unit restarted.

| Profile | Build | Sampled CPU, client / sway | Hottest client frames |
| --- | --- | --- | --- |
| [before](profile-before/flamegraph.svg) | `8xkkpma4` | 8,794 / 2,930 ms | `bits_image_fetch_bilinear_no_repeat_8888` 27.5% self (grid blit at a fractional offset); `theme_ui::chooser_layout` about 35% inclusive (pango re-shaping on every draw) |
| [after1](profile-after1/flamegraph.svg) | `c702z5mz` | 4,045 / 4,015 ms | sheet gradient fill (`combine_over_u`) and grid OVER blit, each about 30% of client samples |
| [after2](profile-after2/flamegraph.svg) | `z1basiwi` | 2,121 / 3,925 ms | grid OVER blit 34% self; full-frame buffer copy 11%; chrome text laid out under the band clip about 10% |

In after2, sway is the larger consumer. Its main costs are
`k230_turn_copy_rect` (29% of its samples), `rvv_composite_over_8888_0565`
(28%) and `k230_rgb565_blit` (16%). In that capture, `curl` (251 ms) was a
child process of the shell.

## Unprofiled timing

Each run used the same workload with no sampler attached. Columns:

- **Render:** `K230_DRAWER_FRAME` during contact, from
  [`analyze.py`](../drawer-scroll/analyze.py.txt).
- **Cadence columns:** from [`cadence.py`](cadence.py.txt). It counts distinct
  presented frames, because one compositor frame can answer several pending
  callbacks.
- **CPU:** cgroup CPU seconds over the whole run.

| Run | Build | Render median / p95 / max | Presented fps (distinct) | Presented interval median / p95 | Commits per presented frame | Callback → commit median | `shell-ui` / `shell` CPU |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [run3](../drawer-scroll/run3) (baseline) | `8xkkpma4` | 39.5 / 53.4 / 75.8 ms | 8.2 | 98 / 115 ms | 1.12 | 57 ms | 17.6 / 6.0 s |
| [after1](run-after1) | `c702z5mz` | 9.0 / 15.7 / 18.2 ms | 16.5 | 34 / 62 ms | 2.04 | 19 ms | 8.9 / 8.4 s |
| [after2](run-after2) | `z1basiwi` | 6.3 / 9.0 / 24.8 ms | 20.1 | 38 / 39 ms | 1.00 | 8 ms | 4.4 / 8.2 s |
| [after3](run-after3) | `z1basiwi` | 6.3 / 8.3 / 10.0 ms | 19.9 | 38 / 39 ms | 1.00 | 8 ms | 4.3 / 8.1 s |

- The baseline used 60 s runs with 48 gestures, and so did all the after runs.
- In after1, the client drew every touch sample. Half its frames were replaced
  before they were presented (2.04 commits per presented frame). The
  frame-callback gate in `z1basiwi` removed that waste.
- Every contact render sample is now under the review's ~20 ms target, except
  one 24.8 ms outlier in after2.

## Why presentation stays at two refreshes

On `z1basiwi`, presented frames arrive every 38.3 ms, which is two panel
refreshes. Two diagnostics located the limit.

- [mrt7](run-mrt7): a 30 s run with `swaymsg output DSI-1 max_render_time 7`
  set at runtime and restored to 12 afterwards. The cadence did not change
  (median 38 ms), so the client's commit deadline is not the limit.
- [bench](run-bench): a 15 s run with the compositor benchmark armed
  (`card_shell benchmark injected` … `benchmark-stop`).
  - sway's repaint (`repaint-timing` from `start_ns` to `commit_start_ns`)
    takes a median of 18.3 ms (p10 15.6, p90 19.8 ms), close to a whole
    19.16 ms refresh.
  - sway did honour the client's band damage: 138 of 145 repaints damaged
    514,976 px rather than the full 699,776.
  - Even so, compositing that area of a translucent drawer over the wallpaper
    into RGB565, and rotating it, takes nearly a full refresh.

So the drawer client now renders in about 6 ms and is no longer what limits
the frame rate. The compositor's repaint caps drawer scroll at about 26 fps,
and with the gesture pauses about 20 fps was measured. The ~20 ms render
target is met on this workload. Presentation still misses the 33.334 ms card
tracking budget (38.3 ms intervals). Raising it needs compositor-side work,
which this change leaves out.

## Grim checks

Each run's workload took `drawer-open`, `mid-scroll` and `after-close`
captures on the board. They are not committed. The `z1basiwi` mid-scroll
capture shows the search chrome intact and the grid scrolled, with no seams at
the band edges. The drawer closed normally after every run.

## Limits

- Injected touch skips the Goodix interrupt and driver path.
- Presentation time is not photon time.
- Only landscape was measured, with 19 apps.
- Sampling distorts timing on one CPU, so timing comes from the unprofiled
  runs.
- sway ran with `-d` debug logging throughout.

## Promotion to the boot default

On 2026-10-22 at 05:42Z, `z1basiwi` replaced `8xkkpma4` as the persistent
system. The kernel, initrd and DTBs are identical between the two builds.
[`promote.py`](promotion/promote.py.txt) ran as root under the board lock. It:

- swapped the system store path (one reference in each file) in
  `/boot/k230-tdisplay.dtb` and `/boot/bootargs.txt`, with atomic writes;
- kept rollback copies, and added GC roots for both systems;
- checked that no other `/boot` file changed;
- set the system profile to `system-85-link`.

An SSH-initiated reboot then booted `z1basiwi` as `/run/booted-system`, with
`shell` and `shell-ui` active and no failed units. See the
[receipt](promotion/receipt.json), boot ID `98601ab7…`.

A 30 s drawer-scroll run on that ordinary boot ([run-boot](run-boot)) measured:

- contact render: median 6.1 ms, p95 10.2 ms;
- 20.6 distinct presented frames per second.

Its mid-scroll grim capture was clean. Rollback: write the copies under
`/var/lib/k230/drawer-promote-20261022/promotion/rollback/` back to `/boot`,
then run `nix-env --profile /nix/var/nix/profiles/system --set` with the
previous system.
