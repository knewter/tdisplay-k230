# Every RM69A10 implementation, compared against ours

Written 2026-09-21 to answer one question: the panel lights, shows a full
frame, and **flickers continuously on a completely static framebuffer**.
Nothing is redrawing it, so this is instability in how the panel is driven.

Four independent RM69A10 implementations were fetched and read in full,
plus LILYGO's Linux kernel patch queue for this exact board. They agree
with each other to the byte on the DCS sequence and disagree with us on
almost nothing there — **the interesting divergence is not in the init
sequence at all, it is in the video timing.**

Everything below is either quoted from a source I fetched (URL given) or
read out of the pristine kernel tree, or it is marked **INFERENCE**.

---

## Sources

| ID | What | URL | provenance |
| --- | --- | --- | --- |
| **RTS** | LILYGO RT-Smart `rm69a10_568x1232_init()` | in-tree | `repo/canmv_k230/src/rtsmart/mpp/kernel/connector/src/rm69a10.c:96-176` |
| **LGL** | LILYGO Linux BSP panel dtsi | `https://raw.githubusercontent.com/Xinyuan-LilyGO/T-Display-K230/main/k230_bsp/overlay/buildroot-overlay/linux/0031-riscv-dts-canaan-add-rm69a10-display.patch` | fetched 2026-09-21 |
| **ESP** | Espressif `esp_lcd_rm69a10.c` | `https://raw.githubusercontent.com/espressif/esp-claw/74b18700a1d6c40de472bfc71c19e49356ca1cc0/application/edge_agent/boards/lilygo/lilygo_t_display_p4_v1/esp_lcd_rm69a10.c` | fetched 2026-09-21 |
| **CBD** | LILYGO `cpp_bus_driver` `Rm69a10` class (GPL-3.0) | `https://components-file.espressif.com/components/llgok/cpp_bus_driver/2.0.0/llgok__cpp_bus_driver-v2.0.0.zip` → `src/chip/mipi/rm69a10.cpp` | fetched 2026-09-21 |
| **LDD** | LILYGO `lilygo_device_driver` board constants | `https://raw.githubusercontent.com/Xinyuan-LilyGO/lilygo_device_driver/main/src/device/t_display_p4/config.h` | fetched 2026-09-21 |
| **OURS** | our dtsi | — | `nix/dts/display-rm69a10-568x1232.dtsi` |

Kernel source read from the pristine tree
`/nix/store/pn7bm6ck5a3x6pnk1ng30hlf24qn85jx-source/drivers/gpu/drm/`, not
from `.build/`.

Also fetched and read: LILYGO's whole 31-file kernel patch queue
(`k230_bsp/overlay/buildroot-overlay/linux/`). The display-relevant ones are
cited by number below.

Not obtained: the RM69A10 datasheet. It exists at
`Xinyuan-LilyGO/T-Display-P4/docs/RM69A10_DataSheet_V0.2_20230330 (Public
version).pdf` but every raw/LFS route 404s. Worth grabbing by hand — it is
the only thing that would say what `0x80` on page `0xFD` does.

---

## 1. Command by command

`—` means the implementation does not send that command at all.

