# K230 VG-Lite offscreen probe

`k230-vglite-probe` is an optional, source-built diagnostic. It does not enter
the NixOS image closure and it never opens DRM or framebuffer devices. The
operator runs it as root because the live device is `/dev/vg_lite` with mode
`0600`; the probe changes no device permissions.

## Pinned source and ABI

The source is Canaan's `k230_linux_sdk` revision
`1104236db4d1e47873bd68924f912747b820228c`, restricted in the derivation to
`buildroot-overlay/package/vg_lite`. Its Buildroot package builds
`VGLite/vg_lite.c` plus the Linux ioctl layer as `libvg_lite.so` and places the
same header in the target SDK. The ioctl layer opens exactly `/dev/vg_lite`.

The vendor Makefile names `-mcpu=c908v`, which the pinned cross GCC does not
recognize. The derivation removes that tuning-only flag and retains the normal
riscv64 target ABI; the selected library sources contain no C908-specific
vector intrinsics. Its cache helper does use a C908-specific `dcache.civa`
mnemonic. The derivation replaces that unsupported spelling with the exact raw
clean-and-invalidate instruction and completion barrier documented by the
pinned kernel's `arch/riscv/include/asm/errata_list.h`. It is deliberately
limited to the known C908 board CPU; this is not a portable VG-Lite build.

The pinned 6.6.36 Xuantie kernel's `drivers/gpu/vglite/vg_lite_hal.c` registers
the character device named `vg_lite`; live preflight reports it as
`/dev/vg_lite` major 239 minor 0. This is an API match at the source and device
name boundary, not a claim that a GPU command has executed. The kernel Kconfig
describes this driver as single-thread context use, so run only one VG-Lite
client during this probe.

The source carries `test/LICENSE.txt`, a Vivante MIT license notice. The
derivation installs that notice beside its independently built library and
probe. It uses no vendor-built userspace object or prebuilt firmware.

## What it does

The probe initializes VG-Lite, allocates private 128x128 and 256x256
`VG_LITE_RGBA8888` buffers, GPU-clears them, scales the first buffer by two,
blits it into the second, and calls `vg_lite_finish`. The source is black with
a red left half and the target begins a distinct nonzero color. The probe then
uses source pixels as its byte-order-independent reference and verifies both
sides of the 2x-scaled target boundary at x=127/128 on rows 0, 63, 127, and
255. This proves a completed blit and scale rather than only an initialized or
cleared buffer. The buffers come from `vg_lite_allocate`; there is no DRM
import, KMS commit, scanout mapping, or panel interaction.

Before applying its strict boundary checks the probe prints raw and in-memory
byte-order views of source x=0/127 plus target x=0/126/127/128/129/255 on each
sampled row. Those diagnostics are intended to distinguish a bad transform,
format interpretation, or target-cache observation from an API failure. They
do not relax the success condition.

Build only the narrow diagnostic:

```sh
nix build .#k230-vglite-probe --max-jobs 1 --cores 8
```

On the board, after the integrator has confirmed no other VG-Lite user is
active, run the resulting `bin/k230-vglite-probe` as root. A zero exit status
and its `offscreen RGBA blit-scale completed` line prove the requested private
buffer operation. Any open, ioctl, allocation, finish, or zero-output failure
is a failed diagnostic; do not fall back to DRM or modify display ownership.
