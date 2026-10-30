## Context

The latest splash handoff evidence shows that stage 1 can keep a static logo
visible to the Linux prompt, while the first Sway modeset still has physical
wrap and color defects. Read-only VO/DSI comparison is now possible, but the
observed register difference does not establish the cause. See
`docs/evidence/boot-splash-handoff.md`. This proposal therefore treats the
static handoff repair as a prerequisite rather than hiding it inside the
animation work.

## Goals / Non-Goals

**Goals:**

- Keep the simulation engine portable C with identical integer rules in U-Boot,
early Linux, and optional Wayland code.
- Define one versioned reserved-RAM record containing validity, boot instance,
generation, dimensions/seed metadata, and the last frame or reconstructible
state.
- Make default output reproducible and recoverable when state is absent or
invalid.
- Give Linux the first required touch interaction: dropping a glider.
- Explain the ownership gap and visible pause between U-Boot exit and Linux
rendering in evidence.

**Non-Goals:**

- Guaranteed uninterrupted animation during kernel decompression, device probe,
or compositor startup.
- Dependence on the second RISC-V core, SMP, RT-Smart, networking, or a home
backup.
- Physical-touch proof in U-Boot, battery-only boot, or a polished Wayland game.
- Acceptance while the static geometry/color handoff remains broken.

## Decisions

**Use a small versioned state record in reserved RAM.** The record is owned by
the boot display contract and has a magic value, ABI version, byte length,
boot-instance marker, generation, seed, dimensions, and checksum. It carries
only same-boot transient state and is invalidated on incompatible version or
bad checksum. The exact reserved address must come from the existing memory
map; no new unverified RAM claim is accepted.

**Share rules and frame encoding, not platform display code.** The C engine owns
cell updates, deterministic seed expansion, glider insertion, and a compact
frame representation. U-Boot and Linux retain their existing panel/VO and DRM
renderers. This separates simulation correctness from the unresolved physical
handoff registers.

**Stop and restart around ownership boundaries.** U-Boot may render successive
frames while it owns the panel. It stops before Linux takes control; Linux may
resume from the record after its display path is ready. The design records the
pause instead of adding unsafe concurrent writers or claiming seamless motion.

**Use deterministic defaults.** A fixed build-time pattern and seed make host
images and recovery boots comparable. Any user interaction is transient and
same-boot only; it never changes the fresh-home defaults.

**Treat touch in layers.** Linux touch dropping a glider is the first required
interaction. U-Boot touch is an optional later investigation that may require
porting Goodix input into U-Boot using the existing Linux driver as a reference,
with separate evidence and no dependency on it. Wayland
continuation is optional and must preserve the existing shell controls.

## Implementation decisions (2026-10-30)

**The record lives inside the existing splash reservation.** `0x102ac000`,
8 KiB, after the 568x1232x4 scanout (ends `0x102ab600`) in the 4 MiB no-map
`reserved-memory` node at `0x10000000` that the splash repair already added
(`nix/boot-splash.nix`). No new node, no new RAM claim;
`tools/check-boot-life-memory.py` checks the window against the DTB the board
boots and the live U-Boot placement. The 40-byte header carries magic, ABI
version, length, dimensions, generation, last-rendered generation, owner and an
FNV-1a checksum over header and grid (`src/game_of_life.h`).

**"Same boot" is a token, not a promise.** Stage 1 picks a nonzero instance
token (low bits of the timer), publishes it in the record and, only if it
published, in `/chosen/canaan,life-instance` through the same
`ft_board_setup` hook that sets `canaan,stage1-splash`. Linux continues from
the record only if the token matches and the checksum holds; a stale record
from an earlier warm reboot, a version mismatch, or any damage falls back to
the deterministic default and says why in the journal.

**The U-Boot code is dormant until told.** `CONFIG_K230_BOOT_LIFE` is off in
the default build (whose output path is unchanged). In the opt-in build the
animation runs at boot only when the environment variable `boot_life` is `1`;
the `k230_life` console command runs it by hand. A first install therefore
boots exactly as before, and the animation is first exercised from the serial
console where a hang is recoverable by reset.

