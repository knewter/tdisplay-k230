# Evaluation only: preserve every pre-existing package and kernel source/config.
{ root, base ? "9248ffa445629ac3f0a87a73aa1f85a0695bba3d" }:
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
  cfg = new.nixosConfigurations.k230-mainline-uart-progress-post-sample.config;
  parent = new.nixosConfigurations.k230-mainline-uart-progress-breadcrumbs.config;
in
assert paths oldp == paths p;
assert sourceConfigs oldp == sourceConfigs p;
assert cfg.boot.kernelPackages.kernel.drvPath == p.kernelMainlineUartProgressPostSample.drvPath;
assert cfg.boot.kernelParams == parent.boot.kernelParams;
assert p.kernelMainlineUartProgressPostSample.structuredExtraConfig == p.kernelMainlineUartProgressBreadcrumbs.structuredExtraConfig;
{
  before = paths oldp;
  after = paths p;
  kernelSourcesConfigs = sourceConfigs p;
  kernel = p.kernelMainlineUartProgressPostSample.drvPath;
  source = p.kernelMainlineUartProgressPostSample.src.drvPath;
  sourceOutput = p.kernelMainlineUartProgressPostSample.src.outPath;
  config = p.kernelMainlineUartProgressPostSample.configfile.drvPath;
  dev = p.kernelMainlineUartProgressPostSample.dev.outPath;
  exactObjects = p.kernelMainlineUartProgressPostSampleExactObjects.drvPath;
  system = p.toplevel-mainline-uart-progress-post-sample.drvPath;
  bundle = p.kernelMainlineUartProgressPostSampleTrialBootFiles.drvPath;
  params = cfg.boot.kernelParams;
  uname = p.kernelMainlineUartProgressPostSample.version;
}
