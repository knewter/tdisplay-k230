# Evaluation only: preserve every pre-existing package and kernel source/config.
{ root, base ? "e2a02cb0015e027f10c7d3fbbacfe1534163a329" }:
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
  cfg = new.nixosConfigurations.k230-mainline-uart-progress-memory-printk.config;
  parent = new.nixosConfigurations.k230-mainline-uart-progress-memory.config;
in
assert paths oldp == paths p;
assert sourceConfigs oldp == sourceConfigs p;
assert cfg.boot.kernelPackages.kernel.drvPath == p.kernelMainlineUartProgressMemoryPrintk.drvPath;
assert cfg.boot.kernelParams == parent.boot.kernelParams;
assert p.kernelMainlineUartProgressMemoryPrintk.structuredExtraConfig == p.kernelMainlineUartProgressMemory.structuredExtraConfig;
{
  before = paths oldp;
  after = paths p;
  kernelSourcesConfigs = sourceConfigs p;
  kernel = p.kernelMainlineUartProgressMemoryPrintk.drvPath;
  source = p.kernelMainlineUartProgressMemoryPrintk.src.drvPath;
  sourceOutput = p.kernelMainlineUartProgressMemoryPrintk.src.outPath;
  config = p.kernelMainlineUartProgressMemoryPrintk.configfile.drvPath;
  dev = p.kernelMainlineUartProgressMemoryPrintk.dev.outPath;
  exactObjects = p.kernelMainlineUartProgressMemoryPrintkExactObjects.drvPath;
  system = cfg.system.build.toplevel.drvPath;
  bundle = p.kernelMainlineUartProgressMemoryPrintkTrialBootFiles.drvPath;
  params = cfg.boot.kernelParams;
  uname = p.kernelMainlineUartProgressMemoryPrintk.version;
}
