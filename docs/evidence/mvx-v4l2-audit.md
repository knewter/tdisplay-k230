# MVX V4L2 codec audit

Investigated 2026-09-22 from the kernel source pinned by
[`nix/kernel-src.nix`](../../nix/kernel-src.nix):
`ruyisdk/linux-xuantie-kernel` commit
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`. This is source evidence, not a
claim that a particular board has completed a hardware decode.

## What `/dev/video0` named `mvx` represents

The pinned `arch/riscv/configs/k230_defconfig` sets `CONFIG_VPU_CANAAN=y`.
`drivers/media/platform/Kconfig` includes
`drivers/media/platform/canaan/vpu/Kconfig`, whose `VPU_CANAAN` help text
identifies the Canaan video codec as hardware acceleration for H.264, HEVC,
and JPEG. Its `Makefile` links the objects into `amvx`; with `=y` it is part
of the kernel, rather than a loadable module.

The device tree node is `arch/riscv/boot/dts/canaan/k230.dtsi`, `vpu@90400000`,
with compatible string `canaan,vpu`. `mvx_dev.c` binds that string.
`mvx_ext_v4l2.c` registers a `VFL_DIR_M2M` video device and declares
`V4L2_CAP_VIDEO_M2M`, `V4L2_CAP_VIDEO_M2M_MPLANE`, and
`V4L2_CAP_STREAMING`. `mvx_v4l2_vidioc.c` returns those same capability bits
from `VIDIOC_QUERYCAP`, with driver `mvx`, card `Linlon Video device`, and bus
`platform:mvx`.

The format map in `mvx_v4l2_vidioc.c` contains compressed
`V4L2_PIX_FMT_H264` (also H.264 MVC and no-start-code variants) and raw
NV12/NV21/YUV formats. The intended standard interface is therefore a V4L2
memory-to-memory decoder: compressed H.264 on the OUTPUT queue and decoded
pixels on the CAPTURE queue.

## Firmware and licensing boundary

The ordinary codec path does not request an external `/lib/firmware` file.
Despite the local callback name `request_firmware_done`,
`mvx_firmware_cache.c` allocates a `struct firmware` and assigns pointers to
arrays compiled from these source files:

| Array source | Bytes |
| --- | ---: |
| `fw_h264dec.c` | 271,104 |
| `fw_h264enc.c` | 361,472 |
| `fw_hevcdec.c` | 219,392 |
| `fw_hevcenc.c` | 353,664 |
| `fw_jpegdec.c` | 184,192 |
| `fw_jpegenc.c` | 277,760 |

`mvx_firmware_cache.c:345-389` selects each array by codec and direction.
There is no `request_firmware(` call under
`drivers/media/platform/canaan/vpu`. Consequently, disabling NixOS's general
redistributable-firmware set neither supplies nor removes these payloads:
the selected codec microcode is already linked into the kernel that runs on
the board.

Those arrays are opaque instruction/data words, so this path is **not
blob-free**, even though the C files are in the pinned kernel source. Each
`fw_*.c` file has a Canaan Bright Sight copyright and BSD-3-style source and
binary redistribution conditions, while also carrying `SPDX-License-Identifier:
GPL-2.0-only`. The main MVX driver sources, including `mvx_driver.c`, carry
both an Arm Technology (China) confidential/proprietary notice and GPL text.
Those conflicting/overlapping notices need vendor/legal review before treating
the embedded microcode as independently redistributable. This is distinct from
the RT-Smart SDK's opaque `mpp/kernel/lib/*.a` files: the Nix kernel builds
this V4L2 driver and its arrays from the pinned Linux source, and does not link
the RT-Smart libraries.

## Minimal board probe

[`tools/mvx-v4l2-probe.c`](../../tools/mvx-v4l2-probe.c) opens the chosen video
node read-only and performs only `VIDIOC_QUERYCAP` and `VIDIOC_ENUM_FMT` for
`VIDEO_OUTPUT_MPLANE` and `VIDEO_CAPTURE_MPLANE`. It does not set a format,
allocate buffers, queue a buffer, or start streaming.

Cross-compile it with the existing toolchain:

```sh
/nix/store/v0dbf36mkxl9lzxp4rldsqn6ryl0svk9-riscv64-unknown-linux-gnu-gcc-wrapper-15.2.0/bin/riscv64-unknown-linux-gnu-gcc \
  -std=c11 -Wall -Wextra -Werror -O2 -o mvx-v4l2-probe tools/mvx-v4l2-probe.c
./mvx-v4l2-probe /dev/video0
```

A usable H.264 decode path must report the M2M/MPLANE/STREAMING capabilities,
`driver=mvx`, and `H264` in `output_mplane`; a raw capture format such as NV12
is expected in `capture_mplane`. That checks the live driver rather than
assuming that the node name alone means decode works.

After an FFmpeg build includes V4L2 M2M, first verify that the decoder was
compiled, then run a short decode-only test against a local H.264 file:

```sh
ffmpeg -hide_banner -decoders | grep h264_v4l2m2m
ffmpeg -v verbose -c:v h264_v4l2m2m -i INPUT -an -f null -
```

`-c:v h264_v4l2m2m` selects this decoder; a generic `-hwaccel` flag is not the
mechanism here. Compare it with `-c:v h264` while recording FFmpeg's selected
codec and CPU use. A successful decode proves only the VPU decoder path.
`mpv --vo=wlshm` still copies and paints the decoded pixels on the CPU, so it
can retain presentation drops even when V4L2 decode is working. It does not
establish GPU acceleration, direct scanout, or compositor throughput.
