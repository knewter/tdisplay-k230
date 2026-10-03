# Separate SBI-only diagnostic layer over the original printk trace source.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-boot-trace.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-boot-trace-sbi-only-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-boot-trace-sbi-only.patch ];
      };
    });
  });
}
