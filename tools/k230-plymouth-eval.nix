# Evaluation-only candidate for display/boot-splash task 5.1.
# Keep this separate from the flake: it does not enable Plymouth in the image.
let
  flake = builtins.getFlake (toString ../.);
  system = flake.inputs.nixpkgs.lib.nixosSystem {
    specialArgs = { inherit (flake) k230Kernel; };
    modules = [
      ../nix/k230.nix
      ../nix/hardware.nix
      ../nix/shell.nix
      {
        k230.shell = { enable = true; probes = true; debugLog = true; };
        boot.plymouth = {
          enable = true;
          # The built-in spinner is the minimal theme baseline for task 5.1.
          theme = "spinner";
        };
      }
    ];
  };
in
system.config.system.build.toplevel
