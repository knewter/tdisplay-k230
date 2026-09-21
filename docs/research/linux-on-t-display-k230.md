# Linux on the LILYGO T-Display-K230: prior art

Researched 2026-09-21. Question: has anyone run Linux on this board with the
RM69A10 panel lit, and what is the state of the art for K230 Linux MIPI DSI?

## 1. Direct answer: yes, it is solved — three times, independently

This is **not** an unexplored problem, and the working fixes are public. The
premise that "nobody has run Linux with this panel" is wrong, but so is the
assumption that it was solved long ago: **everything below landed between
2026-07-27 and 2026-09-03.** Anything written before mid-2026 (including
remlab.net's widely-cited Debian-on-K230 piece) says K230 Linux display is
broken, and that was true when it was written.

Three codebases light the RM69A10 under Linux DRM on this exact board:

| Who | Repo | What it is | Panel |
| --- | --- | --- | --- |
| Lewis Xu (LILYGO lead dev) | [`lewisxhe/k230-t-display-linux-patches`](https://github.com/lewisxhe/k230-t-display-linux-patches) | Standalone patch series, 2026-07-29 | works |
| LILYGO (official) | [`Xinyuan-LilyGO/T-Display-K230`](https://github.com/Xinyuan-LilyGO/T-Display-K230) | Full Buildroot BSP + LVGL launcher | works |
| Thomas Göttgens | [`caveman99/k230-linux`](https://github.com/caveman99/k230-linux) | Debian trixie riscv64, Meshtastic handheld | works |

**LILYGO does publish a Linux BSP** — it is just in a *different repo* from
the CanMV one, with 3 stars, and the LILYGO wiki does not link it. The wiki
points only at `kendryte/k230_sdk` and MaixPy, and the old wiki URL now 404s.
That stale wiki is most likely why this looked like a dead end.

Verified directly: the repo exists, contains `k230_bsp/`, `k230_launcher/`,
`k230_linux_sdk/` (submodule) and `scripts/`, and its README states support
for the "RM69A10 AMOLED MIPI DSI panel" with "AMOLED remains the default
display path".

### The finding that matters most for us

**Our leading hypothesis — that the 4-lane-only PHY path is why the panel is
dark — is almost certainly wrong.** Three independent lines of evidence:

1. **`caveman99/k230-linux` lights this exact panel with `canaan_phy.c` and
   `canaan_dsi.c` completely untouched.** Its `DISPLAY-BRINGUP.md` says
   verbatim: *"Two hunks, both in `drivers/gpu/drm/canaan/canaan_drv.c` ...
   `canaan_vo.c`, `canaan_dsi.c`, `canaan_plane.h` are stock."* It runs stock
   `k230_dsi_config_4lan_phy()` against a 2-lane RM69A10 and gets a login
   prompt on the glass.

2. **Canaan's own RT-Smart blob ignores the lane count when configuring the
   PHY.** I disassembled `libvo.a` from LILYGO's CanMV repo (see §3) — the
   dispatcher `dwc_mipi_phy_config()` never reads the `phy_lan_num` field and
   unconditionally calls `k230_dsi_config_4lan_phy()`. LILYGO's RT-Smart
   `rm69a10.c` does set `phy_lan_num = K_DSI_2LAN`, but **that assignment is
   dead code.** The shipped RT-Smart firmware that lights this panel does so
   through the 4-lane PHY routine.

3. **Every CanMV reference board is also a 2-lane panel through the 4-lane PHY
   path.** Contrary to the brief, `display-st7701-480x800.dtsi` upstream at our
   pinned revision carries `panel-dsi-lane = <2>`, not 4 (verified against
   pristine `ruyisdk/linux-xuantie-kernel@7d4e1f4`). ILI9806 is 2-lane too.
   Only the EVB's HX8399 is 4-lane. So "2-lane link, 4-lane PHY" is the
   vendor's normal, shipping configuration.

The real root cause is far more likely the one caveman99 documents, and it
explains our soft lockup exactly. See §5.

## 2. Concrete leads

### `caveman99/k230-linux` — the strongest lead

- Repo: https://github.com/caveman99/k230-linux
- Bring-up writeup: https://raw.githubusercontent.com/caveman99/k230-linux/main/DISPLAY-BRINGUP.md
- The whole kernel diff: https://raw.githubusercontent.com/caveman99/k230-linux/main/patches/kernel.patch

Debian trixie riscv64, built for a Meshtastic handheld. Its status table claims
working: boot chain, RM69A10 AMOLED via `canaan-drm` at RGB565, GT9895 touch
via `goodix_berlin`, LR2021 radio. WiFi (RTL8189FTV) enumerates but the driver
port is pending.

**Its DTS description matches our tree almost exactly** — `canaan/k230-tdisplay.dts`
including `display-rm69a10-568x1232.dtsi`, DIS_EN on IO35 as a fixed regulator,
LCD_EN IO25 hogged high, LCD_RST IO22 `dsi_reset-gpios` ACTIVE_HIGH. It says
of that wiring: *"DTS wiring (unchanged and correct)"*. That is independent
confirmation that our device tree is not the bug.

The two display hunks, quoted from `patches/kernel.patch`:

```c
/* canaan_drm_platform_probe, after pm_runtime_enable */
pm_runtime_get_sync(disp_dev);
```
> the only pm_runtime_get was in canaan_drm_open (userspace open of
> /dev/dri/card0); the in-kernel fbdev boot modeset never opens the device,
> so nothing held the ref -> genpd suspended the display-subsystem ~2s in ->
> **every VO/DSI register read 0xffffffff** and the timing generator died at
> ~5 frames.

```c
/* canaan_drm_bind */
drm_fbdev_generic_setup(drm_dev, 16);   /* was 32 */
```
> The K230 OSD has no 32-bit-opaque format: 32bpp is always ARGB8888 with
> per-pixel alpha, and the mixer multiplies per-pixel * global alpha. fbcon
> (and any XRGB8888 client) clears the buffer to alpha=0, so the whole plane
> composites transparent and only the VO background shows.

That second hunk is the same defect our `docs/evidence/panel-dark.md` already
identified from the `bpp/depth value of 32/24 not supported` boot error, and
the same one reported against a stock CanMV board in
[`kendryte/k230_linux_sdk#33`](https://github.com/kendryte/k230_linux_sdk/issues/33).
Note their explanation is subtler than ours: it is not only that fbdev setup
fails, it is that 32bpp would composite *transparent* even if it succeeded.

The same file also carries non-display K230 fixes worth knowing about: S-mode
misaligned-access emulation (`csr_read(CSR_TVAL)` instead of `mtval`),
skipping the unaligned-access benchmark, and `SDHCI_QUIRK_BROKEN_ADMA` for
`sdhci-of-kendryte`.

### `Xinyuan-LilyGO/T-Display-K230` — the official BSP

- Repo: https://github.com/Xinyuan-LilyGO/T-Display-K230
- Patch queue: `k230_bsp/overlay/buildroot-overlay/linux/`, 29 patches numbered
  0025–0064, plus `linux.fragment`.
- Defconfig: `k230_canmv_t_display_rm69a10_defconfig`

Directly relevant patches (filenames verified from the directory listing):

| Patch | What |
| --- | --- |
| `0025-drm-canaan-fix-2lan-dsi-phy-with-timeout.patch` | 2-lane PHY path + bounded PHY_STATUS loops |
| `0026-drm-canaan-vo-add-xrgb8888-format.patch` | adds XR24 to the VO plane formats |
| `0027-panel-canaan-universal-enable-reset-in-prepare.patch` | moves panel reset into `prepare()` |
| `0029-drm-canaan-fix-video-mode-to-burst.patch` | `VID_MODE_CFG` 0xbf02 → 0x3f02 |
| `0030-drm-canaan-fix-xrgb8888-opaque-and-rb-swap.patch` | their answer to the alpha trap |
| `0031/0032-riscv-dts-canaan-add-rm69a10-*` | the panel dtsi and board dts |
| `0043-drm-canaan-defer-vo-config-load-to-vblank.patch` | shadow-register latching |
| `0049-...-add-rm69a10-dsi-backlight.patch` | DCS backlight |
| `0051-...-preserve-rm69a10-boot-splash-handoff.patch` | U-Boot logo handoff |

**Caveat, and it is a real one.** These patches are authored by
`Hermes Agent <agent@nousresearch.com>` — an AI agent — and several commit
messages are demonstrably wrong about their own diffs (details in §3). The
*code* is validated by shipped images; the *reasoning* in the messages is not
trustworthy. Read the diffs, not the log.

LILYGO also publishes prebuilt SD-card images at
https://github.com/Xinyuan-LilyGO/T-Display-K230/releases — tags v0.1.0,
v0.2.0, v0.2.2 and v0.2.4, each with downloadable assets (verified the tags
and that assets exist; the page's asset list would not render for me, so the
exact filenames are second-hand). **Flashing one of these is the fastest way
to confirm the panel can be lit under Linux on our specific unit**, before
spending any more time on the driver.

### `lewisxhe/k230-t-display-linux-patches`

https://github.com/lewisxhe/k230-t-display-linux-patches — 2026-07-29, the
standalone series that became the BSP above. Notably it targets **kernel commit
`7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`** — byte-identical to the revision
our `nix/kernel.nix` pins. Its patches should apply to our tree directly.

### `vicliu624/t-display-k230-vision-platform`

https://github.com/vicliu624/t-display-k230-vision-platform — Buildroot with a
native Wayland desktop (labwc, greetd) on the V1.3 keyboard variant, Linux on
CPU0 and RT-Smart on CPU1. Rebases Lewis's display patches under a `lewis-`
prefix. **Thin/risky:** 0 stars, heavy AI involvement, and its own README warns
of a bricked boot after package installs replaced CPU0 libs with RVV builds.
Useful only as corroboration that Lewis's series is the common ancestor.

### Canaan's official Linux LCD porting guide

The URL in most search results is dead. The live one:

- https://www.kendryte.com/k230_linux/zh/main/advanced_adaptation_guide/lcd_adaptation_doc.html
- Source markdown: https://github.com/kendryte/k230_linux_sdk_docs/blob/main/zh/advanced_adaptation_guide/lcd_adaptation_doc.md

It documents `panel-dsi-lane` as a **required** property with legal values
`2/4` (「DSI 数据 lane 数量（2/4）」), and uses the 2-lane ST7701 as its
worked example. Adding a panel is a device-tree-only exercise: `compatible =
"canaan,universal"` plus `panel-init-sequence` plus `display-timings`. So
2-lane is a documented, supported Linux configuration, not an unexplored path.

Canaan also ships a timing calculator whose `lane_num` field **defaults to 2**:
https://kendryte-download.canaan-creative.com/developer/common/K230_MIPI_DSI_Connector_Info_Generator.html
Its clock formula `mipiClock = pclk * 3 * 8 / lane_num; phyClock = mipiClock / 2`
is identical to `canaan_dsi_clk_cfg()`.

### Other dark-panel reports (context, no fixes)

- [`kendryte/k230_linux_sdk#33`](https://github.com/kendryte/k230_linux_sdk/issues/33) — LCKFB board, DSI attaches, then `bpp/depth value of 32/24 not supported` → `Failed to setup generic emulation (ret=-22)`. Vendor replied "looks like a panel connection problem". Closed unfixed. This is the alpha/format trap.
- [`kendryte/k230_linux_sdk#3`](https://github.com/kendryte/k230_linux_sdk/issues/3) — `failed to bind 90850000.dsi` (-19), 01Studio + LT9611.
- [Canaan Q&A 10010000000010182](https://www.kendryte.com/answer/questions/10010000000010182) — LuShan Pi, Linux SDK: backlight on, nothing on glass, `v4l2-drm` captures fine. Vendor answer: check your FPC. Unresolved.
- [Canaan Q&A 10010000000003439](https://www.kendryte.com/answer/questions/10010000000003439) — Canaan support posting a complete 2-lane ST7701 dtsi for the old dual-system SDK, conceding *"the linux+rt-smart SDK just doesn't have it; you have to add the driver yourself"*.
- [remlab.net, Debian on K230-CanMV](https://www.remlab.net/op/k230-canmv-debian.shtml) — *"HDMI is meant to be driven by the RTOS. The vendor kernel does accordingly not provide the necessary Linux DRM drivers."* **Dated and overtaken by events**; cited here because it is probably the source of the folklore that K230 Linux display is impossible.

### Mainline status

**No upstream DRM driver for K230 display exists, and none is in flight.**
Mainline has only initial SoC bring-up (clk, pinctrl, reset); `arch/riscv/boot/dts/canaan/`
is K210-only and there is no `SOC_CANAAN_K230`. Canaan's out-of-tree
`drivers/gpu/drm/canaan/` in the vendor 6.6 kernel is the only option.
See the LKML series ["riscv: add initial support for Canaan Kendryte K230"](https://lkml.iu.edu/hypermail/linux/kernel/2403.0/03370.html),
which boots to busybox with no display. This matches our own
`docs/evidence/why-xuantie-kernel.txt`.

caveman99 flags both of their fixes as dri-devel upstreaming candidates, but
has not posted them. *No mailing-list submission found.*

## 3. Lane-count handling in the K230 DSI PHY — what is actually true

This is the part the brief got wrong, so it is worth being precise. Two
separate things are called "lanes":

**The DSI host link** *is* lane-aware and always has been.
`canaan_dsi_set_lan_num()` writes `PHY_IF_CFG` = 0x2800 / 0x2801 / 0x2803 for
1 / 2 / 4 lanes, and `canaan_dsi_clk_cfg()` divides by `device->lanes` when
computing the PLL rate. `panel-canaan-universal.c` reads `panel-dsi-lane` into
`dsi->lanes`. All correct, all honouring 2 lanes.

**The D-PHY is not lane-aware, by design, everywhere.**
`k230_dsi_config_4lan_phy()` is called unconditionally, and it brings up *both*
of the K230's two 2-lane D-PHY instances (`k230_dsi_phy0_config()` then
`k230_dsi_phy1_config()`, selected via bit 22 of `base + 0x400 + TXDPHY_CFG1`).

I confirmed the same is true of the closed-source RT-Smart side. From
`libvo.a` (LILYGO's CanMV repo, `canmv_k230/src/rtsmart/mpp/kernel/lib/libvo.a`),
disassembling `dwc_mipi_phy_config` out of `kd_vo_reg.o`:

```
  2a: ld a5,-0x18(s0);  lw a4,0x4(a5)    # m
  30: ld a5,-0x18(s0);  lw a1,0x0(a5)    # n
  36: ld a5,-0x18(s0);  lw a5,0x8(a5)    # voc
  40: ld a5,-0x18(s0);  lw a5,0x10(a5)   # hs_freq
  4e: call k230_dsi_config_4lan_phy
```

`k_vo_mipi_phy_attr` is `{ n@0x0, m@0x4, voc@0x8, phy_lan_num@0xc, hs_freq@0x10 }`.
**Offset 0xc — `phy_lan_num` — is never loaded.** The archive exports
`k230_dsi_config_4lan_phy`, `k230_dsi_phy0_config` and `k230_dsi_phy1_config`
and contains no 2-lane variant at all. So `phy_lan_num = K_DSI_2LAN` in
LILYGO's `rm69a10.c` has no effect on hardware.

**LILYGO's Linux `k230_dsi_config_2lan_phy()` is nearly identical to the
4-lane one.** From `0025-drm-canaan-fix-2lan-dsi-phy-with-timeout.patch`: it
still calls both `k230_dsi_phy0_config()` and `k230_dsi_phy1_config()`, and
still waits for `PHY_STATUS == 0x1fbd` twice. The *only* register difference
is `PHY_RSTZ` written as `0x5` then `0x7`, instead of `0xd` then `0xf`. In the
Synopsys DWC DSI host, `PHY_RSTZ` is `{bit0 shutdownz, bit1 rstz, bit2
enableclk, bit3 forcepll}` — so the actual change is **clearing
`phy_forcepll`, not masking any lanes.** The patch's own inline comment
("2-lane: reset only lane 0 and 1") is wrong; `PHY_RSTZ` has no per-lane bits.
The patch even concedes the point in a comment: *"Hardware reports 0x1fbd
regardless of lane config."*

Two more corrections to that patch's commit message, both verified against the
diff and against the stock source:

- It claims `DPI_COLOR_CODING` goes from "YCbCr 4:2:2 (0x105)" to "RGB888
  (0x100)". The diff actually writes **0x005**, and in DWC encoding
  `color_coding = 5` is *already* 24-bit RGB888. Stock 0x105 only additionally
  sets bit 8 (`loosely18`), which is meaningless outside 18-bit modes. That
  hunk is close to a no-op.
- `0029-...-fix-video-mode-to-burst.patch` changes `VID_MODE_CFG` 0xbf02 →
  0x3f02. Bits[1:0] are `0b10` = burst mode in **both**. Stock is already
  burst; the patch only clears bit 15.

### The one genuine numeric divergence: `vco_cntrl`

I derived this independently before finding LILYGO's patch, and the two agree,
which is the strongest corroboration in this document.

LILYGO's working RT-Smart `connector_info_list[]` entry
(`canmv_k230/src/rtsmart/mpp/userapps/src/connector/mpi_connector.c`):

```c
{ "rm69a10", 0, 0, BACKGROUND_BLACK_COLOR, 9, 14,
  K_DSI_2LAN, K_BURST_MODE, K_VO_LP_MODE,
  { 4, 97, 0x19, 0x96 },                                    // { n, m, voc, hs_freq }
  { 39600, 475200, 788, 568, 40, 140, 40, 1268, 1232, 4, 16, 16 },
  RM69A10_MIPI_2LAN_568X1232_60FPS },
```

Working through `canaan_dsi_clk_cfg()` by hand for 39600 kHz at 2 lanes:
`div = 15`, `clk_freq = 39600`, `phy_clk_freq = 39600*3*8/2/2 = 237600`, which
falls in the `< 330000` bucket giving `voc = 0x17`; then `voc_freq = 475200`,
and the divider search lands on `m = 99, n = 5`, passed as `m-2 = 97, n-1 = 4`.

So **the Linux driver already computes exactly the vendor's `m = 97, n = 4`,
and `hsfreq` is the same hardcoded 0x96. The single difference in the entire
PHY setup is `vco_cntrl`: Linux derives 0x17, the vendor uses 0x19.**
`voc >> 4` is 1 either way, so the PLL dividers are unaffected — only the VCO
range select bits differ. LILYGO's patch resolves this by bluntly overriding
the computed values in `canaan_dsi_encoder_enable()`:

```c
/* Override PHY with RT-Smart validated params for 445.5 Mbps, 2-lane */
k230_dsi_config_2lan_phy(dsi, 97, 4, 0x19, 0x96);
```

I sanity-checked the ladder against the other panels: for HX8399
(74250 kHz, 4 lanes) the algorithm reproduces the vendor's `{15, 295, 0x17, 0x96}`
exactly, including `voc`. For LT9611 at 148500 kHz the vendor uses 0x09 where
the ladder gives 0x07 — the same +2 offset as RM69A10. *I could not find
documentation for what the low nibble of `vco_cntrl` selects on this PHY, so I
cannot say whether 0x17 is actually wrong or merely different.*

### Nothing, anywhere, ever tells an RM69A10 its lane count

Worth stating plainly, because it closes the lane question from the panel's
side as well as the SoC's. The RM69A10 has a `0xB2` PAD_CONTROL command with
defined constants `RM69A10_DSI_2_LANE (0x10)` and `RM69A10_DSI_4_LANE (0x00)`.
**That write is commented out in every ESP-IDF variant of the driver** —
LILYGO's, Espressif's, xiaozhi's, jstockdale's — and it does not appear in any
K230 init sequence either, ours included (our dtsi sends `3a 77` and no `b2`).
Every working implementation relies on the panel's power-on 2-lane default.

So the panel is never configured for a lane count, and the K230 D-PHY is never
configured for one either. The only place the number is honoured is the DSI
host's `PHY_IF_CFG`, which our tree already programs correctly from
`panel-dsi-lane = <2>`.

### On the `0x1fbd` wait

Decoding `PHY_STATUS` = 0x1fbd against the DWC MIPI-DSI host register gives
`phy_lock`, `stopstateclk`, and `stopstate`/`ulpsactivenot` set for **all four
lanes** — i.e. the constant bakes in a 4-lane expectation regardless of
`panel-dsi-lane`. *This decode is my/the research agent's reading of the
standard Synopsys register layout, not something a Canaan document states.* It
is consistent with the driver bringing up both PHY instances unconditionally,
and with LILYGO's comment that the value is reported regardless of lane config.

Also worth noting in stock code: `canaan_dsi_encoder_enable()` calls
`canaan_dsi_clk_cfg()` — which runs the PHY config *and* both spins — **before**
`canaan_dsi_set_lan_num()`. So `PHY_IF_CFG` still holds its reset value during
the wait.

## 4. Is there an RM69A10 Linux panel driver?

**No, and nobody needs one.** All three working ports drive it through
Canaan's generic `compatible = "canaan,universal"` panel driver
(`drivers/gpu/drm/panel/panel-canaan-universal.c`), fed a DCS byte blob via the
`panel-init-sequence` device tree property — exactly what our
`display-rm69a10-568x1232.dtsi` already does.

There is no `panel-raydium-rm69a10.c` in mainline or in any tree searched
(this includes an exhaustive enumeration of all branches, tags and 13 forks of
`ruyisdk/linux-xuantie-kernel`). The nearest mainline relatives are
`panel-raydium-rm68200.c`, `panel-raydium-rm67191.c` and
`panel-visionox-rm69299.c`; none is this controller.

Outside Linux the controller is well served, all on ESP32-P4 via `esp_lcd`,
driving the same 568x1232 AMOLED:

- [`espressif/esp-claw`](https://github.com/espressif/esp-claw/blob/74b18700a1d6c40de472bfc71c19e49356ca1cc0/application/edge_agent/boards/lilygo/lilygo_t_display_p4_v1/esp_lcd_rm69a10.c) — `esp_lcd_rm69a10.c`, Apache-2.0, 2026. Lane count comes from `board_peripherals.yaml` (`data_lanes: 2`, `lane_bit_rate_mbps: 1000`), not the driver. Adds a chip-ID check (DCS `0xA1` must return `0x01`) — **a cheap liveness probe we could borrow**, given our RDDPM read times out. Not published to the ESP Component Registry.
- [`jstockdale/T-Display-P4`](https://github.com/jstockdale/T-Display-P4/tree/adsb) — runtime-detects RM69A10 vs HI8561.
- Arduino_GFX hardcodes `.num_data_lanes = 2` in `Arduino_ESP32DSIPanel.cpp` and leaves the default 750 Mbps/lane, where LILYGO and Espressif both use 1000.

One porting hazard if borrowing an init table across platforms: ESP-IDF
defaults to RGB565 (`3a 75`), whereas both K230 paths — RT-Smart and the Linux
DT — use RGB888 (`3a 77`). Ours already sends `3a 77`, which is correct.

Our RM69A10 dtsi and `k230-tdisplay.dts` are **our own additions**: I verified
against pristine `ruyisdk/linux-xuantie-kernel@7d4e1f4` that
`arch/riscv/boot/dts/canaan/` upstream contains only the hx8399, ili9806 and
st7701 dtsi files. LILYGO's `0031`/`0032` patches add their own equivalents.

Their timings differ from ours, which is worth knowing. From `0031`
(fetched and verified):

| | ours (= RT-Smart `connector_info_list[]`) | LILYGO `0031` |
| --- | --- | --- |
| clock-frequency | 39 600 000 | 49 500 000 |
| hfront / hback / hsync | 40 / 140 / 40 | 100 / 40 / 40 |
| vfront / vback / vsync | 16 / 16 / 4 | 4 / 16 / 16 |
| htotal x vtotal | 788 x 1268 → 39.6 Hz | 748 x 1268 → 52.2 Hz |

Both are legal `594000/N` pixel clocks (N = 15 and 12). Ours reproduces the
vendor RT-Smart entry exactly; LILYGO retimed for a higher refresh rate, which
is consistent with their `0042-drm-canaan-rm69a10-use-auto-phy-high-refresh.patch`.
Their vfront/vsync also look transposed relative to the RT-Smart values. This
is a difference to be aware of, not evidence that ours is wrong.

Minor: their `0031` declares touch as `compatible = "goodix,nottingham"`,
where we bind `goodix_berlin`. Ours already works, so this is informational.

## 5. What I would do next

The evidence points away from the PHY and at runtime PM. Ordered by
cost/benefit:

1. **Read the PHY_STATUS value we already log.** Our bounded-loop patch prints
   `PHY_STATUS 0x%x != 0x1fbd after %d tries`. If that value is **`0xffffffff`**,
   the case is closed: the display power domain was suspended out from under
   us, every VO/DSI register reads all-ones, and the equality can never hold.
   That is precisely caveman99's documented failure mode, and it explains the
   soft lockup, the dark panel, and the DCS read timeout with a single cause.
   This costs one boot and needs no new code.

2. **Optionally, flash a LILYGO release image to a spare SD card.** This
   settles "can this panel be lit under Linux on *our* unit at all" in one
   boot, independently of our tree, and gives a known-good dmesg to diff
   against. Cheap, and it removes hardware doubt from everything after it.

3. **Apply caveman99's two hunks** to `canaan_drv.c` — `pm_runtime_get_sync(disp_dev)`
   in `canaan_drm_platform_probe()` after `pm_runtime_enable()`, and
   `drm_fbdev_generic_setup(drm_dev, 16)`. This is the smallest known path to a
   lit panel, it is from an independent author outside LILYGO who explains
   *why*, and it requires no changes to `canaan_phy.c` or `canaan_dsi.c` at all.

4. **Park the 2-lane PHY patch.** `nix/patches/canaan-dsi-2lane-phy-path.patch`
   is built on a hypothesis that the vendor's own working firmware contradicts
   (§1, §3). Keeping the bounded PHY_STATUS loop is still worthwhile — an
   unbounded spin is a genuine defect and LILYGO fixed it too — but the
   separate 2-lane code path should come out unless step 1 shows the PHY really
   is the problem. Its only substantive difference from the 4-lane path is
   clearing `phy_forcepll`, which is worth trying as a one-line experiment
   *after* step 2, not before.

5. **If the panel lights but looks wrong**, the ordered candidates from
   LILYGO's queue are `0043` (defer VO config load to vblank), `0030`/`0026`
   (XRGB8888 opaque + R/B swap, only if we want 32bpp rather than RGB565), and
   `0033` (RGB2YUV colour swap).

6. **Try `voc = 0x19`** only if 1-4 leave the PHY genuinely failing to lock.
   Both LILYGO and my independent derivation agree this is the one numeric
   divergence from the validated RT-Smart parameters, so it is a cheap, precise
   one-line test — but it is not supported by caveman99 running stock and
   working.

7. **Worth pulling regardless of display:** caveman99's non-display K230 fixes
   (S-mode misaligned emulation via `CSR_TVAL`, skipping the unaligned
   benchmark, `SDHCI_QUIRK_BROKEN_ADMA`) are in the same `patches/kernel.patch`
   and look relevant to a NixOS port.

A general caution: the LILYGO series is AI-authored and several of its commit
messages misdescribe their own diffs (§3). Read every hunk before adopting it.

## 6. Method and confidence

Strongest claims here rest on primary sources I fetched or ran myself: the
pristine kernel tree at our pinned revision, the `libvo.a` disassembly, and
the LILYGO and caveman99 patch bodies. Those are solid.

Weaker, and flagged as such where they appear: I have **not** booted any of
these images, so "works" means "the author says so and their diff is
coherent", not "verified on our hardware". GitHub's code search needs auth and
was unavailable throughout, and the unauthenticated REST API rate-limited us
partway, so negatives came from directory enumeration rather than a global
grep. Sourcegraph's index proved to be partial (it missed the entire
Xinyuan-LilyGO org on an `rm69a10` query), so it was used only as
corroboration. The load-bearing negative — that no 2-lane PHY function exists
anywhere in the vendor kernel lineage — comes from exhaustively enumerating
every branch, tag and fork of `ruyisdk/linux-xuantie-kernel`, plus the
`libvo.a` symbol table.
