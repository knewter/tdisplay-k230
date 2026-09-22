# LILYGO's U-Boot logo port for the RM69A10, recorded

Task 1.1 of `the-screen-lights-before-linux`. This file exists so that the
grounding for the boot splash does not depend on a GitHub repository staying
where it is. Everything below was read on 2026-09-22.

## Where it came from, exactly

| | |
| --- | --- |
| repository | `https://github.com/Xinyuan-LilyGO/T-Display-K230` |
| commit | **`bb831ab358b66f5bd9a87ecd7c580fee4537492e`** — "Document v0.2.4 release notes", lewisxhe, 2026-09-03 09:40:41 +0000 |
| how | `git clone --depth 1 --filter=blob:none --sparse`, then `git rev-parse HEAD`; the tree under `k230_bsp/overlay/buildroot-overlay/` checked out and read in full |
| compared against | `kendryte/k230_linux_sdk @ 1104236db4d1e47873bd68924f912747b820228c`, `buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/` — the overlay `nix/uboot-k230.nix` copies over U-Boot 2022.10 (`nix/k230-sdk-src.nix`); read from `.build/k230_linux_sdk/` in the shared checkout |

The four logo files as they are at that commit, so a later re-read can tell
whether LILYGO changed them:

```
e9a1b8428860a5d9d5981b0a5fb5c13bf1ccf3be5e71650a097b567a4f8f6270  display_logo.c
b3f8cd5f1b833d2a1520068b237470d0b5bca8da6b2ffd3994d412a4683b0ab7  display_logo.h
b690839e12cec49c00cf61ba6f326ecfb408b4824d9e73b756d15e0c4402bdd8  k230_logo.c
1f136df92f9e41967f1692c5d83ffeff1a50a62371fd75e474fd2a328e20efaa  st7701.c
```

(`sha256sum` over
`k230_bsp/overlay/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/logo/`.)

## What LILYGO's U-Boot overlay contains

Ten files. The overlay is applied the same way Canaan's is — each file
replaces its counterpart in the tree — so a file absent here is the SDK's.

```
arch/riscv/cpu/k230/Kconfig                       adds K230_BARE_DISP_LOGO_RM69A10; DROPS the K230_HDMI_*/LCD_I2C symbols
arch/riscv/dts/k230_canmv_v3.dts                  IO52 pinmux (keyboard backlight), drops the &i2c3 enable
arch/riscv/dts/k230d.dtsi                         IO52 pinmux
board/canaan/common/k230_board_common.c           DELETES enter_to_usb_burn_mode(); k230_set_dtb error paths
board/canaan/common/logo/display_logo.c           the display path: DSI/VO/PHY register work
board/canaan/common/logo/display_logo.h           two prototypes
board/canaan/common/logo/k230_logo.c              connector table, /logo.xrgb load, framebuffer address
board/canaan/common/logo/st7701.c                 rm69a10_568x1232_init(), GPIO_RST_PIN 22, init order
board/canaan/k230_canmv/board.c                   board_init(): keyboard backlight GPIO52 off
configs/k230_canmv_t_display_defconfig            their board config (see below)
```

`board/canaan/common/logo/Makefile` and `vo_table.h` are not in LILYGO's
overlay; the SDK's copies apply.

Paths the change's specs cite, all present in this record: the SDK's
`.build/k230_linux_sdk/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/logo/`
(`display_logo.c`, `k230_logo.c`, `st7701.c`), `arch/riscv/cpu/k230/Kconfig:35`
(`config K230_BARE_DISP_LOGO`, `select LAST_STAGE_INIT` on line 37),
`k230_logo.c:200` (`_k230_display_logo_load_pic`), `k230_logo.c:206` (the
`0x1000000` staging load), `st7701.c:807` (inside `st7701_init`, which begins
at 805), `board/canaan/common/k230_board_common.c:574` (`ft_board_setup`),
and LILYGO's
`k230_bsp/overlay/buildroot-overlay/boot/uboot/u-boot-2022.10-overlay/board/canaan/common/logo/`
plus `k230_bsp/overlay/buildroot-overlay/linux/{0027,0038,0051}-*.patch`.

The specs also cite four lines outside the logo path, for the kernel-side
half of the handoff; recorded here so the check "every cited path appears
in this file" is complete, each verified 2026-09-22 against the tree named:
`panel-canaan-universal.c:318-329` (pristine pinned tree: the probe-time
reset pulse that patch 0051 makes conditional), `drm_fbdev_generic.c:89-98`
(pristine: `drm_client_framebuffer_create()` and the `vzalloc` of the
shadow buffer), `k230_img.c:110` (SDK U-Boot overlay,
`board_fdt_chosen_bootargs()`), and `canaan_dsi.c:424` — the hardcoded
`0x96`, which is line 383 in the pristine tree, was 424 in this project's
patched tree when `dsi-hsfreqrange-hardcoded.md` was written, and is 428
there now that the `canaan,hsfreqrange` plumbing has landed above it.

## What the port does, read from the diff

1. **Kconfig.** `K230_BARE_DISP_LOGO_RM69A10`, `depends on K230_BARE_DISP_LOGO`.
   The parent symbol (SDK `Kconfig:35-39`) `select`s `LAST_STAGE_INIT`, and
   `k230_logo.c:271-277` runs `k230_display_logo()` from `last_stage_init()`,
   i.e. before the autoboot countdown. Their defconfig enables both.
2. **Image.** `/logo.xrgb`, 568x1232 XRGB8888, `RM69A10_LOGO_XRGB_SIZE =
   568 * 1232 * 4` = **2 799 104 bytes**, `ext4load`ed straight to
   `RM69A10_LOGO_FB_ADDR 0x1f000000UL` (a `#define`, not Kconfig). The
   `ext4load` runs first against `${mmc_boot_dev_num}:1`, then `mmc 0:1`. A
   failed load or a wrong `filesize` prints a message and returns non-zero,
   and `k230_display_logo()` now returns `-1` in that case instead of driving
   the panel anyway. Note the SDK's own path stages through `0x1000000`
   (`k230_logo.c:206`) and then copies to `env_get_bootm_size()`; LILYGO's
   RM69A10 branch does neither.
3. **Connector table** (`k230_logo.c`, the new `#elif`), field order per
   `display_logo.h:438-452`:
   `dsi_test_mode 0, bg_color 0xffffff, intr_line 10, pixclk_div 14,
   buff_num 1, K_DSI_2LAN, K_BURST_MODE, K_VO_LP_MODE`,
   `phy_attr { n 4, m 97, voc 0x19, hs_freq 0x96 }`,
   `resolution { pclk 39600, phyclk 475200, htotal 748, hdisplay 568,
   hsync 40, hbp 40, hfp 100, vtotal 1268, vdisplay 1232, vsync 16, vbp 16,
   vfp 4 }`. That is 39.6 MHz / 475.2 Mbps: RT-Smart's numbers, not the
   49.5 MHz / 594 Mbps this project's device tree runs. `pixclk_div` is
   written as `div << 3` into `0x91100078` (`display_logo.c:108-116`), so it
   is the Linux driver's `div - 1`; 14 is 594000/39600 - 1.
