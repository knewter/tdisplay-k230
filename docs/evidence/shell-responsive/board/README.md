# HDMI board trial: output works; physical app gestures remain open

Physical K230 board, 2026-09-29 UTC, source `27066809`. This is an
unfinished acceptance trial, not a shipped-capability claim. The operator
reported: “drag worked fine but gestures don't work when an app's open or
something. also it was very slow”.

## Runtime and boot provenance

The installed trial system was
`/nix/store/3nnwv20xcagrpds4spba47g5wcfjycdg-nixos-system-nixos-26.11.20260919.20b1ddd`.
See [artifact manifest](artifact-manifest.json) and [boot report](boot-report.json).
The runtime HDMI DTB differs from the immutable build DTB only in `/chosen`
boot arguments, which name this system's init. All staged files passed SHA256
checks; four U-Boot loads passed byte-count and in-memory CRC checks.

The controller was run while holding `/tmp/k230-board.lock`:

```sh
python3 tools/hdmi-board-trial.py \
  --manifest .scratch/hdmi-board-trial/manifest.json \
  --stage-dir /var/lib/k230/hdmi-responsive-trial-27066809 \
  --private-log .scratch/hdmi-board-trial/boot-1.private.log \
  --report .scratch/hdmi-board-trial/boot-1.json
```

The normal panel `/boot` files and system profile were verified before this
one-shot boot. No persistent boot selection was changed. A successful return
to the normal panel boot is **UNVERIFIED** in this trial. Raw UART and staging
transport logs remain private because they contain network and device identity.

## Native captures and operator observations

`HDMI-A-1` is connected at physical 1920×1080, transform 90, scale 1;
the logical output is 1080×1920. Home and wallpaper accepted `1080x1920`
configures. Both `shell` and `shell-ui` were active.

These PNGs were captured **on the board** with `grim`, not host renders or
monitor photographs:

- [Initial terminal](hdmi-before.png).
- [Changed terminal](hdmi-after.png): a new Foot window prints the live-test
  label and date. A test color override used an unsupported Foot section and
  printed configuration errors; this is not evidence of a color change.
- [Injected keyboard input](hdmi-keypresses.png): four `a` keypresses sent
  through the Wayland virtual-keyboard protocol appear at the prompt. No
  Enter was sent. This proves client/display update, not physical-key input.
- [Launcher](hdmi-drawer.png): the real Rust drawer fills the logical output
  and reflows to eight columns, with 19 app entries.

```sh
XDG_RUNTIME_DIR=/run/shell WAYLAND_DISPLAY=wayland-1 grim /run/hdmi-drawer.png
```

The operator confirmed the display changed and that dragging worked. A
passive libinput capture recorded 15 physical touch downs and 985 motions;
the Goodix interrupt count rose from 315 to 1505. Earlier quiet captures
did not establish a dead sensor because no contact during those windows
was confirmed. Explicit live `map_to_output HDMI-A-1` was applied before
the successful contact capture.

The compositor accepted these **injected** events while Foot was open:

```sh
XDG_RUNTIME_DIR=/run/shell SWAYSOCK=/run/shell/sway-ipc.sock \
  swaymsg -r 'card_shell down 93 540 1900'
XDG_RUNTIME_DIR=/run/shell SWAYSOCK=/run/shell/sway-ipc.sock \
  swaymsg -r 'card_shell motion 93 540 1550'
XDG_RUNTIME_DIR=/run/shell SWAYSOCK=/run/shell/sway-ipc.sock \
  swaymsg -r 'card_shell up 93'
```

The resulting scene reported `active=1`, `deck_enabled=1`, `mode=1`,
`entry_progress=1.0000`. Thus the app-to-overview policy works at logical
HDMI coordinates; physical coordinate mapping, edge hit area and input
routing remain **UNVERIFIED** for the reported failure. A subsequent
90-second physical bottom-edge capture recorded no contacts; no conclusion
about gesture recognition follows from that quiet window.

## Performance and trackpad limits

This boot's Rust frame logs show a first Home render of 564.46 ms, an
initial drawer render of 100.71 ms, and warm drawer renders of
3.50–4.67 ms. These are client paint durations, not end-to-end latency.
Rust touch motions were dispatched in bursts separated by about 237 ms;
the cause of that batching has not yet been established.

The bounded [cost probe](gesture-cost-probe.py) runs on the physical board
with explicitly injected compositor input; it restores ordinary app mode and
stops telemetry in its `finally` block. Its [raw trace](k230-gesture-cost.log),
[command timings](k230-gesture-cost.json) and [summary](cost-summary.json)
record 17 measured repaint builds: median 441.84 ms, range 339.20–558.29 ms
of compositor CPU time. Median input handling is 1.94 ms. The session reports
`renderer=pixman`, logical `1080x1920`, and output format `34325241`
(`AR24`, ARGB8888). Thus the current HDMI path uses 32-bit software composition;
the existing RGB565, unrotated scaled-cache path is ineligible. This trace
locates the expensive stage, not the specific routine within it. It does not
establish physical input-to-presentation latency.

The following comparisons use the same physical board, two Foot cards and
1920×1080 physical mode. All input is injected. The rotated runs use the
original probe; the normal runs use the [output-sized probe](gesture-cost-output-probe.py),
which derives its start point and travel from the live output. Orientation
changes the card geometry and damage footprint, so this is not a pixel-identical
rotation microbenchmark.

| Output transform | Format | Frame-build CPU median | Range | Measured builds |
| --- | --- | ---: | ---: | ---: |
| 90 | ARGB8888 | 441.84 ms | 339.20–558.29 ms | 17 |
| 90 | RGB565 | 470.10 ms | 354.17–594.76 ms | 17 |
| normal | RGB565 | 18.56 ms | 15.78–24.92 ms | 17 |
| normal | ARGB8888 | 15.29 ms | 11.09–20.64 ms | 17 |

Raw comparisons: [rotated RGB565](k230-gesture-cost-565.log),
[normal RGB565](k230-gesture-cost-normal.log),
[normal ARGB8888](k230-gesture-cost-normal-32.log). Each has an adjacent
JSON command-timing record. The normal ARGB8888 result keeps the RGB565
scaled cache ineligible and still improves frame building by about 29×
relative to rotated ARGB8888. This strongly identifies the rotated software
composition path for further profiling; it does not identify one offending
Pixman routine or prove that the GPU will be faster.

The live comparison commands selected `output HDMI-A-1 render_bit_depth 6`
or `8`, and `output HDMI-A-1 transform normal` or `90`. After comparison,
the original transform 90 and eight-bit format selection were restored.
No image default was changed by these experiments.

```sh
/nix/store/v189xydz6qkcd4cbkixcmv91w8hbc560-python3-riscv64-unknown-linux-gnu-3.14.7/bin/python3 \
  -I /run/gesture_cost_probe.py
```

A bounded trackpad dry run entered trackpad mode, grabbed the Goodix device,
then ungrabbed it and exited after the 20-second timeout. It did not create
a uinput device and no contact translation was observed during that window.
The default-off trackpad has **not** passed physical pointer, click, scroll,
pinch or panel-restoration acceptance.

An exploratory LT9611 HPD mask write did not verify a change: register
`0x8203` still read `0x3f`. DRM polling was restored to `Y`. Do not attribute
the later successful touch capture to that unverified write.

Still required: real-glass app-to-overview gestures; measured input-to-frame
performance; tap-to-launch proof; a photograph of filled Home on the monitor;
trackpad contacts and restoration; normal panel reboot verification.
