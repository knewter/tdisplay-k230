## Context

The current launcher is a Wayland client and can render only its own SHM surface; it learns window metadata through Sway IPC. In contrast, the installed pinned wlroots 0.20 headers expose compositor scene surfaces, node position/input hooks, scene-output commit/frame completion, and presentation helpers (`wlr_scene.h`, `wlr_presentation_time.h`). The default shell explicitly sets `WLR_RENDERER=pixman` and Sway owns DRM through seatd. Existing VGLite evidence proves bounded private/imported buffers, not compositor integration.

## Goals / Non-Goals

**Goals:**
- Establish whether an existing protocol client or a narrowly patched, opt-in Sway can safely make live cards.
- Specify the handoff contract a later product change consumes without depending on the general UX audit.
- Make failure restore the known normal Pixman Sway session.

**Non-Goals:**
- No product card implementation, GPU rewrite, second DRM client, MPV/video integration, general UX policy, or default renderer change.
- No claim that an image capture is a live surface, a frame callback is panel presentation, or a closed client proves successful dismissal.

## Decisions

1. **Compare client/protocol and compositor routes before selecting one.** The audit first determines whether a viable existing protocol exposes live application surfaces plus global touch/focus ownership. A Wayland client cannot itself reparent another client's `wlr_surface` or receive touch before Sway routes it, so the initial hypothesis is a narrow opt-in Sway patch. wlroots' compositor-side scene API exposes `wlr_scene_xdg_surface_create`, node positioning, clipping, input acceptance, scene output commit and frame-done mechanisms. The route remains conditional on a pinned Sway source audit proving its container/seat hooks can own the required state. If neither route is safe, record a grounded negative result and mark product delivery blocked; do not substitute metadata cards.

2. **Keep the renderer and DRM owner fixed.** Sway remains the only KMS/DRM owner, `WLR_RENDERER=pixman` remains default, and the experiment is an explicit opt-in package/session. The existing VG-Lite CPU result justifies measuring an alternative later, not selecting it here.

3. **Use a capability prototype before product work.** It exposes only two eligible app surfaces, a card scene at the selected boundary, continuous single-finger motion, selection/expand, and a close request. It records per-surface lifecycle: mapped -> captured/scene-attached -> dragging -> selected or dismissal-requested -> restored/destroyed. A client buffer is referenced only while wlroots owns the surface; destruction, unmap, output leave and close/refusal cancel the card and restore focus safely.

4. **Treat formats and completion as observed contracts.** The probe logs Pixman buffer format, dimensions/stride, damage/commit and frame/presentation signals. It does not promise dma-buf, RGB565 texture import, or GPU cache/fence behavior. Any unsupported format, capture policy, or renderer operation ends the experiment and returns the normal session.

5. **Separate architecture from product UX.** This change neither waits on nor supplies the interaction policy in `the-handheld-has-a-coherent-ux-plan`. The sibling card-product change consumes this route decision plus the independently agreed UX contract; no dependency points back to it.

## Interface contract for the consuming product change

The architecture experiment must publish: an opt-in entry condition; eligible-surface policy; stable card IDs owned by the selected boundary; lifecycle events; touch/focus ownership during drag; exact close request/refusal/exit states; fallback/abort behavior; renderer/format and completion observations; and evidence paths. The product change may request card behavior only through those published events, never by opening DRM, copying private application data, or assuming thumbnails, GPU, or zero-copy.

## Risks / Trade-offs

- [Pinned Sway lacks a safe hook] -> finish with a source-cited negative decision and retain the launcher.
- [Capture exposes protected content] -> allowlist test apps and record a privacy policy before any general surface capture.
- [Surface disappears or rejects close] -> cancel drag, remove the scene node, restore a valid focused surface, and log refusal separately.
- [Pixman composition misses budget] -> report measurements and disable the opt-in experiment; do not change default rendering.

## Migration Plan

Ship no default behavior. Build/run the probe only by explicit opt-in; remove its package/patch or decline to enable it to return to the existing Sway session.
