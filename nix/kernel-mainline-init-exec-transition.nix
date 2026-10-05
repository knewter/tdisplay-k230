# Default-disabled PID1 witnesses layered over the selected exec-return source.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-init-exec-return.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-init-exec-transition-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-init-exec-transition.patch ];
      };
    });
  });
}