| # | RTS | LGL | ESP | CBD | OURS | notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `FE FD` | `FE FD` | `FE FD` | `FE FD` | `FE FD` | Raydium page select → page 0xFD |
| 2 | `80 FC` | `80 FC` | `80 FC` | `80 FC` | `80 FC` | the one undocumented vendor write |
| 3 | `FE 00` | `FE 00` | `FE 00` | `FE 00` | `FE 00` | back to user command set |
| 4 | `2A 00 00 02 37` | same | same | same | same | column 0..567 |
| 5 | `2B 00 00 04 CF` | same | same | same | same | page 0..1231 |
| 6 | `31 00 03 02 34` | same | same | same | **—** | partial columns 3..564 |
| 7 | `30 00 00 04 CF` | same | same | same | **—** | partial rows 0..1231 |
| 8 | `12 00` | `12` (no param) | `12 00` | `12 00` | **—** | enter partial mode |
| 8b | — | — | — | — | **`13 00`** | **ours only**: enter normal mode |
| 9 | `35 00` | `35 00` | `35 00` | `35 00` | `35 00` | set_tear_on, V-blank only |
| 10 | `51 FE` | `51 FE` | — | `51 00` | `51 FE` | brightness, before sleep-out |
| 11 | `11` +120 ms | `11` +120 ms | `11` +120 ms | `11` +120 ms | `11` +120 ms | sleep out |
| 12 | `29` | `29` +10 ms | `29` | `29` | `29` | display on |
| 13 | `3A 77` | `3A 77` | — | — | `3A 77` | RGB888; ESP/CBD set format host-side |
| 14 | — | — | `51 FF` | — | — | ESP sets brightness *after* display-on |
| pre | — | — | read `A1` == `0x01` | read `A1` == `0x01` | — | chip-ID liveness probe |

Delays: RTS 3 ms unconditionally after every packet (inside
`dwc_lpdt_send_pkg`), plus 2 ms before `0x11` and 120 ms after. LGL and ESP
use 0 ms everywhere except the 120 ms. We use 3 ms everywhere, matching RTS.

Wire encoding is a non-issue. `canaan_dsi_transfer()`
(`canaan_dsi.c:523-552`) routes `MIPI_DSI_DCS_SHORT_WRITE_PARAM` **and**
`MIPI_DSI_DCS_LONG_WRITE` to `canaan_dsi_dcs_write_long()`, which emits
data type `0x39`. So our `15 …` records and LGL's `39 …` records produce
identical bytes on the wire, and both match RTS's `0x39` for every 2-byte
payload.

### What this table actually says

**We differ from all four in exactly one place: line 6/7/8.** Every other
implementation sends the partial-area block and `ENTER_PARTIAL_MODE`; we
send `ENTER_NORMAL_MODE` instead. That change was made because the vendor
block produced banding (`panel-lit.md:41-58`), and it is the only place we
are the sole outlier.

`0x51 0xFE` vs ESP's `0x51 0xFF`, and before-vs-after `0x29`, are the only
other deltas, and CBD deliberately writes `0x51 0x00` to leave the panel
dark, so the family clearly tolerates any of these.

---

## 2. What *nobody* sends — this kills three hypotheses outright

Across RTS, LGL, ESP and CBD there is **not one** oscillator, frame-rate,
VCOM, power-control, charge-pump, gamma, porch or `MADCTL` register write.
The entire vendor-specific portion of RM69A10 bring-up is three bytes of
page select plus `0x80 = 0xFC`, and then standard DCS.

For comparison, mainline's `panel-raydium-rm68200.c` — same `0xFE` page-select
convention — writes a named VCOM register (`0x46 VCMCTR = 0x56`), AVDD/AVEE
(`0x27`/`0x29`), three charge-pump controls, source-bias, source-delay, and
two 16-byte gamma tables. RM69A10 exposes none of that in any public driver.

Therefore:

- **"VCOM miscalibration"** — not fixable, and not a divergence. There is no
  VCOM command in any implementation. VCOM comes from OTP.
- **"oscillator / frame-rate divider mismatch inside the panel"** — there is
  no frame-rate register being written by anyone, so we cannot be missing a
  write. If the panel's internal rate matters it is fixed in OTP and the
  host must match it.
- **"missing `0xB2` PAD_CONTROL lane select"** — confirmed again: no
  implementation writes `0xB2`. All rely on the power-on 2-lane default.

There is nothing to add to our DCS sequence. That is a real and useful
negative: **the flicker is not a missing init command.**

---

## 3. Video mode: our `MIPI_DSI_MODE_VIDEO_SYNC_PULSE` is dead code, and we are already in burst

