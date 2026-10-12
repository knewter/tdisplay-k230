# Mainline boot splash: laptop proofs for group 1

Host evidence only (laptop claim). No board, serial port or lock was touched,
nothing was flashed, and no physical, QEMU or boot result is claimed. Base
revision `5675e5db`, branch `impl/mainline-splash-2026-10-12`, 2026-10-12.
Retained out-links: `~/.local/state/tdisplay-k230/retained-builds/mainline-splash-2026-10-12`.

## 1.1 Reserved-memory node on the mainline tree

The node is in `nix/dts/k230-tdisplay-mainline-drm-common.dtsi`, included by
the panel, HDMI, HPD-monitor and hotplug DTS files. `nix/device-tree-mainline-drm.nix`
now takes `bootSplashConfig ? import ./boot-splash.nix` and passes the three
`-DK230_SPLASH_FRAMEBUFFER_*` flags, the same constant the vendor tree
(`nix/device-tree.nix:96-98`) and U-Boot's Kconfig fragment use. The base
`k230-tdisplay-mainline.dts` and `nix/device-tree-mainline.nix` are unchanged.

```sh
for a in mainlineDrmHotplugDeviceTreeNormalName mainlineDrmDeviceTreeNormalName \
         deviceTreeMainlineDrm deviceTreeMainlineDrmHdmi \
         deviceTreeMainlineDrmHpdMonitor deviceTreeMainlineDrmHotplug; do
  flock /tmp/k230-nix-build.lock nix build .#$a --max-jobs 1 --cores 4 --out-link $R/$a
done   # all exit 0
fdtget -l <dtb> /reserved-memory               # framebuffer@10000000
fdtget -t x <dtb> /reserved-memory/framebuffer@10000000 reg   # 0 10000000 0 400000
fdtget -p <dtb> /reserved-memory/framebuffer@10000000         # reg no-map phandle
```

Daily DTB: `/nix/store/s95i342w62j6zdnpkz27zzqjsgydxww2-k230-mainline-drm-hotplug-dtb-normal-name/k230-tdisplay.dtb`
(`.#mainlineDrmHotplugDeviceTreeNormalName`). `/memory@0` reads `0 0 0 40000000`.
All four mainline DRM DTBs print `reg` = `0 10000000 0 400000`.

Reserved range 0x10000000..0x10400000 against the U-Boot load map
(`firmware/stage1/tdisplay.env:27`), using the splash bundle's real sizes:

| Item | Start | End | Overlap |
|---|---|---|---|
| bootargs.txt | 0x7000000 | small | no |
| fw_jump_add_uboot_head.bin | 0x8000000 | below 0x8400000 | no |
| kernel Image (header image_size 0x2996000) | 0x200000 | 0x2b96000 | no |
| DTB (14760 bytes) | 0x8400000 | 0x84039a8 | no |
| initrd.uimg (27330502 bytes) | 0x9000000 | 0xaa107c6 | no |
| splash reservation | 0x10000000 | 0x10400000 | inside the 1 GiB node |

The logo itself is loaded into this range by U-Boot, not by these entries.
The kernel image_size is the Image header value; run-time BSS beyond it was
not measured but would need to exceed 0xd4 MiB to reach the range.

## 1.2 Handoff in source and the kernel build

See the "Mainline kernel: stage-1 splash handoff" section of
`docs/evidence/kernel-patches.md` (files, lines, log strings, drop conditions,
and the fbdev-client finding). No driver was patched. Kernel:
`/nix/store/f3rnipvbc5vqam8kwdmn3wgcl5rbz9yx-linux-riscv64-unknown-linux-gnu-7.3.0-rc5`.

## 1.3 Splash image on the mainline shell

New attributes: `nixosConfigurations.k230-mainline-drm-shell-splash`
(`extendModules`, `k230.panelConsole = lib.mkForce false`), `.#sdImage-mainline-splash`,
and `.#kernelMainlineDrmShellSplashBootFiles` (`nix/coherent-shell-boot-files.nix`
gained an optional `splashImage` that adds `logo.xrgb`, checked at 2799104 bytes,
to the bundle and its `SHA256SUMS`; existing bundles are unchanged). The default
at `flake.nix:130-134` stays `true`; `kernelParams` evaluate to `console=tty0` first
for `k230-mainline-drm-shell` and without it for the splash variant.

```sh
flock /tmp/k230-nix-build.lock nix build .#sdImage-mainline-splash --max-jobs 1 --cores 4 --out-link $R/sdImage-mainline-splash
# -> /nix/store/ad30vws162xhr00x747xxilpjbga7qk1-k230-sd-image.img
flock /tmp/k230-nix-build.lock nix build .#kernelMainlineDrmShellSplashBootFiles --max-jobs 1 --cores 4 --out-link $R/kernelMainlineDrmShellSplashBootFiles
# -> /nix/store/kjlnrxv8vdk92lh84w2bkd1v0mx456hy-k230-coherent-shell-boot-files
python3 docs/evidence/mainline-boot-splash/inspect-image.py $R/sdImage-mainline-splash <fdtget> > docs/evidence/mainline-boot-splash/inspect.json
```

[inspect.json](inspect.json) reports PASS: `logo.xrgb` present at 2799104 bytes,
`bootargs.txt` without `console=tty0`, and the image's `k230-tdisplay.dtb` carrying
the reservation. The bundle's `logo.xrgb` is 2799104 bytes; its `system` and
`Image` are the same derivations as the image's.

## Limits

Nothing here shows that the panel stays lit, that `/dev/fb0` is absent, or that
the first modeset is free of a dark frame; those are hardware tasks 2.1 to 2.4.
No binary is committed. The U-Boot logo-device finding is in the commit report,
not in this file.
