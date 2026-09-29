# HDMI hot-plug: can plugging in HDMI switch the display automatically?

Researched 2026-09-28 on worktree `k230-hdmi-hotplug`, branch
`spec/hdmi-hotplug`, base `e843c5d6`. Research only — no board access, no
push/merge. Answers the six questions from the task brief, in order, each
grounded per `.skills/k230-spec-change/SKILL.md`'s tiering (board observation
> vendor source read > nothing, which gets `<!-- UNVERIFIED -->`). Nothing in
this document is tier-1 (board-observed); every claim below is tier 2 (vendor
or our own source, read and cited by path/line) unless flagged UNVERIFIED.

**Headline answer:** there is no mux chip. The four DSI data lanes and clock
are wired in bare parallel to both the RM69A10 panel and the LT9611 bridge —
confirmed from the schematic, not inferred. The panel and the LT9611 also
share their reset and interrupt GPIOs as literal single nets, not merely as
reused pin numbers in different device trees. Every vendor source we found
(LILYGO's own abandoned merge attempt, their shipped launcher UI, and our own
`nix/sd-image.nix`'s documented U-Boot behavior) selects HDMI vs. panel by
**which device tree blob boots**, and switches by **rebooting**. Nobody —
not LILYGO, not Canaan's reference tree, not our own kernel — has ever
switched the K230's single DSI host between a panel and a bridge without a
reboot. Our kernel's bridge-attach path is additionally missing a connector
creation call, so even the reboot-based switch does not work out of the box.
True hot-plug-without-reboot, which is what the user asked for, is therefore
a real, unproven engineering project, not a device-tree edit. Section 5
stages the work so the reboot-based switch (which mirrors a demonstrated
vendor mechanism) ships first, and the no-reboot goal is pursued after it as
explicitly higher-risk, possibly-infeasible follow-on work.

## Sources used

- `Xinyuan-LilyGO/T-Display-K230_canmv_rt` @ `abb07090ad8a666ed7a5e097b3c714b918731645`
  (fetched via `gh api`, 2026-09-28) — carries
  `schematic/T-Display K230_V1.0_NEW.pdf` (8 sheets, Altium-exported,
  `pdfinfo`-confirmed) and the full RT-Smart/U-Boot/CanMV SDK tree
  (`canmv_k230/...`) that `docs/findings.md` and `docs/dts-evidence.md`
  already cite as `repo/...`. No local checkout of this repo exists in this
  worktree; the earlier `repo/` paths cited in `docs/findings.md` were a
  transient clone from a prior session and are gone. This document re-fetched
  the specific files it needed directly from GitHub rather than re-cloning
  ~750 MB.
- `Xinyuan-LilyGO/T-Display-K230` @ `bb831ab358b66f5bd9a87ecd7c580fee4537492e`
  — carries the `k230_bsp/` patch set against `kendryte/k230_linux_sdk`
  (same grounding tier established in
  `docs/research/board-capability-inventory.md`) and the `k230_launcher/`
  LVGL source, including `ui_hdmi_test.c`, the actual shipped "switch to
  HDMI" UI.
- Our pinned kernel, `ruyisdk/linux-xuantie-kernel` @
  `7d4e1f444f461dbe3833bd99a4640e7b6c2cd529`, built locally at
  `/nix/store/prjax8g4y7x40j641qipjk4cwp45fd72-linux-xuantie-k230-src` via
  `nix build .#nixosConfigurations.k230.config.boot.kernelPackages.kernel.src`.
  Every "our tree has/lacks X" claim below was read from that exact checkout.
- Our own `nix/sd-image.nix`, `nix/kernel.nix`, `nix/dts/k230-tdisplay.dts`.

## 1. Hardware routing: how do the DSI lanes and clock reach both outputs?

**No mux or switch chip exists on this board.** The schematic shows plain
parallel copper: the SoC's four DSI data-lane pairs and clock pair are one
set of nets, and both the panel connector and the LT9611 bridge are wired
directly to that same set.

Evidence, from `T-Display K230_V1.0_NEW.pdf` (Altium export, 8 sheets, A4 and
A3/A2 title blocks, drawn by LILYGO, dated 2026-06-26):

- **Sheet "K230" (page 4 of the PDF)**, the SoC's own MIPI block (`U22C`,
  labelled `MIPI`), left column: pins `MIPI_TX0_CLK_P/N` and
  `MIPI_TX0_D0_P/N`..`MIPI_TX1_D3_P/N` are wired to net labels
  `DSI_CLK_P`/`DSI_CLK_N` and `DSI_D0_P/N`..`DSI_D3_P/N` (pins Y9/W9,
  W10/Y10, Y11/W11, W8/Y8, Y7/W7). These are the SoC package pins for its one
  DSI host.