4. **PHY.** A new `k230_dsi_config_2lan_phy()`: same phy0/phy1 programming as
   the 4-lane routine, `PHY_RSTZ` written `0x5` then `0x7` instead of
   `0xd`/`0xf` (clears `forcepll`; `PHY_RSTZ` has no per-lane bits), both
   `PHY_STATUS == 0x1fbd` waits bounded at 100 000 x 10 µs with a printed
   value on timeout. `dwc_mipi_phy_config()` selects it on `phy_lan_num ==
   K_DSI_2LAN`, and `st7701_set_phy_freq()` now passes `info->lan_num`
   through instead of the SDK's hardcoded `K_DSI_4LAN`. Sleeps in
   `k230_dsi_phy_pll_config` and `k230_dsi_phy1_config` go from 1 ms to
   20 ms, and the `PHY_TST_CTRL1 != 0x580` spin gains a 1000-iteration cap.
5. **DSI registers under the ifdef.** `VID_MODE_CFG 0x3f02` (SDK and Linux:
   `0xbf02`; bits[1:0] are burst in both, bit 15 differs), `DPI_COLOR_CODING
   0x005` (SDK and Linux: `0x105`; `color_coding = 5` is 24-bit RGB either
   way). `VO_DISP_YUV2RGB_CTL 0` and `VO_OSD_RGB2YUV_CTL 0` — the picture is
   RGB and goes through no colour-space conversion.
6. **Scanout.** `vo_osd4_logo_test()`: OSD layer 4, 568x1232 at the display's
   `XZONE`/`YZONE` start, stride `568 * 4 / 8`, both address slots pointing
   at the framebuffer, `VO_DISP_ENABLE` bit 8, `VO_REG_LOAD_CTL 0x11`. The
   SDK's `vo_layer1_test()` (video layer 1, NV12) is bypassed.
7. **Init order.** `st7701_init()` is unchanged in shape: hardware reset on
   `GPIO_RST_PIN 22` (SDK: 24), `k230_display_rst()`, pixel clock, PHY, DSI
   resolution + panel init, VO, layer. Under the ifdef `dwc_dsi_enable(1)`
   moves from inside `st7701_dsi_resolution_init()` to after the OSD is set
   up. `k230_display_rst()` itself changes for every board: `0x91101090`
   written `0`, 20 ms, `0xffffffff` (SDK: `0` then `1`, no wait), then a VO
   soft reset (`VO_SOFT_RST_CTL 0x0f`, `VO_DMA_SW_CTL 0`, `VO_REG_LOAD_CTL 0`).
8. **Panel init sequence**, `rm69a10_568x1232_init()`, 13 commands:
   `FE FD`, `80 FC`, `FE 00`, `2A 00 00 02 37`, `2B 00 00 04 CF`,
   `31 00 03 02 34`, `30 00 00 04 CF`, `12`, `35 00` (short), `51 FE` (short),
   `11`, 120 ms, `29`, 10 ms, `3A 77` (short). One- and two-byte commands go
   through a new `kd_dwc_lpdt_send_short_pkg()` as DCS short writes
   (`0x05`/`0x15`); the rest through the SDK's long-packet path, whose
   payload loop is rewritten to zero the word before a partial `memcpy`.
9. **Things unrelated to the panel** that ride in the same overlay and must
   NOT be carried: `board.c` drives GPIO52 (keyboard backlight) low at
   `board_init()`; `k230_board_common.c` deletes `enter_to_usb_burn_mode()`
   and inlines its body into `do_2_burn_mode` (the USB-flash change owns
   that file); the defconfig moves the environment to `ENV_OFFSET 0x1e0000`,
   `ENV_SIZE 0x10000` where this project's card has it at 3 MiB / 3.5 MiB,
   8 KiB (`nix/stage1.nix`, `docs/evidence/uboot-env.txt`).

## Where it disagrees with this project, and which side is grounded

| what | LILYGO's U-Boot | this project | grounded by |
| --- | --- | --- | --- |
| pixel clock / lane rate | 39.6 MHz / 475.2 Mbps | 49.5 MHz / 594 Mbps | `nix/dts/display-rm69a10-568x1232.dtsi`; boot log `DSI PHY: lane 594000 kbps` |
| `hs_freq` | `0x96` | `0x87` | measured, `docs/evidence/dsi-hsfreqrange-hardcoded.md` |
| PLL `{n, m, voc}` | `{4, 97, 0x19}` | `{3, 97, 0x17}` | derived in `dsi-hsfreqrange-hardcoded.md`, voc matches the boot log |
| `pixclk_div` | 14 | 11 | `594000 / 49500 - 1` |
| `VID_MODE_CFG` | `0x3f02` | `0xbf02` | what Linux writes, `canaan_dsi.c:280` |
| `DPI_COLOR_CODING` | `0x005` | `0x105` | what Linux writes, `canaan_dsi.c:288` |
| framebuffer address | `0x1f000000` | see `docs/evidence/stage1-memory-map.md` | the kernel's CMA pool is at `0x1e000000..0x3e000000` on this system |
| init sequence rows 6-8 | `31 …`, `30 …`, `12` (partial area + partial mode) | `13` (normal mode) | the DTSI comment: the partial block lit the panel but glitched; `13` is what runs today |

The last row corrects a sentence in the change's own specs: LILYGO's U-Boot
sequence is *not* "the same 13 commands our device tree sends". Ours is
eleven commands with `13 00` where theirs has `31/30/12`. Their Linux DTS
(patch 0031, below) sends the same 13 as their U-Boot, so on their images
both sides agree with each other; on ours the U-Boot port must send the
DTSI's sequence or the two sides will initialise the panel differently.

Also worth holding onto: the RM69A10 XRGB8888 buffer is
**568 x 1232 x 4 = 2 799 104 bytes**, which is the number U-Boot's size check
compares `filesize` against. The change's tasks say 2 799 616; that is
wrong by 512 and would make every splash file fail the check.

## Their defconfig, display lines

`configs/k230_canmv_t_display_defconfig` lines 119-122:

```
# RM69A10 AMOLED Display
CONFIG_K230_BARE_DISP_LOGO=y
CONFIG_K230_BARE_DISP_LOGO_PATH="board/canaan/k230-soc/rootfs_overlay/logo.yuv"
CONFIG_K230_BARE_DISP_LOGO_RM69A10=y
```

`K230_BARE_DISP_LOGO_PATH` is the SDK's NV12 path and is unused by the
RM69A10 branch, which loads `/logo.xrgb` from the boot partition at runtime.
The whole defconfig against the SDK's `k230_canmv_v3_defconfig` this project
builds:

```diff
--- a/configs/k230_canmv_v3_defconfig
+++ b/configs/k230_canmv_t_display_defconfig
@@ -2,8 +2,8 @@
 CONFIG_SYS_TEXT_BASE=0
 CONFIG_SYS_MALLOC_F_LEN=0x40000
 CONFIG_NR_DRAM_BANKS=2
-CONFIG_ENV_SIZE=0x2000
-CONFIG_ENV_OFFSET=0x300000
+CONFIG_ENV_SIZE=0x10000
+CONFIG_ENV_OFFSET=0x1e0000
 CONFIG_SPL_DM_SPI=y
 CONFIG_DEFAULT_DEVICE_TREE="k230_canmv_v3"
 CONFIG_SPL_TEXT_BASE=0x80300000
@@ -77,6 +77,9 @@
 CONFIG_SPL_DM_DEVICE_REMOVE=y
 CONFIG_SPL_CLK=y
 CONFIG_DM_KEYBOARD=y
+CONFIG_DM_I2C=y
+CONFIG_SYS_I2C_DW=y
+CONFIG_CMD_I2C=y
 CONFIG_MMC=y
 CONFIG_MMC_HS200_SUPPORT=y
 CONFIG_SPL_MMC_HS200_SUPPORT=y
@@ -98,9 +101,6 @@
 CONFIG_SPL_PINCONF=y
 CONFIG_PINCTRL_SINGLE=y
 CONFIG_SYS_NS16550=y
-CONFIG_DM_I2C=y
-CONFIG_SYS_I2C_DW=y
-CONFIG_CMD_I2C=y
 CONFIG_SPI=y
 CONFIG_DESIGNWARE_SPI=y
 CONFIG_USB=y
@@ -115,3 +115,8 @@
 CONFIG_SPL_GZIP=y
 # CONFIG_EFI_LOADER is not set
 CONFIG_CANMV_V3_LPDDR4_2667=y
+
+# RM69A10 AMOLED Display
+CONFIG_K230_BARE_DISP_LOGO=y
+CONFIG_K230_BARE_DISP_LOGO_PATH="board/canaan/k230-soc/rootfs_overlay/logo.yuv"
+CONFIG_K230_BARE_DISP_LOGO_RM69A10=y
```

