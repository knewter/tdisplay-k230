# Boot panic with the VO vblank-latch kernel patch

Evidence class: board serial console (physical boot of the T-Display-K230),
captured 2026-09-25 18:06–18:08 -05:00 with `tools/capture-boot.py` on
`/dev/ttyACM0`.

## What happened

System `mgp3bvv4…-nixos-system-nixos-26.11.20260919.20b1ddd` (master
`ece1ee74`: `max_render_time 8` plus the kernel carrying
`nix/patches/canaan-drm-defer-reg-load-to-vblank.patch`, Image sha256
`07a5a803…`) was installed into `/boot` and rebooted. PID 1 oopsed 20 ms
after canaan-drm bound, inside `loop_init`, and the kernel panicked:

```
[    2.469705] canaan-drm soc:display-subsystem: [drm:canaan_drm_bind] Canaan K230 DRM driver register successfully
[    2.489364] Unable to handle kernel paging request at virtual address 000000000000ad5d
[    2.497437] Oops [#1]
[    2.499732] Modules linked in:
[    2.502811] CPU: 0 PID: 1 Comm: swapper/0 Not tainted 6.6.36 #1-NixOS
[    2.509290] Hardware name: LILYGO T-Display-K230 (DT)
[    2.514367] epc : __insert_inode_hash+0x9c/0xc2
[    2.518938]  ra : __insert_inode_hash+0x7e/0xc2
[    2.523499] epc : ffffffff8030b562 ra : ffffffff8030b544 sp : ffffffc80000bd00
[    2.545273]  s1 : ffffffd8045c7ab8 a0 : ffffffd8045c7b40 a1 : 0000000000000000
[    2.588815]  s11: 0000000000000000 t3 : 0000000000000008 t4 : 0000000000000001
[    2.601411] status: 0000000200000120 badaddr: 000000000000ad5d cause: 000000000000000f
[    2.609367] [<ffffffff8030b562>] __insert_inode_hash+0x9c/0xc2
[    2.615239] [<ffffffff804dce14>] bdev_add+0x48/0x50
[    2.620149] [<ffffffff804fdd72>] device_add_disk+0x302/0x376
[    2.625845] [<ffffffff8080a81c>] loop_add+0x2e0/0x35e
[    2.630931] [<ffffffff8103a274>] loop_init+0x10a/0x12c
[    2.636102] [<ffffffff8000290a>] do_one_initcall+0x62/0x26a
[    2.643555] [<ffffffff81001332>] kernel_init_freeable+0x254/0x2bc
[    2.651552] [<ffffffff80eaf918>] kernel_init+0x2a/0x152
[    2.658670] [<ffffffff80ebb0de>] ret_from_fork+0xe/0x20
[    2.665786] Code: 1124 b823 10f4 000f 0310 3023 00e9 3503 fd84 c391 (e798) f097 
[    2.677003] ---[ end trace 0000000000000000 ]---
[    2.683564] note: swapper/0[1] exited with preempt_count 2
[    2.692042] Kernel panic - not syncing: Attempted to kill init! exitcode=0x0000000b
[    2.703410] Kernel Offset: 0x0 from 0xffffffff80000000
[    2.710438] ---[ end Kernel panic - not syncing: Attempted to kill init! exitcode=0x0000000b ]---
```

The same kernel Image booted cleanly once before (system `f102jiy0`, capture
at 16:53 the same day), so the failure is intermittent.

## What is and is not established

- Established: this kernel build panicked at boot once in two attempts. The
  fault is a corrupted pointer in the inode hash chain (`badaddr 0xad5d`)
  while `loop_add` registers a block device. That kind of failure points to
  memory corruption from earlier code, not a loop-driver bug.
- UNVERIFIED: that the vblank-latch patch caused it. The patch changes the
  VO IRQ handler, which is the most recent kernel change and ran just before
  the fault. No second panic, bisect or KASAN run has been done.
- The patch had no measurable effect on the bottom-band flicker
  (`kernel-vblank-latch.md`); Sway `max_render_time 8` fixed that
  (`max-render-time-fix.md`).

## Decision

The patch is removed from `nix/kernel.nix` (the patch file stays in the tree
for reference). Recovery used U-Boot, with no reflash: a one-shot
`ext4load mmc 1:2` boot of the backed-up original files from
`/var/lib/k230/boot-prev/`, then those files were copied back to `/boot` and
checked against their `SHA256SUMS` (`BOOT_RESTORED_OK`).

## Verification of the patch-free build

System `x2glknys…-nixos-system-nixos-26.11.20260919.20b1ddd` (this branch;
Image sha256 `29727ff3…`, `max_render_time 8` in the live
`k230-sway.conf`):

- Board serial: booted once one-shot from `/var/lib/k230/boot-new` via
  U-Boot, then was installed into `/boot` (`SWAP_INSTALLED`, previous files
  kept in `/var/lib/k230/boot-prev`) and booted again through the normal
  autoboot path. Both boots reached login with no oops; `shell`,
  `shell-keyboard` and `theme-helper` were active and there were no failed
  units.
- Board camera, with injected touch (not a real finger): a 24 s webcam
  recording (1280×720 MJPEG, 30 fps) while `/run/k230-gesture-loop.sh` ran
  four cycles of bottom-edge swipe-up to the overview, a horizontal card
  flick, a tap to open a card, and a bottom-edge app switch. Sixteen
  consecutive full-resolution frames of the panel's bottom end
  (`without-kernel-patch-injected-gestures.png`, crop 480×260 at 800,180
  from t = 2.5 s) show no stale or black band. Across all 720 frames, the
  mean luminance of a 300×120 crop over that end stayed within 114.8–126.6
  and never showed a one-frame spike above 6 levels against both
  neighbours.
- Not yet obtained: a real-finger session on this build.