**Stage 1 redraws only changed cells.** Every framebuffer store in U-Boot is
slow and cache-managed; `gol_render_xrgb_diff` paints only cells that changed
and the loop flushes once per frame.

**Linux continuation is the splash owner, off by default.** `k230-drm-splash
--life` validates the record, draws the grid instead of the static logo, steps
it, and takes touch from any direct multitouch device. `k230.bootLife.enable`
turns it on and adds a root oneshot that copies the window out of `/dev/mem`
(an mmap; a read() of a no-map range fails) for the unprivileged owner.

**The Wayland continuation is a background-layer client.** `k230-life-wayland`
is a layer-shell surface on the BACKGROUND layer with no exclusive zone and no
keyboard interactivity. It opens no DRM device, cannot cover shell surfaces,
and leaving it is `kill`.

**Shared parts are a frame-source interface, Life is the first producer
(added 2026-10-30).** `src/boot_frame.h`/`src/boot_frame.c` define
`struct bf_source` (start, step, publish) and `bf_run`, the freestanding stage-1
loop: invalidate the record window, draw frame 0, then step/flush/publish per
frame. Every record starts with a common prefix (magic, ABI version, length,
boot-instance token, source id at byte 30, FNV-1a checksum) and Linux checks
prefix, checksum and the `/chosen/canaan,life-instance` token before handing
the payload to the owner of that source id (0/1 = Life, 2..255 free). Life
plugs in through `src/boot_life_stage1.c`; its Linux consumer is
`nix/drm-splash/life.c`, keyed the same way. A text-effects producer needs its
own `bf_source`, a Linux-side consumer next to `life.c`, and a source id; the
U-Boot glue (`nix/uboot-k230-life/k230_boot_life.c`), the Kconfig/hook patch,
the reserved window, the dormant-by-env gate, the memory checker and the
install procedure are reused as they are. Names already pushed
(`life`, `canaan,life-instance`) were not renamed.

**Stage 1 animates from a cyclic callback, with the blocking loop as fallback
(user decision 2026-10-30).** The vendor-derived U-Boot is 2022.10 and has no
`CONFIG_CYCLIC`/`schedule()`; a minimal API-compatible back-port
(`nix/uboot-k230-life/cyclic.h`, `k230_cyclic.c`) routes `WATCHDOG_RESET()` to
`schedule()` (opt-in build only, never in SPL). `lib/time.c`'s `udelay()` calls
it, and the SD read loop calls `udelay(10)`, so the callback runs throughout
the roughly 3 s of kernel/initrd reads and the bootdelay without adding a
sleep. The frame is drawn by `bf_advance()` (incremental form of the shared
loop); the hook stops in `ft_board_setup()` so the record Linux reads is the
final frame. The generation at handoff therefore varies with load speed.
Findings, call-site survey and the unmeasured costs are in
`docs/evidence/game-of-life/uboot-cyclic.md`; `CONFIG_K230_BOOT_LIFE_CYCLIC=n`
or `k230_life block` gives the blocking loop.

## Risks / Trade-offs

- [The static handoff remains physically wrong] → block implementation acceptance
  and keep this proposal at zero completed tasks.
- [Reserved RAM overlaps a boot or kernel allocation] → decompile the compiled
  DTB and check explicit U-Boot, kernel, initrd, and reserved-memory intervals
  before writing; reject the experiment if ownership is ambiguous.
- [Stage 1 and Linux disagree on state layout] → reject the record by magic,
  version, length, and checksum and render the deterministic default.
- [The panel is unavailable during Linux startup] → document the pause and test
  recovery; do not add a second-core or concurrent display workaround.
- [Touch driver or U-Boot Goodix support is incomplete] → keep animation usable
  without touch and mark the relevant evidence UNVERIFIED.

## Migration Plan

First repair and verify the static splash handoff. Then add the host-tested
engine and state ABI behind a disabled or opt-in image path, verify deterministic
frames without hardware, and only then run the board experiment. Rollback is
removing the animation path and restoring the current static/no-logo boot; no
home data or persistent user state is involved.