## The diff: the four logo files, LILYGO against the SDK

`diff -u` of the SDK overlay (`a/`) against LILYGO's (`b/`), unmodified.

```diff
--- a/board/canaan/common/logo/display_logo.c
+++ b/board/canaan/common/logo/display_logo.c
@@ -119,7 +119,11 @@
 {
 
     writel(0x1, DSI_BASE_ADDR + MODE_CFG);              // set lp cmd mode
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    writel(0x3f02, DSI_BASE_ADDR + VID_MODE_CFG);
+#else
     writel(0xbf02, DSI_BASE_ADDR + VID_MODE_CFG);
+#endif
     writel(0x10f7f01, DSI_BASE_ADDR + CMD_MODE_CFG);
     writel(0x1c, DSI_BASE_ADDR + PCKHDL_CFG);
     writel(0x1, DSI_BASE_ADDR + 0x4);
@@ -131,7 +135,11 @@
 void dwc_dsi_set_color_coding(void)
 {
     // set color 24-bit , vo 24 bits passed
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    writel(0x005, DSI_BASE_ADDR + DPI_COLOR_CODING);
+#else
     writel(0x105, DSI_BASE_ADDR + DPI_COLOR_CODING);
+#endif
 }
 
 uint32_t dwc_dsi_init(void)
@@ -201,20 +209,14 @@
     {
         while (len)
         {
-            if (len < pld_data_bytes)            // 0 1
-            {
+            uint32_t copy_len = (len < pld_data_bytes) ? len : pld_data_bytes;
 
-                memcpy(&word, buf, pld_data_bytes);
-                writel(word, DSI_BASE_ADDR + GEN_PLD_DATA);
-                len = 0;
-            }
-            else
-            {
-                memcpy(&word, buf, pld_data_bytes);
-                writel(word, DSI_BASE_ADDR + GEN_PLD_DATA);
-                buf += pld_data_bytes;
-                len -= pld_data_bytes;
-            }
+            word = 0;
+            memcpy(&word, buf, copy_len);
+            writel(word, DSI_BASE_ADDR + GEN_PLD_DATA);
+
+            buf += copy_len;
+            len -= copy_len;
         }
 
         hdr_val = 0x39;//0x37;//(0x05) + (0x3 << 6) + (cmd_len << 8);  // long package
@@ -236,13 +238,35 @@
     return 0;
 }
 
+uint32_t kd_dwc_lpdt_send_short_pkg(uint8_t *buf, uint32_t cmd_len)
+{
+    uint32_t hdr_val = 0;
+
+    if (cmd_len == 1) {
+        hdr_val = 0x05 | (buf[0] << 8);
+    } else if (cmd_len == 2) {
+        hdr_val = 0x15 | (buf[0] << 8) | (buf[1] << 16);
+    } else {
+        return kd_dwc_lpdt_send_pkg(buf, cmd_len);
+    }
+
+    writel(hdr_val, DSI_BASE_ADDR + GEN_HDR);
+    msleep(3);
+
+    return 0;
+}
+
 
 void k230_display_rst(void)
 {
-    //uint32_t rdata = 0;
-
     writel(0x0, (volatile void __iomem* )0x91101090);
-    writel(0x1, (volatile void __iomem* )0x91101090);
+    msleep(20);
+    writel(0xffffffff, (volatile void __iomem* )0x91101090);
+
+    msleep(20);
+    writel(0x0f, VO_BASE_ADDR + VO_SOFT_RST_CTL);
+    writel(0x00, VO_BASE_ADDR + VO_DMA_SW_CTL);
+    writel(0x00, VO_BASE_ADDR + VO_REG_LOAD_CTL);
 
     msleep(10);
 }
@@ -374,14 +398,22 @@
     reg = 4 + (5 << 4) + (6 << 8) + (7 << 12) + (8 << 16) + (9 << 20) + (10 << 24) + (11 << 28);
     writel(reg, VO_BASE_ADDR + 0x950);
 
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    writel(0x0, VO_BASE_ADDR + VO_DISP_YUV2RGB_CTL);
+#else
     // config csc
     writel(0x1, VO_BASE_ADDR + VO_DISP_YUV2RGB_CTL);
+#endif
     // disp gamma enable
     writel(0x0, VO_BASE_ADDR + VO_DISP_CLUT_CTL);
     // disp dith enable
     writel(0x1, VO_BASE_ADDR + VO_DISP_DITH_CTL);
 
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    writel(0x00000000, VO_BASE_ADDR + VO_OSD_RGB2YUV_CTL);
+#else
     writel(0x11111111, VO_BASE_ADDR + VO_OSD_RGB2YUV_CTL);
+#endif
 
     writel(0xff, VO_BASE_ADDR + VO_DISP_MIX_LAYER_GLB_EN);
 
@@ -651,6 +683,48 @@
 	writel(reg, VO_BASE_ADDR + VO_DISP_ENABLE);
 }
 #define YUV_PIC_ADD k230_display_logo_get_pic_mem_addr()
+
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+#define RM69A10_LOGO_WIDTH 568
+#define RM69A10_LOGO_HEIGHT 1232
+#define RM69A10_LOGO_OSD 4
+
+void vo_osd4_logo_test(k_connector_info *info)
+{
+    uint32_t reg = 0;
+    uint32_t start_w = readl(VO_BASE_ADDR + VO_DISP_XZONE_CTL) & 0x1fff;
+    uint32_t start_h = readl(VO_BASE_ADDR + VO_DISP_YZONE_CTL) & 0x1fff;
+    uint32_t addr = YUV_PIC_ADD;
+
+    writel(0x03, VO_BASE_ADDR + VO_OSD_INFOR(RM69A10_LOGO_OSD));
+
+    reg = RM69A10_LOGO_WIDTH | (RM69A10_LOGO_HEIGHT << 16);
+    writel(reg, VO_BASE_ADDR + VO_OSD_SIZE(RM69A10_LOGO_OSD));
+
+    reg = ((start_w + RM69A10_LOGO_WIDTH - 1) << 16) + start_w;
+    writel(reg, VO_BASE_ADDR + VO_DISP_OSD_XCTL(RM69A10_LOGO_OSD));
+
+    reg = ((start_h + RM69A10_LOGO_HEIGHT - 1) << 16) + start_h;
+    writel(reg, VO_BASE_ADDR + VO_DISP_OSD_YCTL(RM69A10_LOGO_OSD));
+
+    writel(addr, VO_BASE_ADDR + VO_OSD_VLU_ADDR0(RM69A10_LOGO_OSD));
+    writel(addr, VO_BASE_ADDR + VO_OSD_ALP_ADDR0(RM69A10_LOGO_OSD));
+    writel(addr, VO_BASE_ADDR + VO_OSD_VLU_ADDR1(RM69A10_LOGO_OSD));
+    writel(addr, VO_BASE_ADDR + VO_OSD_ALP_ADDR1(RM69A10_LOGO_OSD));
+
+    writel((RM69A10_LOGO_WIDTH * 4) / 8,
+           VO_BASE_ADDR + VO_OSD_STRIDE(RM69A10_LOGO_OSD));
+    writel(0x40, VO_BASE_ADDR + VO_OSD_DMA_CTRL(RM69A10_LOGO_OSD));
+    writel(0x1100, VO_BASE_ADDR + VO_OSD_ADDR_SEL_MODE(RM69A10_LOGO_OSD));
+
+    reg = readl(VO_BASE_ADDR + VO_DISP_ENABLE);
+    reg |= BIT_MASK(8);
+    writel(reg, VO_BASE_ADDR + VO_DISP_ENABLE);
+
+    writel(0x11, VO_BASE_ADDR + VO_REG_LOAD_CTL);
+}
+#endif
+
 void vo_layer1_test(k_connector_info *info)
 {
     uint32_t reg = 0;
@@ -788,7 +862,7 @@
     reg = (reg & ~(BIT_MASK(10))) | (1 << 10);
     writel(reg, TXPHY_BASE_ADDR + TXDPHY_PLL_CFG1);
 
-    msleep(1);
+    msleep(20);
 
     reg = (reg & ~(BIT_MASK(10))) | (0 << 10);
     writel(reg, TXPHY_BASE_ADDR + TXDPHY_PLL_CFG1);
@@ -839,6 +913,7 @@
 void k230_dsi_phy1_config(uint8_t hsfreq)
 {
     uint32_t reg = 0;
+    uint32_t count = 0;
 
     // select1
     writel(0x400000, TXPHY_BASE_ADDR + TXDPHY_CFG1);
@@ -846,7 +921,7 @@
     // printf("0x400000 is %x \n", readl(TXPHY_BASE_ADDR + TXDPHY_CFG1));
 
     writel(0x1, DSI_BASE_ADDR + PHY_TST_CTRL0);
-    msleep(1);
+    msleep(20);
     writel(0x0, DSI_BASE_ADDR + PHY_TST_CTRL0);
 
     // SET TEST CLR TO LOW
@@ -893,7 +968,9 @@
     while (readl(DSI_BASE_ADDR + PHY_TST_CTRL1) != 0x580)  //0x580
     {
         k230_dsi_write_phy_reg(0x03, 0x80);
-        msleep(1);
+        msleep(20);
+        if (++count >= 1000)
+            break;
     }
 
     // printf("phy1 config done \n");
@@ -933,6 +1010,46 @@
 
 }
 
+void k230_dsi_config_2lan_phy(uint32_t m, uint32_t n, uint8_t vco, uint8_t hsfreq)
+{
+    uint32_t reg = 0;
+    uint32_t timeout = 0;
+
+    k230_dsi_phy0_config(m, n, vco, hsfreq);
+    k230_dsi_phy1_config(hsfreq);
+
+    reg = readl(TXPHY_BASE_ADDR + TXDPHY_CFG1);
+    writel(0x0, TXPHY_BASE_ADDR + TXDPHY_CFG1);
+    writel(0x5, DSI_BASE_ADDR + PHY_RSTZ);
+    writel(0x7, DSI_BASE_ADDR + PHY_RSTZ);
+
+    while (readl(DSI_BASE_ADDR + PHY_STATUS) != 0x1fbd) {
+        if (++timeout > 100000) {
+            printf("DSI 2-lane PHY_STATUS timeout: got 0x%04x\n",
+                   readl(DSI_BASE_ADDR + PHY_STATUS));
+            break;
+        }
+        udelay(10);
+    }
+
+    msleep(20);
+    writel(0x1, DSI_BASE_ADDR + LPCLK_CTRL);
+
+    reg = readl(TXPHY_BASE_ADDR + TXDPHY_CFG1);
+    writel(0x400000, TXPHY_BASE_ADDR + TXDPHY_CFG1);
+
+    timeout = 0;
+    while (readl(DSI_BASE_ADDR + PHY_STATUS) != 0x1fbd) {
+        if (++timeout > 100000) {
+            printf("DSI 2-lane PHY_STATUS(2) timeout: got 0x%04x\n",
+                   readl(DSI_BASE_ADDR + PHY_STATUS));
+            break;
+        }
+        udelay(10);
+    }
+
+    reg = readl(DSI_BASE_ADDR + PHY_STATUS);
+}
 
 
 uint32_t dwc_mipi_phy_config(k_vo_mipi_phy_attr *phy)
@@ -949,7 +1066,10 @@
 
     writel(0x0, DSI_BASE_ADDR + 0xc);
 
-    k230_dsi_config_4lan_phy(phy->m, phy->n, phy->voc, phy->hs_freq);
+    if (phy->phy_lan_num == K_DSI_2LAN)
+        k230_dsi_config_2lan_phy(phy->m, phy->n, phy->voc, phy->hs_freq);
+    else
+        k230_dsi_config_4lan_phy(phy->m, phy->n, phy->voc, phy->hs_freq);
 #endif
     return 0;
 }
--- a/board/canaan/common/logo/display_logo.h
+++ b/board/canaan/common/logo/display_logo.h
@@ -523,11 +523,14 @@
 uint32_t vo_init(void);
 void kd_vo_set_layer(k_connector_info *info, uint32_t width, uint32_t height, uint32_t pos_x , uint32_t pos_y , k_vo_rotation rotation, uint32_t addr);
 void vo_layer1_test(k_connector_info *info);
+void vo_osd4_logo_test(k_connector_info *info);
+unsigned long k230_display_logo_get_pic_mem_addr(void);
 
 
 // dsi
 uint32_t kd_dsi_set_attr(k_vo_dsi_attr *attr);
 uint32_t kd_dwc_lpdt_send_pkg(uint8_t *buf, uint32_t cmd_len);
+uint32_t kd_dwc_lpdt_send_short_pkg(uint8_t *buf, uint32_t cmd_len);
 
 // clk
 void k230_set_pixclk(uint32_t div);
@@ -540,6 +543,4 @@
 int st7701_init(k_connector_info *info);
 uint32_t dwc_dsi_enable(uint32_t enable);
 void kd_vo_set_vtth_intr(bool status, uint32_t vpos);
-uint32_t kd_dwc_lpdt_send_pkg(uint8_t *buf, uint32_t cmd_len);
-unsigned long k230_display_logo_get_pic_mem_addr(void);
 #endif
--- a/board/canaan/common/logo/k230_logo.c
+++ b/board/canaan/common/logo/k230_logo.c
@@ -193,24 +193,91 @@
 }
 #define BACKGROUND_BLACK_COLOR                            (0x808000)
 #define BACKGROUND_PINK_COLOR                             (0xffffff)
+#define RM69A10_LOGO_WIDTH                                568
+#define RM69A10_LOGO_HEIGHT                               1232
+#define RM69A10_LOGO_XRGB_SIZE                            (RM69A10_LOGO_WIDTH * RM69A10_LOGO_HEIGHT * 4)
+#define RM69A10_LOGO_FB_ADDR                              0x1f000000UL
 unsigned long k230_display_logo_get_pic_mem_addr(void)
 {
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    return RM69A10_LOGO_FB_ADDR;
+#else
     return env_get_bootm_size(); //预留1M 给logo；
+#endif
 }
-int _k230_display_logo_load_pic()
+
+int _k230_display_logo_load_pic(void)
 {
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    char cmd[160];
+    const char *mmc_dev = env_get("mmc_boot_dev_num");
+    unsigned long add = k230_display_logo_get_pic_mem_addr();
+    unsigned long size;
+    int ret;
+
+    invalidate_dcache_range(add, add + ROUND(RM69A10_LOGO_XRGB_SIZE, CONFIG_SYS_CACHELINE_SIZE));
+    if (mmc_dev && *mmc_dev)
+        sprintf(cmd, "ext4load mmc %s:1 0x%lx /logo.xrgb", mmc_dev, add);
+    else
+        sprintf(cmd, "ext4load mmc 1:1 0x%lx /logo.xrgb", add);
+    printf("cmd=%s\n", cmd);
+    ret = run_command(cmd, 0);
+    if (ret) {
+        sprintf(cmd, "ext4load mmc 0:1 0x%lx /logo.xrgb", add);
+        printf("cmd=%s\n", cmd);
+        ret = run_command(cmd, 0);
+    }
+    if (ret) {
+        printf("logo.xrgb load failed, skip U-Boot logo\n");
+        return ret;
+    }
+
+    size = env_get_ulong("filesize", 16, 0);
+    if (size != RM69A10_LOGO_XRGB_SIZE) {
+        printf("logo.xrgb size mismatch: got %lu, expected %u\n",
+               size, RM69A10_LOGO_XRGB_SIZE);
+        return -1;
+    }
+    flush_cache(add, ROUND(RM69A10_LOGO_XRGB_SIZE, CONFIG_SYS_CACHELINE_SIZE));
+    printf("RM69A10 direct XRGB8888 logo.xrgb full-screen OSD4\n");
+
+    return 0;
+#else
     char cmd[128];
+    const char *mmc_dev = env_get("mmc_boot_dev_num");
     unsigned long add = k230_display_logo_get_pic_mem_addr();
     unsigned long size = 0x100000;
+    int ret;
 
-    sprintf(cmd, "ext4load mmc ${mmc_boot_dev_num}:1 0x1000000 /logo.yuv ");
+    if (mmc_dev && *mmc_dev)
+        sprintf(cmd, "ext4load mmc %s:1 0x1000000 /logo.yuv", mmc_dev);
+    else
+        sprintf(cmd, "ext4load mmc 1:1 0x1000000 /logo.yuv");
     printf("cmd=%s\n", cmd);
-    run_command(cmd, 0);
+    ret = run_command(cmd, 0);
+    if (ret) {
+        sprintf(cmd, "ext4load mmc 0:1 0x1000000 /logo.yuv");
+        printf("cmd=%s\n", cmd);
+        ret = run_command(cmd, 0);
+    }
+    if (ret) {
+        printf("logo.yuv load failed, skip U-Boot logo\n");
+        return ret;
+    }
 
     size = env_get_ulong("filesize", 16,0x100000);
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    if (size != RM69A10_LOGO_SIZE) {
+        printf("logo.yuv size mismatch: got %lu, expected %u\n",
+               size, RM69A10_LOGO_SIZE);
+        return -1;
+    }
+#endif
+    invalidate_dcache_range(0x1000000, 0x1000000 + ROUND(size, CONFIG_SYS_CACHELINE_SIZE));
     memcpy((void*)add, (void*)0x1000000, size);
     flush_cache(add, ROUND(size, CONFIG_SYS_CACHELINE_SIZE));//
     return 0;
+#endif
 }
 int k230_display_logo(void)
 {
@@ -246,6 +313,21 @@
                   8, 48, 52, 1402,
                    1280, 6, 16, 100 },
     };
+#elif defined(CONFIG_K230_BARE_DISP_LOGO_RM69A10)
+    info = (k_connector_info){
+        0,
+        BACKGROUND_PINK_COLOR,
+        10,
+        14,
+        1,
+        K_DSI_2LAN,
+        K_BURST_MODE,
+        K_VO_LP_MODE,
+        { 4, 97, 0x19, 0x96 },
+        { 39600, 475200, 748, 568,
+                  40, 40, 100, 1268,
+                  1232, 16, 16, 4 },
+    };
 #else
     info = (k_connector_info){
         0,
@@ -261,7 +343,8 @@
     };
 #endif
 
-    _k230_display_logo_load_pic();
+    if (_k230_display_logo_load_pic())
+        return -1;
 
     sysctl_pwr_set_power(SYSCTL_PD_DISP, true);
     st7701_init(&info);
@@ -289,15 +372,15 @@
 
 /*
 usb start;dhcp;
-tftp 0x1000000 192.168.1.2:wjx/disney_800x480_nv12.yuv ;
-tftp 0x100000 192.168.1.2:wjx/display_logo.bin;cp.b 0x100000 0x80200000 0x100000;
+tftp 0x1000000 10.10.1.94:wjx/disney_800x480_nv12.yuv ;
+tftp 0x100000 10.10.1.94:wjx/display_logo.bin;cp.b 0x100000 0x80200000 0x100000;
 boot_baremetal 0 0x80200000 0x100000
 
 
 
-usb start;dhcp; tftp 0x100000 192.168.1.2:wjx/u-boot.bin;cp.b 0x100000 0 0x100000;
+usb start;dhcp; tftp 0x100000 10.10.1.94:wjx/u-boot.bin;cp.b 0x100000 0 0x100000;
 go 0;
-usb start;dhcp;  tftp 0x30000000 192.168.1.2:wjx/disney_800x480_nv12.yuv ; cp.b 0x30000000   0x3ff00000 0x100000;k230_logo;
+usb start;dhcp;  tftp 0x30000000 10.10.1.94:wjx/disney_800x480_nv12.yuv ; cp.b 0x30000000   0x3ff00000 0x100000;k230_logo;
 k230_logo;
 uboot下更新vmlinux;更新设备树：
 
--- a/board/canaan/common/logo/st7701.c
+++ b/board/canaan/common/logo/st7701.c
@@ -27,7 +27,11 @@
 static void st7701_hardware_init(void)
 {
 
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+	#define GPIO_RST_PIN			22
+#else
 	#define GPIO_RST_PIN			24
+#endif
 	#define GPIO_LCD_BACKLIGHT_EN   25
     char high = 1,low = 0;
 
@@ -68,6 +72,39 @@
 
 }
 
+static void rm69a10_568x1232_init(void)
+{
+    uint8_t param1[] = {0xFE, 0xFD};
+    uint8_t param2[] = {0x80, 0xFC};
+    uint8_t param3[] = {0xFE, 0x00};
+    uint8_t param4[] = {0x2A, 0x00, 0x00, 0x02, 0x37};
+    uint8_t param5[] = {0x2B, 0x00, 0x00, 0x04, 0xCF};
+    uint8_t param6[] = {0x31, 0x00, 0x03, 0x02, 0x34};
+    uint8_t param7[] = {0x30, 0x00, 0x00, 0x04, 0xCF};
+    uint8_t param8[] = {0x12};
+    uint8_t param9[] = {0x35, 0x00};
+    uint8_t param10[] = {0x51, 0xFE};
+    uint8_t param11[] = {0x11};
+    uint8_t param12[] = {0x29};
+    uint8_t param13[] = {0x3A, 0x77};
+
+    kd_dwc_lpdt_send_pkg(param1, sizeof(param1));
+    kd_dwc_lpdt_send_pkg(param2, sizeof(param2));
+    kd_dwc_lpdt_send_pkg(param3, sizeof(param3));
+    kd_dwc_lpdt_send_pkg(param4, sizeof(param4));
+    kd_dwc_lpdt_send_pkg(param5, sizeof(param5));
+    kd_dwc_lpdt_send_pkg(param6, sizeof(param6));
+    kd_dwc_lpdt_send_pkg(param7, sizeof(param7));
+    kd_dwc_lpdt_send_pkg(param8, sizeof(param8));
+    kd_dwc_lpdt_send_short_pkg(param9, sizeof(param9));
+    kd_dwc_lpdt_send_short_pkg(param10, sizeof(param10));
+    kd_dwc_lpdt_send_pkg(param11, sizeof(param11));
+    msleep(120);
+    kd_dwc_lpdt_send_pkg(param12, sizeof(param12));
+    msleep(10);
+    kd_dwc_lpdt_send_short_pkg(param13, sizeof(param13));
+}
+
 
 void st7701_480x640_init(void)
 {
@@ -755,10 +792,14 @@
 	st7701_480x640_init();
     #elif defined(CONFIG_K230_BARE_DISP_LOGO_ILI9881)
     ili9881_800x1280_init();
+    #elif defined(CONFIG_K230_BARE_DISP_LOGO_RM69A10)
+    rm69a10_568x1232_init();
     #else
 	st7701_480x800_init();
     #endif
+#ifndef CONFIG_K230_BARE_DISP_LOGO_RM69A10
     dwc_dsi_enable(1);
+#endif
 
     return 0;
 }
@@ -784,9 +825,10 @@
     return 0;
 }
 
-static int st7701_set_phy_freq(k_connectori_phy_attr *phy_attr)
+static int st7701_set_phy_freq(k_connector_info *info)
 {
     k_vo_mipi_phy_attr mipi_phy_attr;
+    k_connectori_phy_attr *phy_attr = &info->phy_attr;
 
     memset(&mipi_phy_attr, 0, sizeof(k_vo_mipi_phy_attr));
 
@@ -794,7 +836,7 @@
     mipi_phy_attr.n = phy_attr->n;
     mipi_phy_attr.hs_freq = phy_attr->hs_freq;
     mipi_phy_attr.voc = phy_attr->voc;
-    mipi_phy_attr.phy_lan_num = K_DSI_4LAN;
+    mipi_phy_attr.phy_lan_num = info->lan_num;
 
     dwc_mipi_phy_config(&mipi_phy_attr);
 
@@ -816,14 +858,22 @@
     if(info->pixclk_div != 0)
         k230_set_pixclk(info->pixclk_div);
 
-    ret |= st7701_set_phy_freq(&info->phy_attr);
+    ret |= st7701_set_phy_freq(info);
 
     ret |= st7701_dsi_resolution_init(info);
 
     ret |= st7701_vo_resolution_init(&info->resolution, info->bg_color, info->intr_line);
 
-	// kd_vo_set_layer(info, 320, 240, 0 , 0 , K_ROTATION_90, 0x13000000);
+		// kd_vo_set_layer(info, 320, 240, 0 , 0 , K_ROTATION_90, 0x13000000);
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+	vo_osd4_logo_test(info);
+#else
 	vo_layer1_test(info);
+#endif
+
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+    dwc_dsi_enable(1);
+#endif
 
     return ret;
 }
```

