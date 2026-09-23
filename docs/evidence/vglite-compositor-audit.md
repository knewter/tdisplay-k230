# K230 VGLite and display acceleration audit

Date: 2026-09-23. This is a source audit, not a performance claim or a proof
that an accelerated compositor works.

## What is present

The pinned K230 kernel enables `CONFIG_GPU_VGLITE=y` in
`arch/riscv/configs/k230_defconfig:278`. Its DTS node is
`gpu@90800000`, compatible with `verisilicon,gc8000ul`, in
`arch/riscv/boot/dts/canaan/k230.dtsi:658-672`. The driver binds that
compatible and creates the character device named `vg_lite` in
`drivers/gpu/vglite/vg_lite_hal.c:752-803`.

This is a real 2.5D accelerator, though not a Mesa/DRI GPU: the vendor API
provides RGB565 and ARGB8888 buffers, clear, transformed/filtering blits,
blending, and vector paths. See the vendor [GPU API reference](https://github.com/kendryte/k230_docs/blob/main/zh/01_software/board/mpp/K230_GPU_API%E5%8F%82%E8%80%83.md)
and its SDK header
[`vg_lite.h`](https://github.com/kendryte/k230_sdk/blob/main/src/big/mpp/userapps/api/vg_lite.h).
The SDK supplies `libvg_lite.a`, not a Mesa driver or EGL/GBM implementation.
The vendor reference also says that the kernel does not validate command-buffer
physical addresses, so this device must remain inaccessible to untrusted desktop
clients.

VGLite permits only one current context and command-submission thread; this is
also explicit in its Kconfig help and vendor reference. It could serve one
compositor renderer, but not unrestricted independent clients.

## KMS and video interfaces

Physical DRM evidence in [drm-info.txt](drm-info.txt) records a Canaan DRM
card with `DRM_CAP_PRIME = 3`, linear NV12/NV21/NV16/NV61 overlay planes, and
RGB565/ARGB OSD planes. The Canaan DRM driver imports PRIME buffers with
`drm_gem_dma_prime_import_sg_table_vmap` in
`drivers/gpu/drm/canaan/canaan_drv.c:190`; generic PRIME export supplies the
other direction. MVX declares `VB2_DMABUF` on both queues in
`drivers/media/platform/canaan/vpu/mvx_v4l2_vidioc.c:738-750`.

These are necessary interfaces, not a completed zero-copy pipeline. In the
actual decoder trial MVX emitted planar YUV420 (`YU12`), whereas the Canaan
video overlays expose only the listed semi-planar NV formats. The driver must
first prove an NV12 capture layout, a compatible shared multi-plane dma-buf,
and correct fence ownership. Existing V4L2 timestamp findings remain separate.

The Canaan atomic check advertises 1/8x to 8x scaling in
`drivers/gpu/drm/canaan/canaan_vo.c:422-445`, and initialization writes scale
coefficients at lines 579-594. However its plane update functions program
source dimensions into both active-size and display zones while ignoring
`crtc_w` and `crtc_h` (`canaan_vo.c:210-226` and the equivalent video path).
Therefore hardware scaling is not a supported optimization until an atomic
scaled-plane test demonstrates its actual result.

## What it would take

The current Sway uses wlroots' Pixman renderer and RGB565 DRM dumb buffers;
it has no VGLite renderer or overlay-promotion policy. Pixman cannot turn an
MVX dma-buf into a KMS overlay. A direct MVX-to-overlay path needs compositor
cooperation, because Sway owns DRM master, and would accelerate a video surface
only, not terminals or the rest of the scene.

There is one credible renderer investigation: export a Canaan DRM dumb buffer,
map it into VGLite with `vg_lite_map(..., VG_LITE_MAP_DMABUF, fd)`, and have a
new single-context wlroots renderer draw into it. VGLite import is implemented
in `drivers/gpu/vglite/vg_lite_hal.c:407-454`. This avoids relying on VGLite
allocation export, which is explicitly unimplemented (`vg_lite_hal.c:401-405`).
It requires a packaged vendor library/header, a wlroots renderer and texture
implementation, RGB565 correctness, cache/fence validation, and measurement.
It is a compositor-development project, not an FFmpeg or environment flag.

## Next action

Keep the measured finite-window software playback configuration as the current
solution. Before implementing any accelerated renderer, run a small privileged
VGLite smoke test that imports an exported RGB565 dumb-buffer dma-buf, clears or
blits it, completes the GPU work, and scans it out. Verify the result visually
and measure wall-clock submit-to-fence time. Only after that passes should a
VGLite wlroots renderer be scoped. Separately, test a Canaan NV12 overlay with
unequal source and CRTC rectangles; do not rely on the driver’s advertised
scaling range.
