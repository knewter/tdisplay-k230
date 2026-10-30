## Context

Layers touched: stage 1 (U-Boot glue and data, gated), Linux userspace (a
player and a unit), Nix, host tooling. The kernel, device tree, initrd and
bootargs are not changed by the host-provable work.

### What ttfx is (host research, `docs/evidence/boot-text-effects/ttfx-research.md`)

- `ttfx` 0.5.1, commit `14ed274`, MIT (Copyright 37signals / omacom-io and
  ChrisBuilds; `LICENSE` and `NOTICE` are already installed beside the package,
  `nix/ttfx.nix`). One crate, library plus binary, about 16 000 lines in
  `src/engine`, `src/fx` and `src/utils`. Runtime dependencies are `clap`,
  `clap_complete`, `terminal_size` and `unicode-width` (plus their
  transitive crates, pure Rust; `libc`/`rustix` are used for terminal and signal
  calls). No C code and no build script.
- The library exposes the engine (`ttfx::fx::Engine`, `ttfx::engine`), but its
  run loop owns a `Terminal` and writes ANSI to stdout. There is no
  grid-and-colour callback to hang a renderer on.
- It does have a deterministic frame mode used by its own parity tests:
  `--seed N --parity-dump [--max-frames M]` (flags hidden from `--help`) writes
  each frame as a length-prefixed block of UTF-8 text with SGR truecolor
  (`ESC[38;2;r;g;bm`) per cell and rows separated by newlines, with a virtual
  clock instead of wall-clock pacing. Over the K230 banner every one of the 37
  effects produced only SGR `0` and `38`, never a background colour, and the
  same seed produced the same SHA-256 on repeated runs (host measurement,
  seed 7, 36x12 canvas: `decrypt` 770 frames, `beams` 213 frames).
- A `no_std` + `alloc` build of the original engine exists as a patch against `14ed274`
  (`nix/ttfx-nostd/ttfx-nostd.patch`): the std CLI and its tests are unchanged, and the
  frames are byte-identical to the std engine's for all 37 effects on the host and, as
  riscv64imac machine code under QEMU user mode, for 37 of 37. What it took, the float and
  memory findings and the sizes are in `docs/evidence/boot-text-effects/nostd-feasibility.md`.
- Packaging for the board already exists and is in use: `nix/ttfx.nix`
  (`.#ttfx`, riscv64 cross build, Cargo.lock committed) and the charging
  exhibition (`nix/term-apps/k230_exhibition.py`) run it in a terminal on the
  shell. The packaged binary is 3.3 MB, dynamically linked against glibc.

### How the board boots and draws today

- Stage 1 (U-Boot proper) lights the panel and draws the logo into the
  reserved scanout at 0x10000000..0x103fffff (`nix/boot-splash.nix`); the
  mainline kernel reserves it as `framebuffer@10000000` (nomap) and logs
  `canaan-drm ... stage 1 splash: leaving fbdev unset` at kernel 2.81 s;
  `/dev/fb0` does not exist and nothing opens `/dev/dri` until a client starts
  (`docs/evidence/mainline-boot-splash/board/README.md`, section 2.3).
- `k230-drm-splash` (`nix/drm-splash/drm-splash.c`) is the only Linux-side
  owner: it sets the CRTC with the logo in an RG16 dumb buffer, writes
  `scanout` to its ready file, and on `SIGUSR1` drops DRM master and writes
  `master-dropped` so the shell may open DRM (`nix/shell.nix` ExecStartPre,
  `nix/drm-splash/drm-splash.c:306-319`). It was observed opening DRM at
  kernel 45.2 s on a boot where the shell was masked.
- The film of a normal boot has the logo from 42.4 s to 121.9 s with no
  intermediate frame to the compositor's first frame (same README, section
  2.4). The kernel clock and the film clock differ; the README gives the
  mapping and its limits.
- The boot files are `/boot/Image`, `/boot/initrd.uimg` (27 MB in the recorded
  boot: `crc32 0x9000000 0x1a107c6`), the device tree and `bootargs.txt`; the
  `init=` store path in `bootargs.txt` picks the system
  (`firmware/stage1/tdisplay.env` `blinux`; memory note on promoting a build).
  The recorded kernel had no panel console (`panelConsole = false` on the
  mainline default, archived `2026-10-20-the-mainline-kernel-keeps-the-boot-splash`).