- **Sheet "HDMI+ETH" (page 7)**, the LT9611 (`U18`), right-hand pin block:
  its **second** MIPI RX port (`MLRXB_D0P/N`..`MLRXB_D3P/N`, pins 49–58) is
  wired to net labels **`DSI_D0_P/N`, `DSI_D1_P/N`, `DSI_D2_P/N`,
  `DSI_D3_P/N`, `DSI_CLK_P/N`** — the identical net names from the MIPI
  sheet above. Its **first** MIPI RX port (`MLRXA_*`, pins 38–47) is drawn
  with only the chip's own alternate pin-function silkscreen text
  (`TX_C+`/`TX_D0+`, etc.) and carries no wire or net label — unpopulated,
  not stuffed onto anything.
- This is a direct, unambiguous conclusion from Altium net-name matching: a
  wire segment on one sheet and a wire segment on another sheet with the
  *same* net label are the same electrical node. The SoC's DSI TX pins, the
  panel connector, and the LT9611's DSI RX pins all sit on that one set of
  nets. There is no resistor array, no analog switch (e.g. no `TS3USB`-style
  part, no `FSA`-family switch, no relay) anywhere between them — R74–R77 on
  the HDMI sheet are 10k pull-ups on the LT9611's I2C/reset/interrupt lines,
  not lane-isolation components.
- The LT9611's TMDS output side (`TX_D0`–`TX_D2`, `TX_C`, its transmit pins)
  goes through two `TPD4E05U06` ESD arrays to the physical `HDMI1` connector
  (page 7, right half), confirming the LT9611 is doing real DSI→TMDS
  protocol conversion (a genuine bridge IC), not passing signals through
  unmodified.

**The panel connector only breaks out two of the four lanes.** Sheet "Video"
(page 4 in file order, titled "Video"), the 15-pin LCD/touch FPC connector
lists pins `DSI_CLK_N`/`DSI_CLK_P`, `DSI_D0_P/N`, `DSI_D1_P/N` only — no D2/D3
pins on that connector. This matches our own device tree's
`panel-dsi-lane = <2>` (`nix/dts/display-rm69a10-568x1232.dtsi:72`) and
confirms the RM69A10 runs 2-lane while the LT9611, wired to all four pairs,
would run 4-lane. **UNVERIFIED**: whether D2/D3 being simultaneously driven
by the host (if a future DT ran the DSI host in 4-lane mode for HDMI) while
left floating/unterminated at the panel connector causes any signal-integrity
concern for the panel's own 2-lane reception; not measured, and the two
lane counts are configured by two different, mutually exclusive device
trees today (see §3), so they have never been electrically simultaneous in
any observed boot.

**GPIO23/24 are literal shared nets, not just reused GPIO numbers.** Sheet
"Video", the net-label table directly above the 15-pin LCD/touch connector
reads (transcribed from the rendered schematic):

```
I2C3_SCL  ->  HDMI_CSCL  ->  TP_SCL   (connector pin 3)
I2C3_SDA  ->  HDMI_CSDA  ->  TP_SDA   (connector pin 4)
HDMI_RSTN ->  TP_RST                  (connector pin 5)
HDMI_INT  ->  TP_INT                  (connector pin 1)
```

Each arrow is the *same wire* carrying two net-label annotations, not two
separate nets tied by a jumper — this is one continuous, unbroken run
connecting the LT9611's `RSTN` pin (33) and `CSCL`/`CSDA` pins (34/35) on the
HDMI sheet to the touch/LCD FPC connector's `TP_SCL`/`TP_SDA`/`TP_RST` pins,
and the LT9611's `INT_ATST_GPIO3` pin (12) to that connector's `TP_INT` pin.
This resolves the "not established" flag in `docs/dts-evidence.md:157-159`
and `docs/findings.md:207-208`: **the schematic has now been read for this
exact question, and the answer is yes, LT9611 reset/interrupt/I2C and touch
reset/interrupt/I2C are the same physical nets.** The panel's own reset
(`LCD_RST`, connector pin 11, `GPIO22`) is a separate, standalone net *not*
tied to `HDMI_RSTN` — the LT9611 does not touch the panel's own reset or
enable lines, only touch's.

