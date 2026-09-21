# How LilyGO's RT-Smart firmware brings up the RM69A10, end to end

Read against our Linux path. Written 2026-09-21 from the vendor source in
`repo/canmv_k230/src/rtsmart/mpp/` plus disassembly of the prebuilt
`kernel/lib/libvo.a`, compared with the pristine kernel tree at
`/nix/store/pn7bm6ck5a3x6pnk1ng30hlf24qn85jx-source/`.

Everything below is either quoted source or disassembly I read. Where I am
inferring, it says so.

---

## The headline: we are sending the wrong panel's init sequence

`docs/evidence/rm69a10-init-sequence.md` records the sequence as coming from
"`rm69a10_568x1232_dsi_send()`". There is no function by that name. What was
actually transcribed is **`rm69a10_OLD_init()`**, and that function has **no
callers**.

```
$ grep -rn "rm69a10_OLD_init\|rm69a10_568x1232_init" repo/canmv_k230/src/rtsmart/mpp
kernel/connector/src/rm69a10.c:39:static void rm69a10_OLD_init(k_u8 test_mode_en)
kernel/connector/src/rm69a10.c:96:static void rm69a10_568x1232_init(k_u8 test_mode_en)
kernel/connector/src/rm69a10.c:100:    rt_kprintf("rm69a10_568x1232_init \n");
kernel/connector/src/rm69a10.c:345:			   rm69a10_568x1232_init(1);
kernel/connector/src/rm69a10.c:347:			   rm69a10_568x1232_init(0);
```

One definition, zero call sites. The live dispatcher is `rm69a10.c:342-348`:

```c
	if(info->type == RM69A10_MIPI_2LAN_568X1232_60FPS)
	   {
		   if(info->screen_test_mode)
			   rm69a10_568x1232_init(1);
		   else
			   rm69a10_568x1232_init(0);
	   }
```

and our panel is exactly that type — `mpi_connector.c:43` sets
`RM69A10_MIPI_2LAN_568X1232_60FPS` for the `"rm69a10"` entry.

### It is not merely unused, it is a different panel's sequence

