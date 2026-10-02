# Normal boot files for exactly one evaluated coherent-shell configuration.
# No image assembly, board mutation, or stage-1 replacement happens here.
{ lib, runCommand, dtc, ubootTools, closureInfo, cfg, deviceTree }:
let
  system = cfg.system.build.toplevel;
  kernel = cfg.boot.kernelPackages.kernel;
  closure = closureInfo { rootPaths = [ system ]; };
  bootargs = builtins.concatStringsSep " " cfg.boot.kernelParams
    + " init=${system}/init";
  identity = builtins.toJSON {
    schema = 1;
    configuration = "k230-coherent-shell";
    system = toString system;
    kernel = "${kernel}/Image";
    device_tree = "${deviceTree}/k230-tdisplay.dtb";
    inherit bootargs;
  };
in
runCommand "k230-coherent-shell-boot-files" {
  nativeBuildInputs = [ dtc ubootTools ];
} ''
  mkdir -p $out/inspect-tools
  cp ${kernel}/Image $out/Image
  cp ${deviceTree}/k230-tdisplay.dtb $out/k230-tdisplay.dtb
  chmod +w $out/k230-tdisplay.dtb
  fdtput -t s $out/k230-tdisplay.dtb /chosen bootargs ${lib.escapeShellArg bootargs}
  printf 'bootargs=%s\n' ${lib.escapeShellArg bootargs} > $out/bootargs.txt
  mkimage -A riscv -O linux -T ramdisk -C none -n initrd \
    -d ${system}/initrd $out/initrd.uimg
  printf '%s\n' ${lib.escapeShellArg identity} > $out/identity.json
  ln -s ${system} $out/system
  cp ${closure}/store-paths $out/store-paths
  cp ${closure}/registration $out/registration
  # Pin host inspection tools without adding them to the board closure.
  ln -s ${dtc}/bin/fdtget $out/inspect-tools/fdtget
  ln -s ${dtc}/bin/fdtput $out/inspect-tools/fdtput
  cd $out
  sha256sum Image k230-tdisplay.dtb initrd.uimg bootargs.txt \
    identity.json store-paths registration > SHA256SUMS
''
