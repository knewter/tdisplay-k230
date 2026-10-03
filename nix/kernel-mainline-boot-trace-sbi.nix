# Separate optional direct-DBCN layer; retain the original trace derivation.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-boot-trace.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-boot-trace-sbi-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-boot-trace-sbi.patch ];
      };
    });
  });
}
