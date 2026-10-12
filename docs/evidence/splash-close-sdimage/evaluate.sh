#!/usr/bin/env bash
# Run from the repository root. Evaluates the configuration `.#sdImage`
# builds (k230-mainline-drm-shell) with k230.panelConsole in both states.
set -euo pipefail
nix eval --json --impure --expr '
let
  f = builtins.getFlake (toString ./.);
  c = f.nixosConfigurations.k230-mainline-drm-shell;
  s = c.extendModules {
    modules = [ ({ lib, ... }: { k230.panelConsole = lib.mkForce false; }) ];
  };
  describe = n: {
    drvPath = n.config.system.build.toplevel.drvPath;
    panelConsole = n.config.k230.panelConsole;
    kernelParams = n.config.boot.kernelParams;
  };
in { true = describe c; false = describe s; }'