Asked directly: are `K_BURST_MODE` and `MIPI_DSI_MODE_VIDEO_SYNC_PULSE` the
same thing, and does `canaan_dsi.c` honour the flag?

**No, and no — and it does not matter, because nothing reads the flag.**

```
$ grep -rn "mode_flags\|msg->flags\|MIPI_DSI_MSG_USE_LPM" \
    /nix/store/pn7bm6…-source/drivers/gpu/drm/canaan/
(no matches)
```

`panel-canaan-universal.c:351` sets `dsi->mode_flags =
MIPI_DSI_MODE_VIDEO_SYNC_PULSE` and no consumer in the Canaan DRM driver
ever looks at it. The video mode is hardcoded:

- `canaan_dsi_lpdt_init()` (`canaan_dsi.c:258-284`) writes
  `VID_MODE_CFG = 0xbf02` at `canaan_dsi.c:280`.
- DWC MIPI-DSI-Host `VID_MODE_CFG[1:0]` is `vid_mode_type`:
  `0` = non-burst sync pulses, `1` = non-burst sync events, `2` = **burst**.
  `0xbf02 & 3 == 2`.

So the host is in **burst mode already**, which is what the vendor's
`K_BURST_MODE` also produces (RT-Smart only calls
`dwc_set_non_brust_mode()` when `work_mode != 0`; see
`rtsmart-panel-bringup.md:§1.6`). The two stacks agree.

Setting `MIPI_DSI_MODE_VIDEO_BURST` in the panel driver would change
nothing. **Burst-vs-sync-pulse is not a flicker candidate.** Cross that off.

Decoding the rest of `0xbf02` (DWC v1.31 field layout — *INFERENCE from the
standard Synopsys register map, not a Canaan document*):

| bit | field | 0xbf02 | LGL's 0x3f02 |
| --- | --- | --- | --- |
| 15 | `lp_cmd_en` | 1 | **0** |
| 14 | `frame_bta_ack_en` | 0 | 0 |
| 13 | `lp_hfp_en` | 1 | 1 |
| 12 | `lp_hbp_en` | 1 | 1 |
| 11 | `lp_vact_en` | 1 | 1 |
| 10 | `lp_vfp_en` | 1 | 1 |
| 9 | `lp_vbp_en` | 1 | 1 |
| 8 | `lp_vsa_en` | 1 | 1 |
| 1:0 | `vid_mode_type` | 2 (burst) | 2 (burst) |

LILYGO patch `0029-drm-canaan-fix-video-mode-to-burst.patch` changes
`0xbf02` → `0x3f02`. Its subject line is wrong (both are already burst;
this is one of the AI-authored commit messages the research doc warns
about) but **the diff is real, it ships in a working image, and its only
effect is to clear `lp_cmd_en`.**

---

## 4. Tearing effect (`0x35 00`)

Asked: is enabling TE while free-running in video mode harmful here, and do
others use command mode?

**All four implementations send `35 00`. All four run the panel in DSI video
mode. None of them consumes TE.**

- ESP and CBD build the display through `esp_lcd_new_panel_dpi()` — DPI
  video mode — with a DBI side-channel used only for the init commands.
  `esp_lcd_rm69a10.c` never registers a TE callback and the board config
  has no TE GPIO.
- RTS and LGL drive the K230 VO continuously into the DSI host in video
  mode.

So `0x35` on this controller enables an output pin that everybody leaves
dangling, and four independent working bring-ups do exactly that. **Not a
flicker cause. Keep it.** No evidence exists in any direction for
"command mode with explicit frame writes" on this part — nobody does it.

---

## 5. The real outlier: our refresh rate

This is the finding. Line up every implementation's video timing:

