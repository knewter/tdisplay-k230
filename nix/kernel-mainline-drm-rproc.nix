# openspec/changes/the-small-core-runs-as-a-coprocessor tasks 4.2 and 5.1: the daily
# mainline DRM kernel plus CONFIG_REMOTEPROC and the CPU0
# remoteproc driver (nix/patches/mainline/k230_cpu0_rproc.c) as a module.
# A SEPARATE derivation: the daily kernel (nix/kernel-mainline-drm.nix) and
# every configured system are unchanged. Only a one-shot board trial boots
# this kernel (docs/evidence/second-core/linux-start-2026-10-12/).
#
# The rproc layer wraps the base kernel's buildLinux and the DRM derivation
# is applied on top of it, so this is exactly kernel-mainline-drm.nix's
# kernel with one more postPatch and two more config symbols.
{ kernelMainline, applyPatches, lib }:
import ./kernel-mainline-drm.nix {
  inherit applyPatches lib;
  kernelMainline = kernelMainline.override (old: {
  buildLinux = args: old.buildLinux (args // {
    src = applyPatches {
      name = "linux-mainline-k230-cpu0-rproc-src";
      src = args.src;
      postPatch = ''
        cp ${./patches/mainline/k230_cpu0_rproc.c} drivers/remoteproc/k230_cpu0_rproc.c
        grep -q '^endmenu$' drivers/remoteproc/Kconfig
        sed -i '0,/^endif # REMOTEPROC$/s//config K230_CPU0_REMOTEPROC\
	tristate "Canaan K230 CPU0 remoteproc"\
	depends on ARCH_CANAAN || COMPILE_TEST\
	depends on RESET_CONTROLLER\
	help\
	  Binds the K230 small core (CPU0) as a remote processor. Starting\
	  it loads a raw image into the firmware carveout, writes the boot\
	  vector and pulses the CPU0 reset. Stop is not supported.\
\
endif # REMOTEPROC/' drivers/remoteproc/Kconfig
        grep -q '^config K230_CPU0_REMOTEPROC$' drivers/remoteproc/Kconfig
        echo 'obj-$(CONFIG_K230_CPU0_REMOTEPROC) += k230_cpu0_rproc.o' >> drivers/remoteproc/Makefile
      '';
    };
    structuredExtraConfig = (args.structuredExtraConfig or { }) // (with lib.kernel; {
      REMOTEPROC = yes;
      K230_CPU0_REMOTEPROC = module;
    });
  });
  });
}
