# Compositor startup source audit

**Scope:** read-only audit of the pinned Sway 1.12 and wlroots 0.20.2 source
used by the preserve-splash trial.  It explains a candidate source path for
the dark interval; it is not hardware proof of the panel's scanout state.

## Observed camera result

The recorded automatic preserve-image boot
[`20260922T214204Z-preserve-image-automatic-boot.mp4`](20260922T214204Z-preserve-image-automatic-boot.mp4)
has a reported approximately 1.2 second dark interval between the retained
logo and visible Sway content (roughly 71.2--72.3 seconds in the first
120-second capture).  That is a camera observation.  This audit does not
infer from it whether the panel was blanked by hardware, whether a black DRM
buffer was scanned out, or whether the capture path contributed to the
appearance.

## Pinned source inputs

| Component | Immutable source path | Relevant paths |
|---|---|---|
| Sway 1.12 | `/nix/store/2j7grygxd5da5r214vzz3y8b54rr739k-source` | `sway/main.c`, `sway/desktop/output.c`, `sway/config/output.c`, `sway/commands/exec_always.c` |
| wlroots 0.20.2 | `/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source` | `types/output/render.c`, `types/scene/wlr_scene.c`, `include/wlr/types/wlr_scene.h` |

The package derivations identify the same riscv64 Sway and wlroots versions:
`/nix/store/cjwd6s14flmqlrxmiqh951d9jj1n50a6-sway-unwrapped-riscv64-unknown-linux-gnu-1.12.drv`
and
`/nix/store/bb8za0hslfmia223zif6j0h8m5sn5lyy-wlroots-riscv64-unknown-linux-gnu-0.20.2.drv`.

## Startup ordering

Sway loads the configuration, starts the backend, marks the configuration
active, then calls `force_modeset()` **before** `load_swaybars()` and
`run_deferred_commands()`:

- `sway/main.c:356-376`

When the DRM backend reports the panel, Sway initializes rendering and creates
the scene output, then queues a modeset:

- `sway/desktop/output.c:527-600`

The configured K230 output requests enabled state and a mode.  The config's
`render_bit_depth 6` selects RGB565 in the immediately following format
branch:

- `sway/config/output.c:488-550`

`apply_stored_output_configs()` prepares the swapchain, builds the scene state,
and commits the backend before it finalizes the output and arranges layers:

- `sway/config/output.c:1017-1096`

The terminal and keyboard commands in the generated Sway configuration are
ordinary `exec` commands.  While configuration is inactive they are deferred;
after the forced modeset they are forked through `sh -c`:

- `sway/commands/exec_always.c:17-80`

Therefore neither their Wayland surfaces nor the swaybar surface can be part
of Sway's first forced modeset.

## Source-backed black-frame mechanism

wlroots allocates an empty primary swapchain buffer for an enabled, mode, or
render-format-changing state.  It explicitly renders `{ 0, 0, 0, 0 }` into
that buffer with blending disabled:

- `types/output/render.c:41-72`

The initial Sway configuration contains exactly those state changes.  The
first scene build then renders an opaque black full-buffer background over any
damaged region before it renders scene entries:

- `types/scene/wlr_scene.c:2313-2365`
- `types/scene/wlr_scene.c:2505-2584`

This is a direct source explanation for a black first compositor framebuffer.
It is a stronger hypothesis for the observed interval than a normal Sway
output-disable cycle: the usual enabled configuration path calls
`wlr_output_state_set_enabled(..., true)` rather than false
(`sway/config/output.c:488-505`).  This does not rule out a driver-specific
hardware transition, and it does not establish what the camera recorded.

## Why timing the existing owner cannot remove that frame

The DRM splash owner intentionally drops DRM master before Sway opens the DRM
device, while retaining its framebuffer until a successor replaces it.  The
shell service releases that master in `ExecStartPre`; Sway's first commit then
owns and replaces the primary framebuffer.  Deferring the owner signal cannot
place the logo in Sway's initial scene, because Sway needs DRM master to make
that first commit.  The first scene is empty at that point, independent of
when swaybar and terminal processes are later started.

## Minimal implementation direction

The narrow route to test is a Sway-specific, immutable static scene buffer:

1. Construct a `wlr_buffer` from the existing immutable logo asset and add it
   to a root scene layer before `server_start()` and the first
   `force_modeset()`.
2. Keep that scene node through the initial output commit.
3. Remove it only after an explicit readiness condition that represents the
   desired first shell content.  The condition must be documented separately;
   a successful DRM commit alone is insufficient.

wlroots exposes `wlr_scene_buffer_create()` for such a node
(`include/wlr/types/wlr_scene.h:474-479`).  This is an implementation
direction, not a tested design: buffer ownership, pixel conversion to the
K230's RGB565 compositor path, the node's layer, and a safe readiness signal
need design and hardware proof.

There is no existing Sway configuration mechanism that inserts an image into
the root scene before this first forced modeset.  `output background` launches
a Wayland background client and therefore maps later, as do swaybar, foot and
wvkbd.  The smallest existing *in-process* primitive is
`wlr_scene_rect_create()` (`include/wlr/types/wlr_scene.h:457-458`), which
could seed a diagnostic solid colour but cannot retain the logo.  A solid
colour test can distinguish an intentional compositor first frame from a
hardware dark period, but is not a no-black-frame solution.

## Separate preservation risk

This document does not attribute the later keyboard-capture question to the
startup black frame.  The preserve-first diagnostic deliberately skips normal
VO initialization, so it must be assessed independently with the physical
high-contrast marker and the recorded DRM/vblank logs.