| | pixel clock | htotal | vtotal | **refresh** | source |
| --- | --- | --- | --- | --- | --- |
| RTS (vendor RT-Smart) | 39.600 MHz | 788 | 1268 | **39.63 Hz** | `mpi_connector.c:42` |
| **OURS** | 39.600 MHz | 788 | 1268 | **39.63 Hz** | our dtsi |
| LGL (LILYGO Linux) | 49.500 MHz | 748 | 1268 | **52.19 Hz** | `0031-*.patch` |
| ESP (esp-claw) | 60.000 MHz | 818 | 1472 | **49.83 Hz** | `setup_device.c:128-139` |
| LDD (LILYGO ESP board hdr) | 60.000 MHz | 818 | 1472 | **49.83 Hz** | `config.h` |

We copied the RT-Smart table exactly, and the RT-Smart table is the lowest
refresh rate anyone runs this panel at — by 10 Hz. Three of the four other
data points are 49–52 Hz. The vendor's own enum for this entry is named
`RM69A10_MIPI_2LAN_568X1232_60FPS` while the numbers give 39.6 Hz, which
reads like a timing table that was never revisited.

And LILYGO's Linux BSP moved off it deliberately.
`0042-drm-canaan-rm69a10-use-auto-phy-high-refresh.patch`, verbatim:

> The fixed 2-lane PHY override was stable at the original 39.6 MHz DPI
> clock, but higher RM69A10 refresh experiments showed the panel behaves
> better when the PHY settings calculated by `canaan_dsi_clk_cfg()` are kept.
>
> Keep the automatic PHY result so the 49.5 MHz RM69A10 timing can run at
> about 52 Hz **without the low-refresh stutter seen at the original timing.**

That is the only first-hand report anywhere of a *visual artifact* on this
panel under Linux on this board, and its stated cause is the 39.6 MHz
timing we are using, and its stated fix is the 49.5 MHz timing we are not.

**Mechanism (INFERENCE, but a well-established one):** an AMOLED emits in
per-frame pulses; there is no backlight to integrate the duty cycle. Full-field
flicker at 39.6 Hz is above the perception threshold for most people, and it
is present on a static image because the *emission* is what is modulated,
not the content. 50 Hz is the usual place this stops being visible. This
explains "flickers on a completely static framebuffer" better than anything
else in this document.

Two secondary observations from the same table, both pointing the same way:

- **vsync width.** ESP uses `vsync_pulse_width = 40`, LGL uses 16, RTS/ours
  use **4**. We have the narrowest VSA of anyone.
- **vertical blanking.** ESP gives the panel 240 blank lines (3.27 ms);
  LGL and ours give 36 (0.72 ms at our clock). ESP has 4.5× the vertical
  blanking time.

---

## 6. Burst headroom: we have exactly zero, by construction

Worked from `canaan_dsi_clk_cfg()` (`canaan_dsi.c:316-390`) and
`canaan_dsi_get_hcomponent_lbcc()` (`canaan_dsi.c:201-214`).

For our mode: `div = round(594000/39600) = 15`, `clk_freq = 39600 kHz`,
`phy_clk_freq = 39600*3*8/2/2 = 237600`, `voc = 0x17` (→ ×2), the m/n search
lands exactly on `m=99, n=5`, and `dsi->phy_freq = 475200 kHz` — the per-lane
bit rate. Lane byte clock = 59.4 MHz.

- Link capacity: 2 lanes × 475.2 Mbps = **950.4 Mbps**
- Pixel load: 39.6 MHz × 24 bpp = **950.4 Mbps**

They are equal, and they are *always* equal, at every pixel clock, because
the driver derives `phy_freq` from `pclk * 24 / lanes / 2`. **The K230 driver
never gives the DSI link any burst headroom.** "Burst mode" with a link
exactly saturated degenerates into filling the whole line.

Per-line budget in lane byte clocks (`lbcc = h * 1.5` for us):

| | HLINE | HSA | HBP | RGB packet | **HFP left** | HFP in µs |
| --- | --- | --- | --- | --- | --- | --- |
| ours, 39.6 MHz | 1182 | 60 | 210 | 855 | **57** | **0.96 µs** |
| LGL, 49.5 MHz | 1122 | 60 | 60 | 855 | **147** | **1.98 µs** |

