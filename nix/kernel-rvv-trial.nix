# Keep the normal image kernel unchanged until actual vector context, signal,
# graphics and restoration checks have passed on the board.
{ kernel, applyPatches, lib }:
kernel.override (old: {
  # kernel.nix owns src/config internally. Intercept buildLinux so this changes
  # its actual inputs instead of passing ignored outer src/config arguments.
  buildLinux = args: old.buildLinux (args // {
    src = applyPatches {
      name = "linux-xuantie-k230-rvv-src";
      src = args.src;
      patches = [ ./patches/riscv-vector-toolchain-probe.patch ];
    };
    structuredExtraConfig = (args.structuredExtraConfig or { }) // {
      RISCV_ISA_V = lib.kernel.yes;
      RISCV_ISA_V_DEFAULT_ENABLE = lib.kernel.yes;
    };
  });
})
