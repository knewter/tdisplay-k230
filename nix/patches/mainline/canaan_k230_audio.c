// SPDX-License-Identifier: GPL-2.0-only
/*
 * Forward-ported from the pinned vendor Xuantie tree's
 * sound/soc/canaan/canaan_k230_audio.c (ruyisdk/linux-xuantie-kernel) onto
 * mainline v7.3-rc5. This file is the K230 SoC's own SAI register block
 * (audio@0x9140f400 in k230.dtsi, compatible "canaan,k230-audio") -- the
 * digital mux between the on-die Inno codec and the raw external I2S pads.
 * It is a pure register-poke driver: no DMA, no ASoC component of its own.
 * See nix/dts/k230-tdisplay-mainline.dts and
 * nix/patches/canaan-audio-external-i2s-switch.patch (the vendor-tree
 * patch this project already carries, whose logic is folded directly into
 * canaan_k230_inno.c's forward port rather than reapplied as a second
 * patch step here).
 *
 * Changes from the vendor file (openspec/changes/the-mainline-shell-reaches-
 * parity, task 5.1):
 *   - struct platform_driver.remove changed from
 *     `int (*)(struct platform_device *)` to `void (*)(...)`, matching
 *     v7.3-rc5's struct platform_device (include/linux/platform_device.h;
 *     same signature change already applied to this project's other
 *     forward-ports, e.g. nix/patches/mainline/sdhci-of-kendryte.c).
 *   - Added an explicit claim of the K230_LS_AUDIO_APB_GATE clock. The
 *     vendor driver claims no clock at all for this register block, which
 *     is safe on the vendor's own 6.6-era clock driver (nothing gates
 *     unused clocks there) but NOT on this project's mainline clk-k230
 *     driver, which gates any clock no consumer has claimed (see this
 *     repo's AGENTS.md "Keep changes moving" lesson and
 *     docs/research/mainline-audio-port.md). ls_audio_apb_gate's parent in
 *     drivers/clk/clk-k230.c is ls_apb_src_rate, NOT the i2s controller's
 *     own ls_audio_dev_rate/_gate pair, so nothing else claiming the i2s
 *     controller's clock would cascade-enable this one -- this register
 *     block needs its own explicit claim or register reads/writes here
 *     hang the SoC exactly like the gates this project has already hit.
 */

#include <linux/clk.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include "canaan_k230_audio.h"
#include <linux/io.h>
#include <linux/of.h>

struct canaan_audio_data {
	struct platform_device *pdev;
	void __iomem *base;
	struct clk *apb_clk;
};

static struct canaan_audio_data sai = { 0 };

void audio_i2s_in_init(void)
{
	if (sai.base) {
		struct audio_in_reg_s *audio_in_reg = sai.base;

		/* default to I2S */
		audio_in_reg->audio_in_pdm_conf_0.audio_in_mode = AUDIO_IO_OUT_MODE_I2S;
		audio_in_reg->audio_in_agc_para_4.agc_bypass = AUDIO_ENABLE;
	}
}
EXPORT_SYMBOL_GPL(audio_i2s_in_init);

void audio_i2s_out_init(bool enable, uint32_t word_len)
{
	enum audio_out_data_width_e out_word_len = AUDIO_OUT_TYPE_32BIT;

	if (word_len == 32)
		out_word_len = AUDIO_OUT_TYPE_32BIT;
	else if (word_len == 24)
		out_word_len = AUDIO_OUT_TYPE_24BIT;
	else if (word_len == 16)
		out_word_len = AUDIO_OUT_TYPE_16BIT;

	if (sai.base) {
		struct audio_out_reg_s *audio_out_reg = sai.base + 0x800;

		audio_out_reg->audio_out_ctl.data_type = out_word_len;
		audio_out_reg->audio_out_ctl.mode = AUDIO_OUT_MODE_I2S; /* i2s/pdm/tdm mode */
		audio_out_reg->audio_out_ctl.enable =
			enable ? AUDIO_ENABLE : AUDIO_DISABLE; /* enable audio out */
	}
}
EXPORT_SYMBOL_GPL(audio_i2s_out_init);

void audio_i2s_enable_audio_codec(bool use_audio_codec)
{
	if (sai.base) {
		struct audio_in_reg_s *audio_in_reg = sai.base;

		/* whether to route through the on-die codec */
		audio_in_reg->audio_in_pdm_conf_0.audio_codec_bypass = !use_audio_codec;
	}
}
EXPORT_SYMBOL_GPL(audio_i2s_enable_audio_codec);

static int canaan_audio_probe(struct platform_device *pdev)
{
	struct resource *res;
	int ret = 0;

	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);

	sai.base = devm_ioremap_resource(&pdev->dev, res);
	if (IS_ERR(sai.base))
		return PTR_ERR(sai.base);

	/*
	 * K230_LS_AUDIO_APB_GATE (include/dt-bindings/clock/canaan,k230-clk.h).
	 * Optional: older/incomplete device trees for this node may not list
	 * it yet, but on this project's mainline clk-k230 driver an unclaimed
	 * gate is disabled, not merely left at its reset state, so request it
	 * whenever the DT offers it.
	 */
	sai.apb_clk = devm_clk_get_optional_enabled(&pdev->dev, "apb");
	if (IS_ERR(sai.apb_clk))
		return PTR_ERR(sai.apb_clk);

	platform_set_drvdata(pdev, &sai);

	return ret;
}

static void canaan_audio_remove(struct platform_device *pdev)
{
}

static const struct of_device_id canaan_audio_ids[] = {
	{
		.compatible = "canaan,k230-audio",
	},
	{ /* sentinel */ },
};
MODULE_DEVICE_TABLE(of, canaan_audio_ids);

static struct platform_driver canaan_audio_driver = {
	.driver = {
		.name = "k230-audio",
		.of_match_table = canaan_audio_ids,
	},
	.probe = canaan_audio_probe,
	.remove = canaan_audio_remove,
};

module_platform_driver(canaan_audio_driver);

MODULE_DESCRIPTION("k230 audio interface");
MODULE_LICENSE("GPL");
