# Why the landscape drawers were janky, and the fix — 2026-10-13

Operator, after the landscape install: "it works but it's kinda janky here
where it wasn't before ... (the two drawers at least)". After the fix:
"ok yeah it's plenty fast now".

## Method

Board: the second T-Display-K230, one Linux core (CPU0 belongs to the
coprocessor), Sway with Pixman. `rotation-bench/bench.sh` arms the card
compositor's telemetry (`swaymsg card_shell benchmark injected`) and runs
`rotation-bench/abrun.sh`: three rounds of a bottom-edge swipe to the
Drawer, `--surface hide`, a top-edge pull to the Shade, `--surface hide`,
with 1.5 s settles. Touches are injected through `tools/inject-tap.sh` on an
`evemu-device` clone. sway and shell-ui CPU come from `/proc/<pid>/stat`
(100 Hz ticks). Frame intervals are the gaps under 400 ms between
consecutive `event=present presented=1` rows, so they cover animation
frames, not idle time. `frame-damage` shows every frame in every mode
damaging the full 699,776-pixel output.

The injector forks one `evemu-event` per axis write on the same core, so
absolute rates are below what a finger sees. All modes pay that cost
equally.

## Result

| Run (log) | Output | Renderer | Frames | Median interval | p90 | sway CPU |
| --- | --- | --- | --- | --- | --- | --- |
| `landscape.log` | 1232×568, transform 270 | stock Pixman | 75 | 287 ms (3.5 fps) | 307 ms | 10.14 s |
| `quarter.log` | same | `WLR_PIXMAN_QUARTER_TURN=1` | 127 | 153 ms (6.5 fps) | 287 ms | 8.09 s |
| `output.log` | same | `WLR_PIXMAN_OUTPUT_TURN=1` | 160 | 115 ms (8.7 fps) | 172 ms | 5.01 s |
| `portrait.log` | 568×1232, transform normal (live `swaymsg`) | stock Pixman | 169 | 96 ms (10.4 fps) | 172 ms | 3.44 s |
| `installed.log` | landscape, installed profile | `WLR_PIXMAN_OUTPUT_TURN=1` | 158 | 115 ms (8.7 fps) | 172 ms | 4.96 s |

shell-ui used 0.57–0.84 s in every run; its own Home frame is about 10 ms. The
jank was the compositor's per-frame software rotation. Stock Pixman applies
the 270° transform to every layer it composites (wallpaper, Home, the
overlay), which takes the slow transformed-fetch path. The output-turn
renderer composes the logical frame normally and rotates it into the
physical buffer once.

The first three landscape rows and `portrait.log` ran on one build, a
non-persistent trial with the patched wlroots (`card-shell-hdmi-trial`), and
switched renderers with a `/run` drop-in. `landscape.log` ran on the
installed stock wlroots before that trial. `installed.log` is the installed
profile after the change below, with no runtime overrides.

## The change

When `k230.shell.panelTransform` is not `normal`, `nix/shell.nix` now builds
the card compositor against the patched wlroots and sets
`WLR_PIXMAN_OUTPUT_TURN=1`, `WLR_PIXMAN_QUARTER_TURN=0`. The portrait
default's toplevel derivation is unchanged (`v8bj22rb…`, evaluated before
and after). The HDMI quarter-turn trial is untouched.

## Limits

`docs/evidence/hdmi-shell-performance/README.md` records the output-turn
path as an open HDMI experiment. Nearest-filter output was byte-exact in its
probes. Scaled bilinear textures can differ by up to three ARGB8888 channel
steps from stock per-texture rotation. Landscape panel content is drawn
unscaled, but no pixel-exact panel comparison was made here. The camera
frame and native captures show the orientation and layout, and the
operator's report covers the feel. No frame budget is claimed.
