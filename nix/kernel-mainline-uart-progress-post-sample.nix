# Separate post-sample records layered over the unchanged Breadcrumbs variant.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-uart-progress-breadcrumbs.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-uart-progress-post-sample-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-uart-progress-post-sample.patch ];
      };
    });
  });
}
