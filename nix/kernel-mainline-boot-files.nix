# Boot files for nixosConfigurations.k230-mainline-console: Image, a DTB
# with this system's bootargs baked into /chosen, and the system's initrd
# wrapped as a U-Boot ramdisk image (initrd.uimg).
#
# openspec/changes/the-board-runs-a-mainline-kernel, milestone 1. This is
# deliberately NOT nix/sd-image.nix: that derivation assembles a full raw SD
# image at the vendor stage 1's exact hardcoded offsets (SPL/U-Boot/env/boot
# partition/root partition) and always pairs the kernel with
# nix/device-tree.nix's vendor DTB and nix/dts/k230-tdisplay.dts's bootargs
# construction -- reusing it here would either silently keep shipping the
# VENDOR DTB alongside this mainline kernel (wrong SoC peripheral set) or
# require threading a `deviceTree`/`dtbName` parameter through a derivation
# that has never needed one, for a flash flow the coordinator is not using
# anyway (this milestone's proof is a manual U-Boot `ext4load`+`bootm`
# against the physical card's EXISTING boot/root partitions, per the task's
# own hard rule, not a re-flash).
#
# Root device: deliberately NOT a hardcoded /dev/mmcblkN device path. This
# system's own `fileSystems."/"` (inherited unmodified from nix/hardware.nix,
# since k230-mainline-console only extends k230-console's kernel/module
# selection, not its filesystem config) already reads:
#
#   fileSystems."/" = { device = "/dev/disk/by-label/NIXOS_SD"; fsType = "ext4"; };
#
# -- exactly what nix/sd-image.nix's own `rootfsImage` is built with
# (`volumeLabel = "NIXOS_SD"`), so a real board's boot flow already resolves
# root by ext4 LABEL through the initrd's own generated fstab, not a raw
# device node -- sidestepping the "does mmc_sd1 really enumerate as
# /dev/mmcblk0" uncertainty entirely, and matching the vendor image's own
# already-proven mechanism (nix/sd-image.nix's bootargs construction is
# exactly `cfg.boot.kernelParams` + `init=`, no `root=` override either).
# So this derivation copies that same construction rather than inventing a
# device-path guess of its own.
#
# What is still UNVERIFIED: whether this system's own toplevel closure and
# `/nix/var/nix/profiles/system` symlink are actually PRESENT on the same
# physical card's root partition the coordinator boots against -- this
# derivation does not populate or modify that partition at all (per the
# task's hard rule, a re-flash is out of scope here); the coordinator's own
# staging step is what would need to put this closure there first.
{ lib
, runCommandCC
, buildPackages
, cfg          # the evaluated nixosConfiguration (k230-mainline-console)
, kernel       # self.k230MainlineKernel.kernel
, deviceTree   # nix/device-tree-mainline.nix output (a directory)
, dtbName ? "k230-tdisplay-mainline.dtb"
}:

runCommandCC "k230-mainline-console-boot-files"
{
  nativeBuildInputs = with buildPackages; [ dtc ubootTools ];
}
  ''
    mkdir -p $out
    cp ${kernel}/Image $out/Image-mainline

    cp ${deviceTree}/${dtbName} $out/${dtbName}
    chmod +w $out/${dtbName}
    fdtput -t s $out/${dtbName} /chosen bootargs \
      ${lib.escapeShellArg (
        builtins.concatStringsSep " " cfg.boot.kernelParams
        + " init=${cfg.system.build.toplevel}/init"
      )}
    echo "bootargs: $(fdtget $out/${dtbName} /chosen bootargs)"

    mkimage -A riscv -O linux -T ramdisk -C none -n initrd \
      -d ${cfg.system.build.toplevel}/initrd $out/initrd.uimg
  ''
