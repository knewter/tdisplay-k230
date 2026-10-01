# Matching boot artifacts and closure inventory for an opt-in manual trial.
# This builds no card image, performs no staging, and changes no normal profile.
{ lib, runCommand, dtc, ubootTools, closureInfo, cfg, kernel, deviceTree }:
let
  system = cfg.system.build.toplevel;
  closure = closureInfo { rootPaths = [ system ]; };
  bootargs = builtins.concatStringsSep " " cfg.boot.kernelParams
    + " init=${system}/init";
in
runCommand "k230-mainline-drm-trial-boot-files" {
  nativeBuildInputs = [ dtc ubootTools ];
} ''
  mkdir -p $out
  cp ${kernel}/Image $out/Image-mainline-drm
  cp ${deviceTree}/k230-tdisplay-mainline-drm.dtb $out/
  chmod +w $out/k230-tdisplay-mainline-drm.dtb
  fdtput -t s $out/k230-tdisplay-mainline-drm.dtb /chosen bootargs ${lib.escapeShellArg bootargs}
  printf 'bootargs=%s\n' ${lib.escapeShellArg bootargs} > $out/bootargs.txt
  mkimage -A riscv -O linux -T ramdisk -C none -n initrd \
    -d ${system}/initrd $out/initrd.uimg
  ln -s ${system} $out/system
  cp ${closure}/store-paths $out/store-paths
  cp ${closure}/registration $out/registration
  sha256sum $out/Image-mainline-drm $out/k230-tdisplay-mainline-drm.dtb \
    $out/initrd.uimg $out/bootargs.txt | sed "s|$out/||" > $out/SHA256SUMS
''
