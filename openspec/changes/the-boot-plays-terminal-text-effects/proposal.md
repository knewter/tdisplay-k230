## Status (2026-10-30)

**Sequenced after Game of Life.** The user's decision (2026-10-30): the Game of
Life boot animation goes forward first and text effects follow it, with a
per-boot choice between them eventually. Host-provable work proceeds now so
that the stage 1 step is ready to review when Life's generic frame interface
has landed; nothing is written to a board or to boot firmware by this change
until the operator approves the install and rollback plan in `design.md`.

The same day the user asked for more than a replay: **ttfx should actually execute in
U-Boot**, so the animation and its text can differ on every boot. The first
version of this proposal assumed a pre-rendered sequence because U-Boot cannot
run a Rust `std` binary. A `no_std` port of ttfx's engine exists on the host now
(`docs/evidence/boot-text-effects/nostd-feasibility.md`), so the pre-rendered
sequence becomes the fallback.

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

- **Stage 1 runs ttfx.** A `no_std` + `alloc` build of ttfx's engine, linked into
  U-Boot as a freestanding riscv64imac staticlib, produces frames; a small
  freestanding glyph renderer draws them on the scanout stage 1 already owns.
  The effect, the text and the seed are chosen per boot (environment override,
  a build-time list, entropy), so the animation varies.
- **Pre-rendered replay is the fallback.** If the engine cannot start (no
  memory, a panic, an unlisted effect), stage 1 replays a frame sequence
  generated on the host from the same ttfx, or leaves the static logo.
- **Linux continues the same run.** As early in Linux as the display allows,
  a live ttfx run with the same effect, text and seed renders through DRM,
  skipping to the frame stage 1 reached (verified by a cell-grid hash carried in
  the hand-off record), and goes on with the real engine.
- The player hands the display to the shell with the protocol the splash owner
  already uses and leaves the last frame on the glass.
- The relationship to Game of Life is still a decision (`design.md`): the user
  has chosen Life first and per-boot selection eventually. Both sit behind the
  neutral frame-source interface and reserved-RAM record; this change adds source
  id 2 and does not edit `the-boot-shows-a-computational-game-of-life`.
- Host-provable work is done or under way: a host tool that turns ttfx output
  into cell sequences, a portable C glyph renderer, the Linux live player (test
  started on the running board), and the `no_std` ttfx patch with a Nix build and
  byte-for-byte parity tests.

### Non-goals

- Uninterrupted animation across the kernel boot. U-Boot stops drawing when it
  starts the kernel; Linux resumes when its display is ready. The gap is
  documented, not hidden (same stance as the Game of Life change).
- Reimplementing the 37 effects in C, or any Rust `std` in U-Boot.
- Enabling the FPU in stage 1. The engine runs in software floating point on the
  `rv64imac` U-Boot as built today.
- Writing U-Boot, SPL or the saved environment, or changing the kernel,
  initrd or bootargs, as part of the host-provable work. Those steps need a
  reviewed install and rollback plan and wait for the operator
  (`design.md`, "Install and rollback plan").
- Touch interaction, a terminal emulator, or arbitrary user text. Texts come from a
  committed list.
- Wide (double-cell) glyphs and ANSI features beyond SGR 0 and 38;2.

## Capabilities

### New Capabilities

- `display/boot-text-effects`: a ttfx effect, chosen per boot, plays at the stage 1
  splash, continues live in early Linux and hands the display to the shell.

### Modified Capabilities

- None. `display/boot-splash` keeps its own requirements; this change draws
  on top of the surface it owns and must not disturb its handoff.

## Impact

Layers: stage 1 (an engine library and C glue in U-Boot, later, gated), Linux
userspace (a new player program and unit, a NixOS option that is off by default),
Nix packaging (a patched ttfx source and a bare-metal staticlib), host tooling. It
reuses, and does not edit, the generic frame-source work from the Game of Life
change (commit `f074552b`: `src/boot_frame.h`, the record window inside the splash
reservation, `tools/check-boot-life-memory.py`, the `canaan,life-instance`
device-tree token).

**Needs the physical board** for: the stage 1 run, its timing on the C908 in
soft float, the filmed boot, the Linux takeover and any claim about what the glass
shows. Host work (the `no_std` port and its parity, sequence tool, glyph renderer,
hashes) and board-process runs (the player and the engine bench started by hand
on the running system) do not need the camera and must not be reported as boot
observations. The webcam must not be used for this change; physical boot video tasks
stay open until the operator films or authorises another method.

**Evidence classes** are kept apart in `tasks.md`: host build/test, QEMU user-mode
run of the firmware object code, board process run (manual start on the running
system), stage 1 console log, and filmed boot.