This single-net sharing has a consequence beyond "pick one in the device
tree": vendor and our own device trees disagree about the electrical
convention on that shared line. The vendor's `k230-canmv-v3.dts` LT9611 node
requests `reset-gpios = <&gpio0_ports 24 GPIO_ACTIVE_HIGH>`
(`k230-canmv-v3.dts:64`, in our pinned kernel tree), while our board's touch
node requests `reset-gpios = <&gpio0_ports 24 GPIO_ACTIVE_LOW>`
(`nix/dts/k230-tdisplay.dts:200`) on the *same physical pin*. Similarly the
vendor LT9611 node asks for `interrupts = <23 IRQ_TYPE_EDGE_FALLING>`
(`k230-canmv-v3.dts:66`) while our touch node asks for
`interrupts = <23 IRQ_TYPE_LEVEL_LOW>` (`nix/dts/k230-tdisplay.dts:224`,
deliberately changed from edge to level per that file's own comment, because
edge-triggered lost interrupts on this exact silicon). Two drivers wanting
different trigger types and different active-sense on one wire is a real
conflict, not a naming coincidence — reinforcing why no vendor source ever
wires both nodes into one device tree at once (§3).

## 2. What GPIO23/24 do, and what else is nearby

- **GPIO24**: touch reset (our DT, active-low) *and* LT9611 reset (vendor
  DT, active-high) — the same physical net, different requested polarity.
  Plain GPIO output in both roles.
- **GPIO23**: touch interrupt (our DT, level-low) *and* LT9611 host
  interrupt (vendor DT, edge-falling) — same physical net, different
  requested trigger type. Plain GPIO input in both roles.
- **GPIO22/GPIO25**: panel-only (reset / backlight-enable). Not touched by
  the LT9611 net set. No conflict.
- **I2C3** (`GPIO36`/`GPIO37`, SCL/SDA): shared bus, not a shared net in the
  problematic sense — I2C buses are designed for multiple devices. Touch is
  `0x5d`, LT9611 is `0x3b`; no address collision
  (`docs/dts-evidence.md:151-155`, confirmed again here from the schematic).
- **HDMI hot-plug sense**: the physical HDMI receptacle's `HOTPLUG` pin
  (connector pin 19, sheet "HDMI+ETH") is wired *only* to the LT9611's own
  `HPD_GPIO2` input (pin 13) — there is no independent HPD-sense line run to
  a spare K230 GPIO. The K230 can only learn a cable was plugged in by
  asking the LT9611 (over I2C, or via its `INT_ATST_GPIO3` output on the
  GPIO23 net), which means **the LT9611 must already be a live, un-reset,
  I2C-probed device for HDMI plug detection to work at all.** This is the
  central hardware constraint on any no-reboot design (§5).
- No other GPIO used by an already-populated peripheral (LoRa: GPIO5,
  14–20, 44; camera: GPIO21, 48/49; SD: GPIO54–59; Wi-Fi: GPIO45) overlaps
  GPIO23/24 or the DSI lanes.

## 3. How LILYGO's own firmware enables HDMI

**It is a boot-time device-tree choice with a full reboot, not a runtime
switch — and LILYGO's own engineering history shows they tried a merged
device tree first and abandoned it.**

Evidence, `Xinyuan-LilyGO/T-Display-K230`, `k230_bsp/overlay/buildroot-overlay/linux/`:

- Patch `0055-riscv-dts-add-rm69a10-hdmi-output-dtb.patch` adds a **new,
  separate** `k230-canmv-rm69a10-hdmi.dts`, built as its own `.dtb`
  (`dtb-$(CONFIG_ARCH_CANAAN) += k230-canmv-rm69a10-hdmi.dtb`, a new line in
  the DTS `Makefile`, not a modification of the panel DTS). It puts the
  LT9611 bridge on `&dsi`'s single `port@1` (`reset-gpios = <&gpio0_ports 24
  GPIO_ACTIVE_HIGH>`, matching the shared net found in §1) and carries no
  touch node and no RM69A10 panel node at all.
- Patch `0062-riscv-dts-rm69a10-hdmi-use-sdk-v3-baseline.patch` then
  `#if 0`s that *entire* custom file and replaces it with a bare
  `#include "k230-canmv-v3.dts"` — the generic Canaan reference-board tree,
  unrelated to this board's panel or touch silicon, whose own comment
  explains why: *"The board-specific HDMI attempt above is kept for
  reference but is not used. The SDK CanMV v3 HDMI DTB was verified on
  T-Display K230: LT9611 probes, EDID is read, and HDMI-A-1 exposes
  800x480@60. Reuse that known-good HDMI graph until a reduced
  board-specific DTS is proven."* LILYGO's own working, verified HDMI mode
  is therefore the **unmodified upstream reference-board DTB**, output at
  800x480@60 (not 720p), with no panel and no touch node present in that
  boot image at all — the two silicon paths were never merged into one
  working device tree by LILYGO either.
