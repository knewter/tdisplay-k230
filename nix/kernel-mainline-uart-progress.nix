# Separate cached-only diagnostic layered over the unchanged SBI-only source.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-boot-trace-sbi-only.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
    buildLinux = args: old.buildLinux (args // {
      src = applyPatches {
        name = "linux-mainline-k230-uart-progress-src";
        src = args.src;
        patches = [ ./patches/mainline/k230-uart-progress.patch ];
        postPatch = ''
          cp ${./patches/mainline/k230-uart-progress.c} drivers/soc/canaan/k230-uart-progress.c
          cp ${./patches/mainline/k230-uart-progress.h} include/linux/k230_uart_progress.h
        '';
      };
      structuredExtraConfig = (args.structuredExtraConfig or { }) // {
        K230_UART_PROGRESS = lib.kernel.yes;
      };
    });
  });
}
