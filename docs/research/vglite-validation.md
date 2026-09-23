# K230 bounded VG-Lite validation

This optional source-built package advances only the unresolved GPU gates. It
does not join the image closure, open the framebuffer, acquire DRM master,
create a framebuffer, set a CRTC, select a plane, restart a service, or modify
the panel. The board coordinator is the sole operator.

The prior private-buffer evidence is deliberately retained: RGBX opaque scale
passed exactly ([transcript](../evidence/video-acceleration/vglite-rgbx.txt));
the partially saturated RGBA test changed a color channel and remains a failed
exact-color result ([transcript](../evidence/video-acceleration/vglite-initial.txt)).
Neither result establishes RGB565 output, alpha fidelity, dma-buf sharing,
scanout, a wlroots renderer, or video acceleration.

## Source and ABI

`nix/vglite-validation.nix` compiles `libvg_lite.so` from the same narrow,
pinned `kendryte/k230_linux_sdk` revision
`1104236db4d1e47873bd68924f912747b820228c` as the prior probe. It builds no
vendor userspace binary and installs the source tree's Vivante MIT notice. The
pinned 6.6.36 Xuantie kernel registers `/dev/vg_lite`; its API has one context,
so run no other VG-Lite process during the test.

The C908 cache instruction spelling is grounded in the pinned kernel's
`arch/riscv/include/asm/errata_list.h`: the cross assembler cannot spell the
SDK mnemonic, so the derivation carries the kernel-documented encodings. This
is C908-specific and not a portable library claim.

## Subtests and claims

`rgb565` uses private source and destination GPU allocations. It clears an
opaque red left half, point-scales by two, calls `vg_lite_finish`, and requires
exact RGB565 `0xf800` / `0x0000` samples across the boundary. It proves only
private RGB565 rendering.

`alpha` prints a source RGBA sample and an RGBA `SRC_OVER` result after
`vg_lite_finish`. It intentionally has no exact color-pass assertion: the
existing RGBA evidence demonstrated that partially saturated components need
an investigated conversion contract. A successful command proves completion,
not alpha-correct composition.

`dmabuf` opens a board-provided DRM node and uses only dumb-create, PRIME
handle export, dumb-map, and dumb-destroy. It maps the private dumb allocation
on the CPU, passes its mapping plus PRIME fd to `vg_lite_map`, clears it, waits,
and requires a CPU-visible `0xf800` RGB565 sample. The source has no
`drmSetMaster`, `drmModeSetCrtc`, add-FB, plane, or atomic call. Prefer
`/dev/dri/renderD128`; if the board has no render node, pass `/dev/dri/card0`
as the explicit second argument. Opening card0 still does not request master,
but this test must run only under the board coordinator while the shell owns
the display.

`benchmark` repeats the same 128x128-to-256x256 point-scale geometry 200
times. GPU timing includes all submissions through a final `vg_lite_finish`;
Pixman timing measures the equivalent RGB565 CPU composite loop. The output is
diagnostic submit/completion timing, not frame timing or a speedup claim.

## Build and board procedure

Host-only build:

```sh
nix build .#k230-vglite-validation --max-jobs 1 --cores 8
```

The coordinator transfers the resulting executable and, with the shell left
running, records one transcript per subtest:

```sh
/nix/store/...-k230-vglite-validation/bin/k230-vglite-validation rgb565
/nix/store/...-k230-vglite-validation/bin/k230-vglite-validation alpha
/nix/store/...-k230-vglite-validation/bin/k230-vglite-validation dmabuf /dev/dri/renderD128
/nix/store/...-k230-vglite-validation/bin/k230-vglite-validation benchmark
```

If `renderD128` does not exist, the coordinator may explicitly substitute
`/dev/dri/card0`, without stopping Sway or seatd. Each run must show its
`*_BEGIN`, operation result, `*_END`, and overall exit status. Capture the
output under `docs/evidence/video-acceleration/`; a host build or QEMU run
cannot prove the GPU or DRM driver.

## Integration gate

Keep Pixman as the shell renderer unless all board evidence is present:

1. exact RGB565 private-buffer results;
2. documented alpha/color behavior acceptable for the proposed renderer;
3. successful imported dumb-buffer write observed through the CPU map; and
4. a renderer design that specifies cache/fence ownership and proves an actual
   scanout frame without disrupting the shell.

Even a passing dma-buf test proves allocation/export/import only. It does not
prove DRM scanout, display-buffer sharing with the live compositor, video
buffer compatibility, or a compositor integration.