(RGB packet = (568×3 + 4 hdr + 2 CRC) / 2 lanes = 855.)

LILYGO's retime does not only raise the refresh rate — by moving blanking
from the back porch (140) to the front porch (100) it also **doubles the
wall-clock front porch**. With `lp_hfp_en` set, the DWC host wants to do an
HS→LP→HS round trip inside HFP every line; at 475 Mbps that round trip is
of the order of half a microsecond. 0.96 µs is uncomfortably close to it;
1.98 µs is not. **INFERENCE** — I have no Canaan or Synopsys timing table
for this part — but it is a coherent mechanism for per-line jitter, and it
is consistent with LILYGO shipping both `0029` (clear `lp_cmd_en`) and the
retime.

Espressif, on a host that lets you choose, runs 1000 Mbps/lane against a
1440 Mbps pixel load — **39% genuine burst headroom.** That is what burst
mode is supposed to look like.

---

## 7. What our tree already has

For ranking, this matters. From `nix/kernel.nix`:

| line | change | status |
| --- | --- | --- |
| 111 | `drm_fbdev_generic_setup(drm_dev, 16)` | applied |
| 137 | panel reset moved into `prepare()`, 20/20/120 ms | applied |
| 194 | bounded `PHY_STATUS != 0x1fbd` loop | applied |
| 232 | `pm_runtime_get_sync(disp_dev)` at probe | applied |
| **249** | **`voc = 0x19` instead of 0x17** | **applied — and the flicker is still here** |

So the `vco_cntrl` hypothesis has already been tested on hardware and did
not fix it. That is the single most useful piece of negative evidence we
have, and it demotes every PLL-band theory. LILYGO reached the same place
from the other direction: `0042` *removes* their `voc = 0x19` override.

Not applied, and present in LILYGO's shipping BSP: `0029` (VID_MODE_CFG),
`0031` timings, `0027`'s `power_on` GPIO assert in prepare, `0033`
(RGB2YUV), `0043` (VO config load deferral).

---

## 8. Ranked changes to try

Ranked by likelihood of fixing **flicker on static content specifically**,
not by likelihood of being a good idea generally.

### 1. Retime to 49.5 MHz / ~52 Hz, and revert `voc` to the computed 0x17

*Confidence this fixes or substantially reduces the flicker: **high**, ~60%.*

In `nix/dts/display-rm69a10-568x1232.dtsi`:

```
clock-frequency = <49500000>;
hactive = <568>;   vactive = <1232>;
hfront-porch = <100>;  hback-porch = <40>;  hsync-len = <40>;
vfront-porch = <4>;    vback-porch = <16>;  vsync-len = <16>;
```

and **drop the `voc = 0x19` sed at `nix/kernel.nix:249`.**

Why: §5. Two independent implementations run this panel near 50 Hz; we are
the only one at 39.6 Hz; and the only first-hand artifact report on this
board names the 39.6 MHz timing as the cause and this exact timing as the
fix. Why the coupled `voc` revert: `0042` is the commit that *removes* the
0x19 override, and its stated reason is that the auto-computed PHY is what
makes the 49.5 MHz timing work. Changing both at once is normally bad
practice, but here the two changes are one upstream change split across two
patches, and we already know 0x19 alone does not help (§7).

Sanity checks done: `594000/49500 = 12` exactly, so the pixel-clock divider
is exact and `clk_freq` is not quantised; `phy_clk_freq = 297000` stays in
the same `< 330000` voc bucket; `phy_freq = 594000` with `m=99, n=4`;
`hsfreqrange` stays at the hardcoded `0x96` as it does for every other
panel this driver supports.

Risk: none to the panel. If it regresses, revert the dtsi hunk.

### 2. `VID_MODE_CFG` 0xbf02 → 0x3f02 (clear `lp_cmd_en`)

*Confidence: **medium**, ~30% on its own; strongly complementary to #1.*

