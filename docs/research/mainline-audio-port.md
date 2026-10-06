# Forward-porting the K230 audio driver to mainline (task 5.1)

openspec/changes/the-mainline-shell-reaches-parity, task 5.1: "Forward-port
`sound/soc/canaan` with the external-I2S-switch patch and owned
audio/codec clocks; DT nodes from the vendor tree. Host proof: kernel
builds; `aplay -l` lists the card in a board boot log."

## Update (task 5.x, board-proven): the generic dwc-i2s driver freezes the SoC

This doc's original conclusion below -- "no Canaan-specific I2S controller
driver needs porting at all," reusing mainline's own
`sound/soc/dwc/dwc-i2s.c` (compatible `snps,designware-i2s`) unmodified --
is **WRONG**, found by an actual board boot: starting ALSA playback
(`speaker-test -D plughw:0,0`) against that configuration **freezes the
whole SoC**, even with `clk_ignore_unused`/`pd_ignore_unused` on the kernel
command line (ruling out an unused-clock-gating hang, this project's other
recurring freeze cause). On the vendor 6.6 kernel, the identical command
completes normally -- the vendor kernel does **not** use the generic
driver; it has its own fork, `sound/soc/dwc_canaan/{canaan-dwc-i2s.c,
canaan-dwc-pcm.c,canaan-local.h}` (compatible
`canaan,snps,designware-i2s`), which this doc's original diff undersold as
"only API-currency differences."

