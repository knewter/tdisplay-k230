# Evaluation only; compare the reviewed source commit before additive wiring.
{ root, base ? "deded9a4d9585110af7a437ebb9fc6e7fb54dd5e" }:
let
  old = builtins.getFlake "git+file://${toString root}?rev=${base}";
  new = builtins.getFlake (toString root);
  existing = import ./check-identities.nix { inherit root; };
  p = new.packages.x86_64-linux;
  oldp = old.packages.x86_64-linux;
  cfg = new.nixosConfigurations.k230-mainline-uart-progress.config;
  parent = new.nixosConfigurations.k230-mainline-boot-trace-sbi-only.config;
  params = cfg.boot.kernelParams;
in
assert p.kernelMainlineUartProgress.drvPath == oldp.kernelMainlineUartProgress.drvPath;
assert p.kernelMainlineUartProgressObjects.drvPath == oldp.kernelMainlineUartProgressObjects.drvPath;
assert cfg.boot.kernelPackages.kernel.drvPath == p.kernelMainlineUartProgress.drvPath;
assert params == parent.boot.kernelParams;
assert builtins.filter (x: x == "console=tty0") params == [];
assert builtins.filter (x: x == "k230.uart_progress=1") params == [];
assert builtins.filter (x: x == "k230.boot_trace=1") params == [ "k230.boot_trace=1" ];
assert builtins.filter (x: x == "k230.boot_trace_sbi_only=1") params == [ "k230.boot_trace_sbi_only=1" ];
{
  inherit existing params;
  preservedKernel = p.kernelMainlineUartProgress.drvPath;
  preservedObjects = p.kernelMainlineUartProgressObjects.drvPath;
  system = p.toplevel-mainline-uart-progress.drvPath;
  selectedSystem = cfg.system.build.toplevel.outPath;
  selectedKernel = cfg.boot.kernelPackages.kernel.outPath;
  bundle = p.kernelMainlineUartProgressTrialBootFiles.drvPath;
  trialUsesMatchingKernel = p.kernelMainlineUartProgressTrialBootFiles.drvPath ==
    (new.inputs.nixpkgs.legacyPackages.x86_64-linux.callPackage (root + "/nix/mainline-drm-trial.nix") {
      inherit cfg;
      kernel = cfg.boot.kernelPackages.kernel;
      deviceTree = p.deviceTreeMainlineDrm;
    }).drvPath;
}
