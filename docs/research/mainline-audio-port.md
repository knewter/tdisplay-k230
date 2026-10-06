# Forward-porting the K230 audio driver to mainline (task 5.1)

openspec/changes/the-mainline-shell-reaches-parity, task 5.1: "Forward-port
`sound/soc/canaan` with the external-I2S-switch patch and owned
audio/codec clocks; DT nodes from the vendor tree. Host proof: kernel
builds; `aplay -l` lists the card in a board boot log."

## What landed

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

Deliberately reused unmodified: mainline's own
`sound/soc/dwc/{dwc-i2s.c,dwc-pcm.c}` (Synopsys DesignWare I2S), already
present upstream (`CONFIG_SND_DESIGNWARE_I2S`/`_PCM`, selecting
`SND_SOC_GENERIC_DMAENGINE_PCM`). Diffing the vendor's
`sound/soc/dwc_canaan/canaan-dwc-i2s.c` against mainline's
`sound/soc/dwc/dwc-i2s.c` (same file, same Synopsys/ST authorship lineage)
shows only API-currency differences (`devm_clk_get_enabled`,
`.remove_new`->`.remove`, `RUNTIME_PM_OPS`, a few DMA burst/width tuning
values) and one compatible-string difference
(`canaan,snps,designware-i2s` vs. mainline's generic
`snps,designware-i2s`) -- not a different IP. The DT nodes above use the
generic string, so **no Canaan-specific I2S controller driver needs
porting at all.**

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

## The blocker: no mainline DMA provider, and no safe way around it

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

## What would unblock task 5.1's remaining host proof

Either of, not both:

1. **Port `drivers/dma/k230_peridma.c` as a mainline dmaengine driver.**
   A real, separate forward-port on the order of the audio work done
   here or larger (1423 lines of register-level descriptor-chain DMA
   engine code, none of it shared with any existing mainline DMA driver).
   Out of scope for task 5.1 as a "forward-port the audio driver" task;
   would need its own OpenSpec task/change.
2. **Confirm the real PLIC IRQ number** for this DesignWare I2S instance
   (SoC TRM, a vendor source this project has not yet located, or reading
   the PLIC pending/enable registers on real hardware while vendor-kernel
   audio is active) and add `interrupts = <N IRQ_TYPE_LEVEL_HIGH>;` to the
   `i2s` node in `nix/dts/k230-tdisplay-mainline.dts`, enable
   `SND_DESIGNWARE_PCM = yes;` in `nix/kernel-mainline.nix`, and the
   existing, already-compiling forward-port here should bind without
   further source changes.

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
  board boot or `aplay -l` capture (blocked on the DMA gap above).

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
