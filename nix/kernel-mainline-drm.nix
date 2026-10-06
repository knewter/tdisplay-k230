# Milestone 2 (display), IN PROGRESS: the Canaan DRM stack + RM69A10 panel,
# forward-ported onto the mainline pin.
#
# openspec/changes/the-board-runs-a-mainline-kernel. A SEPARATE derivation
# from nix/kernel-mainline.nix, per the coordinator's explicit instruction
# ("put the DRM port behind its own Kconfig or a separate derivation until
# it compiles") -- `.#kernelMainline` and `nixosConfigurations.
# k230-mainline-console` are completely unaffected by this file; it
# overrides kernel-mainline.nix's own buildLinux call the same way
# nix/kernel-rvv-trial.nix already overrides nix/kernel.nix's.
#
# WHAT THIS FORWARD-PORTS, all from the pinned VENDOR tree
# (ruyisdk/linux-xuantie-kernel @ 7d4e1f444f461dbe3833bd99a4640e7b6c2cd529),
# with every one of this project's own existing patches against these files
# already carried forward -- verified by literally replaying
# nix/kernel.nix's own `patches`/`postPatch` sequence against the raw
# vendor files in a scratch tree, byte for byte (every `grep -q` guard
# passed), before adapting anything to mainline. Not reconstructed from
# memory:
#
#   drivers/gpu/drm/canaan/{canaan_drv,canaan_crtc,canaan_plane,canaan_vo,
#     canaan_dsi,canaan_phy}.{c,h} + canaan_vo_regs.h/canaan_vo_table.h
#   drivers/gpu/drm/panel/panel-canaan-universal.c
#
# carrying forward: the bounded DSI PHY wait, the pm_runtime DISP pin, the
# fbdev 16bpp fix, the DCS-read implementation and its RDDID/RDDPM
# readback caller, the stage-1-splash handoff plumbing, the DT-settable
# hsfreqrange, the DSI-command backlight, the board-findings single-byte
# brightness fix, the DSI-core packet-framing/message-transport rewrite
# (nix/patches/canaan-dsi-message-transport.patch), and -- from
# feat/hdmi-bridge (another agent's worktree, read via `git show
# feat/hdmi-bridge:...`, never written to) -- the DSI bridge-connector
# patch (component-from-attach for an external bridge,
# drm_bridge_connector_init).
#
# ALSO forward-ports the K230-specific register additions from
# feat/hdmi-bridge's nix/patches/lt9611-dsi-port-b.patch onto MAINLINE's
# OWN drivers/gpu/drm/bridge/lontium-lt9611.c, as a full replacement file
# (nix/patches/mainline/drm/lontium-lt9611-k230.c) rather than an in-place
# patch -- checked directly: mainline at this pin already has essentially
# all of that vendor patch's generic single-Port-B scaffolding merged
# independently of us (dsi0_node optional, dsi1_node as primary, optional
# reset/irq, the MODE_PANEL check), so only the K230-specific register
# tables (`k230_port_b_analog_cfg`, `k230_port_b_cfg`) and the
# `lt9611_k230_output_setup()` function needed adding by hand, not the
# vendor patch's full diff.
#
# See docs/research/mainline-kernel-inventory.md's display row and
# openspec/changes/the-board-runs-a-mainline-kernel/tasks.md for the
# authoritative, evidenced build-by-build record.
{ kernelMainline, applyPatches, lib }:
kernelMainline.override (old: {
  buildLinux = args: old.buildLinux (args // {
    src = applyPatches {
      name = "linux-mainline-k230-drm-src";
      src = args.src;
      # Optional DRM restart and five-clock SD consumer; console is unchanged.
      patches = [
        ./patches/mainline/k230-restart.patch
        ./patches/mainline/k230-sdhci-clocks.patch
        ./patches/mainline/k230-clk-spi2axi-critical.patch
      ];

      postPatch = ''
        cp ${./patches/mainline/k230-power-domains.c} drivers/soc/canaan/k230-power-domains.c
        cp ${./patches/mainline/include}/dt-bindings/soc/canaan,k230_pm_domains.h include/dt-bindings/soc/
        cat >> drivers/soc/canaan/Kconfig <<'EOF'

config SOC_K230_PM_DOMAINS
	bool "Canaan Kendryte K230 power domains controller"
	depends on RISCV && ARCH_CANAAN && OF && PM
	select PM_GENERIC_DOMAINS
	help
	  Vendor-derived K230 power controller for the optional DRM trial.
EOF
        echo 'obj-$(CONFIG_SOC_K230_PM_DOMAINS) += k230-power-domains.o' >> drivers/soc/canaan/Makefile
        mkdir -p drivers/gpu/drm/canaan
        cp ${./patches/mainline/drm}/canaan_*.c ${./patches/mainline/drm}/canaan_*.h drivers/gpu/drm/canaan/
        cp ${./patches/mainline/drm/Kconfig} drivers/gpu/drm/canaan/Kconfig
        cp ${./patches/mainline/drm/Makefile} drivers/gpu/drm/canaan/Makefile
        cp ${./patches/mainline/drm/panel-canaan-universal.c} drivers/gpu/drm/panel/panel-canaan-universal.c
        cp ${./patches/mainline/drm/lontium-lt9611-k230.c} drivers/gpu/drm/bridge/lontium-lt9611.c

        grep -q '^source "drivers/gpu/drm/bridge/Kconfig"$' drivers/gpu/drm/Kconfig
        sed -i '/^source "drivers\/gpu\/drm\/bridge\/Kconfig"$/i source "drivers/gpu/drm/canaan/Kconfig"' \
          drivers/gpu/drm/Kconfig
        grep -q 'drivers/gpu/drm/canaan/Kconfig' drivers/gpu/drm/Kconfig
        echo 'obj-$(CONFIG_DRM_CANAAN) += canaan/' >> drivers/gpu/drm/Makefile

        cat >> drivers/gpu/drm/panel/Kconfig <<'EOK'

config DRM_PANEL_CANAAN_UNIVERSAL
	tristate "Canaan universal DSI panel"
	depends on OF
	depends on DRM_MIPI_DSI
	select DRM_KMS_HELPER
	default DRM_CANAAN_DSI
	help
	  DRM driver for the Canaan universal DSI panel (RM69A10) used on
	  K230 boards.
EOK
        echo 'obj-$(CONFIG_DRM_PANEL_CANAAN_UNIVERSAL) += panel-canaan-universal.o' \
          >> drivers/gpu/drm/panel/Makefile
      '';
    };

    structuredExtraConfig = (args.structuredExtraConfig or { }) // (with lib.kernel; {
      PM = yes;
      PM_GENERIC_DOMAINS = yes;
      PM_GENERIC_DOMAINS_OF = yes;
      SOC_K230_PM_DOMAINS = yes;
      DRM_CANAAN = yes;
      DRM_CANAAN_DSI = yes;
      DRM_PANEL_CANAAN_UNIVERSAL = yes;
      DRM_FBDEV_EMULATION = yes;
      DRM_CLIENT_SETUP = yes;
      # The display DTB carries the board's GT9895/GT9916-compatible
      # controller on mainline's DesignWare I2C driver.
      INPUT_TOUCHSCREEN = yes;
      TOUCHSCREEN_GOODIX_BERLIN_I2C = yes;
      # For the LT9611 HDMI bridge path (canaan-dsi-bridge-connector.patch):
      # already-mainline, generic, I2C-attached bridge driver.
      DRM_LONTIUM_LT9611 = yes;
    });
  });
})
