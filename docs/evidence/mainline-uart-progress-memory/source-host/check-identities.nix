# Evaluation only: preserve every pre-existing package and kernel source/config.
{ root, base ? "a4d6958dddf9572320b63c96b4777c959424ece9" }:
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
  cfg = new.nixosConfigurations.k230-mainline-uart-progress-memory.config;
  parent = new.nixosConfigurations.k230-mainline-uart-progress-post-sample.config;
in
assert paths oldp == paths p;
assert sourceConfigs oldp == sourceConfigs p;
assert cfg.boot.kernelPackages.kernel.drvPath == p.kernelMainlineUartProgressMemory.drvPath;
assert cfg.boot.kernelParams == parent.boot.kernelParams;
assert p.kernelMainlineUartProgressMemory.structuredExtraConfig == p.kernelMainlineUartProgressPostSample.structuredExtraConfig;
{
  before = paths oldp;
  after = paths p;
  kernelSourcesConfigs = sourceConfigs p;
  kernel = p.kernelMainlineUartProgressMemory.drvPath;
  source = p.kernelMainlineUartProgressMemory.src.drvPath;
  sourceOutput = p.kernelMainlineUartProgressMemory.src.outPath;
  config = p.kernelMainlineUartProgressMemory.configfile.drvPath;
  dev = p.kernelMainlineUartProgressMemory.dev.outPath;
  exactObjects = p.kernelMainlineUartProgressMemoryExactObjects.drvPath;
  system = cfg.system.build.toplevel.drvPath;
  bundle = p.kernelMainlineUartProgressMemoryTrialBootFiles.drvPath;
  params = cfg.boot.kernelParams;
  uname = p.kernelMainlineUartProgressMemory.version;
}