## The diff: the other U-Boot overlay files

Recorded because the Kconfig hunk is needed and the other two must be left
out on purpose.

```diff
##### arch/riscv/cpu/k230/Kconfig
--- a/arch/riscv/cpu/k230/Kconfig
+++ b/arch/riscv/cpu/k230/Kconfig
@@ -56,16 +56,10 @@
 	help
 	  df screen
 
-config K230_HDMI_LCD_I2C_BUS
-	int "k230 hdmi lcd i2c bus"
-	default 3
-
-config K230_HDMI_I2C_DEV
-	hex "k230 hdmi i2c dev "
-	default 0x3b
-
-config K230_LCD_I2C_DEV
-	hex "k230 lcd  i2c dev "
-	default 0x38
+config K230_BARE_DISP_LOGO_RM69A10
+	bool "rm69a10 screen"
+	depends on K230_BARE_DISP_LOGO
+	help
+	  LILYGO T-Display K230 RM69A10 AMOLED screen
 
 endif
##### board/canaan/common/k230_board_common.c
--- a/board/canaan/common/k230_board_common.c
+++ b/board/canaan/common/k230_board_common.c
@@ -77,15 +77,6 @@
     }
 	return ENVL_MMC;
 }
-void enter_to_usb_burn_mode(void)
-{
-    printf("now enter to usb burn mode\r\n\n");
-    mdelay(100);
-
-    writel(0x5aa5a55a, (void*)0x80230000);
-    flush_dcache_range(0x80230000,0x80230000+4);
-    writel(0x10001, (void*)SYSCTL_BOOT_BASE_ADDR+0x60);
-}
 #ifndef CONFIG_SPL_BUILD
 int board_early_init_f(void)
 {
@@ -484,11 +475,11 @@
     #define CONFIG_K230_HDMI_LCD_I2C_BUS 3
 #endif
 
-#ifdef CONFIG_K230_HDMI_I2C_DEV
+#ifndef CONFIG_K230_HDMI_I2C_DEV
     #define CONFIG_K230_HDMI_I2C_DEV 0x3b
 #endif
 
-#ifdef CONFIG_K230_LCD_I2C_DEV
+#ifndef CONFIG_K230_LCD_I2C_DEV
     #define CONFIG_K230_LCD_I2C_DEV 0x38
 #endif
 
@@ -528,28 +519,20 @@
     //printf("%s\n",cmd);
     if( (0 == run_command(cmd, 0))  &&
         (0 < env_get_ulong("filesize", 16, 0)) ){
-        ret = k230_set_dtb_env("dtb","force_dtb");
-        if (ret)
-            ret = k230_set_dtb_env("dtb","force_dtb");
-        return ret;
+        return k230_set_dtb_env("dtb","force_dtb");
     }
 
 	ret = uclass_get_device_by_seq(UCLASS_I2C, CONFIG_K230_HDMI_LCD_I2C_BUS, &bus);
 	if (ret ==0 ) {
         if(0 == dm_i2c_probe(bus, CONFIG_K230_LCD_I2C_DEV, 0, &chip)){ //探测到lcd
-            if (!k230_set_dtb_env("dtb", "lcd_dtb"))
-                return 0;
+            return k230_set_dtb_env("dtb", "lcd_dtb");
         }
         if(0 == dm_i2c_probe(bus, CONFIG_K230_HDMI_I2C_DEV, 0, &chip)){ //探测到hdmi；
-            if (!k230_set_dtb_env("dtb", "hdmi_dtb"))
-                return 0;
+            return k230_set_dtb_env("dtb", "hdmi_dtb");
         }
 	}
     //探测失败默认lcd;
-    ret = k230_set_dtb_env("dtb", "lcd_dtb"); //默认lcd
-    if (ret)
-        ret = k230_set_dtb_env("dtb", "lcd_dtb");
-    return ret;
+    return k230_set_dtb_env("dtb", "lcd_dtb");//默认lcd；;
 }
 U_BOOT_CMD(
 	k230_set_dtb, CONFIG_SYS_MAXARGS, 0, do_k230_set_dtb,
@@ -559,7 +542,12 @@
 
 static int do_2_burn_mode(struct cmd_tbl *cmdtp, int flag, int argc, char *const argv[])
 {
-    enter_to_usb_burn_mode();
+    //int ret = 0;
+    // k230_detect_display();
+    // return 0;
+    writel(0x5aa5a55a, (void*)0x80230000);
+    flush_dcache_range(0x80230000,0x80230000+4);
+    writel(0x10001, (void*)SYSCTL_BOOT_BASE_ADDR+0x60);
     return 0;
 }
 U_BOOT_CMD(
##### board/canaan/k230_canmv/board.c
--- a/board/canaan/k230_canmv/board.c
+++ b/board/canaan/k230_canmv/board.c
@@ -24,6 +24,45 @@
 #include <linux/delay.h>
 #include <dm.h>
 
+#ifdef CONFIG_K230_BARE_DISP_LOGO_RM69A10
+#define RM69A10_KEYBOARD_BACKLIGHT_GPIO 52U
+#define RM69A10_KEYBOARD_BACKLIGHT_GPIO_MASK \
+    (1U << (RM69A10_KEYBOARD_BACKLIGHT_GPIO - 32U))
+#define RM69A10_KEYBOARD_BACKLIGHT_IOMUX_IO52 (52U * 4U)
+#define RM69A10_KEYBOARD_BACKLIGHT_IOMUX_GPIO 0x0000018fU
+
+static void rm69a10_keyboard_backlight_early_off(void)
+{
+    u32 data;
+    u32 dir;
+
+    data = readl((void *)(GPIO_BASE_ADDR1 + 0x0));
+    data &= ~RM69A10_KEYBOARD_BACKLIGHT_GPIO_MASK;
+    writel(data, (void *)(GPIO_BASE_ADDR1 + 0x0));
+
+    writel(RM69A10_KEYBOARD_BACKLIGHT_IOMUX_GPIO,
+           (void *)(IOMUX_BASE_ADDR + RM69A10_KEYBOARD_BACKLIGHT_IOMUX_IO52));
+
+    dir = readl((void *)(GPIO_BASE_ADDR1 + 0x4));
+    dir |= RM69A10_KEYBOARD_BACKLIGHT_GPIO_MASK;
+    writel(dir, (void *)(GPIO_BASE_ADDR1 + 0x4));
+
+    data = readl((void *)(GPIO_BASE_ADDR1 + 0x0));
+    data &= ~RM69A10_KEYBOARD_BACKLIGHT_GPIO_MASK;
+    writel(data, (void *)(GPIO_BASE_ADDR1 + 0x0));
+}
+
+int board_init(void)
+{
+    rm69a10_keyboard_backlight_early_off();
+    return 0;
+}
+
+void quick_boot_board_init(void)
+{
+    rm69a10_keyboard_backlight_early_off();
+}
+#endif
 
 sysctl_boot_mode_e sysctl_boot_get_boot_mode(void)
 {
##### arch/riscv/dts/k230_canmv_v3.dts
--- a/arch/riscv/dts/k230_canmv_v3.dts
+++ b/arch/riscv/dts/k230_canmv_v3.dts
@@ -163,8 +163,8 @@
 		// UART3_RXD
 		(IO51) ( 1<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 1<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
 
-		// ext jp
-		(IO52) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 1<<IE | 1<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
+		// RM69A10 keyboard backlight, keep input pulldown until userspace enables PWM4
+		(IO52) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 1<<IE | 0<<OE | 0<<PU | 1<<PD | 7<<DS | 1<<ST )
 		// ext jp
 		(IO53) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 1<<IE | 1<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
 
@@ -187,7 +187,3 @@
 		>;
 	};
 };
-/* Enable I2C3 (IO36=SCL, IO37=SDA) to detect LT9611 HDMI bridge at 0x3b */
-&i2c3 {
-	status = "okay";
-};
##### arch/riscv/dts/k230d.dtsi
--- a/arch/riscv/dts/k230d.dtsi
+++ b/arch/riscv/dts/k230d.dtsi
@@ -58,7 +58,7 @@
 		(IO47) ( 0<<SEL | 0<<SL | 0<<MSC | 0<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
 		(IO50) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 0<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
 		(IO51) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 0<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
-		(IO52) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 0<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
+		(IO52) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 1<<IE | 0<<OE | 0<<PU | 1<<PD | 7<<DS | 1<<ST )
 		(IO53) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 0<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
 		(IO54) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 0<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
 		(IO55) ( 0<<SEL | 0<<SL | BANK_VOLTAGE_IO50_IO61<<MSC | 0<<IE | 0<<OE | 0<<PU | 0<<PD | 7<<DS | 1<<ST )
```

