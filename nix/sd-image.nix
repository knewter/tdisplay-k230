# An SD image for the T-Display-K230.
#
# The layout is not ours to choose: it is what the vendored stage 1 expects,
# read from the SDK's genimage_cfg/genimage.cfg and its default U-Boot
# environment. Both are recorded in docs/evidence/uboot-env.txt.
#
#   offset 1 MiB     fn_u-boot-spl.bin     raw, outside the partition table
#   offset 1.5 MiB   fn_u-boot-spl.bin     a second copy
#   offset 2 MiB     fn_ug_u-boot.bin      raw
#   offset 3 MiB     env.env               raw, 128 KiB slot
#   offset 3.5 MiB   env.env               a second copy
#   offset 4 MiB     boot ext4, 80 MiB, MBR type 0x83   <- U-Boot reads mmc 1:1
#   offset 128 MiB   root ext4, MBR type 0x83
#
# U-Boot's `blinux` command ext4loads exactly three filenames from the root of
# that boot partition, so they are placed by name and nothing here is a
# NixOS bootloader:
#
#   /fw_jump_add_uboot_head.bin   OpenSBI, with a U-Boot image header
#   /Image                        the kernel
#   /force.dtb                    the device tree
{ lib
, stdenvNoCC
, buildPackages
, stage1          # nix/stage1.nix
, kernel          # the Xuantie kernel: provides Image and dtbs/
, rootfsImage     # ext4 of the NixOS closure
, dtbName ? "canaan/k230-canmv-v3.dtb"
, bootargs          # the kernel command line, baked into the DTB
}:

let
  MiB = 1024 * 1024;

  bootPartOffset = 4 * MiB;
  bootPartSize = 80 * MiB;
  rootPartOffset = 128 * MiB;

  # Stage 1 lives in the gap before the first partition. Sizes are checked at
  # build time rather than assumed: a firmware image that outgrew its slot
  # would otherwise overwrite the next one and fail at boot, far from here.
  raw = [
    { file = "fn_u-boot-spl.bin"; offset = 1 * MiB; limit = 512 * 1024; }
    { file = "fn_u-boot-spl.bin"; offset = 1536 * 1024; limit = 512 * 1024; }
    { file = "fn_ug_u-boot.bin"; offset = 2 * MiB; limit = 1024 * 1024; }
    { file = "env.env"; offset = 3 * MiB; limit = 128 * 1024; }
    { file = "env.env"; offset = 3200 * 1024; limit = 128 * 1024; }
  ];

  ddOne = r: ''
    sz=$(stat -c %s ${stage1.src}/${r.file})
    if [ "$sz" -gt ${toString r.limit} ]; then
      echo "error: ${r.file} is $sz bytes, over its ${toString r.limit}-byte slot at offset ${toString r.offset}" >&2
      exit 1
    fi
    dd if=${stage1.src}/${r.file} of=$img bs=512 seek=$(( ${toString r.offset} / 512 )) conv=notrunc status=none
  '';
in
stdenvNoCC.mkDerivation {
  name = "k230-sd-image.img";

  nativeBuildInputs = with buildPackages; [ e2fsprogs util-linux fakeroot dtc ];

  buildCommand = ''
    img=$out

    rootSize=$(stat -c %s ${rootfsImage})
    total=$(( ${toString rootPartOffset} + rootSize + 1024 * 1024 ))
    truncate -s "$total" $img

    echo "--- boot partition"
    mkdir -p boot
    cp ${kernel}/Image boot/Image
    cp ${kernel}/dtbs/${dtbName} boot/$(basename ${dtbName})
    chmod +w boot/$(basename ${dtbName})

    # Put the kernel command line in the device tree.
    #
    # `bootm` hands the kernel this DTB and nothing else, so /chosen/bootargs
    # IS the command line. Without it the kernel gets an empty one: no
    # console=, no root=, no init=. Observed on hardware -- the board booted
    # and then sat silent on both UARTs, which looks exactly like a board
    # that never started. The DTB had stdout-path and no bootargs.
    #
    # Taken from config.boot.kernelParams rather than written here, so the
    # card cannot disagree with the system on it.
    fdtput -t s boot/$(basename ${dtbName}) /chosen bootargs \
      ${lib.escapeShellArg bootargs}
    echo "bootargs: $(fdtget boot/$(basename ${dtbName}) /chosen bootargs)"
    cp ${stage1.src}/fw_jump_add_uboot_head.bin boot/

    # U-Boot's bootcmd runs k230_set_dtb before loading anything, and that
    # command does NOT read a device tree -- it reads a TEXT file naming
    # one, then sets ${"\${dtb}"} to its contents and saves the environment.
    #
    # Observed on hardware: with these files absent it tries hdmi_dtb, then
    # lcd_dtb twice, fails all three, prints its usage message and returns
    # non-zero. bootcmd is an && chain, so nothing is loaded and U-Boot
    # drops to a prompt. The card was otherwise perfect.
    #
    # force_dtb is checked first and short-circuits display detection, so
    # one file is enough. lcd_dtb and hdmi_dtb are written too, pointing at
    # the same tree, so a board that takes the detection path still works.
    echo -n "$(basename ${dtbName})" > boot/force_dtb
    echo -n "$(basename ${dtbName})" > boot/lcd_dtb
    echo -n "$(basename ${dtbName})" > boot/hdmi_dtb

    # Deliberately no extlinux: the vendored U-Boot never calls sysboot.
    faketime_unused=1
    fakeroot mkfs.ext4 -d boot -r 1 -N 0 -m 1 -L "K230_BOOT" -O ^64bit \
      boot.ext4 ${toString (bootPartSize / 1024)}k
    dd if=boot.ext4 of=$img bs=512 seek=$(( ${toString bootPartOffset} / 512 )) conv=notrunc status=none

    echo "--- root partition"
    dd if=${rootfsImage} of=$img bs=4M seek=$(( ${toString rootPartOffset} / 4194304 )) conv=notrunc status=none

    echo "--- MBR: boot and root only; stage 1 is intentionally NOT in the table"
    sfdisk $img <<EOF
label: dos
start=$(( ${toString bootPartOffset} / 512 )), size=$(( ${toString bootPartSize} / 512 )), type=83
start=$(( ${toString rootPartOffset} / 512 )), size=$(( rootSize / 512 )), type=83
EOF

    echo "--- stage 1, raw, into the gap before partition 1"
    ${lib.concatMapStrings ddOne raw}

    echo "--- done"
    fdisk -l $img || true
  '';

  meta.description = "SD image: vendored stage 1 at its raw offsets, plus the boot and root partitions";
}
