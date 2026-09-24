# Matching coherent-shell boot image: operator preparation

The latest host-built candidate is source `017125c8`, image
`/nix/store/i0mp5wbp5gjyrb5x69g6n9hm5khawr82-k230-sd-image.img`.
Its [separate inspection record](current-image-017125c8-host.json) pins the
image and all eight boot-file hashes. It names the same
`/nix/store/48x70j3df8ksiyab0sdgas5nzmgx69nz-nixos-system-nixos-26.11.20260919.20b1ddd`
system that was guarded-test-activated for the supervised keyboard preview.
The earlier [integrated image record](integrated-image-host.json) remains
unchanged as evidence for its own `6ed24efb` source and `5xm4…` system.

This change adds `.#sdImage-coherent` using the same `mkBoardImage` function
as the existing normal `.#sdImage`. It selects the opt-in
`k230-coherent-shell` NixOS configuration. The normal image remains the
bar-session rollback. A matching integrated image was later built and
inspected on the host; no SD write, boot-file change, reboot, or new physical
observation is claimed here. The installed coherent system was last
test-activated, not selected for ordinary boot; its latest proof is the
[supervised keyboard preview](../../keyboard-gestures/supervised-installed/README.md).

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
profile, and a byte-verified recovery image before any write. During the
later guarded selection, register the newly selected system in the durable
`/nix/var/nix/profiles/system` profile and retain the previous system through
a separate durable GC root or verified retained profile generation. Check
both roots before reboot: an absolute `init=/nix/store/...` in `bootargs.txt`
does **not** protect that store closure from garbage collection. On a failed
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

## Exact integrated host build

At source `6ed24efb` (including the final keyboard source), the command above
passed and produced
`/nix/store/x0dpxdq2lc8ic9z8hd11ysnfr7cz9w2s-k230-sd-image.img`.
The [structured host inspection](integrated-image-host.json) records the full
revision, image SHA256, derivation, eight extracted boot-file hashes and
check results. The image's single `init=` token names the built coherent
system `/nix/store/5xm4bwka6waggamz9i48ljjp3yilaf6c-nixos-system-nixos-26.11.20260919.20b1ddd/init`.
Its `Image` bytes match that system's kernel; the U-Boot ramdisk has the
expected image magic and its payload byte-matches that system's initrd. The
decompiled image DTB differs from the pinned source DTB only by the inserted
`/chosen/bootargs`. The normal image derivation remains distinct. This is
host-built artifact identity only; reboot selection, GC roots and restored
theme on glass remain open physical work.

Evaluated from this source checkpoint (before the final keyboard source was
integrated, so these are provisional identities): coherent system
`/nix/store/sgmhnb5fwh3vvd4nx2937ixmlgb9h8mr-nixos-system-nixos-26.11.20260919.20b1ddd`,
coherent image derivation
`/nix/store/gqix4f4q4y4bfnwii9bj8mq00822lg8h-k230-sd-image.img.drv`,
normal image derivation
`/nix/store/mw0y48wxa3f6piwa416dnyjd7rafahmw-k230-sd-image.img.drv`.
The two image derivations differ and no image was built. Repeat evaluation
from the final integrated revision before recording a candidate for boot.

## Current system-matched host build

From clean source `017125c89a1103c0371035f95544a801f41c14e0`, evaluation
returned the installed test system `48x70…` above and coherent image
derivation `/nix/store/agidgzbcm2hzmvn2gj1ab4d5z2js4qn6-k230-sd-image.img.drv`.
The exact build command shown above passed. `sfdisk` found the expected boot
start at sector 8192 and size 229376 sectors; all eight named files were
extracted with `debugfs` using the read-only commands above. The full
2,711,429,120-byte image has SHA-256
`e95bfe56162fc7a9dd9e4c0301fbeb9c20e44259fa6cd471b923e6feb7357fc7`.

The extracted `Image` byte-matches `48x70…/kernel`. The `initrd.uimg` has
U-Boot ramdisk magic `0x27051956`, a 64-byte header and a payload that
byte-matches `48x70…/initrd`. `bootargs.txt` and the image DTB agree and
contain exactly one `init=` naming `48x70…/init`. Decompiled image and source
DTBs differ only by the inserted `/chosen/bootargs`; the three selector files
all name `k230-tdisplay.dtb`. The normal `sdImage` derivation remains distinct.
The [structured record](current-image-017125c8-host.json) carries the exact
paths, timestamps, checks and hashes for review.

Compared with the prior `6ed24efb` host image, `Image`, `initrd.uimg`,
OpenSBI and the three selector files have identical hashes; `bootargs.txt`
and the DTB differ. This comparison is **between two host images**, not with
the board's currently selected boot files. The reserved-board operator must
hash the actual `/boot` files and preserve the previous selection before any
file-only update. No SD write, profile update, reboot, physical theme
restoration or ordinary-boot result is claimed here.

The host extraction commands were rehearsed read-only on the already built
recovery image
`/nix/store/b384ag314xp1gprqy3i5h7sbsci3fmm0-k230-sd-image.img`:
`sfdisk` reported start 8192/size 229376 sectors, all eight named files
extracted, and OpenSBI's wrapped image SHA256 was
`9627edbeea9b115d7040beea27cc61b23b6aca61cd502fd7760d7ee179f42c99`.
That rehearsal validates extraction syntax and the fixed layout only; it
does not identify or validate the new coherent image.