## Their Linux patches 0027, 0038 and 0051

From `k230_bsp/overlay/buildroot-overlay/linux/`, verbatim. What each is
for, in this change's terms:

- **0027** `panel-canaan-universal-enable-reset-in-prepare`: uncomments the
  reset pulse in `canaan_panel_prepare()` (10/20/20 ms) and adds a 200 ms
  wait before the init sequence. This project's `nix/kernel.nix` did the
  equivalent independently.
- **0038** `reserve-rm69a10-uboot-logo-fb`: a `reserved-memory` node,
  `framebuffer@1f000000`, 4 MiB, `no-map`, in their board DTS. The address
  is LILYGO's `#define`; whether it fits *this* system's memory is the
  subject of `docs/evidence/stage1-memory-map.md`.
- **0051** `preserve-rm69a10-boot-splash-handoff`: two static device-tree
  booleans — `canaan,skip-fbdev-setup` on the display node and
  `canaan,preserve-boot-splash` on the panel — read at probe. With the
  first, `canaan_drv.c` skips `drm_fbdev_generic_setup()`; with the second,
  the panel driver requests its reset and backlight GPIOs `GPIOD_ASIS` and
  does not pulse reset at probe. It does not touch `prepare()`, so their
  prepare (with 0027) still pulses reset and replays the sequence at the
  first enable; and being static, a boot where the logo failed to load is a
  boot where nothing lights the panel. The design keys the same two
  mechanisms on a runtime `/chosen` flag instead.