One sed against `canaan_dsi.c:280`. Read from LILYGO
`0029-drm-canaan-fix-video-mode-to-burst.patch`, which ships in a working
image. Ignore its subject line — the diff clears bit 15 and nothing else
(§3).

Why it could matter for static content: `lp_cmd_en` licenses the DWC host
to leave HS and enter LP escape inside video blanking whenever it wants to
send a command. Combined with our 0.96 µs front porch (§6) that is a
per-line opportunity for the host to make a timing decision it may not have
room for. Clearing it forces all command traffic to HS and removes the
opportunity entirely. **The mechanism is INFERENCE; the patch is source.**

Cheap, independent of #1, and safe: our only post-enable DCS traffic is the
diagnostic read in `prepare()`, which runs before
`canaan_mipi_dsi_set_dsi_enable()`.

### 3. Give the DSI link real burst headroom

*Confidence: **medium-low**, ~20%, but it is the one thing no K230
implementation has ever had.*

In `canaan_dsi_clk_cfg()`, scale the PHY target above the pixel bandwidth
before the voc ladder:

```c
phy_clk_freq = dsi->clk_freq * 3 * 8 / device->lanes / 2;
phy_clk_freq = phy_clk_freq * 5 / 4;   /* 25% burst headroom */
```

Everything downstream is self-consistent: `voc`, `m`, `n` and
`dsi->phy_freq` all recompute, and `canaan_dsi_get_hcomponent_lbcc()` scales
`VID_HLINE_TIME`/`HSA`/`HBP` with `phy_freq`, so wall-clock line time is
unchanged and the slack lands in HFP. At our current 39.6 MHz this takes
HFP from 57 to 285 lane byte clocks (0.96 µs → 3.84 µs) and lands
`phy_clk_freq` at 297000 — still the same voc bucket. The pixel-clock
divider is computed from `clk`, not `phy_freq`, so it is untouched.

Why: §6. Burst mode with a link exactly saturated has no slack for any FIFO
hiccup on the VO read path, and an underrun on an AMOLED shows as a flash.
Espressif runs this panel with 39% headroom.

**This is my own construction, not from any source.** It is cheap and
reversible, but it is the first item on this list that nobody has shipped.
Try it only if #1 and #2 leave flicker behind.

### 4. Restore the universal `31` / `30` / `12` partial-mode block

*Confidence as a flicker fix: **low**, ~15%. Confidence that we should not
stay the sole outlier: high.*

```
39 00 05 31 00 03 02 34
39 00 05 30 00 00 04 cf
15 00 02 12 00
```
replacing our `15 03 02 13 00`.

Why: §1. RTS, LGL, ESP and CBD all send it; nobody sends `0x13`. We removed
it for banding, at 39.6 Hz, before any of the other changes here. Retest it
*after* #1 — if the banding was a symptom of the timing rather than of
partial mode, this comes back for free and we stop diverging from four
working implementations.

Note the wire form: RTS/ESP/CBD all send `12` **with** a `0x00` parameter;
only LGL sends the bare `05 00 01 12`. Use the 2-byte form to match the
majority.

### 5. Widen VSA / vertical blanking

*Confidence: **low**, ~10%, and mostly subsumed by #1.*

Ours has `vsync-len = 4`; LGL uses 16, ESP uses 40. ESP also gives 240
lines of vertical blanking against our 36. If #1 is adopted as written we
get `vsync-len = 16` for free. If flicker persists, the next step is an
ESP-shaped vertical blank (vsync 40 / vbp 120 / vfp 80), which at 49.5 MHz
and htotal 748 gives 49.5e6/(748×1472) = 44.9 Hz — so it must be paired with
a higher pixel clock, e.g. 59.4 MHz (`594000/10`) → 53.9 Hz.

### 6. LILYGO `0043` — defer VO config load to vblank

*Confidence: **very low** for this symptom, ~5%.*