- Whether the daily initrd is systemd-based (`boot.initrd.systemd.enable`) is
  <!-- UNVERIFIED: only the Plymouth evaluation in docs/evidence/boot-splash-owner.md shows it true; task 5.1 evaluates the daily attribute. -->.

### What the Game of Life change already provides (not edited here)

The open change `the-boot-shows-a-computational-game-of-life` is being
implemented in another worktree. Its commit `f074552b` (not yet on `master` when
this was written) makes stage 1 a generic frame-source loop:

- `src/boot_frame.h`/`.c`: `struct bf_source { start, step, publish }` driven
  by `bf_run`, over the 568x1232 XRGB8888 scanout, never touching panel or VO
  registers. Every record starts with a common prefix (magic, ABI version,
  length, nonzero boot-instance token, **source id at byte 30**, FNV-1a
  checksum). Life is source id 1; ids 2 to 255 are free. This change claims
  **source id 2** for text effects.
- The record window: 8 KiB at 0x102ac000 inside the existing no-map splash
  reservation (`nix/boot-splash.nix` `lifeRecordOffset/Address/Window`),
  checked by `tools/check-boot-life-memory.py`, with the device-tree token
  `canaan,life-instance` carrying the boot-instance token to Linux.
- U-Boot glue `nix/uboot-k230-life/k230_boot_life.c` and patch
  `0006-k230-stage1-boot-life.patch`, the opt-in `bootLife` switch in
  `nix/uboot-k230.nix`, the `boot_life=1` environment gate, and the
  install and recovery proposal
  `docs/evidence/game-of-life/stage1-install-recovery-proposal.md`.
- On Linux the consumer is Life-specific (`nix/drm-splash/life.c`) on the
  splash owner. Its coordinator note records that a plain read of the no-map
  window through `/dev/mem` returns a bad-address error on the board and that
  mmap is unproven; Life copies the window with a root-side helper
  (`k230-life-capture`).

This change reuses those pieces by id and by convention, adds a sibling
consumer keyed by source id, and re-validates every reference against `master`
before code that depends on it is merged.

## Goals / Non-Goals

**Goals:** a short, deterministic, recognisable ttfx sequence at the stage 1
splash; a live ttfx run in Linux that is the same run, continued; no new hard
dependency of the shell on the animation; host-reproducible hashes for every
claim a host can make.

**Non-Goals:** see the proposal. Additionally: no cross-boot or home state, no
claim of uninterrupted motion, no dependence on the second RISC-V core.

## Decisions

**D1. Stage 1 executes ttfx.** The effect engine is the `no_std` build of ttfx (D13),
linked into U-Boot as `libk230_ttfx_boot.a` (riscv64imac, soft-float, `panic = abort`, its
own allocator over an arena). U-Boot glue creates a run (`ttfx_fw_new`: effect name, text,
seed, canvas), pulls frames (`ttfx_fw_next`, the ANSI text `ttfx --parity-dump` prints),
parses each with the shared `tfx_parse_frame` into the cell grid and draws the changed
cells with the shared blitter (D3). It is a source behind Life's `bf_source` interface
(id 2). The text and effect are data, not code, so each boot can differ (D11).

**D1b. Pre-rendered replay is the fallback, not the main path.** The host also
generates a `TFXS` cell sequence (`tools/textfx_frames.py`) from the same ttfx for a default
effect and text. Stage 1 replays it only if the engine does not start: arena allocation
fails, `ttfx_fw_new` returns null, or the panic hook fires before the first frame. A
replay sets a flag in the record so Linux knows the run is the default one. A sequence is
a few KB to ~200 KB (`wipe` 17 KB, `beams` 213 KB at 35x38) and sits in the U-Boot image
beside the engine, so it needs no filesystem read.

**D2. What goes in the U-Boot-proper slot.** The slot is 1 MiB and the current candidate
uses 385 932 bytes (`docs/evidence/game-of-life/stage1-install-recovery-proposal.md` on the
Life branch). The engine costs 125 KB with one effect, 198 KB with an 8-effect subset and 520 KB
with all 37 (`nostd-sizes.txt`); the font table, glue and fallback sequence add tens of KB.
Firmware therefore carries a subset (the feature list is a build input; the default is the eight effects whose heap peaks under 4 MiB:
`wipe middleout expand slide errorcorrect print decrypt scattered`), shares the slot with Life, and the install plan checks
the margin before any write. The slot cannot grow without moving the saved environment.

