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

      # Stage 1 is built from source. Two cross derivations, one fetched
      # overlay, and the packaging that turns them into what the card
      # carries. See nix/stage1.nix and openspec/specs/image/boot-chain.
      k230Sdk = pkgs.callPackage ./nix/k230-sdk-src.nix { };
      ubootK230 = pkgsCross.callPackage ./nix/uboot-k230.nix { inherit k230Sdk; };
      opensbiK230 = pkgsCross.callPackage ./nix/opensbi-k230.nix { inherit k230Sdk; };
      stage1 = pkgs.callPackage ./nix/stage1.nix { inherit k230Sdk ubootK230 opensbiK230; };

      # Only under --impure: a directory holding a vendor-compiled u-boot.bin
      # and spl/u-boot-spl.bin, so the packaging can be checked against the
      # bytes the SDK's own pipeline produced. Empty otherwise.
      ubootDirEnv = builtins.getEnv "K230_UBOOT_DIR";

      # One pin, two consumers: the kernel build and the standalone device
      # tree build. Native rather than cross because it is a source fetch --
      # a fixed-output derivation lands on the same store path either way.
      kernelSrc = import ./nix/kernel-src.nix { inherit (pkgs) fetchFromGitHub; };
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

        # The board device tree, compiled WITHOUT the kernel, so that
        # iterating on the panel's DCS init sequence costs seconds instead
        # of a 20 minute cross-compile. See nix/device-tree.nix.
        #   nix build --impure .#deviceTree
        deviceTree = pkgs.callPackage ./nix/device-tree.nix { inherit kernelSrc; };

        # Stage 1, piece by piece, so each can be built and inspected alone.
        #   nix build .#uboot-k230      u-boot.bin, spl/u-boot-spl.bin
        #   nix build .#opensbi-k230    fw_jump.bin
        #   nix build .#fwJump          fw_jump_add_uboot_head.bin
        #   nix build .#stage1          the five files the card carries
        k230-sdk-src = k230Sdk;
        uboot-k230 = ubootK230;
        opensbi-k230 = opensbiK230;
        fwJump = stage1.fwJump;
        stage1 = stage1.built;
        # The packaging alone. Over this flake's own U-Boot by default; under
        # --impure with K230_UBOOT_DIR set, over the vendor-compiled one, which
        # is how the packaging was shown to reproduce the vendor's bytes.
        stage1-packaging =
          if ubootDirEnv == "" then stage1.packaging
          else stage1.packagingOf { ubootDir = /. + ubootDirEnv; name = "k230-stage1-packaging-of-vendor-uboot"; };

        # The bootable card image: stage 1 at its raw offsets, a boot ext4
        # holding the three filenames U-Boot loads by name, and our root
        # filesystem.
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

                # /sbin/init, because U-Boot discards our init=.
                #
                # Observed on hardware: the vendor board code sets its own
                # bootargs and overwrites /chosen/bootargs from the DTB, so
                # our init= never reaches the kernel and it falls back to
                # /sbin/init, /etc/init, /bin/init, /bin/sh -- none of which
                # exist on a NixOS root -- and panics with "No working init
                # found". See docs/evidence/hardware-boot.txt.
                #
                # Pointing /sbin/init at the profile rather than at a store
                # path means it follows the current system across updates.
                mkdir -p ./files/sbin
                ln -sf /nix/var/nix/profiles/system/init ./files/sbin/init
              '';
            };
          in
          pkgs.callPackage ./nix/sd-image.nix {
            inherit stage1 rootfsImage;
            initrd = "${cfg.system.build.toplevel}/initrd";
            kernel = self.k230Kernel.kernel;
            inherit (self.packages.${buildSystem}) deviceTree;
            # Our own board, not the CanMV reference. A bare filename now:
            # it names a file in ${deviceTree}, not a path under dtbs/.
            dtbName = "k230-tdisplay.dtb";
            # bootm passes only the DTB, so /chosen/bootargs is the kernel
            # command line. Derived from the system so the two cannot drift.
            bootargs =
              builtins.concatStringsSep " " cfg.boot.kernelParams
              + " init=${cfg.system.build.toplevel}/init";
          };
      };

      # The stage-1 boundary, exposed so it can be inspected without reading
      # the source: its sources, its derivations, and which one an image
      # build carries (`stage1.source`).
      inherit stage1;


      devShells.${buildSystem}.default = pkgs.mkShell {
        packages = [ pkgs.qemu ];
      };
    };
}