Fetched and read. Its own commit message says the artifact it fixes is
"a short tearing or shearing artifact during full-page UI transitions",
i.e. on page flips. With a static framebuffer `canaan_vo_flush_config()`
is not being called, so there is nothing to defer. Adopt it later for
correctness, not now for flicker. (It also flips OSD
`ADDR_SEL_MODE` `0x100` → `0x1100`, which is likewise flip-related.)

### 7. Borrow the `0xA1` chip-ID probe

*Confidence as a flicker fix: **zero**. Value as a diagnostic: real.*

ESP and CBD both gate init on `read(0xA1) == 0x01`. Our `RDDPM (0x0A)` read
still times out even with the panel working (`panel-lit.md:60-67`), so we
have no working liveness probe. `0xA1` is a one-byte read that two
independent drivers rely on, which makes it a better test of our DCS read
path than `0x0A` was.

---

## 9. Explicitly ruled out

| Hypothesis | Verdict | Basis |
| --- | --- | --- |
| Burst vs sync-pulse mode mismatch | **Ruled out** | `canaan_dsi.c` never reads `dsi->mode_flags` (grep, zero hits); `VID_MODE_CFG` hardcoded `0xbf02`, bits[1:0] = burst. We have always been in burst mode. |
| TE (`0x35`) harmful in video mode | **Ruled out** | All four implementations send it, all four are video mode, none consumes TE. |
| Missing VCOM calibration | **Ruled out** | No RM69A10 implementation writes any VCOM register. Compare `panel-raydium-rm68200.c` which writes `0x46 VCMCTR` — RM69A10 exposes no equivalent. |
| Missing oscillator / frame-rate register | **Ruled out** | No implementation writes one. The whole vendor block is `FE FD / 80 FC / FE 00`. |
| Missing `0xB2` lane select | **Ruled out (again)** | Not written by RTS, LGL, ESP or CBD. |
| Panel wants command mode with explicit frame writes | **Ruled out** | Nobody does this. ESP and CBD both build a DPI (video-mode) panel with a DBI side-channel for commands only. |
| Host DPI timing drifting against DSI programmed timing | **Ruled out** | `VID_HLINE_TIME = 788 × 1.5 = 1182` byte clocks at 59.4 MHz = 19.899 µs; VO line = 788 / 39.6 MHz = 19.899 µs. Vertical lines match exactly. No accumulating phase error. |
| `vco_cntrl` 0x17 vs 0x19 | **Tested, negative** | `nix/kernel.nix:249` already forces 0x19 and the flicker is present. LILYGO's `0042` removes the same override. |
| Our init sequence is missing commands | **Ruled out** | §1: we send a superset of ESP's and all but one line of RTS's. |

---

## 10. Read vs inferred

**Read from a source**, quoted or transcribed above: every init sequence in
§1; the `0042` commit message; the `0029` diff; all five timing tables in
§5; `VID_MODE_CFG = 0xbf02` and the absence of any `mode_flags` reader in
`drivers/gpu/drm/canaan/`; `canaan_dsi_transfer()`'s routing; the
`canaan_dsi_clk_cfg()` arithmetic; `esp_lcd_rm69a10.c`'s `0xA1` probe;
`rm68200`'s VCOM/power registers.

**Inference, mine:** the DWC `VID_MODE_CFG` bit decode (standard Synopsys
layout, no Canaan document); the lane-byte-clock budget table in §6 and the
claim that a 0.96 µs HFP is marginal for an LP round trip; the AMOLED
emission-pulse explanation for why 39.6 Hz would flicker on static content;
recommendation #3 in its entirety.

**Not verified by me:** that any of these implementations actually produces
a flicker-free panel. "Works" means the author says so and the code is
coherent. The strongest evidence in this document is `0042`'s first-hand
statement about low-refresh stutter on this board, and even that is an
AI-authored commit message in a series the research doc already flags as
unreliable about its own diffs — though this one is a *behavioural* claim,
not a claim about what the diff does, so the usual failure mode does not
apply.