**D3. One glyph renderer, written once in portable C.** `src/textfx.{h,c}`:
freestanding (no libc calls), a cell grid, the frame parser, `apply_frame` for sequences, and a
blitter to a `bf_target` (XRGB8888) or an RG16 dumb buffer. The font is an 8x16 table
generated from GNU Unifont's BDF (`pkgs.unifont`; dual licensed SIL OFL 1.1 or
GPL-2.0-or-later with the font-embedding exception, notice carried in the
generated file), restricted to the code points the effects use, drawn at
integer scale 2 (16x32 px cells: 35 columns by 38 rows on 568x1232; the K230
banner is 33 columns by 6 rows and fits). Surveyed over the 37
effects on the 35x38 panel grid (`docs/evidence/boot-text-effects/ttfx-research.md`):
`decrypt` draws 429 distinct non-ASCII code points (Latin and half-width
katakana), `matrix` 42, and every other effect 15 or fewer, mostly the box
drawing of the banner itself. Unknown or double-width code points
draw a visible fallback box rather than disappearing. The same file builds into U-Boot
and the Linux player so the two stages cannot disagree on a pixel.

**D4. The live run is the same run, not a lookalike.** The Linux player starts the same
engine with the same effect, text, canvas and seed (all in the record, D5), reads frames,
discards those before the one the record names, and verifies that the FNV-1a hash of its own cell grid
at that frame equals the hash in the record; on mismatch it logs, clears and plays from
frame 0 (a visible restart is better than a continuation that is wrong). Two ways to run
the engine in Linux are kept open. (a) The std `ttfx` child (`--parity-dump`, a hidden
flag of its own parity harness; pinned revision and golden hashes guard it): proven
byte-identical to the `no_std` engine in every host comparison so far, but it uses glibc's
`pow`/`sin`, the firmware uses libm, and no sample has differed yet. (b) The same
`k230_ttfx_boot` library behind a hosted C ABI: identical code in both stages, no
child process, no dependency on the hidden flag. (b) is the recommendation once the
hosted build exists; the hash check protects both. With no valid record the player plays
from frame 0. Continuation improves on a safe default and is not a precondition.

**D5. A record, not shared state.** The text-effects record is the common 40-byte prefix of
the generic interface with source id 2 and a payload (little-endian) of: seed (u64), canvas
columns, rows and frame rate (u16 each), flags (u16: replay-fallback used, selection came
from an environment override), last frame drawn (u32) and the FNV-1a of that frame's cell
grid (u32), an engine id (u32, FNV-1a of "ttfx 14ed274 nostd N": a mismatch means the Linux
side cannot promise identical frames), the effect name (24 bytes, NUL padded), the text id
(u16 index into the build-time list, 0xFFFF for a text from the environment) and the text hash
(u32 FNV-1a of the text bytes, so Linux detects firmware and system disagreeing about the
list). Exactly 60 bytes (`TFX_REC_PAYLOAD_BYTES`) in the 8 KiB window. Validation order is Life's: prefix, checksum,
boot-instance token against `/chosen/canaan,life-instance`, then the source id picks the
consumer. `src/textfx_record.{h,c}` encodes and decodes the payload and is tested on the
host; the prefix belongs to `boot_frame` and is added when that lands.

**D6. Player lifecycle on Linux.** One program, `k230-textfx`, started from a
systemd unit that is off by default (`k230.bootTextEffects.enable`). It uses
the splash owner's proven recipe for the first modeset (RG16 dumb buffer,
`drmModeSetCrtc`), writes `scanout` to a ready file, honours `SIGUSR1` by
dropping DRM master and writing `master-dropped`, and leaves the last frame in
the retained framebuffer. It runs at the lowest CPU weight and drops frames
when late (it never delays by sleeping longer), because the board has one
online CPU and boot is CPU-bound. It is ordered before the shell and must not
be required by it: a failed or absent player leaves the existing owner or the
shell to take the display exactly as today.

