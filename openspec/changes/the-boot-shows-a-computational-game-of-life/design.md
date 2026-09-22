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
interaction. U-Boot touch is an optional later investigation that may require a
port or adaptation of source-built vendor-derived U-Boot Goodix support, with
separate evidence and no dependency on it. Wayland
continuation is optional and must preserve the existing shell controls.

## Risks / Trade-offs

- [The static handoff remains physically wrong] → block implementation acceptance
  and keep this proposal at zero completed tasks.
- [Reserved RAM overlaps a boot or kernel allocation] → derive and inspect the
  memory map before writing; reject the experiment if ownership is ambiguous.
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
