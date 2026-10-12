# openspec/changes/the-small-core-runs-as-a-coprocessor task 4.2: the daily
# mainline DRM kernel plus CONFIG_REMOTEPROC and the read-only CPU0
# remoteproc skeleton (nix/patches/mainline/k230_cpu0_rproc.c) as a module.
# A SEPARATE derivation: the daily kernel (nix/kernel-mainline-drm.nix) and
# every configured system are unchanged. Cross-build proof only; nothing
# boots this kernel until a board task does.
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
	tristate "Canaan K230 CPU0 remoteproc (read-only skeleton)"\
	depends on ARCH_CANAAN || COMPILE_TEST\
	depends on RESET_CONTROLLER\
	help\
	  Binds the K230 small core (CPU0) as a remote processor and\
	  reports its boot vector and firmware carveout. It never starts,\
	  stops or resets CPU0.\
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