```diff
--- a/drivers/gpu/drm/panel/panel-canaan-universal.c	2026-06-16 12:32:07.148309370 +0000
+++ b/drivers/gpu/drm/panel/panel-canaan-universal.c	2026-06-16 12:32:53.751120119 +0000
@@ -125,26 +125,25 @@
 {
 	struct canaan_panel *p = panel_to_canaan_panel(panel);
 
-	// set power on
 	if (p->power_on) {
-		// gpiod_direction_output(p->power_on, 1);
-		// gpiod_set_value_cansleep(p->power_on, 1);
+		gpiod_set_value_cansleep(p->power_on, 1);
+		panel_simple_sleep(10);
 	}
-	// set rst
 	if (p->reset) {
-		// gpiod_direction_output(p->reset, 1);
-
-		// gpiod_set_value_cansleep(p->reset, 1);
-		// panel_simple_sleep(200);
-		// gpiod_set_value_cansleep(p->reset, 0);
-		// panel_simple_sleep(200);
-		// gpiod_set_value_cansleep(p->reset, 1);
-		// panel_simple_sleep(200);
+		gpiod_set_value_cansleep(p->reset, 1);
+		panel_simple_sleep(10);
+		gpiod_set_value_cansleep(p->reset, 0);
+		panel_simple_sleep(20);
+		gpiod_set_value_cansleep(p->reset, 1);
+		panel_simple_sleep(20);
 	}
 
+	msleep(200);
+
 	if (p->init_set_v1_flag) {
-		// config screen
+		dev_info(panel->dev, "prepare: sending init commands\n");
 		panel_simple_xfer_dsi_cmd_seq(p, p->init_seq_v1);
+		dev_info(panel->dev, "prepare: init commands sent\n");
 	}
 	return 0;
 }

From 2a1c0102030405060708090a0b0c0d0e0f101112 Mon Sep 17 00:00:00 2001
From: Codex <codex@local>
Date: Thu, 30 Jul 2026 00:00:00 +0000
Subject: [PATCH] riscv: dts: canaan: reserve RM69A10 U-Boot logo framebuffer

Reserve the physical framebuffer used by the RM69A10 U-Boot logo path so
the early Linux allocator does not overwrite the scanout buffer before the
DRM driver takes ownership of the display.
---
 arch/riscv/boot/dts/canaan/k230-canmv-rm69a10.dts | 11 +++++++++++
 1 file changed, 11 insertions(+)

diff --git a/arch/riscv/boot/dts/canaan/k230-canmv-rm69a10.dts b/arch/riscv/boot/dts/canaan/k230-canmv-rm69a10.dts
index c59d671..f0d1fb1 100644
--- a/arch/riscv/boot/dts/canaan/k230-canmv-rm69a10.dts
+++ b/arch/riscv/boot/dts/canaan/k230-canmv-rm69a10.dts
@@ -21,6 +21,17 @@ / {
 		device_type = "memory";
 		reg = <0x0 0x0 0x0 0x20000000>;
 	};
+
+	reserved-memory {
+		#address-cells = <2>;
+		#size-cells = <2>;
+		ranges;
+
+		uboot_logo_fb: framebuffer@1f000000 {
+			reg = <0x0 0x1f000000 0x0 0x00400000>;
+			no-map;
+		};
+	};
 	sound {
 		status                      = "okay";
 		compatible                  = "canaan,k230-audio-inno";

--- a/arch/riscv/boot/dts/canaan/display-rm69a10-568x1232.dtsi
+++ b/arch/riscv/boot/dts/canaan/display-rm69a10-568x1232.dtsi
@@ -2,6 +2,9 @@
 &vo {
 	vth_line = <10>;
 };
+&display {
+	canaan,skip-fbdev-setup;
+};
 &dsi {
 	ports {
 		port@1 {
@@ -17,6 +20,7 @@
 		panel-width-mm = <65>;
 		panel-height-mm = <145>;
 		panel-dsi-lane = <2>;
+		canaan,preserve-boot-splash;
 		canaan,dsi-command-backlight;
 		default-brightness = <254>;
 		max-brightness = <255>;
--- a/drivers/gpu/drm/canaan/canaan_drv.c
+++ b/drivers/gpu/drm/canaan/canaan_drv.c
@@ -247,7 +247,10 @@
 		goto finish_poll;
 	}
 
-	drm_fbdev_generic_setup(drm_dev, 32);
+	if (of_property_read_bool(dev->of_node, "canaan,skip-fbdev-setup"))
+		dev_info(dev, "skip DRM fbdev setup to preserve boot splash\n");
+	else
+		drm_fbdev_generic_setup(drm_dev, 32);
 	DRM_DEV_INFO(dev, "Canaan K230 DRM driver register successfully\n");
 
 	return 0;
--- a/drivers/gpu/drm/panel/panel-canaan-universal.c
+++ b/drivers/gpu/drm/panel/panel-canaan-universal.c
@@ -72,6 +72,7 @@
 	u32 max_brightness;
 	bool dsi_command_backlight;
 	bool prepared;
+	bool preserve_boot_splash;
 
 	struct panel_cmd_seq *init_seq_v1;
 };
@@ -373,30 +374,44 @@
 
 	mipi_dsi_set_drvdata(dsi, ctx);
 
-	ctx->reset = devm_gpiod_get(&dsi->dev, "dsi_reset", GPIOD_OUT_LOW);
+	ctx->preserve_boot_splash =
+		of_property_read_bool(dsi->dev.of_node,
+				      "canaan,preserve-boot-splash");
+
+	ctx->reset = devm_gpiod_get(&dsi->dev, "dsi_reset",
+				    ctx->preserve_boot_splash ?
+				    GPIOD_ASIS : GPIOD_OUT_LOW);
 	if (IS_ERR(ctx->reset)) {
 		dev_err(&dsi->dev, "Couldn't get our reset GPIO, error: %ld\n",
 			PTR_ERR(ctx->reset));
 		ctx->reset = NULL;
+	} else if (ctx->preserve_boot_splash) {
+		dev_info(&dsi->dev,
+			 "probe: preserving boot splash, skip reset GPIO toggle\n");
 	} else {
 		gpiod_direction_output(ctx->reset, 1);
 		panel_simple_sleep(200);
 		gpiod_set_value_cansleep(ctx->reset, 0);
 		panel_simple_sleep(200);
 		gpiod_set_value_cansleep(ctx->reset, 1);
 	}
 
 	ctx->power_on =
-		devm_gpiod_get(&dsi->dev, "backlight_gpio", GPIOD_OUT_LOW);
+		devm_gpiod_get(&dsi->dev, "backlight_gpio",
+			       ctx->preserve_boot_splash ?
+			       GPIOD_ASIS : GPIOD_OUT_LOW);
 	if (IS_ERR(ctx->power_on)) {
 		dev_err(&dsi->dev,
 			"Couldn't get our backlight_gpio GPIO, error: %ld\n",
 			PTR_ERR(ctx->power_on));
 		ctx->power_on = NULL;
+	} else if (ctx->preserve_boot_splash) {
+		dev_info(&dsi->dev,
+			 "probe: preserving boot splash, leave backlight GPIO unchanged\n");
 	} else {
 		gpiod_direction_output(ctx->power_on, 1);
 	}
 
 	ctx->dsi = dsi;
 	ctx->desc = of_device_get_match_data(&dsi->dev);
```

For completeness, their Linux DTS for the panel (patch 0031) carries the
same 13-command sequence as their U-Boot, at 49.5 MHz:

```
39 00 02 FE FD / 39 00 02 80 FC / 39 00 02 FE 00 / 39 00 05 2A 00 00 02 37 /
39 00 05 2B 00 00 04 CF / 39 00 05 31 00 03 02 34 / 39 00 05 30 00 00 04 CF /
05 00 01 12 / 15 00 02 35 00 / 15 00 02 51 FE / 05 78 01 11 / 05 0A 01 29 /
15 00 02 3A 77
```

## Caveat on provenance

`docs/research/linux-on-t-display-k230.md` §3 records that this series is
AI-authored and that its commit messages misdescribe several hunks (the
`DPI_COLOR_CODING` "YCbCr → RGB" claim, the "reset only lane 0 and 1"
comment). The diff above is what the code does; the messages are not
evidence of anything. What is evidence is that LILYGO ships release images
built from this tree that light this panel from U-Boot — on their numbers.
