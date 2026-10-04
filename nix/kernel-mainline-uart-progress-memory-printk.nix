# Separate MemoryPrintk output channel layered over the unchanged Memory variant.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-uart-progress-memory.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-uart-progress-memory-printk-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-uart-progress-memory-printk.patch ];
      };
    });
  });
}
