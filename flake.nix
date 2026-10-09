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
      # The narrow build and installed editor share one application closure.
      omawrite = pkgsCross.callPackage ./nix/omawrite { };

      # Stage 1 is built from source. Two cross derivations, one fetched
      # overlay, and the packaging that turns them into what the card
      # carries. See nix/stage1.nix and openspec/specs/image/boot-chain.
      k230Sdk = pkgs.callPackage ./nix/k230-sdk-src.nix { };
      ubootK230 = pkgsCross.callPackage ./nix/uboot-k230.nix { inherit k230Sdk; };
      ubootK230Cpu0IdentityProbe = ubootK230.override {
        cpu0IdentityProbe = true;
      };
      # The diagnostic is compiled in both U-Boot variants by the shared
      # source, but a trial needs only the SPL. Keep U-Boot proper normal.
      ubootK230Cpu0IdentitySPL = pkgs.runCommand "k230-cpu0-identity-spl-with-normal-uboot" { } ''
        mkdir -p $out/spl
        cp ${ubootK230}/u-boot.bin $out/u-boot.bin
        cp ${ubootK230Cpu0IdentityProbe}/spl/u-boot-spl.bin $out/spl/u-boot-spl.bin
      '';
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

      # openspec/changes/the-board-runs-a-mainline-kernel: a SEPARATE pin for
      # a parallel, opt-in mainline kernel build. Does not feed kernelSrc,
      # nix/kernel.nix, nix/device-tree.nix, or any nixosConfigurations
      # output above. See nix/kernel-mainline.nix for what mainline actually
      # supports on this SoC today.
      kernelMainlineSrc = import ./nix/kernel-mainline-src.nix { inherit (pkgs) fetchFromGitHub; };
      bootSplashImage = pkgs.callPackage ./nix/boot-splash-image.nix { };
      mkBoardImage = cfg: kernel: mkBoardImageWith { inherit cfg kernel; };
      mkBoardImageWith = { cfg, kernel, deviceTree ? self.packages.${buildSystem}.deviceTree }:
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
          inherit kernel deviceTree;
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
      # The Xuantie kernel, built from source. Mainline cannot boot this SoC
      # to its full shell yet; see nix/kernel.nix.
      k230Kernel = pkgsCross.linuxPackagesFor (pkgsCross.callPackage ./nix/kernel.nix {
        inherit (pkgsCross) buildLinux;
      });

      # openspec/changes/the-board-runs-a-mainline-kernel: the parallel,
      # opt-in mainline kernel, as a full linuxPackagesFor set (not just
      # `.kernel`) so it can be substituted into a nixosConfiguration's
      # `boot.kernelPackages` the same way k230-rvv-trial already
      # substitutes an alternate k230Kernel below. See nix/kernel-mainline.nix.
      k230MainlineKernel = pkgsCross.linuxPackagesFor (pkgsCross.callPackage ./nix/kernel-mainline.nix {
        inherit (pkgsCross) buildLinux;
      });

      nixosConfigurations = {
        # The board, with the shell on. runtime/shell: sway on Pixman, foot,
        # wvkbd, seatd. Switched on here rather than in nix/shell.nix so the
        # module's default stays off and the decision is visible in one place.
        # probes/debugLog are the bring-up settings for this change's
        # evidence; they should leave with it.
        k230 = nixpkgs.lib.nixosSystem {
          specialArgs = { inherit (self) k230Kernel; inherit bootSplashImage omawrite; };
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
        # Integrated userspace candidate. The original k230 configuration is
        # the reproducible bar-session rollback while on-glass acceptance is pending.
        k230-coherent-shell = self.nixosConfigurations.k230.extendModules {
          modules = [ { k230.shell.coherentShell = true; k230.shell.powerKeyTrial = true; } ];
        };
        # Explicit experimental HDMI profile: preserve the faster trial across
        # activation/reboot without silently changing the daily panel renderer.
        k230-coherent-shell-hdmi-trial = self.nixosConfigurations.k230-coherent-shell.extendModules {
          modules = [
            ./nix/touch-trackpad-service.nix
            {
              k230.shell.hdmiQuarterTurnTrial = true;
              k230.touchTrackpad.enable = true;
            }
          ];
        };
        # Historically "same as k230-coherent-shell, plus Nautilus's own
        # drawer entry next to Portfolio's" while filesAppNautilus defaulted
        # off. The operator has since decided to keep both candidates
        # installed and visible by default (nnn's old unusable "Files" entry
        # is removed outright, not superseded), so filesAppNautilus now
        # defaults on and this alias is identical to k230-coherent-shell;
        # kept only so evidence/tooling that names it by this attribute still
        # resolves. See openspec/changes/the-handheld-has-a-themed-files-app.
        k230-coherent-shell-both-files-apps = self.nixosConfigurations.k230-coherent-shell.extendModules {
          modules = [ { k230.shell.filesAppNautilus = true; } ];
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
          specialArgs = { inherit (self) k230Kernel; inherit bootSplashImage omawrite; };
          modules = [
            ./nix/k230.nix ./nix/hardware.nix ./nix/shell.nix
            { k230.panelConsole = true; }
          ];
        };
        k230-qemu = nixpkgs.lib.nixosSystem {
          modules = [ ./nix/k230.nix ./nix/qemu.nix ];
        };

        # openspec/changes/the-board-runs-a-mainline-kernel, milestone 1.
        # Extends k230-console (shell OFF), not k230-coherent-shell: the plain
        # kernelMainline console profile has no K230 DRM/KMS driver. A separate
        # kernelMainlineDrm candidate now carries the forward-ported display
        # stack, but no physical boot/display proof exists. Keep this system
        # variant scoped to the console milestone; the DRM candidate does not
        # make the graphical shell a verified mainline system.
        #
        # boot.extraModulePackages/boot.kernelModules are force-cleared:
        # nix/hardware.nix's k230WifiDriver (the out-of-tree RTL8189FTV
        # module) is built against `config.boot.kernelPackages.kernel`
        # dynamically, and there is no reason to expect a driver written
        # against the 6.6-era vendor tree to compile against a v7.3-rc5
        # kernel's changed internal APIs -- and there is no SDIO/mmc_sd0 DT
        # node enabled for it to bind to anyway (nix/dts/
        # k230-tdisplay-mainline.dts leaves &mmc_sd0 disabled). Forcing
        # these empty is what keeps `nixosConfigurations.k230-mainline-console.
        # config.system.build.toplevel` buildable at all with the kernel
        # swapped -- untested, this derivation would otherwise try to
        # compile that module against mainline headers and most likely fail
        # the whole system build.
        k230-mainline-console = self.nixosConfigurations.k230-console.extendModules {
          specialArgs.k230Kernel = self.k230MainlineKernel;
          modules = [
            {
              boot.extraModulePackages = nixpkgs.lib.mkForce [ ];
              boot.kernelModules = nixpkgs.lib.mkForce [ ];
              systemd.services.k230-wifi.enable = nixpkgs.lib.mkForce false;
            }
          ];
        };
        # Isolated serial-console system for a recoverable DRM hardware trial.
        # No shell claim: display/touch still require physical observations.
        k230-mainline-drm-trial = self.nixosConfigurations.k230-mainline-console.extendModules {
          # Import directly so the returned kernel keeps buildLinux's override
          # interface; callPackage's outer DRM function rejects NixOS's
          # kernel feature overrides.
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-drm.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
        };
        # Full coherent shell on the mainline DRM kernel: the daily system with
        # only the kernel swapped and the vendor-tree Wi-Fi module removed.
        # Vendor-only drivers (PMU power key, audio, thermal, Wi-Fi) are absent.
        k230-mainline-drm-shell = self.nixosConfigurations.k230-coherent-shell.extendModules {
          specialArgs.k230Kernel = self.nixosConfigurations.k230-mainline-drm-trial.config.boot.kernelPackages;
          modules = [
            ({ config, pkgs, ... }: {
              # The RTL8189FTV module with the 7.3 port patch, built against
              # this variant's own kernel (CFG80211=m); same load and service
              # as the vendor-kernel system.
              boot.extraModulePackages = nixpkgs.lib.mkForce [
                (pkgs.callPackage ./nix/k230-wifi-driver.nix {
                  kernel = config.boot.kernelPackages.kernel;
                  extraPatches = [ ./nix/patches/mainline/rtl8189fs-mainline-v7.3-rc5.patch ];
                })
              ];
              boot.kernelModules = nixpkgs.lib.mkForce [ "8189fs" ];
            })
          ];
        };
        # Getter-only autonomous UART observation; no existing variant changes.
        k230-mainline-uart-observer = self.nixosConfigurations.k230-mainline-drm-trial.extendModules {
          modules = [ ./nix/mainline-uart-observer/module.nix ];
        };
        # Ordinary /init with finite optional kernel milestones, serial only.
        # No observer service, global clock bypass or retained boot console.
        k230-mainline-boot-trace = self.nixosConfigurations.k230-mainline-console.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-boot-trace.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
          modules = [ ({ lib, ... }: let
            baseArgs = self.nixosConfigurations.k230-mainline-drm-trial.config.boot.kernelParams;
          in {
            assertions = [{
              assertion = lib.count (arg: arg == "console=tty0") baseArgs == 1;
              message = "boot-trace base must contain exactly one tty0 console";
            }];
            boot.kernelParams = lib.mkForce (
              lib.filter (arg: arg != "console=tty0") baseArgs ++ [ "k230.boot_trace=1" ]
            );
          }) ];
        };
        # Four direct SBI records outside the original trace emergency calls.
        k230-mainline-boot-trace-sbi = self.nixosConfigurations.k230-mainline-boot-trace.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-boot-trace-sbi.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
          modules = [ ({ lib, ... }: {
            boot.kernelParams = lib.mkOverride 40 (
              self.nixosConfigurations.k230-mainline-boot-trace.config.boot.kernelParams
              ++ [ "k230.boot_trace_sbi=1" ]
            );
          }) ];
        };
        # Isolate diagnostic printk dependency without changing normal logging.
        k230-mainline-boot-trace-sbi-only = self.nixosConfigurations.k230-mainline-boot-trace.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-boot-trace-sbi-only.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
          modules = [ ({ lib, ... }: {
            boot.kernelParams = lib.mkOverride 40 (
              self.nixosConfigurations.k230-mainline-boot-trace.config.boot.kernelParams
              ++ [ "k230.boot_trace_sbi_only=1" ]
            );
          }) ];
        };
        # Separate finite cached UART/IRQ reporter; original artifact policy is
        # inherited. The reviewed controller supplies its volatile runtime gate.
        k230-mainline-uart-progress = self.nixosConfigurations.k230-mainline-boot-trace-sbi-only.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-uart-progress.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
        };
        # Memory intervention; preserve PostSample artifact parameters.
        k230-mainline-uart-progress-memory = self.nixosConfigurations.k230-mainline-uart-progress-post-sample.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-uart-progress-memory.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
        };
        # Separate Linux-console observer output; preserve Memory artifact parameters.
        k230-mainline-uart-progress-memory-printk = self.nixosConfigurations.k230-mainline-uart-progress-memory.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-uart-progress-memory-printk.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
        };
        # Default-disabled selected init exec result; preserve p2 artifact policy.
        k230-mainline-init-exec-return = self.nixosConfigurations.k230-mainline-uart-progress-memory-printk.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-init-exec-return.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
        };
        # Two default-disabled PID1 witnesses; preserve the exec-return policy.
        k230-mainline-init-exec-transition = self.nixosConfigurations.k230-mainline-init-exec-return.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-init-exec-transition.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
        };
        # Post-sample records; preserve Breadcrumbs artifact parameters.
        k230-mainline-uart-progress-post-sample = self.nixosConfigurations.k230-mainline-uart-progress-breadcrumbs.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-uart-progress-post-sample.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
        };
        # Worker-only breadcrumbs; inherit exact original artifact parameters.
        k230-mainline-uart-progress-breadcrumbs = self.nixosConfigurations.k230-mainline-uart-progress.extendModules {
          specialArgs.k230Kernel = pkgsCross.linuxPackagesFor (import ./nix/kernel-mainline-uart-progress-breadcrumbs.nix {
            kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
              inherit (pkgsCross) buildLinux;
            };
            inherit (pkgsCross) applyPatches lib;
          });
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
        inherit omawrite;
        # Opt-in Qt Quick software/Wayland evaluation client, never in the image.
        qtquick-software-probe = pkgsCross.callPackage ./nix/qtquick-software-probe/default.nix { };
        # Standalone pinned helper package; no theme service enters the normal
        # image until generation/rollback and physical gates pass.
        omarchy-theme-tools = pkgsCross.callPackage ./nix/omarchy-theme-tools { };
        handheld-theme-default = pkgsCross.callPackage ./nix/handheld-theme-default { };
        handheld-theme-icons = pkgsCross.callPackage ./nix/handheld-theme-icons { };
        handheld-settings = pkgsCross.callPackage ./nix/handheld-settings.nix { };
        wifi-settings-broker = pkgsCross.callPackage ./nix/wifi-settings-broker.nix { };
        handheld-notifications = self.nixosConfigurations.k230.pkgs.callPackage ./nix/handheld-notifications.nix { };
        handheld-shell-rust-probe = pkgsCross.callPackage ./nix/rust-shell-probe { };
        # Opt-in Rust software shell; the probe remains a separate artifact.
        handheld-shell-rust = pkgsCross.callPackage ./nix/rust-shell-client { };
        # Prototype: re-emits the touchscreen as a virtual touchpad while
        # HDMI is the active output (openspec/changes/
        # the-touchscreen-becomes-an-hdmi-trackpad/). Not wired into any
        # NixOS configuration by default; see nix/touch-trackpad-service.nix.
        handheld-touch-trackpad = pkgsCross.callPackage ./nix/touch-trackpad { };
        power-keyd = pkgsCross.callPackage ./nix/power-keyd.nix { };
        # Bounded diagnostic sampler, outside the normal image closure.
        runtime-perf = pkgsCross.callPackage ./nix/runtime-perf.nix { };
        # Opt-in command only; no normal service/default selection until the
        # shared theme consumers and physical rollback trial pass.
        handheld-theme-command = pkgsCross.callPackage ./nix/handheld-theme-command.nix {
          omarchyThemeTools = self.packages.${buildSystem}.omarchy-theme-tools;
          themeDefault = self.packages.${buildSystem}.handheld-theme-default;
          rustShellTool = self.packages.${buildSystem}.handheld-shell-rust;
        };
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
        # Read-only DRM WAIT_VBLANK sampler for
        # the-card-deck-still-misses-its-frame-budget. Never in the normal
        # image closure; pushed to a running board with tools/push-file.py.
        panel-refresh-probe = pkgsCross.callPackage ./nix/panel-refresh-probe.nix { };
        # The card trial must use the same overlaid Pixman graph as the normal
        # board compositor; build it from that package set, not pkgsCross.
        card-shell = self.nixosConfigurations.k230.pkgs.callPackage ./nix/card-shell.nix {
          swayUnwrapped = self.nixosConfigurations.k230.pkgs.sway-unwrapped;
        };
        # Historical diagnostic output name retained for trial scripts. The
        # actual candidate now uses the fully rebuilt normal board graph.
        card-shell-rvv = self.packages.${buildSystem}.card-shell;
        # Opt-in software quarter-turn candidate. Runtime enablement requires
        # WLR_PIXMAN_QUARTER_TURN=1 or WLR_PIXMAN_OUTPUT_TURN=1; the normal
        # image stays on the baseline.
        card-shell-hdmi-trial = self.nixosConfigurations.k230.pkgs.callPackage ./nix/card-shell.nix {
          swayUnwrapped = self.nixosConfigurations.k230.pkgs.sway-unwrapped;
          quarterTurnTrial = true;
        };
        pixman-quarter-turn-probe = self.nixosConfigurations.k230.pkgs.callPackage ./nix/pixman-quarter-turn-probe.nix { };
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

        # openspec/changes/the-mainline-shell-reaches-parity task 6.1: the
        # same out-of-tree source (nix/k230-wifi-driver.nix is already
        # parameterized by `kernel`, not vendor-specific), built against the
        # mainline DRM kernel (CFG80211=m). Every mainline kernel carries
        # nix/patches/mainline/k230-sdhci-clocks.patch, so &mmc_sd0 owns all
        # five SD0 gates (override in nix/dts/k230-tdisplay-mainline.dts).
        #
        # Built 2026-10-06 against the CFG80211=m DRM kernel (see
        # docs/evidence/mainline-wifi-port/): the 7.3 port patch (API drift
        # plus the cfg80211_ops signature port) compiles and passes modpost.
        # k230-mainline-drm-shell loads the same module; binding on the
        # board is a separate physical check.
        k230-wifi-driver-mainline = pkgsCross.callPackage ./nix/k230-wifi-driver.nix {
          kernel = self.packages.${buildSystem}.kernelMainlineDrm;
          extraPatches = [ ./nix/patches/mainline/rtl8189fs-mainline-v7.3-rc5.patch ];
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

        # openspec/changes/the-board-runs-a-mainline-kernel: a parallel,
        # opt-in mainline kernel/DTB/boot-files set. NOT referenced by
        # `kernel`, `deviceTree`, `sdImage`, or any nixosConfigurations
        # output above -- the shipped image is unaffected by these existing.
        #   nix build .#kernelMainline
        #   nix build --impure .#deviceTreeMainline
        #   nix build .#kernelMainlineBootFiles
        kernelMainline = self.k230MainlineKernel.kernel;
        deviceTreeMainline = pkgs.callPackage ./nix/device-tree-mainline.nix {
          inherit kernelMainlineSrc;
        };
        # A plain directory of the two files a one-shot U-Boot `ext4load`
        # test needs, named clearly (not the vendor blinux flow's fixed
        # `/Image` + `/force.dtb` names, since this is not that flow -- see
        # design.md). Building this performs no board action; it only
        # collects what a board action would need.
        kernelMainlineBootFiles = pkgs.runCommand "k230-mainline-boot-files" { } ''
          mkdir -p $out
          cp ${self.packages.${buildSystem}.kernelMainline}/Image $out/Image-mainline
          cp ${self.packages.${buildSystem}.deviceTreeMainline}/k230-tdisplay-mainline.dtb $out/
        '';
        # display/hdmi's alternate DTB (openspec/changes/
        # plugging-in-hdmi-moves-the-display, task 2.2): the LT9611 bridge
        # on this board's own &i2c3/GPIO23/GPIO24, no RM69A10 panel node.
        # The Goodix touch node stays present and owns its shared reset GPIO.
        # A separate output name, not an override of
        # deviceTree above, so the default panel boot path never depends
        # on this file existing or building.
        #   nix build --impure .#deviceTreeHdmi
        deviceTreeHdmi = pkgs.callPackage ./nix/device-tree.nix {
          inherit kernelSrc;
          dtbName = "k230-tdisplay-hdmi.dtb";
          dtsFile = ./nix/dts/k230-tdisplay-hdmi.dts;
        };

        # openspec/changes/the-board-runs-a-mainline-kernel, milestone 2
        # (display), IN PROGRESS: the Canaan DRM stack + RM69A10 panel,
        # forward-ported onto the mainline pin. A SEPARATE derivation from
        # kernelMainline (per the coordinator's instruction), overriding a
        # freshly-built, UNWRAPPED kernel-mainline.nix result the same way
        # nix/kernel-rvv-trial.nix overrides nix/kernel.nix's.
        #   nix build .#kernelMainlineDrm
        kernelMainlineDrm = pkgsCross.callPackage ./nix/kernel-mainline-drm.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        # Matching opt-in DTB/boot bundle for the display candidate. This
        # bundle only collects Image + DTB for manual U-Boot testing; it has
        # no initrd/rootfs and is not part of any configured system/image.
        deviceTreeMainlineDrm = pkgs.callPackage ./nix/device-tree-mainline-drm.nix {
          inherit kernelMainlineSrc;
        };
        # The LT9611 HDMI variant of the same tree (plugging-in-hdmi-moves-the-
        # display, group 7). Booted instead of the panel DTB; never both.
        deviceTreeMainlineDrmHdmi = pkgs.callPackage ./nix/device-tree-mainline-drm.nix {
          inherit kernelMainlineSrc;
          dtbName = "k230-tdisplay-mainline-drm-hdmi.dtb";
          dtsFile = ./nix/dts/k230-tdisplay-mainline-drm-hdmi.dts;
        };
        kernelMainlineDrmBootFiles = pkgs.runCommand "k230-mainline-drm-boot-files" { } ''
          mkdir -p $out
          cp ${self.packages.${buildSystem}.kernelMainlineDrm}/Image $out/Image-mainline-drm
          cp ${self.packages.${buildSystem}.deviceTreeMainlineDrm}/k230-tdisplay-mainline-drm.dtb $out/
        '';

        # Complete matching trial boot path; the Image+DTB-only bundle above
        # remains available for artifact inspection.
        toplevel-mainline-drm-trial = self.nixosConfigurations.k230-mainline-drm-trial.config.system.build.toplevel;
        # The console mainline system in the guarded system-trial bundle layout.
        kernelMainlineConsoleTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-console.config;
          kernel = self.nixosConfigurations.k230-mainline-console.config.boot.kernelPackages.kernel;
          # The trial layout names its DTB after the DRM profile; the console
          # DTB is presented under that file name, unchanged.
          deviceTree = pkgs.runCommand "k230-mainline-console-dtb-trial-name" { } ''
            mkdir -p $out
            cp ${self.packages.${buildSystem}.deviceTreeMainline}/k230-tdisplay-mainline.dtb $out/k230-tdisplay-mainline-drm.dtb
          '';
        };
        toplevel-mainline-drm-shell = self.nixosConfigurations.k230-mainline-drm-shell.config.system.build.toplevel;
        kernelMainlineDrmShellTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-drm-shell.config;
          kernel = self.nixosConfigurations.k230-mainline-drm-shell.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };
        kernelMainlineDrmTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-drm-trial.config;
          kernel = self.nixosConfigurations.k230-mainline-drm-trial.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };

        kernelMainlineBootTrace = pkgsCross.callPackage ./nix/kernel-mainline-boot-trace.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-boot-trace = self.nixosConfigurations.k230-mainline-boot-trace.config.system.build.toplevel;
        kernelMainlineBootTraceTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-boot-trace.config;
          kernel = self.nixosConfigurations.k230-mainline-boot-trace.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };

        kernelMainlineBootTraceSbi = pkgsCross.callPackage ./nix/kernel-mainline-boot-trace-sbi.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-boot-trace-sbi = self.nixosConfigurations.k230-mainline-boot-trace-sbi.config.system.build.toplevel;
        kernelMainlineBootTraceSbiTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-boot-trace-sbi.config;
          kernel = self.nixosConfigurations.k230-mainline-boot-trace-sbi.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };

        kernelMainlineBootTraceSbiOnly = pkgsCross.callPackage ./nix/kernel-mainline-boot-trace-sbi-only.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-boot-trace-sbi-only = self.nixosConfigurations.k230-mainline-boot-trace-sbi-only.config.system.build.toplevel;
        kernelMainlineBootTraceSbiOnlyTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-boot-trace-sbi-only.config;
          kernel = self.nixosConfigurations.k230-mainline-boot-trace-sbi-only.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };

        kernelMainlineUartProgress = pkgsCross.callPackage ./nix/kernel-mainline-uart-progress.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        kernelMainlineUartProgressObjects = pkgs.callPackage ./nix/kernel-mainline-uart-progress-objects.nix {
          crossCc = pkgsCross.stdenv.cc;
          kernel = self.packages.${buildSystem}.kernelMainlineUartProgress;
          baseKernel = self.packages.${buildSystem}.kernelMainlineBootTraceSbiOnly;
        };

        kernelMainlineUartProgressExactObjects = pkgs.callPackage ./nix/kernel-mainline-uart-progress-exact-objects.nix {
          crossCc = pkgsCross.stdenv.cc;
          kernel = self.packages.${buildSystem}.kernelMainlineUartProgress;
        };

        toplevel-mainline-uart-progress = self.nixosConfigurations.k230-mainline-uart-progress.config.system.build.toplevel;
        kernelMainlineUartProgressTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-uart-progress.config;
          kernel = self.nixosConfigurations.k230-mainline-uart-progress.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };

        kernelMainlineUartProgressMemory = pkgsCross.callPackage ./nix/kernel-mainline-uart-progress-memory.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-uart-progress-memory = self.nixosConfigurations.k230-mainline-uart-progress-memory.config.system.build.toplevel;
        kernelMainlineUartProgressMemoryTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-uart-progress-memory.config;
          kernel = self.nixosConfigurations.k230-mainline-uart-progress-memory.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };
        kernelMainlineUartProgressMemoryExactObjects = pkgs.callPackage ./nix/kernel-mainline-uart-progress-exact-objects.nix {
          crossCc = pkgsCross.stdenv.cc;
          kernel = self.packages.${buildSystem}.kernelMainlineUartProgressMemory;
        };

        kernelMainlineUartProgressMemoryPrintk = pkgsCross.callPackage ./nix/kernel-mainline-uart-progress-memory-printk.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-uart-progress-memory-printk = self.nixosConfigurations.k230-mainline-uart-progress-memory-printk.config.system.build.toplevel;
        kernelMainlineUartProgressMemoryPrintkTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-uart-progress-memory-printk.config;
          kernel = self.nixosConfigurations.k230-mainline-uart-progress-memory-printk.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };
        kernelMainlineUartProgressMemoryPrintkExactObjects = pkgs.callPackage ./nix/kernel-mainline-uart-progress-exact-objects.nix {
          crossCc = pkgsCross.stdenv.cc;
          kernel = self.packages.${buildSystem}.kernelMainlineUartProgressMemoryPrintk;
        };

        kernelMainlineInitExecReturn = pkgsCross.callPackage ./nix/kernel-mainline-init-exec-return.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-init-exec-return = self.nixosConfigurations.k230-mainline-init-exec-return.config.system.build.toplevel;
        kernelMainlineInitExecReturnTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-init-exec-return.config;
          kernel = self.nixosConfigurations.k230-mainline-init-exec-return.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };

        kernelMainlineInitExecTransition = pkgsCross.callPackage ./nix/kernel-mainline-init-exec-transition.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-init-exec-transition = self.nixosConfigurations.k230-mainline-init-exec-transition.config.system.build.toplevel;
        kernelMainlineInitExecTransitionTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-init-exec-transition.config;
          kernel = self.nixosConfigurations.k230-mainline-init-exec-transition.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };

        kernelMainlineUartProgressPostSample = pkgsCross.callPackage ./nix/kernel-mainline-uart-progress-post-sample.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-uart-progress-post-sample = self.nixosConfigurations.k230-mainline-uart-progress-post-sample.config.system.build.toplevel;
        kernelMainlineUartProgressPostSampleTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-uart-progress-post-sample.config;
          kernel = self.nixosConfigurations.k230-mainline-uart-progress-post-sample.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };
        kernelMainlineUartProgressPostSampleExactObjects = pkgs.callPackage ./nix/kernel-mainline-uart-progress-exact-objects.nix {
          crossCc = pkgsCross.stdenv.cc;
          kernel = self.packages.${buildSystem}.kernelMainlineUartProgressPostSample;
        };

        kernelMainlineUartProgressBreadcrumbs = pkgsCross.callPackage ./nix/kernel-mainline-uart-progress-breadcrumbs.nix {
          kernelMainline = pkgsCross.callPackage ./nix/kernel-mainline.nix {
            inherit (pkgsCross) buildLinux;
          };
        };
        toplevel-mainline-uart-progress-breadcrumbs = self.nixosConfigurations.k230-mainline-uart-progress-breadcrumbs.config.system.build.toplevel;
        kernelMainlineUartProgressBreadcrumbsTrialBootFiles = pkgs.callPackage ./nix/mainline-drm-trial.nix {
          cfg = self.nixosConfigurations.k230-mainline-uart-progress-breadcrumbs.config;
          kernel = self.nixosConfigurations.k230-mainline-uart-progress-breadcrumbs.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
        };
        kernelMainlineUartProgressBreadcrumbsExactObjects = pkgs.callPackage ./nix/kernel-mainline-uart-progress-exact-objects.nix {
          crossCc = pkgsCross.stdenv.cc;
          kernel = self.packages.${buildSystem}.kernelMainlineUartProgressBreadcrumbs;
        };

        mainline-uart-observer = pkgsCross.callPackage ./nix/mainline-uart-observer { };
        toplevel-mainline-uart-observer = self.nixosConfigurations.k230-mainline-uart-observer.config.system.build.toplevel;
        kernelMainlineUartObserverBootFiles = let
          cfg = self.nixosConfigurations.k230-mainline-uart-observer.config;
          trial = pkgs.callPackage ./nix/mainline-drm-trial.nix {
            inherit cfg;
            kernel = cfg.boot.kernelPackages.kernel;
            deviceTree = self.packages.${buildSystem}.deviceTreeMainlineDrm;
          };
        in pkgs.callPackage ./nix/mainline-uart-observer/bundle.nix {
          inherit trial;
          baseBundle = self.packages.${buildSystem}.kernelMainlineDrmTrialBootFiles;
          kernel = cfg.boot.kernelPackages.kernel;
          system = cfg.system.build.toplevel;
          helper = self.nixosConfigurations.k230-mainline-uart-observer.pkgs.callPackage ./nix/mainline-uart-observer {
            systemd = cfg.boot.initrd.systemd.package;
          };
        };

        # openspec/changes/the-board-runs-a-mainline-kernel, milestone 1: the
        # full NixOS system variant, cross-built against kernelMainline, and
        # its matching boot files (Image, DTB-with-bootargs, initrd.uimg).
        # NOT referenced by `toplevel`, `sdImage`, or any default output.
        #   nix build .#toplevel-mainline-console
        #   nix build .#kernelMainlineConsoleBootFiles
        toplevel-mainline-console = self.nixosConfigurations.k230-mainline-console.config.system.build.toplevel;
        kernelMainlineConsoleBootFiles = pkgs.callPackage ./nix/kernel-mainline-boot-files.nix {
          cfg = self.nixosConfigurations.k230-mainline-console.config;
          kernel = self.packages.${buildSystem}.kernelMainline;
          deviceTree = self.packages.${buildSystem}.deviceTreeMainline;
        };

        # Stage 1, piece by piece, so each can be built and inspected alone.
        #   nix build .#uboot-k230      u-boot.bin, spl/u-boot-spl.bin
        #   nix build .#opensbi-k230    fw_jump.bin
        #   nix build .#fwJump          fw_jump_add_uboot_head.bin
        #   nix build .#stage1          the five files the card carries
        k230-sdk-src = k230Sdk;
        uboot-k230 = ubootK230;
        # Isolated, default-off SPL diagnostic. Do not substitute this for
        # the normal stage1 package or treat it as an SMP implementation.
        uboot-k230-cpu0-identity-probe = ubootK230Cpu0IdentityProbe;
        # Firmware-header packaging for an explicitly selected SPL trial.
        # This is never referenced by the normal stage1/image package.
        stage1-cpu0-identity-probe = stage1.packagingOf {
          ubootDir = ubootK230Cpu0IdentitySPL;
        };
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
        # The daily system the board runs: the mainline coherent shell, with
        # its 7.3 kernel and the mainline DRM tree under the name stage 1 loads
        # (the same files as kernelMainlineDrmShellBootFiles).
        sdImage = mkBoardImageWith {
          cfg = self.nixosConfigurations.k230-mainline-drm-shell.config;
          kernel = self.nixosConfigurations.k230-mainline-drm-shell.config.boot.kernelPackages.kernel;
          deviceTree = self.packages.${buildSystem}.mainlineDrmDeviceTreeNormalName;
        };
        # Vendor-kernel Rust shell image, kept as a rollback and release target.
        sdImage-coherent = mkBoardImage self.nixosConfigurations.k230-coherent-shell.config
          self.k230Kernel.kernel;
        # Matching normal boot update, independent of whole-card flashing.
        # Host inspection is not physical boot/display qualification.
        coherentShellBootFiles = pkgs.callPackage ./nix/coherent-shell-boot-files.nix {
          cfg = self.nixosConfigurations.k230-coherent-shell.config;
          inherit (self.packages.${buildSystem}) deviceTree;
        };
        # The mainline full coherent shell as a normal (daily) boot bundle:
        # same layout, with the mainline DRM DTB under the name stage 1 loads.
        kernelMainlineDrmShellBootFiles = pkgs.callPackage ./nix/coherent-shell-boot-files.nix {
          cfg = self.nixosConfigurations.k230-mainline-drm-shell.config;
          configuration = "k230-mainline-drm-shell";
          deviceTree = self.packages.${buildSystem}.mainlineDrmDeviceTreeNormalName;
        };
        # The daily mainline bundle with the HDMI DTB under the filename stage 1
        # loads, for a volatile coherent trial boot on a monitor.
        kernelMainlineDrmShellHdmiBootFiles = pkgs.callPackage ./nix/coherent-shell-boot-files.nix {
          cfg = self.nixosConfigurations.k230-mainline-drm-shell.config;
          configuration = "k230-mainline-drm-shell";
          deviceTree = pkgs.runCommand "k230-mainline-drm-hdmi-dtb-normal-name" { } ''
            mkdir -p $out
            cp ${self.packages.${buildSystem}.deviceTreeMainlineDrmHdmi}/k230-tdisplay-mainline-drm-hdmi.dtb $out/k230-tdisplay.dtb
          '';
        };
        mainlineDrmDeviceTreeNormalName = pkgs.runCommand "k230-mainline-drm-dtb-normal-name" { } ''
          mkdir -p $out
          cp ${self.packages.${buildSystem}.deviceTreeMainlineDrm}/k230-tdisplay-mainline-drm.dtb $out/k230-tdisplay.dtb
        '';
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