Re-diffing both files directly (this project's pinned mainline
`sound/soc/dwc/dwc-i2s.c` vs. the vendor's `sound/soc/dwc_canaan/
canaan-dwc-i2s.c`) finds real register-programming divergence, not just
API currency:

- **`dw_i2s_hw_params()`**: the vendor driver forces `data_width = 32` and
  `ccr = 0x10` for every PCM format (S16_LE/S24_LE/S32_LE); mainline's
  generic driver varies both by format (16/0x00, 24/0x08, 32/0x10). The
  vendor driver then unconditionally ORs in `(1<<5) | (3<<8)` ("standard
  i2s format and dma_tx_en/dma_rx_en" per its own comment) -- a CCR bit
  pattern the generic driver never sets at all. The vendor driver also
  sets `play_dma_data.dt.addr_width`/`capture_dma_data.dt.addr_width`
  per format (2 bytes for S16_LE, 4 bytes for S24_LE/S32_LE); the generic
  driver does not touch `addr_width` in `hw_params()` at all (it comes
  once, at probe time, from a `COMP1_APB_DATA_WIDTH` register read).
- **`dw_configure_dai_by_dt()`**: DMA `maxburst` is `4` in the vendor
  driver, `16` in the generic one.
- **`i2s_start()`/`i2s_stop()` -- the most likely cause of the freeze**:
  the vendor driver's IRQ/DMA enable is a strict either/or --
  `i2s_enable_irqs()` only for the PIO or JH7110 path,
  `i2s_enable_dma()` only otherwise. Mainline's generic `dwc-i2s.c` no
  longer branches this way: `i2s_start()` now calls
  `i2s_enable_irqs(dev, substream->stream, config->chan_nr)`
  **unconditionally**, in addition to `i2s_enable_dma()` on the
  DMA-engine path. This board's `i2s` DT node carries **no `interrupts`
  property** (true in both the vendor and this project's DT, and
  deliberately so -- the real PLIC line for this IP has never been
  established from any source this project has, see below), so
  `dw_i2s_probe()` never calls `devm_request_irq()` and no handler is
  ever installed for whatever interrupt line this hardware is wired to.
  Against the generic driver, `TRIGGER_START` -> `i2s_start()` still
  unmasks the TX-FIFO-empty/RX-data-available sources in the IMR
  register regardless of that -- if the hardware then raises that PLIC
  line (plausible: TX FIFO empty happens immediately once playback
  starts), nothing ever acknowledges it, and depending on how that line
  is wired this plausibly explains an unhandled-interrupt storm freezing
  the core. The vendor driver's strict either/or never unmasks an
  interrupt source when there is no handler for it.

**Fix applied**: forward-ported the vendor's own `sound/soc/dwc_canaan/`
driver as `nix/patches/mainline/dwc_canaan/{canaan-dwc-i2s.c,
canaan-dwc-pcm.c,canaan-local.h,Kconfig,Makefile}`, wired into
`nix/kernel-mainline.nix` under its own `CANAAN_SND_DESIGNWARE_I2S`/
`CANAAN_SND_DESIGNWARE_PCM` Kconfig symbols (distinct from mainline's own
`SND_DESIGNWARE_I2S`/`_PCM`, left enabled since nothing on this board's DT
uses the generic compatible string anymore, so there is no bind
conflict), and changed the `i2s` DT node's compatible string in
`nix/dts/k230-tdisplay-mainline.dts` from `snps,designware-i2s` to
`canaan,snps,designware-i2s`. Every other property on that DT node (reg,
dmas/dma-names, clocks/clock-names) is unchanged -- checked directly
against the vendor's own `k230.dtsi` i2s node, which carries no other
`canaan,`-prefixed property this driver reads.

API-currency changes made porting the vendor file to v7.3-rc5 (see
`nix/patches/mainline/dwc_canaan/canaan-dwc-i2s.c`'s own header comment
for the full list, kept in sync): `.remove_new` -> `.remove` (already
void-returning in the vendor source, only the struct field name moved),
`asoc_substream_to_rtd()` -> `snd_soc_substream_to_rtd()`,
`asoc_rtd_to_cpu()` -> `snd_soc_rtd_to_cpu()` (in `canaan-dwc-pcm.c`),
`SET_RUNTIME_PM_OPS` -> `RUNTIME_PM_OPS` wrapped in `pm_ptr(&dwc_pm_ops)`
on `.driver.pm` (and `dw_i2s_runtime_suspend()`/`_resume()` moved out from
under `#ifdef CONFIG_PM` to stay unconditionally compiled, since the
`dev_pm_ops` struct referencing them by name is itself unconditionally
compiled now), `devm_clk_get()` + `clk_prepare_enable()` ->
`devm_clk_get_enabled()` with the `err_clk_disable` probe-error-path label
and the `remove()` function's own `clk_disable_unprepare()` call both
dropped (devm's reverse-order cleanup replaces them), `irq >= 0` ->
explicit `if (irq == -EPROBE_DEFER) return irq;` then `if (irq > 0)`
(mainline's own currency fix, ported verbatim), and `.pcm_construct` ->
`.pcm_new` in `canaan-dwc-pcm.c`'s component driver struct. One
pre-existing vendor bug fixed in `canaan-local.h` (not an API-currency
change): its `CONFIG_CANAAN_SND_DESIGNWARE_PCM=n` fallback declared
unprefixed inline stubs (`dw_pcm_push_tx`/`_pop_rx`/`_register`) that
don't match what `canaan-dwc-i2s.c` actually calls
(`canaan_dw_pcm_push_tx`/etc.) -- a mismatch the vendor tree never hit
because its own defconfig always turns the PCM symbol on, but one that
fails this board's build (which leaves it off, same reasoning as
mainline's own `SND_DESIGNWARE_PCM` below). Renamed the fallback stubs to
match.

**Verification performed (host-only; no board)**:

- Both files compiled as out-of-tree kernel modules (`make M=...
  modules`) against this project's pinned mainline v7.3-rc5 dev tree,
  riscv64 cross-compiler, `W=1`, zero warnings/errors, in two
  configurations: `canaan-dwc-i2s.c` alone (`CANAAN_SND_DESIGNWARE_PCM`
  unset, matching this board's actual `structuredExtraConfig`) and
  `canaan-dwc-i2s.c` + `canaan-dwc-pcm.c` together with
  `CONFIG_CANAAN_SND_DESIGNWARE_PCM=1` forced via `ccflags-y` (to exercise
  the PCM PIO file too, even though it is not built for this board).
- `nix/dts/k230-tdisplay-mainline.dts` and its
  `k230-tdisplay-mainline-drm.dts` includer both preprocess (`cpp`) and
  compile (`dtc -I dts -O dtb`) cleanly against mainline's own
  `include/`+`arch/riscv/boot/dts(/canaan)` search path, zero
  warnings; decompiling the resulting `.dtb` confirms the `i2s` node's
  `compatible` is now `canaan,snps,designware-i2s` with every other
  property (`reg`, `dmas`, `dma-names`, `clocks`, `clock-names`)
  byte-identical to before.
- `nix-instantiate --parse nix/kernel-mainline.nix` succeeds.
- The `sed`/`grep` hunks this file's `postPatch` adds for
  `sound/soc/{Kconfig,Makefile}` were dry-run by hand against real copies
  of those two files from the pinned mainline source tree (after first
  applying the prior `canaan/` insertion they anchor on) and produced the
  expected `source "sound/soc/dwc_canaan/Kconfig"` line immediately after
  the existing `canaan/Kconfig` line, and the expected `obj-$(CONFIG_SND_SOC)
  += dwc_canaan/` Makefile line.
- Not run: `nix build` of the kernel derivation itself (out of scope for
  this task); any board boot, `aplay -l` capture, or a
  `speaker-test`/playback run against this new driver. **This port fixes
  the specific freeze-causing divergence identified above, but does not
  itself prove audio plays** -- `aplay -l` listing the card and a
  non-frozen `speaker-test` run remain this task's own open host/board
  proofs.

## What landed (original task 5.1 port; still current for canaan/codecs)

Forward-ported, compiled clean (zero warnings) against this project's
pinned mainline v7.3-rc5 dev tree, and wired into `nix/kernel-mainline.nix`
(Kconfig/Makefile postPatch + `structuredExtraConfig`):

- `nix/patches/mainline/canaan_k230_audio.c` + `.h` -> `sound/soc/canaan/` --
  the SAI register mux (`audio@0x9140f400`, compatible `canaan,k230-audio`).
  Adds an explicit `K230_LS_AUDIO_APB_GATE` clock claim the vendor file
  never made.
- `nix/patches/mainline/canaan_k230_inno.c` -> `sound/soc/canaan/` -- the
  `canaan,k230-audio-inno` machine driver. Folds in this project's own
  `nix/patches/canaan-audio-external-i2s-switch.patch` directly (same
  "External I2S Output Switch" control, same
  `canaan,external-i2s-output-default` property) rather than reapplying
  that patch textually.
- `nix/patches/mainline/inno_k230.c` + `inno_k230_reg.{c,h}` ->
  `sound/soc/codecs/` -- the on-die Inno codec ASoC component
  (`inno_codec@0x9140e000`, compatible `canaan,k230-inno-codec`). Adds an
  explicit `K230_LS_CODEC_APB_GATE` clock claim the vendor file never made.
- DT nodes in `nix/dts/k230-tdisplay-mainline.dts`: `i2s@9140f000`,
  `audio@9140f400`, `inno_codec@9140e000`, and the `sound` machine node,
  with every clock this analysis identifies as needed.
- `nix/kernel-mainline.nix`: new `sound/soc/canaan/{Kconfig,Makefile}` (a
  directory mainline does not have at all), a new `SND_SOC_K230_INNO`
  Kconfig entry under `sound/soc/codecs/Kconfig`, and
  `structuredExtraConfig` turning all of it on.

**SUPERSEDED by the "Update" section above**: this section originally said
mainline's own `sound/soc/dwc/{dwc-i2s.c,dwc-pcm.c}` (Synopsys DesignWare
I2S) was reused unmodified, with only API-currency differences from the
vendor's `sound/soc/dwc_canaan/canaan-dwc-i2s.c`, and that "no
Canaan-specific I2S controller driver needs porting at all." A board boot
proved that wrong (playback freezes the SoC against the generic driver);
see the "Update" section above for the real register-programming
divergence and the forward-ported `sound/soc/dwc_canaan/` fix. The DT
nodes below now use `canaan,snps,designware-i2s` for the `i2s` node, not
the generic `snps,designware-i2s` this paragraph originally described.

## API changes made (6.6 vendor -> 7.3-rc5 mainline), confirmed against headers

- `struct platform_driver.remove`: `int (*)(struct platform_device *)` ->
  `void (*)(...)` (`include/linux/platform_device.h`). Fixed in
  `canaan_audio_remove()` and `inno_k230_codec_platform_remove()`.
- `SND_SOC_DAIFMT_CBS_CFS` no longer exists in
  `include/sound/soc-dai.h` -- mainline fully renamed every DAIFMT
  clock-role macro to provider/consumer terms. `CBS_CFS` ("codec bitclock
  slave, codec frame slave") is the same role as the new
  `SND_SOC_DAIFMT_CBC_CFC` ("codec clock consumer & frame consumer").
  Fixed in `canaan_k230_inno.c`'s `dai_fmt`.
- `#include <linux/of_gpio.h>` no longer exists upstream at all (removed).
  Dropped from `canaan_k230_inno.c` along with the equally-unused
  `<linux/gpio.h>` -- neither file ever called a GPIO function.
- `devm_clk_get()` + `clk_prepare_enable()` pairs replaced with
  `devm_clk_get_enabled()`/`devm_clk_get_optional_enabled()`
  (`include/linux/clk.h`, both present in v7.3-rc5) for every clock claim,
  old and newly-added.
- Checked and found UNCHANGED, so left alone: `struct
  snd_soc_component_driver`'s `.open`/`.idle_bias_on`/`.use_pmdown_time`/
  `.endianness`/`.legacy_dai_naming` fields (now declared in the split-out
  `include/sound/soc-component.h`, not `soc.h`, but otherwise identical);
  `SND_SOC_DAILINK_DEFS`/`COMP_CODEC`/`COMP_EMPTY`/`SND_SOC_DAILINK_REG`;
  `snd_soc_card`, `snd_soc_dai_driver`, `snd_kcontrol_new` shapes.

## Clocks claimed, and why (the AGENTS.md "claim every clock" lesson)

Checked directly against this project's pinned mainline
`drivers/clk/clk-k230.c` and `include/dt-bindings/clock/canaan,k230-clk.h`:

| Clock ID | Value | Parent in clk-k230.c | Claimed by |
|---|---|---|---|
| `K230_LS_AUDIO_DEV_RATE` | 158 | `ls_audio_dev_gate` | `i2s` node, clock-names `i2sclk` |
| `K230_LS_AUDIO_DEV_GATE` | 95 | `pll0_div4` | *(cascade-enabled by DEV_RATE above -- not claimed directly)* |
| `K230_LS_AUDIO_APB_GATE` | 85 | `ls_apb_src_rate` | `audio` node, clock-names `apb` (**new**) |
| `K230_LS_CODEC_ADC_RATE` | 156 | `ls_codec_adc_gate` | `inno_codec` node, clock-names `adc` |
| `K230_LS_CODEC_ADC_GATE` | 93 | `pll0_div4` | *(cascade-enabled by ADC_RATE above)* |
| `K230_LS_CODEC_DAC_RATE` | 157 | `ls_codec_dac_gate` | `inno_codec` node, clock-names `dac` |
| `K230_LS_CODEC_DAC_GATE` | 94 | `pll0_div4` | *(cascade-enabled by DAC_RATE above)* |
| `K230_LS_CODEC_APB_GATE` | 87 | `ls_apb_src_rate` | `inno_codec` node, clock-names `apb` (**new**) |
| `K230_LS_PDM_GATE`/`_RATE` | 96/159 | -- | **not claimed** -- PDM mic input path is not part of this board's `k230-audio-inno` (I2S) configuration; left ungated-but-unclaimed deliberately, same as upstream leaves any unused peripheral. A future PDM-mic change must claim it. |

The common clock framework enables a clock's parent whenever the clock
itself is prepared/enabled (`clk_core_prepare`/`clk_core_enable` walk the
parent chain). Because `K230_CLK_RATE_FORMAT(ls_audio_dev_rate, ...,
&ls_audio_dev_gate.clk.hw)` (and the matching ADC/DAC pairs) wire the RATE
clock's hardware parent directly to its GATE, a single `devm_clk_get_enabled()`
call on the RATE clock (what the vendor code already did, unchanged, for
`i2sclk`/`adc`/`dac`) already cascades to the GATE -- confirmed by reading
the macro invocations themselves, not assumed. The two APB gates
(`ls_audio_apb_gate`, `ls_codec_apb_gate`) are parented from
`ls_apb_src_rate` instead, a branch nothing else here claims, so each
needed its own explicit, additional claim -- added as `devm_clk_get_optional_enabled()`
so a device tree written before this change (with no `apb` clock listed)
still probes.

## Resolution (2026-10-06): the PDMA controller is now forward-ported

The blocker below (no mainline DMA provider for `compatible =
"canaan,k230-pdma"`) is resolved by porting
`drivers/dma/k230_peridma.c` from the pinned vendor tree as
`nix/patches/mainline/k230-peridma.c`, wired into
`nix/kernel-mainline.nix` (new `drivers/dma/k230-peridma.c` via
postPatch, a `K230_PERIDMA` Kconfig entry inserted before
`DW_AXI_DMAC` in `drivers/dma/Kconfig`, a Makefile line, and
`structuredExtraConfig.K230_PERIDMA = yes`), with a `&pdma` DT node and
`dmas`/`dma-names` on the `i2s` node added to
`nix/dts/k230-tdisplay-mainline.dts`.

**API changes from the vendor's 6.6-era source, confirmed against this
project's pinned v7.3-rc5 headers** (see the ported file's own header
comment for the same list, kept in sync):

- `struct platform_driver.remove`: `int (*)(struct platform_device *)`
  -> `void (*)(...)` (`include/linux/platform_device.h`) -- same
  signature change every other driver this project has forward-ported
  needed. Fixed in `k230_peridma_remove()`.
- `devm_clk_get()` + a separate `clk_prepare_enable()` call in
  `k230_peridma_probe()` replaced with a single
  `devm_clk_get_enabled()` (`include/linux/clk.h`) -- the AGENTS.md
  "claim every clock" lesson. The probe's `err_clk_disable` label and
  both of its `clk_disable_unprepare()` calls (probe error path and
  `remove()`) are dropped along with it: devm's reverse-order cleanup
  now does that automatically.
- `#include <linux/property.h>` added explicitly for
  `device_property_read_u32()` (`parse_device_properties()`) -- not
  reliably pulled in transitively via `platform_device.h` on this tree.
- One dead-code cleanup unrelated to API currency: a commented-out
  multi-line debug `dev_vdbg()` call had a stray trailing `\` inside a
  `//` comment, which GCC's `-Wcomment` (triggered by this task's `W=1`
  compile check) flags as an unterminated line-continuation. Removed
  the backslash; no functional change, the code was never live.
- Checked and found **unchanged**, so left alone: `device_prep_slave_sg`/
  `device_prep_dma_cyclic`/`device_config`/`device_pause`/
  `device_resume`/`device_terminate_all`/`device_tx_status`/
  `device_issue_pending` signatures (`include/linux/dmaengine.h`);
  `dma_async_device_register()`, `of_dma_controller_register()`/
  `_free()` (`include/linux/of_dma.h`); every `virt-dma.h` helper this
  file calls (`vchan_init`, `vchan_tx_prep`, `vchan_cookie_complete`,
  `vchan_cyclic_callback`, `vchan_get_all_descriptors`,
  `vchan_dma_desc_free_list`, `vchan_free_chan_resources`) -- including
  `struct virt_dma_chan` still using a `tasklet_struct` internally in
  v7.3-rc5, not a workqueue/BH conversion, checked directly rather than
  assumed. `dma_slave_config`'s `src_addr`/`dst_addr` fields changed
  type from `dma_addr_t` to `phys_addr_t` upstream, but both are 64-bit
  on riscv64 and the vendor code only moves them through local
  `dma_addr_t` variables, so no source change was needed -- confirmed
  by the zero-warning `W=1` compile, not assumed.

**Clock claimed**: `K230_SHRM_PDMA_AXI_GATE` = 130
(`include/dt-bindings/clock/canaan,k230-clk.h`), claimed by the driver
itself via `devm_clk_get_enabled(&pdev->dev, NULL)` (unnamed, single
clock, matching the vendor's own single-clock probe call) and
separately listed on the DT node (`clocks = <&sysclk
K230_SHRM_PDMA_AXI_GATE>;`, no `clock-names` needed for an unnamed
`devm_clk_get()`/`_enabled()` call). Confirmed register-identical to
the vendor's own gate, not inferred:

| Source | Register offset | Bit | Parent |
|---|---|---|---|
| Vendor `k230_clock_provider.dtsi`, `pdma_aclk_gate` node | `clk-gate-reg-offset = <0x5C>` | `clk-gate-reg-bit-enable = <3>` | `shrm_axim_clk_gate` |
| Mainline `drivers/clk/clk-k230.c`, `K230_CLK_GATE_FORMAT(shrm_pdma_axi_gate, K230_SHRM_PDMA_AXI_GATE, 0x5C, 3, 0, 0, ...)` | `0x5C` | `3` | `shrm_axim_clk_gate` (mainline's own clock of that exact name, `drivers/clk/clk-k230.c:1772: &shrm_pdma_axi_gate`) |

Same offset, same bit, same parent name -- the mainline clock ID is the
correct one for this gate, confirmed by reading both sources directly.

**DT changes**: a `pdma: pdma@80804000` node added to
`nix/dts/k230-tdisplay-mainline.dts` with `reg`, `interrupts = <203
IRQ_TYPE_LEVEL_HIGH>;`, `#dma-cells = <4>;`, `dma-channels = <8>;`,
`dma-requests = <35>;`, and `status = "okay";` -- every field copied
verbatim from the vendor `k230.dtsi`'s own `pdma@0x80804000` node. The
`i2s` node's `dmas = <&pdma 1 0xfff 0 0x14>, <&pdma 1 0xfff 0 0x15>;`
and `dma-names = "tx", "rx";` are likewise copied verbatim from the
vendor's `i2s@0x9140f000` node (args are `<priority, dev_tout,
dat_endian, dev_sel>`; `0x14`/`0x15` are `AUDIO_TX`/`AUDIO_RX` in the
driver's own `enum ch_peri_dev_sel_t`). `cpp`+`dtc` validation
(`docs/evidence/mainline-audio-port/pdma-dtc-validate.json`) decompiles
the resulting `.dtb` and confirms both the clock-ID and dmas phandle
args resolve to these exact numeric values, not merely that the syntax
parses.

**Verification performed (host-only; no board, no full kernel build)**,
same evidence classes as the rest of this task:

- `nix/patches/mainline/k230-peridma.c` compiled as an out-of-tree
  kernel module against this project's pinned mainline v7.3-rc5
  dev/module tree, riscv64 cross-compiler, `W=1`, zero warnings (after
  the dead-comment fix above), one `.ko` produced. See
  `docs/evidence/mainline-audio-port/pdma-module-compile.json`. This
  module build needed two of `drivers/dma/`'s own *private* headers
  (`virt-dma.h`, `dmaengine.h`) that are not part of the installed
  dev-tree module headers; unmodified copies from the pinned v7.3-rc5
  research source tree were used for this build only and are not part
  of the shipped patch or this commit.
- `nix/dts/k230-tdisplay-mainline.dts` and its
  `k230-tdisplay-mainline-drm.dts` includer both preprocess and compile
  cleanly with the new `&pdma` node and the `i2s` node's new
  `dmas`/`dma-names`, zero warnings; resolved values checked
  byte-for-byte as above. See
  `docs/evidence/mainline-audio-port/pdma-dtc-validate.json`.
- The exact `postPatch` `grep`/`sed` hunks `nix/kernel-mainline.nix`
  adds for this driver (Kconfig insertion, Makefile line) were dry-run
  by hand against copies of the real pinned mainline `drivers/dma/`
  `Kconfig`/`Makefile` and produced the expected, correctly-indented
  result -- not run through the full Nix kernel derivation (out of
  scope for this task; no full kernel/system nix build was run).
- Not run: `nix build .#deviceTreeMainline` or any full kernel build of
  the mainline kernel derivation itself; any board boot or `aplay -l`
  capture.

**What remains**: this task's own host-proof criterion -- `aplay -l`
listing the card in a board boot log -- requires a full kernel build
and a board boot, neither performed by this worktree (board access,
`/dev/ttyACM0` and the nix build lock were explicitly out of scope).
The `K230_PERIDMA`/audio Kconfig symbols have not been run through a
real `make oldconfig`/defconfig pass against the full tree, only
checked against the already-built pinned dev tree's `.config` for the
dependencies this entry needs (`DMADEVICES`/`DMA_ENGINE`/
`DMA_VIRTUAL_CHANNELS`/`DMA_OF`/`OF`/`HAS_IOMEM`, all already `y`).
UNVERIFIED, same as the rest of this task's clock claims: whether
`K230_SHRM_PDMA_AXI_GATE`'s register-level programming actually gates
the PDMA block correctly at runtime -- read directly from both sources
and found identical, not board-tested. UNVERIFIED: the PDMA
controller's actual descriptor-chain DMA behavior on real silicon (the
`pdma_llt_t`/`pdma_ch_cfg_t` register programming itself, unchanged
from the vendor source) -- this port changed only API-currency
surface, not the register-level logic, so a correct compile does not
by itself prove correct hardware behavior.

## The blocker (historical; now resolved above): no mainline DMA provider

The vendor `i2s` DT node (`k230.dtsi`, shared by every Canaan board in that
tree, not just this one) is:

```
i2s: i2s@0x9140f000 {
	compatible = "canaan,snps,designware-i2s";
	reg = <0x0 0x9140f000 0x0 0x400>;
	dmas = <&pdma 1 0xfff 0 0x14>, <&pdma 1 0xfff 0 0x15>;
	dma-names = "tx", "rx";
	clocks = <&audio_dev_clk>;
	clock-names = "i2sclk";
};
```

It carries **no `interrupts` property**. In `sound/soc/dwc/dwc-i2s.c`'s
`dw_i2s_probe()`:

```c
if (!pdata || dev->is_jh7110) {
	if (irq >= 0) {
		ret = dw_pcm_register(pdev);   /* PIO FIFO push/pop, no DMA */
		dev->use_pio = true;
		...
	} else {
		ret = devm_snd_dmaengine_pcm_register(&pdev->dev, NULL, 0);
		dev->use_pio = false;
	}
```

`pdata` is always `NULL` for a device-tree-probed platform device (it is
only ever set by x86 board files), so this reduces to: **with an IRQ, use
PIO; without one, require a dmaengine-registered DMA channel.** Since the
only vendor DT reference for this IP has no `interrupts` property, the
vendor's own reference configuration takes the DMA branch, which calls
(`sound/soc/soc-generic-dmaengine-pcm.c`, `dmaengine_pcm_request_chan_of()`,
invoked synchronously from `dw_i2s_probe()` itself, i.e. at platform-driver
probe time, not deferred to stream open):

```c
chan = dma_request_chan(dev, name);   /* name = "tx" / "rx" */
```

This resolves the `dmas = <&pdma ...>` phandle via the kernel's
`of_dma`/`dmaengine` framework, which requires a registered DMA controller
driver bound to the `pdma` node's `compatible = "canaan,k230-pdma"`. **No
such driver exists in mainline.** Checked directly:

- `drivers/dma/k230_peridma.c` (vendor tree, 1423 lines) is a from-scratch
  register interface -- custom `pdma_llt_t` linked-list descriptors, a
  bespoke `pdma_ch_cfg_t` bitfield layout, global/per-channel register
  offsets (`PDMA_CH_EN`, `CH_CTL`, `CH_LLT_SADDR`, ...) matching nothing in
  any upstream DMA engine driver. It is not a DesignWare APB DMAC
  (`drivers/dma/dw/`, compatible `snps,dma-spear1340`) and not a
  DesignWare AXI DMAC (`drivers/dma/dw-axi-dmac/`, compatible
  `snps,axi-dma-1.01a`) -- both exist in mainline, neither matches this
  register layout or this `compatible` string.
- Mainline's own `drivers/clk/clk-k230.c` even has a clock for it
  (`K230_SHRM_PDMA_AXI_GATE` = 130), confirming the SoC side of this IP is
  otherwise accounted for in the ported clock tree -- only the DMA engine
  driver itself is missing.

With no provider ever registered for that `compatible` string,
`dma_request_chan()` cannot resolve the phandle to a channel. Checked
against `dmaengine_pcm_request_chan_of()`'s own error handling: a probe
deferral (`-EPROBE_DEFER`) is returned and retried forever only while
there is *some* hope a provider will eventually register; here none ever
will, so the `i2s` platform device never completes probe, the
`canaan,k230-audio-inno` card's `cpu`/`platform` DAI component is never
registered, and `devm_snd_soc_register_card()` never completes either.
**`aplay -l` would not list the card** -- this task's own host-proof
criterion is not reachable without resolving this.

### Why this DT does not instead add an `interrupts` property to force PIO

The PIO branch above is attractive -- it needs no DMA engine at all, and
mainline's `dw_pcm_register()` is already compiled in by this change's own
`structuredExtraConfig` groundwork (`SND_DESIGNWARE_I2S`; `SND_DESIGNWARE_PCM`
was left unset only because nothing can use it yet -- see the Kconfig
comment). But it requires knowing the real PLIC interrupt line this SoC
wires to this specific DesignWare I2S instance, and:

- the vendor's own `k230.dtsi` -- the only grounding tier 2 source this
  project has for this IP -- carries no `interrupts` property on this node
  in any of the board files in that tree;
- no other file available to this project (the mainline v7.3-rc5 research
  tree's own `k230.dtsi`/`k230-evb.dts`, which has no audio node at all;
  this project's own `docs/research/` corpus) states this number;
- inventing one would be exactly the "do not infer a hardware result from
  a host-only check" / no-guessing rule this repo's AGENTS.md and this
  task's own brief both state. A wrong IRQ number is worse than an honest
  gap: it would either silently never fire (identical symptom to today,
  but now with a false paper trail saying PIO was wired up) or, if it
  happens to alias a real peripheral's line, corrupt that peripheral's
  interrupt handling.

## What would unblock task 5.1's remaining host proof (historical)

This section recorded two options at the time the DMA gap was first
found; option 1 is now done (see "Resolution" above). Recorded here
unedited for history, plus what's now left:

1. ~~**Port `drivers/dma/k230_peridma.c` as a mainline dmaengine
   driver.**~~ Done -- see "Resolution" above,
   `nix/patches/mainline/k230-peridma.c`.
2. **Confirm the real PLIC IRQ number** for this DesignWare I2S instance
   remains a live alternative/supplement nobody has pursued: it would
   let `dw_i2s_probe()` take the PIO branch instead of (or in addition
   to testing) the now-available dmaengine_pcm branch, but still
   requires a source this project has not located (SoC TRM, or reading
   PLIC registers on real hardware). Not needed now that the DMA
   provider exists, but would be a useful independent cross-check if a
   board boot shows the dmaengine_pcm path failing for an unrelated
   reason.

What's left now is purely the board-side proof: a full kernel build
(this worktree did not build one, as directed) and a board boot
capturing `aplay -l` listing the `canaan,k230-audio-inno` card -- this
task's own named host-proof criterion, still open.

## Verification performed (host-only; no board, no full kernel build)

- `nix/dts/k230-tdisplay-mainline.dts` and its `k230-tdisplay-mainline-drm.dts`
  includer both preprocess (cpp, mainline's own `include/`+`arch/riscv/boot/dts(/canaan)`
  search path) and compile (`dtc -I dts -O dtb`) cleanly, zero warnings; the
  resolved clock cell values were checked byte-for-byte against the table
  above. See `docs/evidence/mainline-audio-port/dtc-validate.json`.
- The four forward-ported `.c` files were compiled as out-of-tree kernel
  modules (`make M=... modules`) against this project's pinned mainline
  v7.3-rc5 dev/module tree (the same tree
  `docs/evidence/mainline-init-exec-transition/actual-host/new-header-object.json`
  used), riscv64 cross-compiler, zero errors, zero warnings, three `.ko`
  files produced. See `docs/evidence/mainline-audio-port/module-compile.json`.
  This did **not** use `/tmp/k230-nix-build.lock` (held by a concurrent
  worktree at the time, and not needed: the build only read the
  already-built, read-only dev tree and wrote into a private scratch
  directory, so there was no shared mutable state to serialize).
- Not run: `nix build .#deviceTreeMainline` (the host `dtc`+`cpp` check
  above already gave a clean, fully-resolved compile, so the task's named
  fallback was not needed); any full kernel build (`nix build` of the
  kernel derivation itself, explicitly out of scope for this task); any
  board boot or `aplay -l` capture (at the time, blocked on the DMA gap;
  see "Resolution" above for the now-ported DMA provider and
  `docs/evidence/mainline-audio-port/pdma-*.json` for its own, separate
  verification -- the board boot/`aplay -l` capture itself is still not
  done by any worktree as of this writing).

## Remaining risks (not independently confirmed, flagged `UNVERIFIED`)

- UNVERIFIED: whether `K230_LS_AUDIO_DEV_RATE`'s cascade-enable of
  `K230_LS_AUDIO_DEV_GATE` (and the matching ADC/DAC pairs) actually holds
  at runtime the way the static parent-pointer wiring in `clk-k230.c`
  implies -- read directly from source, not board-tested.
  `K230_LS_AUDIO_APB_GATE`/`K230_LS_CODEC_APB_GATE`'s explicit claims are
  likewise unverified on real hardware; the project's own prior
  unclaimed-gate hangs (ls_audio_apb_gate, ls_audio_dev_gate,
  ls_codec_apb_gate, ls_codec_adc_gate, ls_codec_dac_gate, ls_pdm_gate --
  all named in this task's brief) were observed on *other* peripherals'
  gates, not these exact ones, so this analysis extends that lesson by
  pattern, not by having reproduced an audio-specific hang.
- UNVERIFIED: vendor DAC/ADC init sequencing (`audio_codec_dac_init()`/
  `audio_codec_adc_init()` in `inno_k230_reg.c`, forward-ported unchanged)
  against real silicon -- this file is pure register programming with no
  kernel-version dependency, so it was not a focus of this port, only
  compiled.
- The external-I2S-switch control (`nix/patches/canaan-audio-external-i2s-switch.patch`,
  folded into `canaan_k230_inno.c`) and the MAX98357A wiring it targets
  (`nix/dts/k230-tdisplay.dts`'s own GPIO documentation) are a *vendor-tree*
  feature; this mainline DT does not yet add the MAX98357A's GPIO
  documentation or default-route property, matching
  `nix/dts/k230-tdisplay.dts`'s own choice to leave
  `canaan,external-i2s-output-default` unset (boot through the Inno codec).
