# Default-disabled selected ramdisk exec result over the unchanged p2 source.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-uart-progress-memory-printk.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-init-exec-return-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-init-exec-return.patch ];
      };
    });
  });
}