**D7. Standalone first, owner mode later.** The shell's release script signals
`pkill -x k230-drm-splash`. The player speaks the same ready-file protocol under
a path of its own and is tested standalone. Merging it into the splash owner as
a `--textfx` mode (sibling to Life's `--life`), or teaching the release script a
second process name, touches `nix/drm-splash` and `nix/shell.nix`, which the
Game of Life work is also changing; it waits until that change lands
(task 5.2).

**D8. Earliest start in Linux is a measurement, not a guess.** The DRM driver
binds at kernel 2.81 s but the only current owner starts at 45.2 s. Between
them lie the initrd (27 MB), root mount and switch-root. A rootfs unit with
`DefaultDependencies=no`, ordered after the DRM device and before the owner, is
the first target and needs no boot-file change. An initrd unit would start
sooner but needs the player and `ttfx` (3.3 MB, dynamically linked) in the
initrd and changes `initrd.uimg`, so it is the gated step. The decision uses a
boot trace (task 5.1) and carries the player's progress across switch-root in
`/run`, which systemd preserves.

**D9. Effect and text are product choices, decided from data.** Default text:
the committed `nix/exhibition/K230.txt` banner (6 rows by 33 columns of box
drawing), because it already exists, fits the portrait panel at scale 2, and
is the identity the exhibition uses. Candidates measured on the real 35x38
grid (seed 3, 30 fps sequence rate, uncompressed delta sequence): `expand` 50
frames, 6 KB; `middleout` 94, 13 KB; `slide` 110, 20 KB; `wipe` 138, 17 KB;
`errorcorrect` 274, 19 KB; `beams` 321, 213 KB; `decrypt` 753, 131 KB with the
429-glyph set. ttfx's frame counts do not depend on the frame rate, so the
play time is frames divided by the rate chosen for playback (`wipe` is about 2.3
s at 60 fps). The shortlist for the user: `wipe` or `middleout` for a short
stage 1 moment, `beams` for a colour sweep (8.5 MiB of heap, so it needs the larger arena of D14), and `decrypt` for the recognisable
"BIOS decode" look, which is long and glyph-heavy and would be the live
continuation more than the U-Boot part. Task 2.3 records the final table;
the pick is the user's. Orientation (banner readable on the portrait scan, or
rotated for landscape use) is also open.

**D10. Relationship to Game of Life.** The user has decided (2026-10-30): Life first, text effects
after, and eventually a per-boot choice between them. That is option B below; A and C are kept
as the options that were considered.
- A. *Replace*: text effects are the boot animation; Life stays queued behind
  the same interface. Simplest, one source in the image, but discards work the
  user has just un-queued.
- B. *Complement, one chosen per boot*: both sources exist behind
  `bf_source`; the build picks the default and stage 1 reads a variable
  (`boot_anim=textfx|life`, alongside `boot_life=1`) so either can be selected
  without reflashing firmware. The Linux side selects the consumer by source
  id. Costs one extra branch, buys the user's "or in addition".
- C. *Sequence*: text effect at stage 1 (the short BIOS moment), Life in Linux
  (the long wait). Needs the Linux Life consumer to start fresh from a record
  with source id 2, which is a defined case (invalid-for-Life record falls back
  to the deterministic default). More parts moving; do as a follow-up to B.

The record window and the scanout are single-writer, so two sources never draw
at once under any option.


**D11. Per-boot variation.** Three things vary: the effect, the text, and the seed. Sources, in
priority order, each optional:
1. *U-Boot environment overrides*, for testing and for the operator: `tfx_effect`, `tfx_text`
   (an index into the list, or `-` for none), `tfx_seed`, `tfx_off=1`. Set at the console for one
   boot; they are never saved (`saveenv` is a separate approval).
2. *A build-time list* in the firmware: effect names (the compiled-in subset) and texts (the K230
   banner, a "T-Display K230" line, a few others), as `nix/textfx/texts.txt` (entries separated by a
   `%%` line). The pick is `list[mix(seed) mod n]` for each. The same file is installed in the
   system so Linux can look the text up by id; the text hash in the record catches a mismatch.
3. *Entropy for the seed*: `get_ticks()` (cycles since reset, which varies by the jitter of
   DDR training and MMC timing) mixed with any RTC seconds U-Boot can read and the environment
   value. A cold boot may repeat more than a warm one, so the quality of this source is
   <!-- UNVERIFIED: the spread of get_ticks() at stage 1 across boots, and whether a hardware RNG or RTC is readable in U-Boot, are not measured. -->.
   A repeated animation on a repeated boot is an acceptable failure; a crash is not, so the seed
   never changes anything but the choice.
The deterministic default (effect `wipe`, K230 banner, seed 3) is used when `tfx_*` are unset and
the list or entropy is unavailable, and is what the fallback sequence encodes.

