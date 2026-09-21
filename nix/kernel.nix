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
  # Pinned by kendryte/k230_linux_sdk @ dev, buildroot-overlay/configs/
  # k230_canmv_v3_defconfig:
  #   BR2_LINUX_KERNEL_CUSTOM_REPO_URL="https://github.com/ruyisdk/linux-xuantie-kernel.git"
  #   BR2_LINUX_KERNEL_CUSTOM_REPO_VERSION="7d4e1f444f461dbe3833bd99a4640e7b6c2cd529"
  #   BR2_LINUX_KERNEL_DEFCONFIG="k230"
  rev = "7d4e1f444f461dbe3833bd99a4640e7b6c2cd529";
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
    src = fetchFromGitHub {
      owner = "ruyisdk";
      repo = "linux-xuantie-kernel";
      inherit rev;
      hash = "sha256-ITlci/1nGcE46kglR7i1AG3MZH6RBfpcGLWPakyXMTk=";
    };
    postPatch = ''
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3.dtb' >> arch/riscv/boot/dts/canaan/Makefile
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-v3-lcd.dtb' >> arch/riscv/boot/dts/canaan/Makefile

      # This board's own device tree and panel.
      cp ${../nix/dts/display-rm69a10-568x1232.dtsi} \
         arch/riscv/boot/dts/canaan/display-rm69a10-568x1232.dtsi
      cp ${../nix/dts/k230-tdisplay.dts} \
         arch/riscv/boot/dts/canaan/k230-tdisplay.dts
      echo 'dtb-$(CONFIG_ARCH_CANAAN) += k230-tdisplay.dtb' >> arch/riscv/boot/dts/canaan/Makefile

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
      sed -i 's|\tif (p->init_set_v1_flag) {|\tif (p->reset) {\n\t\tgpiod_set_value_cansleep(p->reset, 1);\n\t\tpanel_simple_sleep(20);\n\t\tgpiod_set_value_cansleep(p->reset, 0);\n\t\tpanel_simple_sleep(20);\n\t\tgpiod_set_value_cansleep(p->reset, 1);\n\t\tpanel_simple_sleep(120);\n\t}\n\n\tif (p->init_set_v1_flag) {|' \
        drivers/gpu/drm/panel/panel-canaan-universal.c
      grep -q 'panel_simple_sleep(120);' drivers/gpu/drm/panel/panel-canaan-universal.c

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
      # pristine tree nix unpacks, NOT .build/k230_linux_sdk/output/*/build/
      # linux-*/. They differ -- the SDK's built tree has these pm_runtime
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
    FRAMEBUFFER_CONSOLE = lib.mkForce no;

    TOUCHSCREEN_GOODIX_BERLIN_CORE = yes;
    TOUCHSCREEN_GOODIX_BERLIN_I2C = yes;
  };

  extraMeta = {
    description = "Xuantie kernel with Canaan K230 support, as used by k230_linux_sdk";
    platforms = [ "riscv64-linux" ];
  };
} // (args.argsOverride or { }))
