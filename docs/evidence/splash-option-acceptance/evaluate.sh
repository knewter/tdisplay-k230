#!/usr/bin/env bash
# Run from the repository root; this evaluates without changing configuration.
set -euo pipefail
nix eval --json --impure --expr '
let
  f = builtins.getFlake (toString ./.);
  c = f.nixosConfigurations.k230;
  s = c.extendModules {
    modules = [ ({ lib, ... }: { k230.panelConsole = lib.mkForce false; }) ];
  };
  describe = n: {
    drvPath = n.config.system.build.toplevel.drvPath;
    systemPath = n.config.system.build.toplevel.outPath;
    panelConsole = n.config.k230.panelConsole;
    initialSplash = n.config.k230.shell.initialSplash;
    kernelParams = n.config.boot.kernelParams;
  };
in {
  console = describe c;
  splash = describe s;
  consoleImage = {
    drvPath = f.packages.x86_64-linux.sdImage.drvPath;
    imagePath = f.packages.x86_64-linux.sdImage.outPath;
  };
}'