**D12. Stage 1 timing: animate while loading, or before.** The user wants stage 1 to keep
animating while U-Boot loads the kernel. The pinned U-Boot 2022.10 tarball has no `common/cyclic.c`
(checked with `tar tjf`), so a cyclic framework is not there to hook; the Life agent is researching the
options and will record them at `docs/evidence/game-of-life/uboot-cyclic.md` on its branch, which this
change will cite rather than duplicate. Without it, two shapes work with this library: (a) play
the effect to completion, then load (adds the animation's length to boot, a few seconds; simplest);
(b) a boot command that reads the kernel, device tree and initrd with `fs_read` in chunks of
1 to 4 MiB and calls `ttfx_fw_next` plus a draw between chunks, so each frame costs
one frame's compute, not a stall. The ext4 reads in the recorded boot took 1.8 s for the 27 MB initrd
alone. Either way the engine is single-threaded and U-Boot's own work waits while a frame computes.
The cost of a frame in soft float on the C908 is <!-- UNVERIFIED: not measured; `nix/ttfx-boot/bench/bench.c` run on the board gives it per effect (task 4.3). -->.

**D13. How the engine is built for U-Boot.** The patch is written to go upstream: default features
keep the std CLI and its tests; `--no-default-features --features nostd` is the engine on `core` +
`alloc` + `hashbrown` + `libm`; `effect-<name>` features select effects. `nix/ttfx-nostd` applies the
patch to the pinned source; `nix/ttfx-boot` builds the staticlib with the official `rust-std` for
`riscv64imac-unknown-none-elf` (nixpkgs ships only `riscv64gc`, which is hard-float and would trap in
U-Boot; the pinned U-Boot is `rv64imac`, `lp64`, with `mstatus.FS` never set). Position-independent
(`-C relocation-model=pic`) because U-Boot relocates itself.

**D14. Memory.** The engine's peak heap is 1 to 4 MiB for most effects and up to 13 MiB for the largest
(`nostd-feasibility.md`), against U-Boot's default 4 MiB pool. The library therefore allocates from an
arena the host hands it (`ttfx_fw_init`), never from U-Boot's `malloc`. The arena is either carved from
a larger `CONFIG_SYS_MALLOC_LEN` or a fixed free DRAM range during stage 1; the memory-map tool from the
Life change decides which addresses are safe. The default effect subset is chosen so every member
peaks under 4 MiB, so the first install can use the pool as it is.

## Rejected

- *Port the effects to C for U-Boot.* 19 500 lines of parity-tested engine for
  37 effects; any divergence defeats D4. The `no_std` Rust port was 600 hand-written lines
  and is checked against the original byte for byte.
- *Pre-rendered frames only.* Cheap and safe, and kept as the fallback, but the user asked for
  an animation and text that differ per boot.
- *Link ttfx into a Rust renderer.* Needs a new Rust DRM stack on riscv64 and
  couples to ttfx internals that have no stable renderer interface; the
  `--parity-dump` stream is what its own parity harness depends on. It is a
  hidden flag, so the revision is pinned and a golden hash fails the host test
  if a bump changes the format.
- *Run ttfx in a terminal on the kernel console.* The mainline default keeps
  fbdev unset so stage 1's image survives (`/dev/fb0` absent), which is why
  `panelConsole` is false; enabling fbcon takes the display from stage 1 and
  the kernel virtual terminal quantises colours <!-- UNVERIFIED: not observed on this board -->.
  The exhibition's terminal-in-the-shell approach starts only when the shell
  does, which is the thing being improved.
- *Plymouth.* Already rejected on budget (`docs/evidence/boot-splash-owner.md`).
- *Pre-rendered pixel frames or a video.* 2.8 MB per full frame.
- *Editing `the-boot-shows-a-computational-game-of-life` or the Life files.*
  Another agent owns them; this change cites them.

## Risks / Trade-offs

- [One online CPU, boot is CPU-bound] -> lowest priority, frame dropping, and a
  measured CPU-per-frame figure (task 3.3) before any boot-time enablement.
- [Hidden flags change on a ttfx bump] -> pinned revision, golden hashes in
  `tests/test_textfx_frames.py`.
- [Stage 1 pixel format of the scanout] -> inherited from the Life glue (the
  `bf_target` is XRGB8888 per `src/boot_frame.h`; Linux draws the same surface
  as RG16 in the owner). <!-- UNVERIFIED: confirm which format the stage 1 hardware plane scans at install time; the register evidence in boot-splash-handoff.md reads format 2 with stride 0x8e. -->
- [Record unreadable from Linux] -> playing from frame 0 is the specified
  fallback; Life's capture helper is reused if it is proven.
- [U-Boot playback delays the kernel] -> sequence length is a build constant;
  its duration is added to the 26 s the recorded boot spent in U-Boot before
  `bootm`, and the default is a few seconds.
- [Startup modeset glitches] -> the player reuses the owner's recipe; the
  handoff defect work stays with `display/boot-splash`.
- [Soft-float speed on the C908 is unknown] -> the engine bench runs on the board before any stage 1
  decision; if a frame costs more than the frame period, the glue steps the engine more than once per
  displayed frame or the default effect is chosen from the cheaper ones, and the replay fallback stays.
- [libm differs from glibc in some last bit] -> 0 of 148 host and 0 of 37 firmware comparisons differed;
  the cell-grid hash at the continuation frame catches it, and Linux then replays from frame 0. Running
  the same library in Linux (D4, option b) removes the question.
- [Rust in stage 1 panics or runs out of memory] -> `panic = abort` calls a host hook that falls back to the
  replay sequence or the static logo; the arena is bounded; nothing the engine does can write outside the
  scanout (the glue owns the blits, not the engine).
- [The slot is full] -> the subset is a build input and the install plan refuses a candidate over the slot
  limit, as the DMA trial's writer already does.
- [Font licence] -> OFL/GPL-with-exception notice travels with the generated
  table; reviewed in task 2.2.

## Install and rollback plan (stage 1 and boot files; not executed)

**This is a plan for the operator. Nothing below has been run, and nothing is
written to the board until the operator approves it.** It mirrors the plan
Game of Life proposes and shares its firmware write: one U-Boot-proper
build can carry both sources, so the board is flashed once.

Preconditions: a named operator and the board lock; charger online; the running
system and boot id recorded; a fresh verified backup of the first 4 MiB of the
card (the saved environment lives there and may carry credentials, so it stays
out of Git); `python3 tools/check-boot-life-memory.py` passes against the DTB
the board boots; `openspec validate` and every host task above pass.

1. *Host build.* `nix build .#k230-ttfx-boot` (the staticlib, its size recorded), then
   `nix build .#uboot-k230-boot-textfx` (stage 1 with source id 2 and the library linked in) and
   `nix build .#stage1`; record hashes and the image size against the 1 MiB slot in
   `docs/evidence/boot-text-effects/`.
2. *Install.* Reuse the guarded writer from the DMA trial
   (`docs/evidence/mainline-boot-splash/dma-request-trial-2026-10-20/`):
   write only the 1 MiB U-Boot-proper slot at byte offset 2 097 152 of the
   boot device, fsync, read back 4 MiB with `iflag=direct`, and restore the
   original slot automatically if the readback is not backup-with-payload.
   SPL, environment, partition table and every `/boot` file are untouched.
3. *First boots.* The animation is dormant unless `boot_anim` selects it, so
   the first reboot must look like today's. Then `k230_textfx` at `K230#` (also with
   `tfx_effect`, `tfx_text` and `tfx_seed` set for that boot), transcript to
   `docs/evidence/boot-text-effects/`, then `boot`. The transcript shows the engine's frame count,
   the frame period it achieved, and whether the fallback ran.
