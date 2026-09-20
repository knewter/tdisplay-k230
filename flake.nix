{
  description = "NixOS on the LILYGO T-Display-K230 (Kendryte K230D, riscv64)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      # The build host. riscv64-linux is community-tier in nixpkgs with no
      # binary cache, so everything for the board is cross-compiled from here
      # rather than built natively or under emulation. See
      # openspec/specs/image/cross-build.
      buildSystem = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${buildSystem};
      pkgsCross = pkgs.pkgsCross.riscv64;

      # Stage 1 is vendored, never built. See nix/stage1.nix and
      # openspec/specs/image/boot-chain.
      stage1 = import ./nix/stage1.nix { inherit (pkgs) lib; };
    in
    {
      nixosConfigurations.k230 = nixpkgs.lib.nixosSystem {
        modules = [ ./nix/k230.nix ];
      };

      checks.${buildSystem} = {
        # Smoke test for the cross toolchain itself. If this does not build,
        # nothing else in this flake can.
        cross-hello = pkgsCross.hello;
      };

      packages.${buildSystem} = {
        cross-hello = pkgsCross.hello;
        toplevel = self.nixosConfigurations.k230.config.system.build.toplevel;
        kernel = self.nixosConfigurations.k230.config.boot.kernelPackages.kernel;
      };

      # The vendored stage-1 boundary, exposed so it can be inspected without
      # reading the source. `vendored = true` and `builtFromSource = false`
      # are the contract: nothing in this flake compiles U-Boot or OpenSBI.
      inherit stage1;

      devShells.${buildSystem}.default = pkgs.mkShell {
        packages = [ pkgs.qemu ];
      };
    };
}
