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
      stage1 = import ./nix/stage1.nix { inherit (pkgs) lib fetchurl runCommand stdenvNoCC; };
    in
    {
      # Two systems on one base, because the boot paths genuinely differ.
      # k230      the board: vendored U-Boot reads extlinux, root on SD
      # k230-qemu QEMU: kernel loaded directly, whole system in an initrd
      # The Xuantie kernel, built from source. Mainline cannot boot this SoC;
      # see nix/kernel.nix.
      k230Kernel = pkgsCross.linuxPackagesFor (pkgsCross.callPackage ./nix/kernel.nix {
        inherit (pkgsCross) buildLinux;
      });

      nixosConfigurations = {
        k230 = nixpkgs.lib.nixosSystem {
          specialArgs = { inherit (self) k230Kernel; };
          modules = [ ./nix/k230.nix ./nix/hardware.nix ];
        };
        k230-qemu = nixpkgs.lib.nixosSystem {
          modules = [ ./nix/k230.nix ./nix/qemu.nix ];
        };
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

        # What tools/qemu-k230.sh boots: a kernel with standard RISC-V PTE
        # bits, and the whole system as a ramdisk.
        qemu-kernel = self.nixosConfigurations.k230-qemu.config.system.build.kernel;
        qemu-initrd = self.nixosConfigurations.k230-qemu.config.system.build.netbootRamdisk;

        xuantie-kernel = self.k230Kernel.kernel;

        # The bootable card image: vendored stage 1 at its raw offsets, a
        # boot ext4 holding the three filenames U-Boot loads by name, and
        # our root filesystem.
        sdImage =
          let
            cfg = self.nixosConfigurations.k230.config;
            rootfsImage = pkgs.callPackage "${nixpkgs}/nixos/lib/make-ext4-fs.nix" {
              storePaths = [ cfg.system.build.toplevel ];
              volumeLabel = "NIXOS_SD";
              populateImageCommands = ''
                mkdir -p ./files/nix/var/nix/profiles
                ln -sf ${cfg.system.build.toplevel} ./files/nix/var/nix/profiles/system-1-link
                ln -sf system-1-link ./files/nix/var/nix/profiles/system
              '';
            };
          in
          pkgs.callPackage ./nix/sd-image.nix {
            inherit stage1 rootfsImage;
            kernel = self.k230Kernel.kernel;
          };
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
