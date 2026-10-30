# VG-Lite board trial blocked: the boot-default kernel has no GPU driver

Observed 2026-10-30 about 08:05-08:10 UTC, read-only over SSH, no board state
changed (no lock needed beyond reads; nothing deployed, loaded, or restarted).
Evidence class: **board read-only observation**. It is not a GPU result.

## Observations on the running, boot-default system

```sh
ssh k230 'uname -a; readlink /run/current-system; cat /boot/bootargs.txt;
  cat /proc/sys/kernel/yama/ptrace_scope; ls -l /dev/vg_lite;
  lsmod | head; ls /dev | grep -i -E "vg|gpu|dri"; cat /proc/devices | grep -i vg;
  ls /proc/device-tree/soc | grep -i -E "gpu|vg|90800";
  cat /proc/iomem | grep -i -E "9080|gpu"; zcat /proc/config.gz | grep -i -E "vglite|VG_LITE|ETNAVIV"'
```

- Kernel `7.3.0-rc5` (mainline plus the forward-ported Canaan DRM driver).
  `/run/current-system` equals the `init=` in `/boot/bootargs.txt`
  (`...-nixos-system-nixos-26.11.20260919.20b1ddd`); `/boot/Image` is dated
  Oct 20.
- `ls -l /dev/vg_lite`: **No such file or directory**. No `vg` entry in
  `/proc/devices`; `/dev` holds only `dri`; no loaded GPU module.
- `/proc/device-tree/soc` has **no** `gpu@90800000` node; `/proc/iomem` has no
  `9080xxxx` region.
- `/proc/config.gz`: no `VGLITE`/`VG_LITE` option, `DRM_ETNAVIV` unset.
  `ptrace_scope` is 1 and `lsm=landlock,yama,bpf` is on the command line.

## Why this closes no board task

Every committed board GPU result (`docs/evidence/vglite-scene-board/`,
2026-09-23) ran on the earlier vendor kernel (Xuantie 6.6.36 tree, revision
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`), which carries
`drivers/gpu/vglite` (about 2.5 kLOC platform driver: `gc8000ul` compatible,
`vglite` clock and reset, one IRQ, register window `0x90800000`, DISP power
domain) and a `gpu@90800000` node in its `k230.dtsi`. The board has booted
mainline by default since archived change
`2026-10-08-the-board-boots-mainline-by-default`, and
`nix/kernel-mainline*.nix` / `nix/dts/` carry neither the driver nor the node.
The vendor SDK library opens `/dev/vg_lite`, so on the present image
`vg_lite_init` cannot succeed and the opt-in renderer can only fall back to
Pixman. Tasks 2.5, 3.2 and 3.3 (and the board parts of 2.1-2.4) therefore
cannot be run on the boot-default system, and the real-shell GPU-versus-Pixman
question has no measurement newer than the September synthetic-scene pairs.

## What exists and still passes (host class)

```sh
nix build .#k230-vglite-probe.src --out-link <scratch>/sdk-src   # -> pvpqrg3d...-source
TMPDIR=<scratch> WLROOTS_SOURCE=/nix/store/r2zcb3d3dgmz09qjaqsy945inal2h41r-source \
  VGLITE_SOURCE=/nix/store/pvpqrg3diyi9mcgmqjc0f80hpdmk699p-source/buildroot-overlay/package/vg_lite \
  tools/test-vglite-renderer.sh
```

Exit 0, ASan/UBSan, 2026-10-30:
`PASS: exact scene-default color identity and rejected metadata matrix,
production renderer snapshots, RGB channel order, padded upload, crop/scale
translation, alpha/clip/partial-damage replay, exact opt-in,
record/map/init/command/finish failures, completion quarantine; real pinned
Pixman output comparison`. Host test doubles, not hardware.

## Last measured answer (September, vendor kernel, synthetic scene)

`docs/evidence/vglite-scene-board/context-lifetime/README.md`: three paired
GPU/forced-Pixman repeats of an animated SHM parent/child scene at 568x1232
RGB565. With one retained context the GPU path cost about 44 ms wall and
37 ms process CPU per pass against 36.5 ms and 32.5 ms for Pixman: about 21%
more wall and 14% more process CPU. Snapshot copy (~20 ms) and source
conversion/upload (~17 ms) dominate; GPU completion is ~2.4 ms. Not the real
shell, not interaction, no system-wide or IRQ accounting.

## Decision needed (scope, not mine to take silently)

Testing VG-Lite on the real shell now needs a successor prerequisite:

1. Port the 2.5 kLOC `vg_lite` kernel driver to the 7.3 mainline tree (as a
   module or built in), with a `gpu@90800000` DT node, the `disp_gpu` clock
   gate, the V2P5D reset and the DISP power domain as mainline exposes them
   (see `docs/research/k230-clock-gates-vendor-vs-mainline.md`).
2. Ship that kernel and DTB through `/boot` and reboot the shared board
   (irreversible-class boot-file change; needs the coordinator and a serial
   reservation).
3. Then run the existing prepared runner
   (`tools/vglite-normal-service-trial.py`, procedure in
   `docs/evidence/vglite-normal-service-trial/README.md`) for 2.5, 3.2 and 3.3.

Until then the tasks stay open, Pixman stays the default, and the unchanged
September result is the best available evidence: no offload benefit shown.
