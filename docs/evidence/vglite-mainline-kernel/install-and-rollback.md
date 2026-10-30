# Installing the GPU node on the board, and rolling it back

Prepared 2026-10-30. Nothing here has been run against `/boot`. The kernel
Image is **unchanged**: the DTB-only plan below leaves `/boot/Image` byte
for byte as it is (sha256 `d6b2153d...c4` on the board equals the Image of the
kernel the new system closure would use, `/nix/store/21lz5c6p...-linux-...-7.3.0-rc5`).

## Artifacts (host store paths)

| Item | Path / hash |
| --- | --- |
| DTB for `/boot/k230-tdisplay.dtb` | `/nix/store/dddi9nmkb4d5pjmvzzdych4safx5lcm5-k230-tdisplay-vglite.dtb`, sha256 `f3fe41f75a0de41895e5d9cfe0bdd28e0c1df1307abfe254058d7a2c3e0b2558`, 19308 bytes. The nix `mainlineDrmHotplugDeviceTreeNormalName` DTB with the board's existing `/chosen bootargs` string put back, so the only differences from the file now on the board are the `gpu@90800000` node, its `__symbols__` entry and the phandle renumbering that follows (diff checked: every other property is equal). Already copied to the board as `/var/tmp/k230-tdisplay-vglite.dtb` (hash verified there). |
| Driver and overlay modules | `/nix/store/c07fydj8f3z1nwww0xn500ni2c4laphc-k230-vglite-module-riscv64-unknown-linux-gnu-7.3-port/lib/modules/7.3.0-rc5/extra/{vglite.ko,vglite_overlay.ko}`. Already in the board's store (`nix copy`). Vermagic equals the running kernel's. |
| Probe | `/nix/store/m0y8nk5nr38pvmkjlmbnmz800rfp6fg5-k230-vglite-probe-riscv64-unknown-linux-gnu-0-1104236db4d1e47873bd68924f912747b820228c/bin/k230-vglite-probe`, in the board's store. |
| Sample coherent bundle (not for install as is) | `/nix/store/pngc281sn0pb7jdq2xn6jb74x374dwms-k230-coherent-shell-boot-files`: system `3djwpfni...`, built from this branch's base, so it lacks other agents' newer shell work. Rebuild from merged `master` before any system promotion. |
| Backups (nothing under `/boot` touched to make them) | board: `/var/lib/k230-vglite-backup/{k230-tdisplay.dtb,bootargs.txt}` (dtb sha256 `f6d31149d75d50fc997fe1d1aa1e7ba9c15c33ea682a6b858cda55f93225a618`); host: `~/k230-boot-backups/k230-tdisplay.dtb.before-vglite-20261030` (same hash). |

## What changes in `/boot`

Only `/boot/k230-tdisplay.dtb` (19048 -> 19308 bytes; the 100 MB partition has
27 MB free). `Image`, `initrd.uimg`, `bootargs.txt` (so `init=` stays on the
current boot default), `logo.xrgb`, `fw_jump_add_uboot_head.bin`, `force_dtb`,
`lcd_dtb`, `hdmi_dtb` are untouched. Nothing loads a GPU driver at boot in this
plan (the module is not in the booted closure), so the node is inert until
someone `insmod`s the module.

## Install commands (board lock held; charger online; run on the host)

```sh
flock /tmp/k230-board.lock ssh -F ~/tmp/k230-coordination/ssh_config.private k230 '
  set -e
  test "$(sha256sum /var/tmp/k230-tdisplay-vglite.dtb | cut -d" " -f1)" = f3fe41f75a0de41895e5d9cfe0bdd28e0c1df1307abfe254058d7a2c3e0b2558
  test "$(sha256sum /var/lib/k230-vglite-backup/k230-tdisplay.dtb | cut -d" " -f1)" = f6d31149d75d50fc997fe1d1aa1e7ba9c15c33ea682a6b858cda55f93225a618
  cp /var/tmp/k230-tdisplay-vglite.dtb /boot/k230-tdisplay.dtb.k230-new
  sync
  mv /boot/k230-tdisplay.dtb.k230-new /boot/k230-tdisplay.dtb
  sync
  sha256sum /boot/k230-tdisplay.dtb
'
# then reboot (warm), wait for ready-idle in the journal, and check
# /run/booted-system == init= in /boot/bootargs.txt
```

## Verify after the reboot

```sh
ls /sys/bus/platform/devices | grep 90800000        # 90800000.gpu exists, no driver bound yet
M=/nix/store/c07fydj8f3z1nwww0xn500ni2c4laphc-k230-vglite-module-riscv64-unknown-linux-gnu-7.3-port/lib/modules/7.3.0-rc5/extra
insmod $M/vglite.ko                                  # probe line: "VG-Lite GPU registered as /dev/vg_lite"
ls -l /dev/vg_lite
timeout 20 /nix/store/m0y8nk5n...-k230-vglite-probe-.../bin/k230-vglite-probe   # exit 0, "completed (boundary verified)"
rmmod vglite
```

(No overlay module is needed once the DTB carries the node. Do **not** use
`vglite_overlay.ko` on a DTB that already has the node; it refuses to load.)

## Rollback

1. Board up (normal case): restore the file and reboot.
   ```sh
   flock /tmp/k230-board.lock ssh -F ~/tmp/k230-coordination/ssh_config.private k230 '
     cp /var/lib/k230-vglite-backup/k230-tdisplay.dtb /boot/k230-tdisplay.dtb.k230-new && sync &&
     mv /boot/k230-tdisplay.dtb.k230-new /boot/k230-tdisplay.dtb && sync &&
     sha256sum /boot/k230-tdisplay.dtb   # must print f6d31149...'
   ```
2. Board does not boot: take the console (`flock /tmp/k230-board.lock`), interrupt
   U-Boot, `ums 0 mmc 1`; on the host the card appears as
   `/dev/disk/by-id/usb-Linux_UMS_disk_0-0:0` on the J3 cable (see
   `docs/uboot-ums.md`, `tools/ums-session.py`, memory notes "board access and
   USB flashing"). Mount partition 1 (`...-part1`, the ext4 boot partition) and copy
   `~/k230-boot-backups/k230-tdisplay.dtb.before-vglite-20261030` over
   `k230-tdisplay.dtb`; unmount, stop `ums`, `reset`.
3. Stage-1 is never touched; `bootargs.txt` and the Image are unchanged, so the
   previous system boots as soon as the previous DTB is back.

## Current board state (read this first)

An earlier test-load on the running kernel left the board in a degraded state
that only a reboot clears: see `overlay-trial-2-oops.txt` and
`overlay-trial-2-oops-dmesg.txt`. A leaked IRQ 135 handler from the first
(successful) trial's unload, followed by a probe-error-path oops in the second
load, leaves `vglite_overlay`/`vglite` stuck loaded, one `rmmod` in D state, the
overlay node live in the tree and a stale PLIC 135 action. The GPU is idle and
gated, so it is dormant; shell and seatd stay active. Both defects are fixed in
the committed driver (`port-notes.md`). **No further GPU module load should be
attempted before the reboot.**