4. *Linux side.* Ship the player in the system closure with the option off,
   deploy with `nix copy` and `switch-to-configuration test` (runtime only).
   Enabling it at boot changes the closure that `init=` in
   `/boot/bootargs.txt` selects: edit `bootargs.txt` as the memory note on
   promoting a build describes (back it up under a path outside `/boot`,
   write `bootargs.txt.new`, sync, move over, sync, reboot on the charger,
   check `/run/booted-system`). If the kernel or initrd differ, use
   `tools/coherent-shell-board-install.py`. An initrd-resident player
   replaces `initrd.uimg` the same way and is a separate approval.

Rollback, in order of speed: (a) set `boot_anim` to something else, or stop
the unit; (b) restore the backed-up `bootargs.txt` (previous `init=`), which
returns the previous system and, if the initrd changed, the previous
`initrd.uimg` kept beside it; (c) restore the U-Boot slot from the verified
backup with the recorded `dd` slot command and verify the 4 MiB hash;
(d) if U-Boot does not start, the card is no longer a working boot device:
re-image from the last known-good card using the BootROM USB path in
`docs/uboot-ums.md` and the characterisation of BootROM recovery (open change
`characterise-bootrom-usb-recovery`); this is the failure the guarded writer is
meant to make unlikely.

Each step leaves the board recoverable by reset until step 2, and by (b)
or (c) afterwards.