`rm69a10_OLD_init()` (`rm69a10.c:41-61`) is a **byte-for-byte copy of
`hx8399_v2_init()`** (`hx8399.c:41-61`) — the Himax HX8399 1080x1920 panel.
Same twenty `k_u8 param*` arrays, same values, same order, same
`pag20[50]` blue test-pattern array, same `0xB9 0xFF 0x83 0x99` opener
(which is Himax's SETEXTC "password"). It is dead copy-paste left in the
file when the driver was forked from `hx8399.c`.

Our `nix/dts/display-rm69a10-568x1232.dtsi:54-75` ships that HX8399
sequence. Twenty commands, 297 payload bytes, verified byte-identical — to
the wrong panel.

### Confirmed on the vendor's own boot log

`docs/rtsmart-boot-log.txt` lines 71-82, captured from this board running
LilyGO's firmware:

```
rm69a10_power_on
rm69a10_power_reset
rm69a10 rst_gpio is 22
rm69a10_power_reset
rm69a10 rst_gpio is 22
rm69a10_power_reset
rm69a10 rst_gpio is 22
rm69a10_set_backlight
rm69a10_init
rm69a10_set_phy_freq
rm69a10_dsi_resolution_init
rm69a10_568x1232_init
rm69a10_vo_resolution_init
```

`rm69a10_568x1232_init` prints its own name (`rm69a10.c:100`). It is what
runs on the shipped firmware.

Caveat on provenance: the source in `repo/` also has
`rt_kprintf("connecter_dsi_send_pkg: %d \n", ret)` at `rm69a10.c:140` and
two read printfs at `:160`/`:163`, and **those lines do not appear in the
boot log**. So the flashed binary is probably an older build of the same
function, before those debug printfs were added. That does not affect the
conclusion — the function name printed is the dispatcher's, and the
dispatcher has only ever had one branch — but the body might differ in
detail from the snapshot we hold. I could not check: there is no RT-Smart
image in `firmware/`, only U-Boot/SPL/OpenSBI blobs.

### The sequence that actually runs

`rm69a10.c:114-163`, in order. Each `connecter_dsi_send_pkg()` is followed
by an unconditional 3 ms delay inside the transport (see below).

| # | line | bytes | DCS meaning |
| --- | --- | --- | --- |
| 1 | 116,139 | `fe fd` | manufacturer command page select (Raydium) |
| 2 | 117,141 | `80 fc` | page-0xFD register write |
| 3 | 118,142 | `fe 00` | back to user command set |
| 4 | 119,143 | `2a 00 00 02 37` | **set_column_address 0..567** |
| 5 | 120,144 | `2b 00 00 04 cf` | **set_page_address 0..1231** |
| 6 | 121,145 | `31 00 03 02 34` | set_partial_columns 3..564 |
| 7 | 122,146 | `30 00 00 04 cf` | set_partial_rows 0..1231 |
| 8 | 123,147 | `12 00` | **enter_partial_mode** |
| 9 | 124,148 | `35 00` | set_tear_on |
| 10 | 125,149 | `51 fe` | **write_display_brightness = 0xFE** |
| | 150 | | `connector_delay_us(2000)` |
| 11 | 126,151 | `11` | exit_sleep_mode |
| | 152 | | **`connector_delay_us(120000)` — 120 ms** |
| 12 | 127,153 | `29` | set_display_on |
| 13 | 130,156 | `3a 77` | set_pixel_format = 24 bpp |
| | 159,162 | | `connecter_dsi_read_pkg(0x05)`, `(0x0C)` |

Thirteen commands, 36 payload bytes. Not one of them appears in what we
send. Three differences stand out as sufficient on their own to keep an
AMOLED dark:

- **`0x51 0xFE`** — `write_display_brightness`. A DCS-brightness-controlled
  AMOLED powers up at brightness 0. Nothing else in the sequence turns the
  emitter on. We never send it.
- **`0x2A` / `0x2B`** — the frame-memory window. The RM69A10 is a RAM-backed
  controller; without a column/page window the DPI stream has nowhere to
  land. We never send them.
- **120 ms after `0x11`** — we allow 1 ms. The MIPI/DCS minimum after
  `exit_sleep_mode` before `set_display_on` is 120 ms on most of this class
  of part. 1 ms is not a "longer than the vendor" safety margin as
  `rm69a10-init-sequence.md` claims; that claim was measured against the
  dead function's 300 µs.

Also note `0x3A 0x77` (pixel format) is sent **after** `0x29`, and the
manufacturer page dance `0xFE 0xFD` / `0x80 0xFC` / `0xFE 0x00` opens the
sequence. Neither is expressible as "just append the missing commands" —
the order matters.

---

## 1. The ordered bring-up, power-on to lit panel

### 1.0 Power domain — on device open

`connector_dev.c:53`, in `connector_dev_open()`:

```c
    sysctl_pwr_up(SYSCTL_PD_DISP);
```

Same thing we now do with `pm_runtime_get_sync()` pinned at probe. No
divergence.

### 1.1 `kd_mpi_connector_power_set(fd, 1)` → `rm69a10_power_on()`

`rm69a10.c:282-307`:

```c
    if (on) {
        // rst vo;
        k230_display_rst();
        // rst rm69a10
        rm69a10_power_reset(1);
        rt_thread_mdelay(g_blacklight_delay_ms);
        rm69a10_power_reset(0);
        rt_thread_mdelay(10);
        rm69a10_power_reset(1);
        rt_thread_mdelay(20);
        g_blacklight_delay_ms = DELAY_MS_BACKLIGHT_DEFAULT;

        //enable backlight
        rm69a10_set_backlight(1);
    }
```

`g_blacklight_delay_ms` is `DELAY_MS_BACKLIGHT_FIRST = 1` on the first call
(`rm69a10.c:33,37`) and 200 thereafter. So on a cold boot:

```
display reset (below)
GPIO22 = 1
   1 ms
GPIO22 = 0
  10 ms
GPIO22 = 1
  20 ms
GPIO25 = 1   (backlight)
```

`rm69a10_power_reset()` (`rm69a10.c:248-263`) does
`kd_pin_mode(rst_gpio, GPIO_DM_OUTPUT)` then writes
`GPIO_PV_HIGH`/`GPIO_PV_LOW`; active-low reset, GPIO22.
`rm69a10_set_backlight()` (`rm69a10.c:265-279`) drives GPIO25 high.

Pin numbers from `repo/canmv_k230/include/generated/autoconf.h:37,57`:
`CONFIG_MPP_DSI_LCD_BACKLIGHT_PIN 25`, `CONFIG_MPP_DSI_LCD_RESET_PIN 22`.

### 1.2 `k230_display_rst()` — SoC display-subsystem reset

Not in the RT-Smart source tree; it lives in `kernel/lib/libvo.a`
(`kd_vo_reg.o`, symbol `k230_display_rst`). Disassembled:

```
writel(0x00000000, 0x91101090)     ; lui 0x9110 + 0x109, slli 4 -> 0x91101090
rt_thread_mdelay(1)
writel(0xffffffff, 0x91101090)
rt_thread_mdelay(1)
writel(0x0, dsi_base + 0x04)       ; PWR_UP = 0  (DSI host held in reset)
kd_vo_software_reset()
```

and `kd_vo_software_reset()` (same object):

```
writel(0xf, vo_base + 0x00)        ; VO_SOFT_RST_CTL
writel(0x0, vo_base + 0x08)
writel(0x0, vo_base + 0x04)        ; VO_REG_LOAD_CTL
```

This is the **first thing** the vendor does, on the power-on path, before
the panel reset pulse.

### 1.3 `kd_mpi_connector_init(fd, info)` → `rm69a10_init()`

`rm69a10.c:379-393`:

```c
    if(info->pixclk_div != 0)
        connector_set_pixclk(info->pixclk_div);

    ret |= rm69a10_set_phy_freq(&info->phy_attr);
    ret |= rm69a10_dsi_resolution_init(info);
    ret |= rm69a10_vo_resolution_init(&info->resolution, info->bg_color, info->intr_line);
```

The table entry driving all of this is `mpi_connector.c:32-44`:

```c
     {
        "rm69a10",
        0,                                     /* screen_test_mode */
        0,                                     /* dsi_test_mode */
        BACKGROUND_BLACK_COLOR,
        9,                                     /* intr_line */
        14,                                    /* pixclk_div */
        K_DSI_2LAN,
        K_BURST_MODE,
        K_VO_LP_MODE,
      	{ 4, 97, 0x19, 0x96 },                 /* n, m, voc, hs_freq */
        { 39600, 475200, 788, 568, 40, 140, 40, 1268, 1232, 4, 16, 16  },
        RM69A10_MIPI_2LAN_568X1232_60FPS,
    },
```

field order from `k_connector_comm.h:80-93`; `k_connectori_phy_attr` is
`{n, m, voc, hs_freq}` (`k_connector_comm.h:71-77`).

### 1.4 Pixel clock — `k230_set_pixclk(14)`

`connector_comm.c:200-203` → `k230_set_pixclk()` in `libvo.a`:

```
reg  = readl(clk_base + 0x78)      ; clk_base = 0x91100000
reg &= ~0x7F8                      ; GENMASK(10,3)
reg |= div << 3                    ; div = 14
reg |= 0x80000000
writel(reg, clk_base + 0x78)
```

Identical to `canaan_dsi.c:376-381`, which writes `(div - 1) << 3` with
`div = round(594000/39600) = 15`, i.e. also 14. **No divergence** — except
in *when* it happens (see §2.7).

### 1.5 PHY — `rm69a10_set_phy_freq()` → `connector_set_phy_freq()` → `dwc_mipi_phy_config()`

`rm69a10.c:310-325`:

```c
    mipi_phy_attr.m = phy_attr->m;
    mipi_phy_attr.n = phy_attr->n;
    mipi_phy_attr.hs_freq = phy_attr->hs_freq;
    mipi_phy_attr.voc = phy_attr->voc;
    mipi_phy_attr.phy_lan_num = K_DSI_2LAN;
    connector_set_phy_freq(&mipi_phy_attr);
```

`connector_comm.c:155-158` forwards to `dwc_mipi_phy_config()`, which is in
`libvo.a`. Disassembled in full (it is 0x62 bytes):

```
writel(0x0, phy_base + 0x0c)                 ; phy_base = dsi_base + 0x400
a0 = attr[0x04]   (m)
a1 = attr[0x00]   (n)
a2 = attr[0x08] & 0xff   (voc)
a3 = attr[0x10] & 0xff   (hs_freq)
call k230_dsi_config_4lan_phy(m, n, voc, hs_freq)
return 0
```

**`phy_lan_num` is at offset 0x0c of `k_vo_mipi_phy_attr`
(`k_vo_comm.h:256-262`) and is never loaded.** The only reference to offset
0x0c in the function is the `writel(0x0, phy_base + 0x0c)` at entry, which
is a register write to `dsi_base + 0x400 + 0x0c`, not a struct read.

See §3 for what this means.

`k230_dsi_config_4lan_phy`, `k230_dsi_phy0_config`, `k230_dsi_phy1_config`,
`k230_dsi_phy_pll_config` and `k230_dsi_write_phy_reg` all exist in
`libvo.a` under exactly those names, and the disassembly matches
`canaan_phy.c` instruction for instruction in structure. Diffs are in §2.

### 1.6 DSI host — `rm69a10_dsi_resolution_init()`

`rm69a10.c:328-355`:

```c
    attr.lan_num = info->lan_num;          /* K_DSI_2LAN == 1 */
    attr.cmd_mode = info->cmd_mode;        /* K_VO_LP_MODE == 0 */
    attr.lp_div = 8;
    attr.work_mode = info->work_mode;      /* K_BURST_MODE == 0 */
    memcpy(&attr.resolution, &resolution, ...);
    connector_set_dsi_attr(&attr);
       ... init sequence ...
    connector_set_dsi_enable(1);
```

`connector_set_dsi_attr` → `kd_dsi_dsi_attr()` (`kd_vo.o`):

```
dwc_dsi_set_lan_num(attr->lan_num)     ; attr+0x30
dwc_dsi_set_lpdt_div(attr->lp_div)     ; attr+0x3c
dwc_dsi_set_vcid()
dwc_dsi_set_timing(attr)
if (attr->cmd_mode == 0) dwc_dsi_set_lpdt_mode(); else dwc_dsi_set_hs_mode();
if (attr->work_mode != 0) dwc_set_non_brust_mode(attr->work_mode);
```

For our panel: LP command mode, and burst mode means
`dwc_set_non_brust_mode()` is **not** called.

The individual writes, all to `dsi_base` (DWC MIPI-DSI-Host v1.31 offsets;
the names are my mapping, the offsets and values are read out of the
binary):

| function | register | value |
| --- | --- | --- |
| `dwc_dsi_set_lan_num` | `0xa4` PHY_IF_CFG | `0x2800 + lan_num` → **`0x2801`** |
| `dwc_dsi_set_lpdt_div` | `0x08` CLKMGR_CFG | `0x100 + lp_div` → `0x108` |
| `dwc_dsi_set_vcid` | `0x30` GEN_VCID | `0x303` |
| `dwc_dsi_set_timing` | `0x3c` VID_PKT_SIZE | `hdisplay` |
| | `0x40` VID_NUM_CHUNKS | `0` |
| | `0x44` VID_NULL_SIZE | `0` |
| | `0x48` VID_HSA_TIME | `lbcc(hsync_len)` |
| | `0x4c` VID_HBP_TIME | `lbcc(hback_porch)` |
| | `0x50` VID_HLINE_TIME | `lbcc(htotal)` |
| | `0x54` VID_VSA_LINES | `vsync_len` |
| | `0x58` VID_VBP_LINES | `vback_porch` |
| | `0x5c` VID_VFP_LINES | `vfront_porch` |
| | `0x60` VID_VACTIVE_LINES | `vdisplay` |
| `dwc_dsi_set_lpdt_mode` | `0x34` MODE_CFG | `0x1` (command mode) |
| | `0x38` VID_MODE_CFG | `0xbf02` |
| | `0x68` CMD_MODE_CFG | `0x10f7f01` |
| | `0x2c` PCKHDL_CFG | `0x1c` |
| | `0x04` PWR_UP | `0x1` |

`lbcc` is `dw_mipi_dsi_get_hcomponent_lbcc(hcomp, phyclk, pclk)` =
`hcomp * phyclk / 8 / pclk`, rounded up — same formula as
`canaan_dsi_get_hcomponent_lbcc()` (`canaan_dsi.c:201-215`).

**This block is identical to Linux `canaan_dsi_lpdt_init()`
(`canaan_dsi.c:258-284`) plus `canaan_dsi_set_lan_num()`
(`canaan_dsi.c:183-199`).** No divergence at all.

`dwc_dsi_set_hs_mode()` exists and differs (`PCKHDL_CFG = 0x38`, plus
`LPCLK_CTRL = 3`) but is not taken for this panel, and Linux has no
equivalent. Noted for completeness only.

### 1.7 The init sequence — transport

`connecter_dsi_send_pkg()` (`connector_comm.c:145-148`) → `dwc_lpdt_send_pkg()`
in `libvo.a`. Disassembled:

```
if (cmd_len <= 1):
    hdr = 0x05 | (buf[0] << 8)                  ; DCS short write, vcid 0
    writel(hdr, dsi_base + 0x6c)                ; GEN_HDR
else:
    for each 4-byte chunk of buf:
        writel(chunk, dsi_base + 0x70)          ; GEN_PLD_DATA
    hdr = 0x39 | (cmd_len << 8)                 ; DCS long write, vcid 0
    writel(hdr, dsi_base + 0x6c)
rt_thread_mdelay(3)                             ; <-- unconditional, every packet
```

Two things:

- The length split is `1 → 0x05`, `>= 2 → 0x39`. Linux reaches the same
  wire types: `mipi_dsi_dcs_write_buffer()` picks `0x05`/`0x15`/`0x39`, and
  `canaan_dsi_transfer()` routes both `DCS_SHORT_WRITE_PARAM` and
  `DCS_LONG_WRITE` to `canaan_dsi_dcs_write_long()`, which emits `0x39`
  (`canaan_dsi.c:171`). **Equivalent.**
- **3 ms after every single packet.** Linux applies only the per-command
  `delay` byte from the DT blob (`panel-canaan-universal.c:118-119`), which
  in our dtsi is `00` for eighteen of twenty commands.

There is no FIFO-full polling in the vendor path at all — the 3 ms is the
flow control.

### 1.8 `connector_set_dsi_enable(1)` → `dwc_dsi_enable()`

`connector_comm.c:165-168` → `dwc_dsi_enable()` in `libvo.a`:

```
call dwc_dsi_init()
writel(0x1, dsi_base + 0x94)       ; LPCLK_CTRL
```

and `dwc_dsi_init()`:

```
call dwc_dsi_set_color_coding()    ; writel(0x105, dsi_base + 0x10)  DPI_COLOR_CODING
writel(0x320068, dsi_base + 0x9c)  ; PHY_TMR_CFG
writel(0x2e0080, dsi_base + 0x98)  ; PHY_TMR_LPCLK_CFG
writel(0xffffffff, dsi_base + 0xc4); INT_MSK0
writel(0xffffffff, dsi_base + 0xc8); INT_MSK1
writel(0x0, dsi_base + 0x34)       ; MODE_CFG  -> video mode
writel(0x0, dsi_base + 0x68)       ; CMD_MODE_CFG
writel(0x3, dsi_base + 0x94)       ; LPCLK_CTRL
```

**Identical, in the same order, to Linux `canaan_mipi_dsi_set_dsi_enable()`
(`canaan_dsi.c:286-297`).** No divergence.

### 1.9 VO — `rm69a10_vo_resolution_init()`

`rm69a10.c:358-376`:

```c
    attr.bg_color = bg_color;
    attr.intf_sync = K_VO_OUT_1080P30;
    attr.intf_type = K_VO_INTF_MIPI;
    attr.sync_info = resolution;

    connector_set_vo_init();
    connector_set_vtth_intr(1, intr_line);
    connector_set_vo_param(&attr);
    connector_set_vo_enable();
```

From `libvo.a`:

- `vo_init()` calls, in order: `kd_vo_wrap_init`, `kd_vo_set_config_mix`,
  `kd_vo_table_init`, `kd_vo_osd_set_addr_select_mode`,
  `kd_vo_osd_set_dma_map`, `kd_vo_osd_set_dma_request`,
  `kd_vo_layer_set_uv_endian_mode`, `kd_vo_layer_set_y_endian_mode`,
  `kd_vo_layer_set_img_blenth`, `kd_vo_layer_addr_select_mode`,
  **`layer0_test`**, `kd_vo_set_layer_outstanding`, `kd_vo_set_vtth_intr`.
- `kd_vo_set_vtth_intr(status, vpos)`:
  `writel((status << 20) | (vpos & 0x1fff), vo_base + 0x3e4)` —
  VO_DISP_IRQ1_CTL. **`vpos` is the real line number, 9 for this panel.**
- `kd_vo_set_dev_param()` calls `kd_vo_set_timing` then `kd_vo_set_background`.
- `kd_vo_enable()`: `writel(0x11, vo_base + 0x04)` then
  `kd_vo_timestamp_enable()`.

Note the vendor brings the **VO up last**, after the DSI link is already in
video mode.

---

## 2. Diff list: what RT-Smart does that our Linux path does not

Ordered by how likely each is to be the reason the panel is dark.

### 2.1 The init sequence is a different panel's (fatal, near-certain)

- **Vendor**: `rm69a10_568x1232_init()`, 13 commands, 36 bytes, including
  `0x51 0xFE` brightness, `0x2A`/`0x2B` window, partial mode, TE on, and
  **120 ms** between `0x11` and `0x29`, with `0x3A 0x77` after `0x29`.
  `rm69a10.c:114-163`.
- **Ours**: the 20-command / 297-byte HX8399 sequence from the dead
  `rm69a10_OLD_init()`, 1 ms between `0x11` and `0x29`, no brightness, no
  window. `nix/dts/display-rm69a10-568x1232.dtsi:54-75`.

### 2.2 No SoC display reset on the enable path

- **Vendor**: `k230_display_rst()` runs first thing in
  `rm69a10_power_on()` (`rm69a10.c:290`) — `0x91101090 = 0`, 1 ms,
  `= 0xffffffff`, 1 ms; then DSI `PWR_UP = 0`; then VO soft reset
  (`VO_SOFT_RST_CTL = 0xf`, `0x08 = 0`, `VO_REG_LOAD_CTL = 0`).
- **Ours**: the *only* write to `0x91101090` in the kernel tree is in
  `canaan_vo_disable_crtc()` (`canaan_vo.c:666-676`) — the **disable**
  path. Nothing resets the display subsystem before bring-up.
  `VO_SOFT_RST_CTL` (`canaan_vo_regs.h:12`) is defined and never written.
  DSI `PWR_UP` is only ever set to 1 (`canaan_dsi.c:283`), never cleared.

### 2.3 Panel reset is stale and mistimed

- **Vendor**: high / 1 ms / low / 10 ms / high / 20 ms, immediately before
  the init sequence, within the same power-on ioctl
  (`rm69a10.c:292-297`); backlight asserted after the last delay
  (`rm69a10.c:301`).
- **Ours**: the pulse is at **probe** only — high / 200 ms / low / 200 ms /
  high, **with no settle delay after the final release**
  (`panel-canaan-universal.c:323-329`) — and the prepare-time pulse is
  commented out by the vendor (`panel-canaan-universal.c:128-143`). By the
  time `drm_panel_prepare()` sends the init sequence, the reset happened
  in a different callback, potentially seconds earlier, and before the DSI
  host was configured.

### 2.4 3 ms between every DCS command

- **Vendor**: `rt_thread_mdelay(3)` at the tail of `dwc_lpdt_send_pkg()`,
  unconditionally, after each packet.
- **Ours**: `panel_simple_sleep(cmd->header.delay)` only when non-zero
  (`panel-canaan-universal.c:118-119`); our dtsi uses `00` for all but the
  last two commands.

### 2.5 `vco_cntrl` differs

- **Vendor**: `0x19` for this panel (`mpi_connector.c:41`, the third field
  of `{ 4, 97, 0x19, 0x96 }`).
- **Ours**: `canaan_dsi_clk_cfg()` computes `phy_clk_freq = 39600*3*8/2/2 =
  237600`, hits the `< 330000` arm, and sets `voc = 0x17`
  (`canaan_dsi.c:338-339`).
- `m` and `n` agree exactly: Linux derives `m = 99, n = 5` and passes
  `(m-2, n-1) = (97, 4)` (`canaan_dsi.c:383`), matching the vendor table.
  `hs_freq` also agrees (`0x96`).
- So the PLL divider chain is right and only the VCO range code is wrong.
  Both values have `>>4 == 1`, so the post-divider matches and the output
  frequency computes to 475.2 MHz either way; whether `0x17` vs `0x19`
  matters is a question about the Synopsys VCO band table, which is not in
  this tree. **Inference, not measured.**

### 2.6 `intr_line` / `vth_line`

- **Vendor**: `intr_line = 9` for `"rm69a10"` (`mpi_connector.c:36`),
  written as the literal line number into VO_DISP_IRQ1_CTL[12:0] with the
  enable bit at 20.
- **Ours**: the dtsi says `vth_line = <10>` (`display-rm69a10-568x1232.dtsi:24`),
  which is moot — Linux declares `vth_line` in `canaan_vo.h:26`, never
  reads it from DT, and instead writes `32 - __builtin_clz(vtotal) - 1`
  into the same register (`canaan_vo.c:648-649`). The earlier edit from 9
  to 10 changed nothing, and the vendor's value for *this* panel was 9 all
  along.

### 2.7 Bring-up order is inverted: VO before DSI vs DSI before VO

- **Vendor** (`rm69a10.c:385-390`): pixclk → PHY → DSI host + init sequence
  + DSI enable → **then** VO init / vtth / timing / enable.
- **Ours**: `drm_atomic_helper_commit_modeset_enables()` runs all CRTC
  `atomic_enable`s first, so `canaan_vo_enable_crtc()`
  (`canaan_vo.c:652-664`) does VO init, timing, background and
  `REG_LOAD_CTL = 0x11` **before** `canaan_dsi_encoder_enable()`
  (`canaan_dsi.c:388`) touches the pixel clock, the PHY or the DSI host.
  The VO is therefore streaming pixels into an unconfigured link, and the
  pixel-clock divider is reprogrammed underneath a running VO.

### 2.8 Smaller, probably harmless

| | vendor | ours |
| --- | --- | --- |
| DSI host register block | identical writes, identical order (§1.6, §1.8) | — |
| PHY register block | identical (§3) | — |
| `PHY_TST_CTRL0` settle in phy1_config | `rt_thread_mdelay(1)` | `msleep(20)` (`canaan_phy.c:174`) |
| post-`PHY_STATUS` settle in config_4lan | `rt_thread_mdelay(1)` | `msleep(20)` (`canaan_phy.c:252`) |
| `PHY_TST_CTRL1 != 0x580` loop | unbounded | bounded at 1000 (`canaan_phy.c:230-231`) |
| `PHY_STATUS != 0x1fbd` loops | unbounded | unbounded upstream; bounded in our patched tree |
| VO background | `bg_color` from the table | hard-coded `0xffffff` (`canaan_vo.c:660`) |
| `layer0_test()` in `vo_init` | called | no equivalent |
| DCS read busy poll | reads `0xb0` bit 6 — looks like a vendor bug, should be `0x74` | we poll `0x74` correctly |

---

## 3. The 2-lane question, answered: it is a non-issue

The leading hypothesis in `docs/evidence/dsi-phy-hang.md` — that the Linux
driver programs the D-PHY for four lanes because `canaan_phy.c` exports only
`k230_dsi_config_4lan_phy()` — **is wrong, and the vendor binary proves it.**

`dwc_mipi_phy_config()` is the only consumer of `phy_lan_num`, and it does
not consume it. Full disassembly (`libvo.a`, `kd_vo_reg.o`,
`.text.dwc_mipi_phy_config`, 0x62 bytes):

```
   8: sd   a0, -0x18(s0)               ; save attr pointer
  10: auipc a5, display_remap          ; phy base = remap[1] (dsi_base + 0x400)
  1c: addi a5, a5, 0xc
  20: li   a0, 0x0
  22: call __raw_writel                ; writel(0, phy_base + 0x0c)
  2a: ld   a5, -0x18(s0)
  2e: lw   a4, 0x4(a5)                 ; attr->m
  30: ld   a5, -0x18(s0)
  34: lw   a1, 0x0(a5)                 ; attr->n
  36: ld   a5, -0x18(s0)
  3a: lw   a5, 0x8(a5)
  3c: zext.b a2, a5                    ; attr->voc
  40: ld   a5, -0x18(s0)
  44: lw   a5, 0x10(a5)
  46: zext.b a5, a5
  4a: mv   a3, a5                      ; attr->hs_freq
  4c: mv   a0, a4
  4e: call k230_dsi_config_4lan_phy    ; (m, n, voc, hs_freq)
  56: li   a5, 0x0
```

Struct offsets from `k_vo_comm.h:255-262`:

```c
typedef struct
{
    k_u32 n;            /* +0x00 */
    k_u32 m;            /* +0x04 */
    k_u32 voc;          /* +0x08 */
    k_u32 phy_lan_num;  /* +0x0c */
    k_u32 hs_freq;      /* +0x10 */
} k_vo_mipi_phy_attr;
```

Offset `0x00`, `0x04`, `0x08` and `0x10` are loaded. **`0x0c` is not.**
`phy_lan_num` is dead in the vendor firmware too — every panel, 2-lane and
4-lane alike, gets the identical `k230_dsi_config_4lan_phy()` call. Setting
`mipi_phy_attr.phy_lan_num = K_DSI_2LAN` at `rm69a10.c:321` has no effect
whatsoever.

### Where lane count *is* consumed

Exactly one register, in both stacks:

- **Vendor**: `dwc_dsi_set_lan_num(n)` → `writel(0x2800 + n, dsi_base + 0xa4)`.
  With `K_DSI_2LAN == 1` (`k_vo_comm.h:157-163`) that is **`0x2801`**.
- **Ours**: `canaan_dsi_set_lan_num()` (`canaan_dsi.c:183-199`), `case 2:
  dsi_write(dsi, PHY_IF_CFG, 0x2801);` — **the same value**, driven from
  `panel-dsi-lane = <2>` via `device->lanes` (`canaan_dsi.c:403`).

Linux has one *additional* lane dependency the vendor lacks:
`phy_clk_freq = dsi->clk_freq * 3 * 8 / device->lanes / 2`
(`canaan_dsi.c:325`). That is the vendor's table-driven `phyclk = 475200`
recomputed, and it comes out right for 2 lanes.

### Structural comparison of the PHY code

`canaan_phy.c` is a faithful transliteration of the `libvo.a` functions.
I walked all four side by side:

| RT-Smart (`libvo.a`) | Linux | verdict |
| --- | --- | --- |
| `k230_dsi_write_phy_reg` | `canaan_phy.c:42-56` | same |
| `k230_dsi_phy_pll_config` | `canaan_phy.c:58-113` | same structure |
| `k230_dsi_phy0_config(m,n,voc,hsfreq)` | `canaan_phy.c:115-163` | same |
| `k230_dsi_phy1_config(hsfreq)` | `canaan_phy.c:165-234` | same except delays and the loop bound |
| `k230_dsi_config_4lan_phy(m,n,voc,hsfreq)` | `canaan_phy.c:236-266` | same except `mdelay(1)` vs `msleep(20)` |

`k230_dsi_config_4lan_phy` disassembles to exactly:

```
k230_dsi_phy0_config(m, n, voc, hs_freq)
k230_dsi_phy1_config(hs_freq)
readl(phy_base + 0x04);  writel(0x0, phy_base + 0x04)
writel(0xd, dsi_base + 0xa0);  writel(0xf, dsi_base + 0xa0)
while (readl(dsi_base + 0xb0) != 0x1fbd) ;
rt_thread_mdelay(1)                              /* Linux: msleep(20) */
writel(0x1, dsi_base + 0x94)
readl(phy_base + 0x04);  writel(0x400000, phy_base + 0x04)
while (readl(dsi_base + 0xb0) != 0x1fbd) ;
readl(dsi_base + 0xb0)
```

`0x1fbd` is the vendor's own expected value on a **2-lane** panel — the same
constant, in the same firmware, that lights this exact board. It was never
a 4-lane encoding.

**Conclusion.** `nix/patches/canaan-dsi-2lane-phy-path.patch`, currently
staged, is chasing a defect that does not exist. The vendor programs the
D-PHY identically for 2 and 4 lanes, and our PHY already reaches `0x1fbd`
on hardware. That work should be dropped and the effort moved to §2.1.

---

## 4. Panel supply rails

**There are none to model.** The vendor's entire panel power story is two
GPIOs:

- GPIO22, reset, `rm69a10_power_reset()` (`rm69a10.c:248-263`),
  `CONFIG_MPP_DSI_LCD_RESET_PIN=22`.
- GPIO25, "backlight", `rm69a10_set_backlight()` (`rm69a10.c:265-279`),
  `CONFIG_MPP_DSI_LCD_BACKLIGHT_PIN=25`.

No regulator, no PMIC write, no I²C to a charge pump, no third GPIO. Grep
for VCI / ELVDD / AVDD / `regulator` across
`repo/canmv_k230/src/rtsmart/mpp/kernel/connector/` returns nothing.

So the "missing VCI/ELVDD/AVDD" suspect from `dsi-phy-hang.md` is
**retired**: if the vendor needs no such rail, neither do we. On an AMOLED
whose ELVDD comes from an on-FPC charge pump, the equivalent of "turn on
the supply" is `0x51` — the DCS brightness write we are not sending.

Our side already drives both GPIOs (`panel-canaan-universal.c:318, 331`,
asserted at `:324-328` and `:339`), so there is nothing to add; only the
reset *timing* differs (§2.3).

---

## What to do next, in order

1. **Replace the init sequence** in `nix/dts/display-rm69a10-568x1232.dtsi`
   with the thirteen commands from `rm69a10_568x1232_init()`, with the
   120 ms after `0x11`, and `0x3A 0x77` after `0x29`. This is the one change
   that is both high-probability and cheap. The DT `delay` byte is u8
   milliseconds, so 120 fits; the 2000 µs before `0x11` becomes 2 ms.
2. **Set the DT `delay` byte to 3 on every command**, matching the vendor
   transport.
3. **Drop `nix/patches/canaan-dsi-2lane-phy-path.patch`** (§3).
4. If still dark: move the reset pulse into `canaan_panel_prepare()` with
   the vendor's 1/10/20 ms timing, and add `k230_display_rst()`'s
   `0x91101090` poke to the enable path (§2.2, §2.3).
5. Then `voc = 0x19` (§2.5) and the VO/DSI ordering (§2.7).

The DCS read (`0x0A`) that currently times out should start answering as
soon as the panel is actually initialised — the vendor's own code reads
`0x05` and `0x0C` right after `0x29` (`rm69a10.c:159-163`) and expects a
reply, so a successful read is the pass/fail signal for step 1.
