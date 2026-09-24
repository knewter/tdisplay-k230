# GPUI on the K230 handheld: renderer feasibility

Research snapshot: 2026-09-23. GPUI source was read at Zed commit
[`4c902c9db22a82f5f3a14c02442e7f60ec40d9c8`](https://github.com/zed-industries/zed/tree/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8),
the `HEAD` returned by `git ls-remote https://github.com/zed-industries/zed.git HEAD`.
This is a source and existing-evidence assessment; there was no GPUI build,
board run, or performance measurement.

## Decision

**Do not replace or accelerate the present Sway/Pixman shell with GPUI now.**
GPUI can be a Wayland *client* inside Sway, but its current Linux window renderer
requires a surface-compatible Vulkan or OpenGL/GLES adapter. The K230's proven
VG-Lite 2.5D interface is a vendor command API, not such an adapter. No working
K230 Vulkan/OpenGL driver has been established in this repository. A CPU
software adapter may be technically possible, but would still render a client
window for the CPU-composited Sway session; it is not evidence of a faster
card shell. A small renderer preflight could be useful if GPUI remains of
interest, before investing in a cross-build or UI rewrite.

## What upstream actually provides

| Path | Source-grounded status | K230 implication |
| --- | --- | --- |
| Native Linux window | GPUI's [README](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui/README.md) calls for the `wayland` or `x11` feature; [the Linux feature manifest](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_linux/Cargo.toml) connects both to `gpui_wgpu`. The [platform selector](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_linux/src/linux.rs) chooses a Wayland client when the compositor is Wayland. | A GPUI app could conceptually be one more app window in the existing Sway session, if it builds and obtains a renderer. This would not implement the compositor's card overview or own the panel. X11 is unnecessary; the current shell builds Sway with Xwayland disabled. |
| Native renderer | [`WgpuContext::instance`](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_wgpu/src/wgpu_context.rs#L289-L298) enables **Vulkan or GL**. [`WgpuRenderer::new`](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_wgpu/src/wgpu_renderer.rs#L264-L311) creates a window surface. Adapter selection tests surface configuration and can return “No GPU adapters found”; normal initialization does not reject CPU adapters, but [device-loss reinitialization](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_wgpu/src/wgpu_renderer.rs#L2154-L2164) does. | A Wayland socket alone is insufficient. The selected Vulkan/GL device must present to that Wayland surface. A software Vulkan/GL adapter is a possible fallback, not VG-Lite hardware acceleration. The current [wgpu API](https://docs.rs/wgpu/29.0.4/wgpu/enum.Backend.html) distinguishes Vulkan and GL; its GL path requires a suitable OpenGL/GLES implementation. |
| Headless | [`gpui_platform::headless`](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_platform/src/gpui_platform.rs#L23-L25) selects a headless platform. The same file's `current_headless_renderer` returns `None` outside macOS. The [Linux headless client](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_linux/src/linux/headless/client.rs) is an event/window test implementation. | Headless tests cannot establish that GPUI draws pixels on this panel, or measure a visible software renderer. |
| Browser/Web | The pinned [context](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_wgpu/src/wgpu_context.rs#L151-L198) has browser WebGPU/WebGL selection only under WASM. | This is not a native K230 rendering escape hatch; it would require a browser and still need a working browser graphics stack. |
| RISC-V build | Rust lists [`riscv64gc-unknown-linux-gnu`](https://doc.rust-lang.org/rustc/platform-support/riscv64gc-unknown-linux-gnu.html) as tier 2 with host tools. Pinned GPUI uses Rust edition 2024 and [wgpu 29.0.4](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/Cargo.toml); Linux pulls in Wayland, `xkbcommon`, font/text, portal and wgpu dependencies. | A Rust target exists, but **GPUI and its native dependencies have not been cross-built here**. The project's current Nix image cross-compiles from x86_64 and has no GPUI derivation. A successful `cargo check` would establish compilation only, not surface support, pixels, touch, or speed. |

The renderer detail matters: upstream [`select_adapter_and_device`](https://github.com/zed-industries/zed/blob/4c902c9db22a82f5f3a14c02442e7f60ec40d9c8/crates/gpui_wgpu/src/wgpu_context.rs#L316-L455)
enumerates adapters, prefers a display-compatible hardware device, and tries
surface configuration. It may accept a CPU device on initial startup. That is
not a built-in Pixman raster path, and it does not translate VG-Lite's clear,
blit and blend commands into Vulkan or GL. A separate driver or renderer port
would be needed for VG-Lite; that is substantial new platform work, with the
single-context/trust constraints recorded in the [local accelerator audit](../evidence/vglite-compositor-audit.md).

## Fit with this device and current measurements

The normal system's [`nix/shell.nix`](../../nix/shell.nix) sets
`WLR_RENDERER=pixman`; Sway runs as the compositor and already owns the display.
The pinned [VG-Lite audit](../evidence/vglite-compositor-audit.md) identifies
the GC8000UL vendor API and explicitly finds no Mesa, EGL or GBM implementation
from the Linux SDK's `libvg_lite.so`. This does **not** prove that every possible
software Vulkan/OpenGL library is absent from a future image; it establishes
that the working hardware path is not a wgpu driver. The opt-in VG-Lite
compositor trial still lost to its paired Pixman fallback—about 44 ms versus
36 ms wall time per render pass, and 37 ms versus 33 ms process CPU—after its
context lifetime fix, with source preparation dominant
([three paired board runs](../evidence/vglite-scene-board/context-lifetime/README.md)).

The live-card shell is also above its declared CPU and tracking budgets: the
[paired cache trial](../evidence/card-shell/scaled-cache-board/README.md)
reported one-card update CPU p95 16.773–18.685 ms and tracking interval p95
about 57.48 ms against 16.667 ms and 33.334 ms limits. GPUI would draw its
*own* window, then Sway would still composite it. It cannot be credited with
reducing these card-shell costs without an equivalent end-to-end workload and
physical measurement. The extra client rendering pass could increase CPU and
memory if its only usable adapter is software; that is an inference, not a
measured GPUI result.

## Bounded next experiment, if revisited

1. **Renderer preflight first, isolated from the normal image.** Under an
   operator-reserved build/board slot, build a tiny pinned-wgpu 29.0.4 Wayland
   client for the existing cross target. In a bounded normal Sway session,
   enumerate Vulkan/GL adapters, device type and driver; create/configure a
   Wayland surface, draw one known-color frame, and capture its pixels. Preserve
   adapter logs, exact store paths, source commit, native capture and
   restoration record. Stop if no surface-compatible adapter, unsupported
   target dependencies, missing pixels, service disruption, or failed normal
   restoration. No display takeover or VG-Lite device access is needed.
2. **Only if that gate passes**, build a minimal GPUI Wayland app with the
   `wayland` feature and an equivalent simple SHM client. Time whole client
   plus Sway process CPU, update/present cadence, incremental resident memory,
   native screenshot and actual touch route at 568×1232. Identify whether the
   adapter is hardware or software. A CPU adapter alone is not a performance
   win. Stop performance exploration unless the GPUI path shows lower
   *combined* CPU than the equivalent client while preserving pixels and input;
   then repeat under the existing card workload and its unchanged 16.667 ms
   p95 / 33.334 ms maximum update-CPU and 33.334 ms tracking-p95 limits.

The first host-only action, after a build slot is free, could be an isolated
`cargo check --locked --target riscv64gc-unknown-linux-gnu` of the pinned
Wayland-only example with the Nix cross linker and native libraries declared.
That is useful only as a compilation risk check. It does not answer the
renderer gate, and no cross-build was run for this note. If a surface-capable
adapter and credible comparison emerge, propose a narrow opt-in GPUI **client**
trial. There is no basis yet for a product-shell rewrite or a new compositor
proposal.
