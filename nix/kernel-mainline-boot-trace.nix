# Optional finite boot-boundary instrumentation; never an existing output.
# Wrap buildLinux before composing the DRM layer so this final patch receives
# the exact DRM/restart/five-clock source, retaining NixOS's override interface.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-drm.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-boot-trace-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-boot-trace.patch ];
      };
    });
  });
}