- The actual switch mechanism, `k230_launcher/k230_phone_ui/src/ui_hdmi_test.c`
  (490 lines), is a **double-tap-confirm, reboot-based, self-reverting**
  boot-DTB swap:
  - `HDMI_ACTIVE_DTB "/boot/k.dtb"` is the file U-Boot actually loads.
    `HDMI_PANEL_DTB` and `HDMI_OUTPUT_DTB` are the two alternatives.
  - Tapping the HDMI button once arms a confirmation (`"Tap again to confirm
    HDMI reboot"`, 8-second window, `ui_hdmi_test.c:384-389`); a second tap
    within that window calls `hdmi_start_boot_switch()`.
  - `hdmi_boot_switch_thread()` (`ui_hdmi_test.c:312-343`) runs: remount
    `/boot` read-write, write a **one-shot restore marker**
    (`/boot/k230_hdmi_next_boot_only`, containing `restore=<panel DTB
    path>`), `cp` the HDMI DTB over the active `k.dtb`, `sync`, `reboot`.
  - `ui_hdmi_test_restore_one_shot_boot()` (`ui_hdmi_test.c:279-300`) runs
    early on **every** subsequent boot: if the marker file exists, it
    immediately copies the panel DTB back over `k.dtb`, deletes the marker,
    and syncs — so HDMI mode is automatically good for exactly one boot.
    Power-cycle again (for any reason, not just to leave HDMI mode) and the
    board silently reverts to the AMOLED panel. There is no path in this
    source that switches without a `reboot` call.
  - The same file also polls `/sys/class/drm` at runtime (read-only,
    `hdmi_find_connector()`, `ui_hdmi_test.c:147-172`) for entries matching
    `"HDMI"` / `"DSI"` and shows live connected/mode status plus a
    "next boot: HDMI boot / AMOLED boot / AMOLED restore pending" line —
    confirming the vendor's own kernel enumerates connectors as
    `*-HDMI-*` / `*-DSI-*`, consistent with standard DRM connector naming
    and with the `HDMI-A-1/DSI-1` names used in this document.
- Init sequence / timings: not separately re-derived here since LILYGO's
  working HDMI path uses the *unmodified* upstream `k230-canmv-v3.dts` and
  the mainline `lontium-lt9611.c` driver's own internal register sequences
  (`drivers/gpu/drm/bridge/lontium-lt9611.c`, §4) — there is no
  board-specific LT9611 init sequence to transcribe, unlike the panel.

