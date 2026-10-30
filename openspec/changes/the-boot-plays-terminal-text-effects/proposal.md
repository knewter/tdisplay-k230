## Why

From power-on until the shell draws, the glass shows one frozen logo. On the
daily mainline image the logo is lit by stage 1, kept by the kernel, and still
unchanged when the compositor takes over; the film of that boot measured the
logo on screen from 42.4 s to 121.9 s of video, with the first Linux frame
identical to the last stage 1 frame
(`docs/evidence/mainline-boot-splash/board/README.md`, section 2.4). The board
does nothing visible for most of that interval, and the interval is exactly
the time a person spends looking at the device.

The user asked (2026-10-30) for the Rust text effects from Omarchy to become
a boot animation: "compile the rust text fx from omarchy into a boot animation
and lead into a real run of the text fx as soon as possible in the boot or
even run them during bootup for the bios animation". That is `ttfx`
(`github.com/omacom-io/ttfx`, MIT, a parity-exact Rust port of
TerminalTextEffects with 37 effects). The board already runs it: it is
packaged for riscv64 (`nix/ttfx.nix`, `.#ttfx`) and the charging-display
exhibition pipes the committed K230 banner into it
(`nix/exhibition/K230.txt`). What is missing is any use of it before the
shell exists.

## What Changes

- Stage 1 ("the BIOS moment") plays a short pre-rendered sequence of one
  ttfx effect over the K230 banner. The sequence is generated on the host at
  build time by the pinned `ttfx` itself, because U-Boot cannot run a Rust
  `std` binary; U-Boot only replays character cells through a small freestanding
  glyph renderer.
- As early in Linux as the display allows, a live `ttfx` run renders into DRM
  and continues the same run: the same seed and arguments reproduce the
  pre-rendered frames exactly, so the live run skips to the frame stage 1
  reached (verified by a frame hash carried in the hand-off record) and goes
  on from there with the real engine.
- The player gives the display to the shell with the protocol the existing
  splash owner already uses, and leaves the last frame on the glass.
- The relationship to Game of Life is an open decision recorded in
  `design.md`: replace it, run in addition (selectable per boot), or play
  both in sequence. Both animations sit behind the same neutral frame-source
  interface and reserved-RAM record; this change adds source id 2 and does not
  edit `the-boot-shows-a-computational-game-of-life`.
- The host-provable parts land first: a host tool that turns `ttfx` output
  into a cell-sequence file with deterministic hashes, a portable C glyph
  renderer, and the Linux live player (test-started on the running board).

### Non-goals

- Uninterrupted animation across the kernel boot. U-Boot stops drawing when it
  starts the kernel; Linux resumes when its display is ready. The gap is
  documented, not hidden (same stance as the Game of Life change).
- Running `ttfx`, or any Rust, inside U-Boot or reimplementing its 37 effects
  in C.
- Writing U-Boot, SPL or the saved environment, or changing the kernel,
  initrd or bootargs, as part of the host-provable work. Those steps need a
  reviewed install and rollback plan and wait for the operator
  (`design.md`, "Install and rollback plan").
- Touch interaction, a terminal emulator, or arbitrary user text. The text is
  a committed banner.
- Wide (double-cell) glyphs and ANSI features beyond SGR 0 and 38;2.

## Capabilities

### New Capabilities

- `display/boot-text-effects`: a ttfx effect plays at the stage 1 splash,
  continues live in early Linux and hands the display to the shell.

### Modified Capabilities

- None. `display/boot-splash` keeps its own requirements; this change draws
  on top of the surface it owns and must not disturb its handoff.

## Impact

Layers: stage 1 (U-Boot glue, later, gated), Linux userspace (a new player
program and unit, a NixOS option that is off by default), Nix packaging, host
tooling. It reuses, and does not edit, the generic frame-source work from the
Game of Life change (commit `f074552b`: `src/boot_frame.h`, the record window
inside the splash reservation, `tools/check-boot-life-memory.py`, the
`canaan,life-instance` device-tree token).

**Needs the physical board** for: the filmed boot, the stage 1 playback, the
timing of the Linux takeover and any claim about what the glass shows. Host
work (sequence tool, glyph renderer, hashes) and board-process runs (the live
player started by hand on the running system, with its framebuffer hashed)
do not need the camera and must not be reported as boot observations. The
webcam must not be used for this change; physical boot video tasks stay open
until the operator films or authorises another method.

**Evidence classes** are kept apart in `tasks.md`: host build/test, board
process run (manual start on the running system), stage 1 console log, and
filmed boot.
