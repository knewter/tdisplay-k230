# Additive worker-only breadcrumbs over the unchanged finite reporter source.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-uart-progress.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-uart-progress-breadcrumbs-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-uart-progress-breadcrumbs.patch ];
      };
    });
  });
}
