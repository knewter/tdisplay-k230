# Separate Memory intervention layered over the unchanged PostSample variant.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-uart-progress-post-sample.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-uart-progress-memory-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-uart-progress-memory.patch ];
      };
    });
  });
}
