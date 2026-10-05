let
  base = builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-init-exec-transition-source?rev=ea54f9e0f367e04c8a8baba8d11a2f6c5ebb37b9";
  current = builtins.getFlake "git+file:///home/jadams/tmp/k230-mainline-init-exec-transition-source";
  old = base.packages.x86_64-linux;
  new = current.packages.x86_64-linux;
  names = builtins.attrNames old;
  oldPaths = builtins.mapAttrs (_: p: p.drvPath) old;
  unchanged = builtins.all (n: old.${n}.drvPath == new.${n}.drvPath) names;
  cfg = current.nixosConfigurations.k230-mainline-init-exec-transition.config;
  parent = base.nixosConfigurations.k230-mainline-init-exec-return.config;
  kernel = new.kernelMainlineInitExecTransition;
in assert unchanged;
assert cfg.boot.kernelPackages.kernel.drvPath == kernel.drvPath;
assert cfg.boot.kernelParams == parent.boot.kernelParams;
assert kernel.structuredExtraConfig == old.kernelMainlineInitExecReturn.structuredExtraConfig;
{ old_packages_unchanged = builtins.length names; old_paths = oldPaths;
  kernel = kernel.outPath; kernel_drv = kernel.drvPath; dev = kernel.dev.outPath;
  source = kernel.src.outPath; source_drv = kernel.src.drvPath;
  system = cfg.system.build.toplevel.outPath;
  bundle = new.kernelMainlineInitExecTransitionTrialBootFiles.outPath;
  bundle_drv = new.kernelMainlineInitExecTransitionTrialBootFiles.drvPath;
  params = cfg.boot.kernelParams;
}
