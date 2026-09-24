# Matching coherent-shell boot image: operator preparation

This source checkpoint adds `.#sdImage-coherent` using the same `mkBoardImage`
function as the existing normal `.#sdImage`. It selects the opt-in
`k230-coherent-shell` NixOS configuration. The normal image remains the
bar-session rollback. No image build, SD write, boot-file change, reboot, or
new physical observation is claimed here. The installed coherent system was
last test-activated, not selected for ordinary boot; its exact prior evidence
is in [refined-installed](../refined-installed/README.md).

On the host, after the sole Nix build slot is released, build and record the
two identities together:

```sh
nix eval --raw .#nixosConfigurations.k230-coherent-shell.config.system.build.toplevel
nix eval --raw .#sdImage-coherent.drvPath
nix build .#sdImage-coherent --max-jobs 1 --cores 4 --no-link --print-out-paths
```

The image is the existing [SD layout](../../../../nix/sd-image.nix): boot ext4
starts at byte 4 MiB, spans 112 MiB, and contains `Image`, `initrd.uimg`,
`k230-tdisplay.dtb`, `bootargs.txt`, `fw_jump_add_uboot_head.bin` and the DTB
selector files. Before any selection, extract those files **on the host** and
hash them. Substitute the exact built image path and create a new private
output directory; these commands only read the image.
Confirm the `sfdisk` output shows boot start 8192 and size 229376 in 512-byte
sectors before using the fixed `dd` offsets below.

```sh
image=/nix/store/REPLACE-WITH-EXACT-k230-sd-image.img
boot_dir=$(mktemp -d)
sfdisk -d "$image"
dd if="$image" of="$boot_dir/boot.ext4" bs=1M skip=4 count=112 status=none
for name in Image initrd.uimg k230-tdisplay.dtb bootargs.txt fw_jump_add_uboot_head.bin force_dtb lcd_dtb hdmi_dtb; do
  debugfs -R "dump /$name $boot_dir/$name" "$boot_dir/boot.ext4"
done
sha256sum "$boot_dir"/{Image,initrd.uimg,k230-tdisplay.dtb,bootargs.txt,fw_jump_add_uboot_head.bin,force_dtb,lcd_dtb,hdmi_dtb}
```

Check that `bootargs.txt` has exactly one `init=` token and it names the
evaluated coherent system plus `/init`. Compare **all** eight file hashes with
the running card before deciding which files need replacement. The previous
[root-growth selection](../../storage-capacity/README.md) imported the
whole matching closure and found kernel/initrd hashes unchanged, so it
replaced only differing `bootargs.txt` and DTB bytes. That prior comparison
does not establish that this coherent candidate has the same kernel/initrd;
repeat it on the exact candidate. Preserve the current boot files, system
profile, and a byte-verified recovery image before any write. On a failed
ordinary boot, a Linux rollback timer cannot run; use the preserved boot
selection or the proved USB recovery route.

This board's external bootloader install hook is a no-op. U-Boot imports the
fixed `/boot/bootargs.txt` and its `init=` names a system store path, so
`switch-to-configuration test`, a profile change, or
`switch-to-configuration boot` alone does not make the coherent shell survive
restart. Physical task 5.8 requires a later reserved-board file selection or
full-image flash, a fresh ordinary boot, exact `/run/current-system` and
service checks, and the selected theme appearing again. The theme's private
`current/active` pointer is designed to survive a service restart, but this
document provides no reboot proof.

The host extraction commands were rehearsed read-only on the already built
recovery image
`/nix/store/b384ag314xp1gprqy3i5h7sbsci3fmm0-k230-sd-image.img`:
`sfdisk` reported start 8192/size 229376 sectors, all eight named files
extracted, and OpenSBI's wrapped image SHA256 was
`9627edbeea9b115d7040beea27cc61b23b6aca61cd502fd7760d7ee179f42c99`.
That rehearsal validates extraction syntax and the fixed layout only; it
does not identify or validate the new coherent image.