**Our own vendored U-Boot already has an equivalent selection mechanism,**
independently confirmed from our own committed, hardware-tested source
comments in `nix/sd-image.nix:142-156`: U-Boot's `bootcmd` runs a
`k230_set_dtb` command that reads a *text file naming a DTB* — trying
`force_dtb` first (short-circuits selection), then falling back to
`hdmi_dtb`, then `lcd_dtb` twice, observed on hardware to fail all three and
drop to a U-Boot prompt if none of the three files exist. Our SD image
writes all three names pointing at the same panel DTB today, to keep first
boot simple. **UNVERIFIED**: whether U-Boot's `hdmi_dtb`/`lcd_dtb` fallback
path performs its own live display-presence probe (i.e., a stage-1
auto-detect independent of LILYGO's userspace toggle) or is purely an
operator-set preference file read at boot with no hardware probing; the
U-Boot C source for `k230_set_dtb` was not read for this document (it ships
as a prebuilt blob per `nix/uboot-k230.nix`, not as buildable source we
have checked out). This is worth resolving before design work in §5, since
if U-Boot itself already probes for a live cable, that is a much cheaper
place to do boot-time selection than anything in Linux.

## 4. Our kernel

- **`CONFIG_DRM_LONTIUM_LT9611=y`** is set in the pinned kernel's own
  `arch/riscv/configs/k230_defconfig:286`, and `nix/kernel.nix` (`defconfig
  = "k230_defconfig"`, `structuredExtraConfig` starting line 610) does not
  touch that symbol — so it inherits `y` and the mainline
  `drivers/gpu/drm/bridge/lontium-lt9611.c` driver is already built into
  every kernel we produce today. It is simply unused: no device tree we
  ship references an LT9611 node.
- **The DSI host is architecturally single-output, resolved once at boot,
  not switchable at runtime.** `drivers/gpu/drm/canaan/canaan_dsi.c`'s
  `canaan_dsi_bind()` (line 695) calls
  `drm_of_find_panel_or_bridge(dsi->dev->of_node, 1, -1, &dsi->panel,
  &dsi->bridge)` — a single lookup of `&dsi`'s `port@1`, executed exactly
  once, during component-master bind at driver probe (module load / boot
  time). Whichever single endpoint is described under `port@1` in the
  loaded DTB (the RM69A10 panel node in our DT, or the LT9611 bridge node in
  the vendor DT — never both; a DT graph port has one endpoint) becomes
  `dsi->panel` XOR `dsi->bridge` for the life of that boot. There is no code
  path anywhere in `canaan_dsi.c` that re-invokes this lookup, and
  `canaan_dsi_detach()` (line 560) only clears these fields when the child
  `mipi_dsi_device` itself unregisters (its own probe/remove), not as a
  general "swap to a different device" API. **A true runtime swap between
  panel and bridge does not exist in this driver as written**, which matches
  every vendor source found in §3: nobody switches without a reboot because
  the driver genuinely cannot.
- **The bridge path is currently missing its connector.** In
  `canaan_dsi_bind()`, the panel branch (`if (dsi->panel)`, lines 699-711)
  creates a `drm_connector` (`DRM_MODE_CONNECTOR_DSI`) and attaches it to
  the encoder. The bridge branch (`if (dsi->bridge)`, lines 713-714) only
  calls `drm_bridge_attach(&dsi->encoder, dsi->bridge, NULL,
  DRM_BRIDGE_ATTACH_NO_CONNECTOR)` — and `DRM_BRIDGE_ATTACH_NO_CONNECTOR`
  means the caller promises to create the connector itself, elsewhere.
  Neither `canaan_dsi.c` nor `canaan_drv.c` (grepped for
  `drm_bridge_connector`, zero hits in
  `drivers/gpu/drm/canaan/canaan_drv.c` and `canaan_dsi.c`) ever calls
  `drm_bridge_connector_init()`. **As our kernel stands today, wiring an
  LT9611 node into a board DTB would attach the bridge to the encoder but
  create no DRM connector at all** — no `HDMI-A-1` would ever appear to
  `modetest`, Sway, or anything else. This is a small, well-understood
  kernel patch (add `drm_bridge_connector_init(dsi->drm, &dsi->encoder)` +
  `drm_connector_attach_encoder()` in the bridge branch), but it is a real
  gap, not merely a missing DT node, and is a prerequisite for *any* HDMI
  output under our kernel, reboot-based or not. Task 2.1 of
  `openspec/changes/plugging-in-hdmi-moves-the-display` implements exactly
  this call as `nix/patches/canaan-dsi-bridge-connector.patch`, applied
  unconditionally in `nix/kernel.nix`; it is inert on the panel boot path
  because it only runs when `dsi->bridge` is non-NULL.
- **The vendor `k230-canmv-v3.dts` LT9611 port numbering does not satisfy
  this kernel's own `lontium-lt9611.c` as written.** That file's node (§1,
  §3) wires the LT9611's DSI-input endpoint at `port@1` (`reg = <1>`) and
  its downstream-connector endpoint at `port@2`, with no `port@0` at all.
  But `lt9611_parse_dt()` (`lontium-lt9611.c:906-919`, this same pinned
  tree) reads the primary DSI node from **port 0**
  (`of_graph_get_remote_node(dev->of_node, 0, -1)`, fatal to probe if
  absent — `"failed to get remote node for primary dsi"`), an *optional*
  dual-link DSI node from port 1, and the downstream bridge/connector from
  **port 2**. `of_graph_get_remote_node()` matches a port node's `reg`
  property, not its position in the file
  (`drivers/of/property.c:837-855`), so a node with only `reg=1`/`reg=2`
  has no `reg=0` port and `lt9611_probe()` would fail
  `lt9611_parse_dt()` before ever touching hardware. Whether Canaan's or
  LILYGO's own kernel fork's `lontium-lt9611.c` tolerates the vendor
  file's own 1/2 numbering was not checked — that is a different source
  tree, not read for this document. What is established is that *this*
  pinned tree's driver needs `port@0`/`port@2`, and task 2.2's
  `nix/dts/k230-tdisplay-hdmi.dts` is written against that reading rather
  than copied from `k230-canmv-v3.dts`'s numbers. This is unverified on
  hardware either way — it changes the DTB compile-time facts only; the
  probe that would confirm or refute it is tasks.md group 3/4's board
  time.
- **DSI lane rate is not a blocker.** `canaan_dsi_clk_cfg()`
  (`canaan_dsi.c:330-405`) derives the pixel clock as an integer division of
  a fixed 594 MHz reference (`div = DIV64_U64_ROUND_CLOSEST(594000, clk)`),
  and `canaan_dsi_encoder_mode_fixup()` (line 497) snaps any requested mode
  clock onto that same 594/n grid. The panel's 49.5 MHz is exactly 594/12;
  720p60's 74.25 MHz is exactly 594/8; 1080p60's 148.5 MHz is exactly 594/4
  — all three land precisely on-grid, so no new clock-generation code is
  needed. The PHY bit-rate bound checked in the same function
  (`phy_clk_freq` must be 40,000–1,250,000 kbps) comfortably covers 4-lane
  1080p60 RGB888 (≈891 Mbps/lane) and 720p60 (≈445.5 Mbps/lane); the panel
  runs 2-lane at 594 Mbps aggregate today (`docs/evidence/dsi-hsfreqrange-hardcoded.md`
  records 594 Mbps measured). Lane *count* does change (2 for the panel
  connector, 4 for the LT9611, per §1) and is a `mipi_dsi_device->lanes` /
  DT property difference between the two mutually-exclusive board files,
  not a runtime-negotiated value.
- **The LT9611 HPD interrupt is fully implemented in the mainline driver**
  but shares hardware with touch. `lt9611_irq_thread_handler()`
  (`drivers/gpu/drm/bridge/lontium-lt9611.c:413-450`) reads the chip's own
  status registers (`0x820f`, `0x820c`), distinguishes HPD-low/HPD-high
  internally, and the bridge implements `.detect`, `.hpd_enable`
  (`lt9611_bridge_funcs`, lines 888-903) — standard `drm_bridge` hotplug
  machinery. `canaan_drv.c:265` already calls `drm_kms_helper_poll_init()`,
  so a correctly-connectored LT9611 bridge would propagate a real hotplug
  uevent to userspace. But the physical interrupt line the mainline driver
  expects (`client->irq`, from the i2c node's `interrupts` property) is the
  GPIO23 net shared with touch (§1/§2) — using it live, concurrently with
  touch, requires `IRQF_SHARED`-compatible handling on both drivers'
  request calls and, **UNVERIFIED**, depends on whether the LT9611's
  `INT_ATST_GPIO3` output and the GT9895's own interrupt output are both
  genuinely open-drain (safe to wire-OR) rather than push-pull (which would
  contend electrically) — not established from the schematic (drive type
  isn't shown on a schematic net) and not measured on hardware.

## 5. Designing a hot-swap

Given §3 and §4, split the goal into what is demonstrated to work
(reboot-based switching, once our kernel gets the missing connector patch)
and what is not demonstrated anywhere (no-reboot switching while Linux keeps
running). The OpenSpec proposal
(`openspec/changes/plugging-in-hdmi-moves-the-display/`) stages exactly
this split; summarized here:

1. **Read-only board probe** (board-gated, narrow, no writes): confirm the
   0x3b I2C identity actually answers on `&i2c3` with touch present and
   read the LT9611's HPD status register through it, and read GPIO23/24's
   current direction/level with touch running, without changing anything.
   This is the answer to "what is the first board probe command" below.
2. **Driver/DT build** (host-build-proof only, no board changes): add the
   missing `drm_bridge_connector_init()` call to `canaan_dsi.c`, and build
   (not boot) a second, HDMI-only DTB derived from `k230-tdisplay.dts`'s own
   `&dsi` graph (our own board's I2C/GPIO facts, not the vendor's
   generic tree) so the resulting `HDMI-A-1` connector is genuinely this
   board's LT9611, not a copy of the unrelated Canaan reference tree.
   Verified by `nix build`, not by booting.
3. **Manual switch, reboot-based** (board-gated): the credible near-term
   deliverable. Mirrors LILYGO's own proven, self-reverting one-shot
   mechanism (§3) using our own `nix/sd-image.nix`/`nix/device-tree.nix`
   machinery: write an alternate `/boot/k230-tdisplay-hdmi.dtb`, flip
   U-Boot's DTB-selector text file, reboot; a one-shot marker restores the
   panel DTB on the *next* boot regardless of why it happened, so a bad
   probe or an unrelated crash always self-heals back to the panel. This
   satisfies the AGENTS.md/task risk requirement directly: recovery is a
   plain reboot, and it defaults to the panel.
4. **Hotplug automation, no reboot** (board-gated, explicitly high risk):
   attempt the design the user actually asked for. The concrete blockers,
   all found above, that make this uncertain rather than merely large:
   - The LT9611 can only be *found* by the K230 (§2) if it is already a
     live, un-reset, I2C-probed device — which means it must be present in
     the *running* boot's device tree even while the panel is the active
     display, contradicting §4's one-endpoint-per-port finding. A DT where
     the LT9611 exists as a plain I2C client (for HPD/status polling)
     without being the `&dsi` `port@1` endpoint might let it probe and
     raise its shared-GPIO23 interrupt without contending for the DSI
     graph — untested, and depends on the open-drain question in §4.
   - GPIO24 (reset) is a single net with two disagreeing polarity
     conventions (§1). A no-reboot design cannot reset one chip without
     also resetting the other; the only safe pattern is to never
     re-toggle GPIO24 after both chips' initial power-on reset, and confirm
     — UNVERIFIED, not measured — that neither driver retoggles it during
     normal `atomic_enable`/mode-change operation.
   - Actually repainting the DSI host from panel to bridge live requires
     new `canaan_dsi.c` logic (tear down the panel connector/encoder state,
     bring up a bridge connector/encoder, without the one-shot
     `drm_of_find_panel_or_bridge()` this driver currently relies on) —
     real, unbounded-until-attempted kernel work, not present in any source
     surveyed.
   - Sway/card-shell must additionally handle the resulting output-topology
     change (`DSI-1` disappearing, `HDMI-A-1` appearing at a different
     resolution and orientation) — see the landscape audit below, and note
     it is Large on its own.
   Given this, task the OpenSpec proposal to attempt automation but mark it
   explicitly speculative, separate from the reboot-based switch, so the
   reboot-based switch is not held hostage to an unproven no-reboot design.
5. **Manual override in Settings**: a Settings row that triggers the
   reboot-based switch (stage 3) directly, independent of whether stage 4
   ever lands — cheap, and gives the user *a* working "go to HDMI" control
   immediately even if true hot-plug automation stalls.

### What in the shell and card-shell assumes a fixed 568×1232 portrait panel

Grep for `568`/`1232` and output names across `nix/shell.nix` and
`nix/rust-shell-client/src/*.rs` (the "shell" capability) and
`nix/card-shell/`, `nix/card-shell-policy/` (the "card-shell" capability):

- **`nix/shell.nix:679`**: Sway config hardcodes
  `output DSI-1 mode 568x1232 transform normal scale 1 render_bit_depth 6
  max_render_time 8`, and `:680` hardcodes
  `input type:touch map_to_output DSI-1`. Nothing here recognizes or
  positions an `HDMI-A-1` output; a second connector today gets whatever
  Sway's own default heuristic does with it, unconfigured.
- **`nix/rust-shell-client/src/lib.rs:82`**:
  `const DESIGN_ASPECT: f64 = 568.0 / 1232.0;` — a single compiled-in
  portrait aspect ratio checked throughout rendering and hit-testing
  (`configure_preserves_aspect`, `frame_bytes`, etc., `lib.rs:222-282`).
- **476 lines across `nix/rust-shell-client/src/*.rs`** contain a literal
  `568` or `1232` (`grep -rn "568\|1232" nix/rust-shell-client/src/*.rs |
  wc -l`; 380 of those lines are outside anything matching `#[test]`,
  `assert_eq`, `assert!` or `fn test_`, i.e. not test-only). Heaviest
  concentrations: `render.rs` (167 hits, the largest file),
  `navigation.rs` (66, including tile-grid math like
  `navigation.rs:10`'s `2*24 + 3*24 + 4*112 = 568`), `main.rs` (61),
  `home_grid.rs` (55), `service_ui.rs` (52). Representative non-test
  examples: `render.rs:1098` (`cr.scale(width / 568.0, height / 1232.0)`),
  `wifi_ui.rs:400-401` (touch-point rescaling hardcoded to 568/1232 rather
  than derived from the actual output geometry).
- **`nix/card-shell-policy/card-shell-policy.c:58`** independently notes the
  card shape as "(568:1232), i.e. a phone-shaped card" in a comment —
  confirming the card-shell's own policy layer also assumes this aspect
  ratio, though it has no other numeric 568/1232 occurrences (grepped, one
  hit total).
- No occurrence of `landscape` as a real code path was found; the shell has
  never run at a non-portrait aspect ratio.

This is a **Large** item on its own (476 raw literal-constant hits, 380 of
them outside test code), separate from and larger than the DSI/DT
work above. It needs, at minimum: deriving the design-space transform from
the actual output's reported geometry instead of the `568.0`/`1232.0`
literals in `lib.rs`/`render.rs`/`wifi_ui.rs`; a landscape layout for the
grid/navigation/service-UI screens (`navigation.rs`, `home_grid.rs`,
`service_ui.rs`) rather than a naive stretch of the portrait design; and a
Sway output/input stanza for `HDMI-A-1` alongside the existing `DSI-1` one
in `nix/shell.nix`. None of this can be host-verified beyond compiling and
unit-testing the now-parameterized math; the actual on-monitor layout needs
a board with an HDMI display attached.

## 6. Risk and recovery

A wrong mux/modeset gives a black panel or a black HDMI output. Because
there is no mux (§1), "wrong mux" in practice means "wrong DTB" or "wrong
GPIO polarity on the shared reset net" — both are boot-time, not
runtime-silent, failure modes once stage 3 exists. Recovery is a reboot,
and it must default to the panel:

- The U-Boot DTB-selector text files (`force_dtb`, `lcd_dtb`, `hdmi_dtb`,
  `nix/sd-image.nix:154-156`) must keep pointing at the panel DTB by
  default on every fresh image build; only an explicit, one-shot runtime
  action (mirroring LILYGO's `HDMI_ONE_SHOT_MARKER` restore-on-next-boot
  pattern, §3) may switch them, and that action must itself write the
  restore marker before rebooting, so any subsequent reboot — deliberate or
  a crash — lands back on the panel automatically. This is the same
  property LILYGO already ships and is directly reusable.
- Nothing about this design touches stage 1 binaries, U-Boot SPL, or the
  boot partition's fixed files (`Image`, `fw_jump_add_uboot_head.bin`,
  `boot/bootargs.txt`) — only which named `.dtb` file the existing,
  already-hardware-proven selector mechanism points at. A failed HDMI probe
  or a bad DTB build therefore cannot break the existing boot path; at
  worst it leaves the board on the panel DTB, unchanged from today.

## Answers to the report questions

- **Mux or not**: not a mux. Bare parallel wiring of all four DSI lanes and
  the clock (schematic-confirmed, §1); the panel and LT9611 additionally
  share their reset and interrupt GPIOs as one literal net each, with
  disagreeing polarity/trigger-type conventions between the vendor's LT9611
  node and our own touch node.
- **Runtime hot-swap feasibility**: not demonstrated anywhere (LILYGO,
  Canaan's reference tree, or our own kernel), and our DSI host driver's
  architecture (one-shot `drm_of_find_panel_or_bridge()` at boot,
  `canaan_dsi.c:695`) does not support it as written. A reboot-based switch
  is feasible and has a working precedent to copy (§3, §5 stage 3). True
  no-reboot hot-plug is unproven, high-risk new kernel work (§5 stage 4).
- **Effort per stage**: probe = S (board time, no writes); driver/DT build
  = M (one kernel patch + one alternate DTB, host-verified only); manual
  reboot-based switch = M (mirrors a proven mechanism, board-gated);
  no-reboot hotplug automation = L, high risk, possibly infeasible without
  further kernel rearchitecture; shell/card-shell landscape support = L
  (476 literal-constant call sites).
- **First board probe command**: read-only, on the reserved board/serial
  port, with touch running and untouched —
  `i2cdetect -y $(cat /sys/class/i2c-adapter/*/name | grep -l i2c3 2>/dev/null; echo 3)`
  to confirm something answers at `0x3b` alongside touch's `0x5d`, then
  `i2cget -y 3 0x3b 0x00` (chip-ID/status register read only, no write) to
  attempt to read back an LT9611 identity byte without touching GPIO23/24
  or any reset state. Exact adapter number for `&i2c3` on this board should
  be confirmed from `/sys/class/i2c-adapter/*/name` at probe time rather
  than assumed, since Linux adapter numbering is not guaranteed to match
  the DT alias.
