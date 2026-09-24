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
      bootSplashImage = pkgs.callPackage ./nix/boot-splash-image.nix { };
      mkBoardImage = cfg: kernel:
        let
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
          splashImage = if cfg.k230.panelConsole then null else bootSplashImage;
          initrd = "${cfg.system.build.toplevel}/initrd";
          inherit kernel;
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
        # The board, with the shell on. runtime/shell: sway on Pixman, foot,
        # wvkbd, seatd. Switched on here rather than in nix/shell.nix so the
        # module's default stays off and the decision is visible in one place.
        # probes/debugLog are the bring-up settings for this change's
        # evidence; they should leave with it.
        k230 = nixpkgs.lib.nixosSystem {
          specialArgs = { inherit (self) k230Kernel; inherit bootSplashImage; };
          modules = [
            ./nix/k230.nix
            ./nix/hardware.nix
            ./nix/shell.nix
            {
              k230.shell = { enable = true; probes = true; debugLog = true; };
              # The logo is proven in U-Boot, but its Linux handoff currently
              # corrupts physical scanout. Keep the daily shell image usable
              # until both owners pass the recorded handoff test.
              k230.panelConsole = true;
            }
          ];
        };
        # Retain the diagnostic configuration and context probe. The normal
        # board kernel is now the same tested vector-capable kernel, so the
        # trial alias must not apply the source patch a second time.
        k230-rvv-trial = self.nixosConfigurations.k230.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor self.packages.${buildSystem}.kernel-rvv-trial;
          modules = [ ({ pkgs, ... }: {
            environment.systemPackages = [ (pkgs.callPackage ./nix/rvv-context-probe.nix { }) ];
          }) ];
        };
        # The same board with the shell off: the minimal closure
        # system/nixos-config requires, kept evaluable so the shell's cost
        # can be measured as a delta against it.
        k230-console = nixpkgs.lib.nixosSystem {
          specialArgs = { inherit (self) k230Kernel; inherit bootSplashImage; };
          modules = [
            ./nix/k230.nix ./nix/hardware.nix ./nix/shell.nix
            { k230.panelConsole = true; }
          ];
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
        toplevel-console = self.nixosConfigurations.k230-console.config.system.build.toplevel;

        # The compositor alone, from the same package set the system uses,
        # so it can be cross-built first (runtime/shell task 2.2) and its
        # store path is the one the closure will contain.
        shell-compositor = self.nixosConfigurations.k230.config.k230.shell.compositor;
        # Opt-in only: Sway linked against the guarded VG-Lite wlroots fork.
        # This is deliberately outside the default shell and image closure.
        shell-compositor-vglite = self.nixosConfigurations.k230.config.k230.shell.vgliteCompositor;
        shell-compositor-vglite-service = self.nixosConfigurations.k230.config.k230.shell.vgliteServiceCompositor;
        # Diagnostic-only sway: task 6.1 can build this narrow derivation after
        # the image builder is idle, then enable k230.shell.frameTiming on a
        # board image to log CPU scene-build plus KMS-commit submission time.
        shell-compositor-frame-timing = self.nixosConfigurations.k230.config.k230.shell.frameTimingCompositor;
        # Opt-in only: carries the immutable logo scene before Sway's first
        # output commit. The daily configuration keeps initialSplash false.
        shell-compositor-initial-splash = self.nixosConfigurations.k230.config.k230.shell.initialSplashCompositor;
        neofetch = self.nixosConfigurations.k230.pkgs.callPackage ./nix/neofetch.nix { };
        touch-launcher = self.nixosConfigurations.k230.config.k230.shell.launcher;
        # Standalone pinned helper package; no theme service enters the normal
        # image until generation/rollback and physical gates pass.
        omarchy-theme-tools = pkgsCross.callPackage ./nix/omarchy-theme-tools { };
        # Source-built route checkpoint for card-composition investigation. It
        # is intentionally outside the system closure and starts no session.
        root-growth = pkgsCross.callPackage ./nix/root-growth.nix { };
        root-growth-guest = pkgsCross.callPackage ./nix/root-growth-guest.nix { };
        pixman-rvv = pkgsCross.callPackage ./nix/pixman-rvv.nix { };
        pixman-rvv-pixel-probe = pkgsCross.callPackage ./nix/pixman-rvv-pixel-probe.nix {
          pixman = self.packages.${buildSystem}.pixman-rvv;
        };
        rvv-context-probe = pkgsCross.callPackage ./nix/rvv-context-probe.nix { };
        rvv-context-probe-corrupt = pkgsCross.callPackage ./nix/rvv-context-probe.nix { corrupt = true; };
        # Standalone execution diagnostic for declared bit-manipulation
        # extensions. It is never in the normal image closure.
        c908-bitmanip-probe = pkgsCross.callPackage ./nix/c908-bitmanip-probe.nix { };
        # The card trial must use the same overlaid Pixman graph as the normal
        # board compositor; build it from that package set, not pkgsCross.
        card-shell = self.nixosConfigurations.k230.pkgs.callPackage ./nix/card-shell.nix {
          swayUnwrapped = self.nixosConfigurations.k230.pkgs.sway-unwrapped;
        };
        # Historical diagnostic output name retained for trial scripts. The
        # actual candidate now uses the fully rebuilt normal board graph.
        card-shell-rvv = self.packages.${buildSystem}.card-shell;
        card-composition-probe = pkgsCross.callPackage ./nix/card-composition-probe.nix {
          sway = pkgsCross.sway;
          swayUnwrapped = pkgsCross.sway-unwrapped;
        };
        # Narrow builds use the same pinned packages as the shell image.
        video-player = (self.nixosConfigurations.k230.pkgs.callPackage ./nix/video-probe.nix { }).player;
        video-ffmpeg = (self.nixosConfigurations.k230.pkgs.callPackage ./nix/video-probe.nix { }).ffmpeg;
        # Native asset conversion; the U-Boot and Linux owners share this image.
        inherit bootSplashImage;
        drm-splash = self.nixosConfigurations.k230.pkgs.callPackage ./nix/drm-splash { inherit bootSplashImage; };
        kernel = self.nixosConfigurations.k230.config.boot.kernelPackages.kernel;
        kernel-rvv-trial = self.k230Kernel.kernel;

        # What tools/qemu-k230.sh boots: a kernel with standard RISC-V PTE
        # bits, and the whole system as a ramdisk.
        qemu-kernel = self.nixosConfigurations.k230-qemu.config.system.build.kernel;
        qemu-initrd = self.nixosConfigurations.k230-qemu.config.system.build.netbootRamdisk;

        xuantie-kernel = self.k230Kernel.kernel;

        # The RTL8189FTV SDIO module is intentionally exposed separately:
        # building it verifies kernel API compatibility but does not claim a
        # physical board has bound it or can use Wi-Fi.
        k230-wifi-driver = pkgsCross.callPackage ./nix/k230-wifi-driver.nix {
          kernel = self.k230Kernel.kernel;
        };

        # Optional source-built GPU diagnostic.  It is deliberately outside
        # the system closure until its /dev/vg_lite ABI is proven on hardware.
        k230-vglite-probe = pkgsCross.callPackage ./nix/vglite-probe.nix { };
        k230-vglite-color-probe = pkgsCross.callPackage ./nix/vglite-color-probe.nix {
          vgliteProbe = self.packages.${buildSystem}.k230-vglite-probe;
        };

        # Board-only follow-up validation. It is outside the system closure and
        # deliberately does not provide a compositor or display-owner path.
        k230-vglite-validation = pkgsCross.callPackage ./nix/vglite-validation.nix { };

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
        sdImage = mkBoardImage self.nixosConfigurations.k230.config self.k230Kernel.kernel;
        sdImage-rvv-trial = mkBoardImage self.nixosConfigurations.k230-rvv-trial.config
          self.nixosConfigurations.k230-rvv-trial.config.boot.kernelPackages.kernel;
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
