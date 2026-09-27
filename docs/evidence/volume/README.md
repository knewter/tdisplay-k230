# Volume slider and HUD on the headless compositor

Host QEMU capture (evidence class `headless-qemu-injected-touch`, the same
class `docs/evidence/brightness-slider/README.md` and
`docs/evidence/coherent-shell/rust-service-surface-qemu/README.md` already
use), for `the-handheld-controls-volume`. Real cross-built RISC-V
`sway`/`k230-shell-rust` executables ran under `qemu-riscv64-static`, with a
568x1232 headless Pixman output and touch events injected through Sway's
headless-only `card_shell test-touch` fixture, exactly as the brightness
slider's own capture does.

- Rust package: `nix build .#handheld-shell-rust --max-jobs 1 --cores 6`,
  `/nix/store/7imslxpfxnam1zwmcvfng048hwl3z7a1-k230-shell-rust-riscv64-unknown-linux-gnu-0.1.0`.
- Sway: this repo's own `sway-k230-card-shell`-patched `sway-unwrapped`
  (`nix build .#card-shell`), `/nix/store/0a2f857nc1rz65gnjdfn46h32zsyxm18-sway-unwrapped-riscv64-unknown-linux-gnu-1.12`.
  Invoked directly (not through `.#card-shell`'s own `bin/sway` wrapper
  script, which re-execs this same binary after setting `argv[0]`/
  `XDG_CURRENT_DESKTOP` -- a wrapper *script* cannot itself run under
  `qemu-riscv64-static`, which needs a raw RISC-V ELF).
- The settings command is the same synthetic local fixture the brightness
  slider's own capture uses (`k230-settings status` replies with a fixed
  45% brightness). **New for this capture**: `K230_PW_DUMP`/`K230_PW_CLI`
  point at two small local fixture scripts standing in for a real PipeWire
  session -- `pw-dump` prints one initial dump (one sink, "K230 Inno codec
  line-out", 80%; one stream, "k230 video") and, in `--monitor` mode, a
  second, "external" delta 3.0s later dropping the sink to 70% (simulating
  another app/a hardware key/`wpctl` from a console, never this capture's
  own gesture); `pw-cli` reads and discards whatever the persistent writer
  sends it. Neither fixture is a real PipeWire daemon.

## What this shows

Opening the shade shows **both sliders** at once, in the order the task
asks for -- brightness (sun glyphs, 45%) directly above volume (speaker
glyph, mute-tap zone at its own left end, thumb at whatever percent the
fixture's `channelVolumes` maps through the cubic curve)
(`shade-both-sliders.png`). About three seconds later, the fixture's own
"external change" delta lands; the volume slider's thumb moves to the new
position **and the volume HUD pill appears on the panel's right edge**
(speaker glyph, vertical fill bar, "..." affordance) without this capture
ever touching the slider or the HUD itself -- proving the HUD raises for
an external PipeWire change and not for the shell's own gesture
(`hud-collapsed.png`, `volume::ChangeOrigin::raises_hud`). Tapping the "..."
affordance expands the panel: it grows both wider and taller, and now
shows one row per PipeWire stream/sink -- "k230 video"'s own mini slider
(with a fallback initial-letter avatar, since this synthetic capture
resolves no real icon theme) and "K230 Inno codec line-out" with a filled
dot marking it as the current default sink, the output-device picker's own
list (`hud-expanded.png`).

Getting this capture working found a real gap, not just a fixture-timing
one: `render.rs`'s `draw_hud` function (the HUD's own paint code) existed
and was unit-tested, but nothing in `main.rs` ever called it against the
live canvas actually attached to a Wayland surface -- the HUD state
machine and touch dispatch were real, but the pixels never reached the
screen. `render.rs::RendererCache::draw_with_hud` (composited directly
onto `draw()`'s own canvas, on top of whatever route it just painted) is
the fix this capture is evidence for, alongside its own new unit test
(`draw_with_hud_composites_the_pill_on_top_of_the_live_settings_scene`)
that specifically catches a regression back to "painted but never
composited". `openspec/changes/the-handheld-controls-volume/tasks.md`
records the one remaining, still-open piece: `draw_with_hud` only runs
while the overlay layer (Drawer/Shade/Settings) is already mapped, so a
hardware key pressed with nothing open updates the graph/slider state
correctly today but shows no HUD until some sheet happens to be open --
this capture's own choreography (shade already open) exercises the path
that does work.

The high host load this capture ran under (`uptime` showed a 60+ load
average across 32 cores from other concurrent worktrees) reproduced the
exact same `--surface` route-request timeout
`docs/evidence/brightness-slider/README.md` already documented and
worked around; `tests/volume_hud_qemu.py`'s own `route()` helper uses the
identical direct-socket-write workaround for the same reason, not a
change to the shipped client's route protocol.

## Commands

```sh
nix build .#handheld-shell-rust --max-jobs 1 --cores 6 --print-out-paths
nix build .#card-shell --max-jobs 1 --cores 6 --no-link --print-out-paths
python3 -u tests/volume_hud_qemu.py \
  --sway <card-shell's own sway-unwrapped store path>/bin/sway \
  --rust <handheld-shell-rust store path>/bin/k230-shell-rust \
  --output <dir>
```

## Limits

Synthetic `pw-dump`/`pw-cli` fixtures, not a real PipeWire daemon; no
physical touch, panel, or board audio. This proves QEMU composition, the
HUD's own external-change detection and expand affordance, and the shade's
two-slider layout -- not an installed image, real glass, real PipeWire, or
physical finger input. Those gates remain open; see `tasks.md` in
`openspec/changes/the-handheld-controls-volume/`, groups 1.4, 3.3, and 9.
