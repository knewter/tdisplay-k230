# Evaluation only: preserve every pre-existing package and kernel source/config.
{ root, base ? "8e66e2991cc0c3fbf5028abf04c1ccd827e30bed" }:
let
  old = builtins.getFlake "git+file://${toString root}?rev=${base}";
  new = builtins.getFlake (toString root);
  oldp = old.packages.x86_64-linux;
  p = new.packages.x86_64-linux;
  names = builtins.attrNames oldp;
  paths = packages: builtins.listToAttrs (map (name: {
    inherit name; value = packages.${name}.drvPath;
  }) names);
  kernels = builtins.filter (name: builtins.isAttrs oldp.${name} && oldp.${name} ? configfile && oldp.${name} ? src) names;
  sourceConfigs = packages: builtins.listToAttrs (map (name: {
    inherit name;
    value = { source = packages.${name}.src.drvPath; config = packages.${name}.configfile.drvPath; };
  }) kernels);
  cfg = new.nixosConfigurations.k230-mainline-uart-progress-breadcrumbs.config;
  parent = new.nixosConfigurations.k230-mainline-uart-progress.config;
in
assert paths oldp == paths p;
assert sourceConfigs oldp == sourceConfigs p;
assert cfg.boot.kernelPackages.kernel.drvPath == p.kernelMainlineUartProgressBreadcrumbs.drvPath;
assert cfg.boot.kernelParams == parent.boot.kernelParams;
assert p.kernelMainlineUartProgressBreadcrumbs.structuredExtraConfig == p.kernelMainlineUartProgress.structuredExtraConfig;
{
  before = paths oldp;
  after = paths p;
  kernelSourcesConfigs = sourceConfigs p;
  kernel = p.kernelMainlineUartProgressBreadcrumbs.drvPath;
  source = p.kernelMainlineUartProgressBreadcrumbs.src.drvPath;
  sourceOutput = p.kernelMainlineUartProgressBreadcrumbs.src.outPath;
  config = p.kernelMainlineUartProgressBreadcrumbs.configfile.drvPath;
  dev = p.kernelMainlineUartProgressBreadcrumbs.dev.outPath;
  exactObjects = p.kernelMainlineUartProgressBreadcrumbsExactObjects.drvPath;
  system = p.toplevel-mainline-uart-progress-breadcrumbs.drvPath;
  bundle = p.kernelMainlineUartProgressBreadcrumbsTrialBootFiles.drvPath;
  params = cfg.boot.kernelParams;
  uname = p.kernelMainlineUartProgressBreadcrumbs.version;
}
