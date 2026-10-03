# Read-only evaluation; no derivation is realized by this expression.
{ root, base ? "a5629a3d40a1d9f15a0bd5f875a190472a19648f" }:
let
  old = builtins.getFlake "git+file://${toString root}?rev=${base}";
  new = builtins.getFlake (toString root);
  names = [
    "kernel" "kernelMainline" "kernelMainlineDrm"
    "kernelMainlineDrmTrialBootFiles" "kernelMainlineUartObserverBootFiles"
    "kernelMainlineBootTrace" "kernelMainlineBootTraceTrialBootFiles"
    "kernelMainlineBootTraceSbi" "kernelMainlineBootTraceSbiTrialBootFiles"
    "kernelMainlineBootTraceSbiOnly" "kernelMainlineBootTraceSbiOnlyTrialBootFiles"
    "toplevel" "toplevel-mainline-console" "toplevel-mainline-drm-trial"
    "toplevel-mainline-uart-observer" "toplevel-mainline-boot-trace"
    "toplevel-mainline-boot-trace-sbi" "toplevel-mainline-boot-trace-sbi-only"
    "deviceTree" "deviceTreeMainline" "deviceTreeMainlineDrm" "sdImage"
  ];
  paths = f: builtins.listToAttrs (map (name: {
    inherit name; value = f.packages.x86_64-linux.${name}.drvPath;
  }) names);
  p = new.packages.x86_64-linux;
in assert paths old == paths new; {
  before = paths old;
  after = paths new;
  kernel = p.kernelMainlineUartProgress.drvPath;
  source = p.kernelMainlineUartProgress.src.drvPath;
  config = p.kernelMainlineUartProgress.configfile.drvPath;
  objects = p.kernelMainlineUartProgressObjects.drvPath;
  uname = p.kernelMainlineUartProgress.version;
}
