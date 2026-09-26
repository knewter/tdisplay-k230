# The kernel for the T-Display-K230.
#
# Mainline cannot boot this SoC. Linux 6.18 carries pinctrl-k230.c and
# reset-k230.c but ships no K230 device tree -- arch/riscv/boot/dts/canaan/
# is K210-only -- and Kconfig.socs has no SOC_CANAAN_K230, only
# SOC_CANAAN_K210, itself `depends on !MMU`. See
# docs/evidence/why-xuantie-kernel.txt.
#
# So we take the tree Canaan's own Linux SDK pins, and build it from source
# rather than vendoring a kernel binary.
{ lib, buildLinux, fetchFromGitHub, applyPatches, ... }@args:

let
  # The pin itself lives in nix/kernel-src.nix, because nix/device-tree.nix
  # needs the same tree for its headers and the two must not drift.
  kernelSrc = import ./kernel-src.nix { inherit fetchFromGitHub; };
in
buildLinux (args // {
  version = "6.6.36-xuantie";
  modDirVersion = "6.6.36";

  # arch/riscv/boot/dts/canaan/Makefile lists k230-canmv, k230d-canmv and
  # k230-evb but NOT the v3 board, even though k230-canmv-v3.dts and
  # k230-canmv-v3-lcd.dts are both in the tree. Canaan's buildroot sidesteps
  # that by naming DTBs explicitly in BR2_LINUX_KERNEL_INTREE_DTS_NAME, so
  # `make dtbs` alone never produces them.
  #
  # Patched into the SOURCE, not via postPatch: buildLinux does not forward
  # postPatch to the kernel derivation, so setting it there is a silent
  # no-op -- the build returns the same store path and the DTB is still
  # missing. Found by the derivation hash not changing.
  src = applyPatches {
    name = "linux-xuantie-k230-src";
    src = kernelSrc;

    # A real patch file, not a sed, because this replaces a whole function
    # body. canaan_dsi_dcs_read() ships as "// TODO; return 1", so the panel
    # cannot be asked anything -- and six hypotheses about why the screen
    # stays dark have now died for want of exactly that. Reading DCS 0x04
    # (RDDID) or 0x0A (RDDPM) separates "the panel never receives the init
    # sequence" from "it receives it, acknowledges it, and still does not
    # light". See docs/evidence/dsi-phy-hang.md.
    patches = [
      # The vendor Kconfig V probe omits M despite the target ABI needing it;
      # use the correction physically tested in the isolated vector kernel.
      ../nix/patches/riscv-vector-toolchain-probe.patch
      ../nix/patches/canaan-dsi-implement-dcs-read.patch
      # Implementing the read is useless on its own -- nothing in the
      # panel driver ever issues one. This adds the caller: read RDDID
      # (0x04) and RDDPM (0x0A) right after the init sequence, and log
      # both. RDDPM bit 4 is sleep-out and bit 2 is display-on, which is
      # precisely what the 0x11 and 0x29 at the tail of the sequence are
      # supposed to have set. Diagnostic only; failures are logged, never
      # fatal to prepare().
      ../nix/patches/canaan-panel-read-back-id-and-power-mode.patch
      # canaan-drm-defer-reg-load-to-vblank.patch is deliberately NOT applied:
      # it left the bottom-band flicker unchanged (sway max_render_time 8
      # fixed it) and a kernel carrying it panicked at boot in
      # __insert_inode_hash right after canaan-drm bound. See
      # docs/evidence/card-shell/bottom-band-flicker/kernel-patch-boot-panic.md.
    ];

    postPatch = ''
      # Seed dependencies before oldconfig traverses NFT_COMPAT/NFT_CT.
      # Their prerequisites occur later in Kconfig; answering new prompts
      # against the vendor's modular prerequisites otherwise loops forever.
      cat ${./kernel-firewall.config} >> arch/riscv/configs/k230_defconfig
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3.dtb' >> arch/riscv/boot/dts/canaan/Makefile
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3-lcd.dtb' >> arch/riscv/boot/dts/canaan/Makefile

      # NOT our board's device tree. nix/dts/k230-tdisplay.dts and
      # nix/dts/display-rm69a10-568x1232.dtsi used to be copied in here and
      # added to that Makefile, which put them in the kernel's `src` -- so a
      # one-byte edit to panel-init-sequence invalidated the whole kernel
      # and cost a ~20 minute cross-compile. They are compiled in their own
      # derivation now (nix/device-tree.nix) and the image takes the DTB
      # from there; the output is byte-identical. Nothing in this kernel
      # depends on them any more, which is the entire point -- do not add
      # them back.

      # goodix_berlin, backported from v6.12. The pinned 6.6 tree has only
      # the older GT9xx goodix.c. See docs/evidence/gt9895-touch.md -- note
      # this driver does NOT match the GT9895 upstream, so whether it can
      # drive this panel's controller is an open experiment.
      cp ${../nix/patches/goodix-berlin}/goodix_berlin*.{c,h} \
         drivers/input/touchscreen/
      # 6.12 moved asm/unaligned.h to linux/unaligned.h; 6.6 predates that.
      sed -i 's|#include <linux/unaligned.h>|#include <asm/unaligned.h>|' \
        drivers/input/touchscreen/goodix_berlin_core.c \
        drivers/input/touchscreen/goodix_berlin_i2c.c \
        drivers/input/touchscreen/goodix_berlin_spi.c
      cat >> drivers/input/touchscreen/Kconfig <<'EOK'

config TOUCHSCREEN_GOODIX_BERLIN_CORE
	tristate
	select REGMAP

config TOUCHSCREEN_GOODIX_BERLIN_I2C
	tristate "Goodix Berlin I2C touchscreen"
	depends on I2C
	select REGMAP_I2C
	select TOUCHSCREEN_GOODIX_BERLIN_CORE
	help
	  Backported from v6.12 for the T-Display-K230's GT9895.
EOK
      cat >> drivers/input/touchscreen/Makefile <<'EOM'
obj-$(CONFIG_TOUCHSCREEN_GOODIX_BERLIN_CORE) += goodix_berlin_core.o
obj-$(CONFIG_TOUCHSCREEN_GOODIX_BERLIN_I2C)  += goodix_berlin_i2c.o
EOM

      # fbdev emulation asks canaan-drm for 32 bpp, which means XRGB8888.
      # The driver's RGB planes advertise AR24 AR12 AR15 RG24 RG16 BG24 and
      # NOT XR24, so the format negotiation fails and there is no /dev/fb0:
      #
      #   [drm] bpp/depth value of 32/24 not supported
      #   [drm] No compatible format found
      #   [drm] *ERROR* fbdev: Failed to setup generic emulation (ret=-22)
      #
      # Observed on hardware -- docs/evidence/panel-probe.txt. 16 bpp maps to
      # RGB565, which those planes do advertise. This costs colour depth on
      # the fbdev console only; DRM clients still negotiate AR24 for
      # themselves and are unaffected.
      sed -i 's|drm_fbdev_generic_setup(drm_dev, 32);|drm_fbdev_generic_setup(drm_dev, 16);|' \
        drivers/gpu/drm/canaan/canaan_drv.c
      grep -q 'drm_fbdev_generic_setup(drm_dev, 16);' drivers/gpu/drm/canaan/canaan_drv.c

      # Instrument the panel bring-up path.
      #
      # The panel probes and a modeset succeeds, but the glass stays dark and
      # the DCS init sequence appears never to be written -- inferred from the
      # ABSENCE of log lines, which is weak evidence. This one line turns
      # that into a positive statement either way on the next boot, so a
      # wrong hypothesis costs a boot rather than a card swap and a rebuild.
      # See docs/evidence/panel-dark.md. Remove once the panel is up.
      sed -i 's|\tif (p->init_set_v1_flag) {|\tdev_info(panel->dev, "canaan_panel_prepare: entered, init_set_v1_flag=%u\\n", p->init_set_v1_flag);\n\tif (p->init_set_v1_flag) {|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'canaan_panel_prepare: entered' drivers/gpu/drm/panel/panel-canaan-universal.c

      # Reset the panel immediately before the init sequence.
      #
      # canaan_panel_prepare() has the vendor's own reset pulses commented
      # out, so the only reset happens in probe, seconds earlier. RT-Smart
      # drives three resets on GPIO22 immediately before it writes the init
      # sequence -- docs/evidence/rm69a10-init-sequence.md, taken from the
      # shipped firmware's boot log. With the reset that far away the panel
      # does not answer, and once fbdev started actually performing a modeset
      # the DCS write blocked forever: "soft lockup - CPU#0 stuck for 130s!".
      # See docs/evidence/panel-dark.md.
      sed -i 's|\tif (p->init_set_v1_flag) {|\tif (p->reset) {\n\t\tret = gpiod_direction_output(p->reset, 1);\n\t\tif (ret) {\n\t\t\tdev_err(panel->dev, "failed to set panel reset output: %d\\n", ret);\n\t\t\treturn ret;\n\t\t}\n\t\tgpiod_set_value_cansleep(p->reset, 1);\n\t\tpanel_simple_sleep(20);\n\t\tgpiod_set_value_cansleep(p->reset, 0);\n\t\tpanel_simple_sleep(20);\n\t\tgpiod_set_value_cansleep(p->reset, 1);\n\t\tpanel_simple_sleep(120);\n\t}\n\n\tif (p->init_set_v1_flag) {|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'panel_simple_sleep(120);' drivers/gpu/drm/panel/panel-canaan-universal.c

      # Preserve a panel that this boot's stage 1 successfully initialized.
      #
      # U-Boot writes the empty boolean canaan,stage1-splash in /chosen only
      # after it has loaded logo.xrgb and completed the RM69A10 init path.
      # This is deliberately read at runtime: absent or failed stage 1 means
      # the ordinary probe/reset/init/fbdev path stays intact.  Do not turn it
      # into a static board-DT property.
      #
      # The reset GPIO needs GPIOD_ASIS in that successful-stage-1 case. The
      # vendor's GPIOD_OUT_LOW request immediately drives GPIO22 and would
      # extinguish the image before prepare() can decide to preserve it.
      sed -i 's|#include <linux/of_device.h>|#include <linux/of_device.h>\n#include <linux/of.h>|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q '#include <linux/of.h>' drivers/gpu/drm/panel/panel-canaan-universal.c
      sed -i 's|\tu32 init_set_v1_flag;|\tu32 init_set_v1_flag;\n\tbool stage1_splash;|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'bool stage1_splash;' drivers/gpu/drm/panel/panel-canaan-universal.c
      sed -i 's|\tctx->reset = devm_gpiod_get(&dsi->dev, "dsi_reset", GPIOD_OUT_LOW);|\tctx->stage1_splash = of_property_read_bool(of_chosen, "canaan,stage1-splash");\n\n\tctx->reset = devm_gpiod_get(\&dsi->dev, "dsi_reset",\n\t\t\t\t    ctx->stage1_splash ? GPIOD_ASIS : GPIOD_OUT_LOW);|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'ctx->stage1_splash = of_property_read_bool(of_chosen, "canaan,stage1-splash");' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      sed -i '/ctx->reset = devm_gpiod_get/,/ctx->power_on =/ s|^\t} else {$|\t} else if (!ctx->stage1_splash) {|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'else if (!ctx->stage1_splash)' drivers/gpu/drm/panel/panel-canaan-universal.c
      sed -i '/static int canaan_panel_prepare/,/\/\/ set power on/ s|\tstruct canaan_panel \*p = panel_to_canaan_panel(panel);|\tstruct canaan_panel *p = panel_to_canaan_panel(panel);\n\tint ret;\n\n\tif (p->stage1_splash) {\n\t\tdev_info(panel->dev, "canaan_panel_prepare: left as stage 1 set it\\n");\n\t\tp->stage1_splash = false;\n\t\treturn 0;\n\t}|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'canaan_panel_prepare: left as stage 1 set it' \
        drivers/gpu/drm/panel/panel-canaan-universal.c

      # fbdev's initial hotplug/modeset allocates a zeroed buffer and would
      # overwrite the preserved U-Boot scanout. This is also keyed only to
      # this boot's /chosen flag; a boot without it still creates fb0.
      sed -i 's|#include <linux/of_graph.h>|#include <linux/of_graph.h>\n#include <linux/of.h>|' \
        drivers/gpu/drm/canaan/canaan_drv.c
      grep -q '#include <linux/of.h>' drivers/gpu/drm/canaan/canaan_drv.c
      sed -i 's|\tdrm_fbdev_generic_setup(drm_dev, 16);|\tif (of_property_read_bool(of_chosen, "canaan,stage1-splash"))\n\t\tDRM_DEV_INFO(dev, "stage 1 splash: leaving fbdev unset\\n");\n\telse\n\t\tdrm_fbdev_generic_setup(drm_dev, 16);|' \
        drivers/gpu/drm/canaan/canaan_drv.c
      grep -q 'stage 1 splash: leaving fbdev unset' drivers/gpu/drm/canaan/canaan_drv.c


      # Preserve U-Boot's already-running VO/DSI through exactly the first
      # matching DRM modeset.  The stage-1 flag is only a claim that U-Boot
      # initialized this boot; both drivers independently require the exact
      # RM69A10 timing before trusting its live hardware state.  A mismatch,
      # a disable before the first enable, or every later enable follows the
      # ordinary vendor initialization path.
      #
      # This does not adopt a framebuffer: the same atomic commit still runs
      # the Linux OSD plane update and register load.  It only avoids the
      # preceding VO/DSI reprogramming that disturbed the physical panel in
      # the retained-logo trial.  Keep the narrowly-scoped fallback visible.
      sed -i 's|#include <linux/of_graph.h>|#include <linux/of_graph.h>\n#include <linux/of.h>|' \
        drivers/gpu/drm/canaan/canaan_vo.c
      grep -q '#include <linux/of.h>' drivers/gpu/drm/canaan/canaan_vo.c
      sed -i 's|#include <linux/of_address.h>|#include <linux/of_address.h>\n#include <linux/of.h>|' \
        drivers/gpu/drm/canaan/canaan_dsi.c
      grep -q '#include <linux/of.h>' drivers/gpu/drm/canaan/canaan_dsi.c
      sed -i 's|#include <video/videomode.h>|#include <video/videomode.h>\n\n#include "../canaan/canaan_dsi.h"|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'canaan_dsi.h' drivers/gpu/drm/panel/panel-canaan-universal.c

      sed -i 's|\tatomic_t vsync_enabled;|\tatomic_t vsync_enabled;\n\tbool stage1_handoff_pending;|' \
        drivers/gpu/drm/canaan/canaan_vo.h
      grep -q 'bool stage1_handoff_pending;' drivers/gpu/drm/canaan/canaan_vo.h
      sed -i 's|\tu32 clk_freq;|\tu32 clk_freq;\n\tbool stage1_handoff_pending;\n\tbool stage1_handoff_active;|' \
        drivers/gpu/drm/canaan/canaan_dsi.h
      grep -q 'bool stage1_handoff_active;' drivers/gpu/drm/canaan/canaan_dsi.h
      sed -i 's|^void k230_dsi_config_4lan_phy|static inline bool canaan_dsi_stage1_handoff_active(struct mipi_dsi_device *device)\n{\n\treturn device \&\& device->host \&\&\n\t\thost_to_canaan_dsi(device->host)->stage1_handoff_active;\n}\n\nvoid k230_dsi_config_4lan_phy|' \
        drivers/gpu/drm/canaan/canaan_dsi.h
      grep -q 'canaan_dsi_stage1_handoff_active' drivers/gpu/drm/canaan/canaan_dsi.h

      sed -i 's|\tvo->drm_dev = drm_dev;|\tvo->drm_dev = drm_dev;\n\tvo->stage1_handoff_pending =\n\t\tof_property_read_bool(of_chosen, "canaan,stage1-splash");|' \
        drivers/gpu/drm/canaan/canaan_vo.c
      grep -q 'vo->stage1_handoff_pending =' drivers/gpu/drm/canaan/canaan_vo.c
      sed -i 's|^void canaan_vo_enable_crtc(struct canaan_vo \*vo,|static bool canaan_stage1_mode_matches(const struct drm_display_mode *mode)\n{\n\treturn mode->clock == 49500 \&\&\n\t\tmode->hdisplay == 568 \&\& mode->hsync_start == 668 \&\&\n\t\tmode->hsync_end == 708 \&\& mode->htotal == 748 \&\&\n\t\tmode->vdisplay == 1232 \&\& mode->vsync_start == 1236 \&\&\n\t\tmode->vsync_end == 1252 \&\& mode->vtotal == 1268;\n}\n\nstatic void canaan_vo_set_stage1_vblank_timing(struct canaan_vo *vo,\n\t\t\t\t\t const struct drm_display_mode *mode)\n{\n\tu32 irq_line = 32 - __builtin_clz(mode->vtotal) - 1;\n\n\t/* Match canaan_vo_set_timing() without changing visual registers. */\n\tcanaan_vo_write(vo, VO_DISP_IRQ1_CTL, irq_line);\n}\n\nvoid canaan_vo_enable_crtc(struct canaan_vo *vo,|' \
        drivers/gpu/drm/canaan/canaan_vo.c
      grep -q 'canaan_vo_set_stage1_vblank_timing' drivers/gpu/drm/canaan/canaan_vo.c
      sed -i '/^void canaan_vo_enable_crtc/,/canaan_vo_init(vo);/ s|\tcanaan_vo_init(vo);|\tif (vo->stage1_handoff_pending) {\n\t\tvo->stage1_handoff_pending = false;\n\t\tif (canaan_stage1_mode_matches(adjusted_mode)) {\n\t\t\tcanaan_vo_set_stage1_vblank_timing(vo, adjusted_mode);\n\t\t\tdev_info(vo->dev, "stage 1 splash: preserving VO to first plane update\\n");\n\t\t\treturn;\n\t\t}\n\t\tdev_warn(vo->dev, "stage 1 splash: VO mode differs; reinitializing\\n");\n\t}\n\n\tcanaan_vo_init(vo);|' \
        drivers/gpu/drm/canaan/canaan_vo.c
      grep -q 'preserving VO to first plane update' drivers/gpu/drm/canaan/canaan_vo.c
      sed -i '/^void canaan_vo_disable_crtc/,/\tvoid \*rst;/ s|\tvoid \*rst;|\tvoid *rst;\n\n\tif (vo->stage1_handoff_pending) {\n\t\tdev_info(vo->dev, "stage 1 splash: VO disabled before handoff; reinitializing later\\n");\n\t\tvo->stage1_handoff_pending = false;\n\t}|' \
        drivers/gpu/drm/canaan/canaan_vo.c
      grep -q 'VO disabled before handoff' drivers/gpu/drm/canaan/canaan_vo.c

      sed -i 's|\tdsi->host.dev = dev;|\tdsi->host.dev = dev;\n\tdsi->stage1_handoff_pending =\n\t\tof_property_read_bool(of_chosen, "canaan,stage1-splash");|' \
        drivers/gpu/drm/canaan/canaan_dsi.c
      grep -q 'dsi->stage1_handoff_pending =' drivers/gpu/drm/canaan/canaan_dsi.c
      sed -i 's|^static void canaan_dsi_encoder_enable(struct drm_encoder \*encoder)|static bool canaan_dsi_stage1_mode_matches(const struct drm_display_mode *mode)\n{\n\treturn mode->clock == 49500 \&\&\n\t\tmode->hdisplay == 568 \&\& mode->hsync_start == 668 \&\&\n\t\tmode->hsync_end == 708 \&\& mode->htotal == 748 \&\&\n\t\tmode->vdisplay == 1232 \&\& mode->vsync_start == 1236 \&\&\n\t\tmode->vsync_end == 1252 \&\& mode->vtotal == 1268;\n}\n\nstatic void canaan_dsi_encoder_enable(struct drm_encoder *encoder)|' \
        drivers/gpu/drm/canaan/canaan_dsi.c
      grep -q 'canaan_dsi_stage1_mode_matches' drivers/gpu/drm/canaan/canaan_dsi.c
      sed -i '/^static void canaan_dsi_encoder_enable/,/if (canaan_dsi_clk_cfg/ s|\tif (canaan_dsi_clk_cfg(dsi, adjusted_mode->clock))|\tif (dsi->stage1_handoff_pending) {\n\t\tdsi->stage1_handoff_pending = false;\n\t\tdsi->stage1_handoff_active = canaan_dsi_stage1_mode_matches(adjusted_mode);\n\t\tif (dsi->stage1_handoff_active) {\n\t\t\tif (dsi->panel)\n\t\t\t\tdrm_panel_prepare(dsi->panel);\n\t\t\tif (dsi->panel)\n\t\t\t\tdrm_panel_enable(dsi->panel);\n\t\t\tdev_info(dsi->dev, "stage 1 splash: preserving DSI to first plane update\\n");\n\t\t\treturn;\n\t\t}\n\t\tdev_warn(dsi->dev, "stage 1 splash: DSI mode differs; reinitializing\\n");\n\t}\n\n\tif (canaan_dsi_clk_cfg(dsi, adjusted_mode->clock))|' \
        drivers/gpu/drm/canaan/canaan_dsi.c
      grep -q 'preserving DSI to first plane update' drivers/gpu/drm/canaan/canaan_dsi.c
      sed -i '/^static void canaan_dsi_encoder_disable/,/DRM_DEBUG_DRIVER/ s|\tDRM_DEBUG_DRIVER|\tif (dsi->stage1_handoff_pending) {\n\t\tdev_info(dsi->dev, "stage 1 splash: DSI disabled before handoff; reinitializing later\\n");\n\t\tdsi->stage1_handoff_pending = false;\n\t}\n\tdsi->stage1_handoff_active = false;\n\n\tDRM_DEBUG_DRIVER|' \
        drivers/gpu/drm/canaan/canaan_dsi.c
      grep -q 'DSI disabled before handoff' drivers/gpu/drm/canaan/canaan_dsi.c

      # A mismatched first mode must not leave the panel's own one-shot
      # preservation bit set: it receives the normal reset and DCS sequence.
      # An early disable also consumes it, so the next enable is normal.
      sed -i '/static int canaan_panel_prepare/,/\/\/ set power on/ s|\tif (p->stage1_splash) {|\tif (p->stage1_splash \&\&\n\t    canaan_dsi_stage1_handoff_active(p->dsi)) {|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'canaan_dsi_stage1_handoff_active(p->dsi)' drivers/gpu/drm/panel/panel-canaan-universal.c
      sed -i '/static int canaan_panel_prepare/,/\/\*$/ s|^\t/\*$|\tif (p->stage1_splash) {\n\t\tdev_warn(panel->dev, "stage 1 splash: mode mismatch; reinitializing panel\\n");\n\t\tp->stage1_splash = false;\n\t}\n\n\t/*|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'mode mismatch; reinitializing panel' drivers/gpu/drm/panel/panel-canaan-universal.c
      sed -i '/static int canaan_panel_unprepare/,/if (p->power_on)/ s|\tif (p->power_on)|\tif (p->stage1_splash) {\n\t\tdev_info(panel->dev, "stage 1 splash: panel disabled before handoff; reinitializing later\\n");\n\t\tp->stage1_splash = false;\n\t}\n\n\tif (p->power_on)|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'panel disabled before handoff' drivers/gpu/drm/panel/panel-canaan-universal.c

      # Bound the thermal sensor read loop.
      #
      # canaan_get_temp() busy-polls TS_DATA in "while (1)" with no timeout,
      # no iteration cap and no sleep, breaking only when (val >> 12) is
      # non-zero. If the sensor does not produce that, the loop spins in
      # kernel context forever. Thermal zone reads run from a workqueue, so
      # the symptom is exactly what the board does: "BUG: soft lockup -
      # CPU#0 stuck for 22s! [kworker/0:5:45]", starting the moment udev
      # begins coldplugging devices, with no call trace because the CPU
      # never gets to print one. See docs/thermal.md, which flagged this
      # loop before it was observed to bite.
      #
      # Cap it at 10000 iterations and sleep between reads so the loop is
      # both bounded and schedulable. A failed read now reports 0 rather
      # than hanging the machine -- and 0 is no less meaningful than the
      # raw ADC code this driver reports on success, since it does no
      # conversion to millidegrees at all.
      sed -i 's|\tu32 val = 0;|\tu32 val = 0;\n\tint tries = 0;\n\n\t*temp = 0;|' \
        drivers/thermal/canaan_thermal.c
      sed -i 's|\twhile (1) {|\twhile (tries++ < 10000) {|' drivers/thermal/canaan_thermal.c
      sed -i 's|\t\t// msleep(2600);|\t\tusleep_range(100, 200);|' drivers/thermal/canaan_thermal.c
      grep -q 'tries++ < 10000' drivers/thermal/canaan_thermal.c
      grep -q 'usleep_range(100, 200);' drivers/thermal/canaan_thermal.c

      # Bound the DSI PHY ready spin, and say what the PHY actually reports.
      #
      # THIS is the hang. canaan_phy.c waits for the D-PHY to report ready
      # with two bare infinite loops whose body is a single semicolon:
      #
      #     while (readl(dsi->base + PHY_STATUS) != 0x1fbd)
      #             ;
      #
      # No timeout, no sleep, no iteration cap -- note the vendor DID bound
      # the PHY_TST_CTRL1 loop just above these with "count >= 1000; break",
      # so the omission looks accidental. On this board PHY_STATUS never
      # reaches 0x1fbd and the CPU spins in kernel context forever:
      #
      #   watchdog: BUG: soft lockup - CPU#0 stuck for 26s! [kworker/0:5:44]
      #   Workqueue: events output_poll_execute
      #   epc : k230_dsi_config_4lan_phy+0x562/0x620
      #   [<..>] canaan_dsi_encoder_enable+0x216/0x532
      #   [<..>] drm_atomic_helper_commit_modeset_enables+0x194/0x1b4
      #
      # That also explains the dark panel: encoder_enable never returns, so
      # drm_panel_prepare() is never reached and the DCS init sequence is
      # never written. Captured with softlockup_panic=1, because the plain
      # soft-lockup path deadlocks before it can print a trace.
      #
      # 0x1fbd is very likely an all-four-lanes-ready encoding --
      # canaan_dsi.c calls k230_dsi_config_4lan_phy() unconditionally and
      # only sets the real lane count afterwards -- and this panel is
      # 2-lane. Bounding the wait turns an unkillable hang into a logged
      # value, which is the evidence needed to decide the real fix.
      sed -i 's|^\twhile (readl(dsi->base + PHY_STATUS) != 0x1fbd)$|\t{ int _w = 0; u32 _s = 0; while ((_s = readl(dsi->base + PHY_STATUS)) != 0x1fbd \&\& _w++ < 2000) usleep_range(100, 200); if (_s != 0x1fbd) dev_err(dsi->dev, "PHY_STATUS 0x%x != 0x1fbd after %d tries, continuing\\n", _s, _w); }|' \
        drivers/gpu/drm/canaan/canaan_phy.c
      test "$(grep -c 'PHY_STATUS 0x%x != 0x1fbd' drivers/gpu/drm/canaan/canaan_phy.c)" = 2

      # Take a runtime-PM reference on the display block at probe.
      #
      # With the PHY wait bounded the boot survives, and shows the real
      # problem: the whole 0x90850000 region reads back all-ones and every
      # DCS write times out.
      #
      #   PHY_STATUS 0xffffffff != 0x1fbd after 2001 tries, continuing
      #   failed to get available write payload FIFO
      #   canaan-panel-dsi 90850000.dsi.0: failed to write dcs cmd: -110
      #
      # All-ones reads with write timeouts is an unpowered block. The SoC
      # has K230_PM_DOMAIN_DISP and k230.dtsi assigns it to the
      # canaan,display-subsystem node, so the domain exists and is wired up.
      #
      # What is missing is a reference. canaan_drv.c calls
      # pm_runtime_enable() at probe but pm_runtime_get_sync() only in
      # canaan_drm_open(), i.e. when userspace opens /dev/dri/card0. The
      # modeset that has to work here comes from the in-kernel fbdev helper
      # (drm_fb_helper_hotplug_event, see dsi-phy-hang.md), which never goes
      # through drm_open -- so nothing holds the domain up at the moment the
      # display pipeline is actually driven.
      #
      # Take the reference at probe and never drop it, pinning DISP on.
      #
      # SOURCE PROVENANCE, learned the hard way: check this against the
      # pristine tree nix unpacks, NOT the vendor SDK's built copy under
      # k230_linux_sdk/output/*/build/linux-*/. They differ -- the SDK's built tree has these pm_runtime
      # calls commented out, and a patch written against that copy matched
      # nothing and failed its guard. Every other patch here was compared
      # against both trees and is identical in each.
      #
      # A hypothesis with a cheap test attached, not an established fix: if
      # the block still reads 0xffffffff with the domain pinned, the cause
      # lies elsewhere.
      sed -i 's|^\tpm_runtime_enable(disp_dev);$|\tpm_runtime_enable(disp_dev);\n\tpm_runtime_get_sync(disp_dev); /* pin DISP on; see kernel-patches.md */|' \
        drivers/gpu/drm/canaan/canaan_drv.c
      grep -q 'pm_runtime_get_sync(disp_dev); /\* pin DISP on' drivers/gpu/drm/canaan/canaan_drv.c

      # NOT DONE: burst headroom on the DSI link.
      #
      # canaan_dsi_clk_cfg() derives the PHY bit clock as exactly
      #   pclk * 3 * 8 / lanes / 2
      # i.e. precisely the pixel bandwidth, with ZERO slack, and
      # VID_MODE_CFG is hardcoded 0xbf02, whose bits[1:0] select burst.
      # A burst link is supposed to run faster than the pixel rate and
      # idle in the blanking, so multiplying that expression by 5/4 to
      # buy 25% headroom looks obviously right.
      #
      # It is not. It blanks the panel outright. See
      # docs/evidence/dsi-burst-headroom.md: the VO's pixel timing and
      # the DSI byte clock are not independent in this driver, and
      # scaling one without the other shears every scanline. Measured
      # both ways on hardware.
      #
      # The flicker this was meant to fix (jitter -9..+1 px, 19
      # brightness dips in 30 s) is real and still unfixed. Whatever
      # fixes it has to keep the two clocks locked.

      # Make the DSI PHY hsfreqrange settable from the device tree.
      #
      # canaan_dsi.c passes a literal 0x96 -- the driver's own
      # TXPHY_445_5_HS_FREQ -- as hsfreqrange, while computing voc from
      # the requested frequency. In a DWC D-PHY that register selects the
      # HS timing calibration (T_hs-prepare, T_hs-zero, T_hs-trail) and
      # must track the real lane rate. Ours never moves, so the link runs
      # 33% outside its calibration at our 594 Mbps and degrades
      # monotonically above it: 682 Mbps freezes the panel, 742 blanks it.
      # docs/evidence/dsi-hsfreqrange-hardcoded.md.
      #
      # The vendor does not hardcode it -- its U-Boot passes
      # phy->hs_freq from a per-panel struct.
      #
      # The right value is NOT known: the driver exposes three points and
      # they do not interpolate (445.5 -> 0x96, 891 -> 0x96, 475 -> 0xa3).
      # Guessing PHY timing is how the panel got blanked once already, so
      # this does not guess -- it reads the value from the device tree and
      # keeps 0x96 as the default. Candidates then cost an 11 second
      # push-file.py DTB push instead of a 20 minute rebuild each, the
      # same trick that made the panel init sequence tractable. The
      # dev_info prints the live lane rate beside the value used, so a
      # boot log says what was actually tried.
      # The braces matter: a bare "u32 hsfr" here would be a declaration
      # after a statement, and 6.6 builds with -Wdeclaration-after-statement
      # and CONFIG_WERROR=y, so it would fail the build twenty minutes in.
      sed -i 's|^\tk230_dsi_config_4lan_phy(dsi, m - 2, n - 1, voc, 0x96);$|\t{\n\t\tu32 hsfr = 0x96;\n\t\tof_property_read_u32(dsi->dev->of_node, "canaan,hsfreqrange", \&hsfr);\n\t\tdev_info(dsi->dev, "DSI PHY: lane %u kbps, voc 0x%x, hsfreqrange 0x%x\\n", phy_clk_freq * 2, voc, hsfr);\n\t\tk230_dsi_config_4lan_phy(dsi, m - 2, n - 1, voc, (uint8_t)hsfr);\n\t}|' \
        drivers/gpu/drm/canaan/canaan_dsi.c
      grep -q 'canaan,hsfreqrange' drivers/gpu/drm/canaan/canaan_dsi.c

      # ---------------------------------------------------------------
      # the-panel-brightness-is-adjustable
      #
      # A DSI-command backlight for the RM69A10, adapted from this pinned
      # tree's own drivers/gpu/drm/panel/panel-samsung-s6d7aa0.c
      # (s6d7aa0_create_backlight/s6d7aa0_bl_update_status), not invented
      # from scratch -- and matching the DT property names LILYGO's own
      # k230_bsp patch
      # 0049-drm-panel-canaan-universal-add-rm69a10-dsi-backlight.patch
      # uses. See docs/research/board-capability-inventory.md and
      # openspec/changes/the-panel-brightness-is-adjustable/design.md.
      #
      # Kept as its own clearly delimited block: feat/speaker is
      # concurrently editing this same file for audio Kconfig, and touches
      # none of the lines below.
      # ---------------------------------------------------------------

      sed -i 's|#include <linux/module.h>|#include <linux/module.h>\n#include <linux/backlight.h>|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q '#include <linux/backlight.h>' drivers/gpu/drm/panel/panel-canaan-universal.c

      # New per-panel state: whether this panel opted into a DSI-command
      # backlight, its default/max brightness from the device tree, the
      # registered backlight_device, and whether the panel is currently
      # enabled -- this guards every DSI brightness write against arriving
      # while the panel is mid-reset or not yet enabled.
      sed -i 's|\tbool stage1_splash;|\tbool stage1_splash;\n\tbool prepared;\n\tbool dsi_command_backlight;\n\tu32 default_brightness;\n\tu32 max_brightness;\n\tstruct backlight_device *bl;|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'struct backlight_device \*bl;' drivers/gpu/drm/panel/panel-canaan-universal.c

      # Parse the three DT properties. Default to today's fixed brightness
      # (0xFE of 255) so a board that does not set the boolean opt-in is
      # completely unaffected.
      sed -i 's|\tof_property_read_u32(np, "panel-dsi-lane", \&ctx->lan_num);|\tof_property_read_u32(np, "panel-dsi-lane", \&ctx->lan_num);\n\n\tctx->default_brightness = 254;\n\tctx->max_brightness = 255;\n\tof_property_read_u32(np, "default-brightness", \&ctx->default_brightness);\n\tof_property_read_u32(np, "max-brightness", \&ctx->max_brightness);\n\tctx->dsi_command_backlight = of_property_read_bool(np, "canaan,dsi-command-backlight");|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'canaan,dsi-command-backlight' drivers/gpu/drm/panel/panel-canaan-universal.c

      # The backlight ops. get_brightness is deliberately left unset -- the
      # backlight core then returns the cached bl->props.brightness rather
      # than issuing an unproven MIPI_DCS_GET_DISPLAY_BRIGHTNESS (0x52)
      # read; only RDDID/RDDPM reads are proven against this panel so far
      # (see the diagnostic block already in canaan_panel_prepare()).
      # update_status no-ops while the panel is not enabled, since a DSI
      # write to a mid-reset or not-yet-enabled controller is exactly the
      # class of hang this kernel's other postPatch history (bounded PHY
      # waits, bounded thermal loop) has already had to fix.
      sed -i 's|static int canaan_panel_get_modes(struct drm_panel \*panel,|static int canaan_panel_apply_brightness(struct canaan_panel *p, u16 brightness)\n{\n\t/* BCTRL, DD, BL: brightness control block, dimming, backlight all on. */\n\tu8 ctrl = 0x24;\n\tint ret;\n\n\tret = mipi_dsi_dcs_write(p->dsi, MIPI_DCS_WRITE_CONTROL_DISPLAY, \&ctrl, 1);\n\tif (ret < 0)\n\t\tdev_err(p->panel.dev, "failed to enable brightness control: %d\\n", ret);\n\n\tret = mipi_dsi_dcs_set_display_brightness(p->dsi, brightness);\n\tif (ret < 0)\n\t\tdev_err(p->panel.dev, "failed to set display brightness: %d\\n", ret);\n\n\treturn ret;\n}\n\nstatic int canaan_panel_bl_update_status(struct backlight_device *bl)\n{\n\tstruct canaan_panel *p = bl_get_data(bl);\n\n\tif (!p->prepared)\n\t\treturn 0;\n\n\treturn canaan_panel_apply_brightness(p, backlight_get_brightness(bl));\n}\n\nstatic const struct backlight_ops canaan_panel_bl_ops = {\n\t.update_status = canaan_panel_bl_update_status,\n};\n\nstatic int canaan_panel_get_modes(struct drm_panel *panel,|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'canaan_panel_bl_update_status' drivers/gpu/drm/panel/panel-canaan-universal.c

      # Register the backlight once DT properties are parsed and the DRM
      # panel is initialized, so ctx->panel.backlight is valid before
      # drm_panel_add(). drm_panel_enable()/drm_panel_disable() -- already
      # called by canaan_dsi.c's encoder enable/disable path on every
      # modeset -- then drive it automatically via backlight_enable()/
      # backlight_disable(), which is what makes a brightness value
      # survive a later modeset or DPMS cycle. See design.md decision 4.
      sed -i 's|\tdrm_panel_add(\&ctx->panel);|\tif (ctx->dsi_command_backlight) {\n\t\tconst struct backlight_properties bl_props = {\n\t\t\t.type = BACKLIGHT_RAW,\n\t\t\t.brightness = ctx->default_brightness,\n\t\t\t.max_brightness = ctx->max_brightness,\n\t\t};\n\n\t\tctx->bl = devm_backlight_device_register(\&dsi->dev,\n\t\t\t\t"canaan-dsi-backlight", \&dsi->dev, ctx,\n\t\t\t\t\&canaan_panel_bl_ops, \&bl_props);\n\t\tif (IS_ERR(ctx->bl)) {\n\t\t\tdev_err(\&dsi->dev, "failed to register backlight: %ld\\n",\n\t\t\t\tPTR_ERR(ctx->bl));\n\t\t\tctx->bl = NULL;\n\t\t} else {\n\t\t\tctx->panel.backlight = ctx->bl;\n\t\t}\n\t}\n\n\tdrm_panel_add(\&ctx->panel);|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'canaan-dsi-backlight' drivers/gpu/drm/panel/panel-canaan-universal.c

      # Mark the panel enabled/disabled, scoped to each function
      # individually (both bodies are otherwise the identical `return 0;`,
      # so the range address is what disambiguates them).
      sed -i '/^static int canaan_panel_enable(struct drm_panel \*panel)/,/^}/ s|\treturn 0;|\tstruct canaan_panel *p = panel_to_canaan_panel(panel);\n\n\tp->prepared = true;\n\n\treturn 0;|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      sed -i '/^static int canaan_panel_disable(struct drm_panel \*panel)/,/^}/ s|\treturn 0;|\tstruct canaan_panel *p = panel_to_canaan_panel(panel);\n\n\tp->prepared = false;\n\n\treturn 0;|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'p->prepared = true;' drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'p->prepared = false;' drivers/gpu/drm/panel/panel-canaan-universal.c

    '';
  };

  defconfig = "k230_defconfig";

  # Build what the vendor builds, and little else.
  #
  # nixpkgs defaults autoModules to true, enabling every module it can on
  # top of the defconfig. Against a vendor tree that is actively harmful: it
  # turns on drivers the vendor never compiles, so their bugs have never
  # been hit. The first build died in drivers/rpmsg/th1520_rpmsg.c with
  # "redefinition of init_module" -- a driver for the TH1520, a different
  # SoC, that k230_defconfig does not enable and nobody builds as a module.
  # Greybus was compiling too.
  autoModules = false;

  # NixOS needs things a vendor defconfig does not bother with. systemd
  # refuses to boot without most of these, and the board would stop at an
  # initrd panic that says nothing about the real cause.
  structuredExtraConfig = with lib.kernel; {
    # The physical trial passed hwprobe V, context preservation through
    # signals/scheduling, and 192 exact Pixman pixel comparisons. Userspace
    # still requires its runtime hwprobe gate; this is not global V codegen.
    RISCV_ISA_V = yes;
    RISCV_ISA_V_DEFAULT_ENABLE = yes;
    DEVTMPFS = yes;
    DEVTMPFS_MOUNT = yes;
    CGROUPS = yes;
    INOTIFY_USER = yes;
    SIGNALFD = yes;
    TIMERFD = yes;
    EPOLL = yes;
    NET = yes;
    SYSFS = yes;
    PROC_FS = yes;
    FHANDLE = yes;
    CRYPTO_USER_API_HASH = yes;
    CRYPTO_HMAC = yes;
    CRYPTO_SHA256 = yes;
    TMPFS = yes;
    TMPFS_POSIX_ACL = yes;
    SECCOMP = yes;
    # An initrd that cannot unpack itself looks exactly like a dead board.
    BLK_DEV_INITRD = yes;
    RD_GZIP = yes;
    RD_ZSTD = yes;
    # For another SoC, and does not compile in this tree.
    RPMSG_TH1520 = lib.mkForce no;

    # The backported Berlin touch driver. Built in, not a module, so a
    # failure to probe shows up in the boot log rather than in whether
    # something got modprobed.
    # Make the soft lockup actually name its culprit.
    #
    # k230_defconfig sets CONFIG_SOFTLOCKUP_DETECTOR=y and nothing else:
    # no FRAME_POINTER, no STACKTRACE. On RISC-V the default unwinder walks
    # frame pointers, so dump_stack() emits nothing and every lockup we have
    # seen prints its header and then an EMPTY stack dump:
    #
    #   watchdog: BUG: soft lockup - CPU#0 stuck for 22s! [kworker/0:5:45]
    #   rcu: Stack dump where RCU GP kthread last ran:
    #   <nothing>
    #
    # Three hypotheses were formed and discarded against that silence --
    # a spinning DSI write, fbcon holding console_lock, and an unbounded
    # thermal read -- because the one piece of evidence that would have
    # settled it in one boot was configured out. Turn it on and read the
    # trace instead of guessing again.
    FRAME_POINTER = yes;
    STACKTRACE = yes;
    # NOT KALLSYMS_ALL. Adding it panicked the board during init:
    #
    #   do_raw_spin_lock <- complete <- module_kobj_release
    #     <- kobject_put <- locate_module_kobject
    #     <- param_sysfs_builtin_init <- do_one_initcall
    #   Kernel panic - not syncing: Attempted to kill init!
    #
    # badaddr 0xc, cause 0xd: a load fault on a near-NULL pointer. It is the
    # known 6.6-era bug where locate_module_kobject fails, kobject_put then
    # runs module_kobj_release, and that calls complete() on the
    # kobj_completion of a synthetic builtin-module object, which is NULL.
    # KALLSYMS_ALL only adds data symbols and is not needed for backtraces;
    # FRAME_POINTER alone is what makes dump_stack() work.
    # See docs/evidence/panel-dark.md.

    # fb0 yes, fbcon no -- for now.
    #
    # Creating fb0 (the 16 bpp fix above) is what started hanging the boot:
    # a kworker soft-locks ~30s in, after udev, and NOTHING prints
    # afterwards, not even the lockup's own call trace. Console output dying
    # with the task is what holding console_lock looks like, and fbcon's
    # deferred take-over is the thing that takes that lock and then does a
    # modeset. The panel path itself cannot be the spin: its DSI timeout is
    # 20ms and panel_simple_sleep() sleeps rather than busy-waits.
    #
    # Turning fbcon off keeps the framebuffer that display/panel 3.1 needs
    # while removing the console take-over, so the board boots to a shell
    # and dmesg can be read -- which is the only way to see the panel
    # messages at all. Task 3.3 (console on the panel) needs this back on,
    # and should only be attempted once the panel actually lights.
    # fbcon back ON. It was turned off to test whether its console
    # take-over was holding console_lock across the boot hang; it was not
    # (the board hung identically without it), and the real cause was the
    # unbounded DSI PHY wait. Now that the panel displays, display/panel
    # task 3.3 wants the kernel console on it, which needs fbcon.
    FRAMEBUFFER_CONSOLE = yes;
    # INPUT_UINPUT sits under the INPUT_MISC Kconfig menu.  Setting the child
    # alone is silently discarded by oldconfig when the menu is off, which
    # yielded no /dev/uinput in the first shell image.  Build it in so no
    # boot.kernelModules entry or module-store lookup is needed.
    INPUT_MISC = yes;
    # /dev/uinput lets the shell change inject touches at known panel
    # coordinates with evemu and exercise compositor -> keyboard -> terminal
    # unattended. A software proxy only: the touch requirement still closes
    # on a real tap at the bench, and the evidence must say which was which.
    INPUT_UINPUT = yes;

    TOUCHSCREEN_GOODIX_BERLIN_CORE = yes;
    TOUCHSCREEN_GOODIX_BERLIN_I2C = yes;

    # --- the-handheld-talks-bluetooth -----------------------------------
    # Kconfig only: no device tree, no kernel patch. drivers/bluetooth/
    # btusb.c is already mainline code present in this pinned tree; it was
    # simply never turned on. Modules, so a board with no dongle attached
    # loads none of this. BT_HCIBTUSB_RTL matches the CSR8510-clone dongle
    # (0a12:0001) this project's accessory kit bundles -- see
    # docs/research/board-capability-inventory.md and
    # openspec/changes/the-handheld-talks-bluetooth/design.md. Kept as its
    # own delimited block: feat/speaker's concurrent audio Kconfig edits
    # touch none of these symbols.
    BT = module;
    BT_HCIBTUSB = module;
    BT_HCIBTUSB_RTL = yes;

    # --- the-clock-survives-a-reboot -------------------------------------
    # One line: rtc@0x91000c00 (compatible "canaan,k230-rtc") is already
    # status-enabled by default in k230.dtsi; drivers/rtc/rtc-k230.c
    # already exists in this pinned tree, gated only by this symbol
    # (`default n`). Built in, not a module -- the RTC is wanted from very
    # early boot, before any module-loading userspace runs. See
    # docs/research/board-capability-inventory.md and
    # openspec/changes/the-clock-survives-a-reboot/design.md.
    RTC_DRV_K230 = yes;
  };

  extraMeta = {
    description = "Xuantie kernel with Canaan K230 support, as used by k230_linux_sdk";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
