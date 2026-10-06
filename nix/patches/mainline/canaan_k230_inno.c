// SPDX-License-Identifier: GPL-2.0-only
/*
 * This program is free software; you can redistribute it and/or modify it
 * under the terms and conditions of the GNU General Public License,
 * version 2, as published by the Free Software Foundation.
 *
 * This program is distributed in the hope it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
 * more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Forward-ported from the pinned vendor Xuantie tree's
 * sound/soc/canaan/canaan_k230_inno.c onto mainline v7.3-rc5
 * (openspec/changes/the-mainline-shell-reaches-parity, task 5.1). This is
 * the "canaan,k230-audio-inno" machine (card) driver: it binds the
 * mainline Synopsys DesignWare I2S controller (sound/soc/dwc/dwc-i2s.c,
 * compatible "snps,designware-i2s" -- see nix/dts/k230-tdisplay-
 * mainline.dts) as CPU+platform DAI to the forward-ported Inno codec
 * (sound/soc/codecs/inno_k230.c, "k230-inno-codec-dai").
 *
 * Changes from the vendor file:
 *   - SND_SOC_DAIFMT_CBS_CFS -> SND_SOC_DAIFMT_CBC_CFC. Mainline renamed
 *     every DAIFMT clock-role macro from master/slave to provider/consumer
 *     terms; CBS_CFS ("codec bitclock slave, codec frame slave") no longer
 *     exists at all in v7.3-rc5's include/sound/soc-dai.h. CBC_CFC
 *     ("codec clock consumer & frame consumer") is the exact same role:
 *     the SoC's I2S controller drives BCLK/WS, the Inno codec receives
 *     them. Checked directly against
 *     sound/soc/dwc/dwc-i2s.c's own already-mainline DW_I2S_MASTER usage.
 *   - Dropped the unused `#include <linux/gpio.h>` and
 *     `#include <linux/of_gpio.h>`. Neither vendor file nor this one ever
 *     calls a GPIO function; of_gpio.h no longer exists in v7.3-rc5 at all
 *     (removed upstream), so keeping the include would fail the build for
 *     a header this file never needed.
 *   - Folded in nix/patches/canaan-audio-external-i2s-switch.patch's
 *     "External I2S Output Switch" ALSA control directly, rather than
 *     reapplying that patch textually against this forward-ported copy.
 *     Same control name, same semantics, same
 *     canaan,external-i2s-output-default DT property -- see that patch
 *     file's own header comment for why the name must match exactly what
 *     Xinyuan-LilyGO/T-Display-K230's launcher already drives via
 *     `amixer -q cset`.
 *   - No clock claim added here: this node (compatible
 *     "canaan,k230-audio-inno") has no `reg` of its own and owns no
 *     hardware -- it only points at the i2s and inno_codec phandles,
 *     which claim their own clocks. See canaan_k230_audio.c and
 *     sound/soc/codecs/inno_k230.c's own forward-port headers for the
 *     clocks this change adds.
 */

#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/mutex.h>
#include <sound/core.h>
#include <sound/jack.h>
#include <sound/pcm.h>
#include <sound/pcm_params.h>
#include <sound/soc.h>

#include "canaan_k230_audio.h"

#define DRV_NAME "canaan-k230-snd-inno"

struct k230_inno_info {
	struct clk *xtal;
	struct clk *pclk;
	struct mutex clk_lock;
	int clk_users;
	bool external_i2s_output;
};

/*
 * Route the shared SAI block (k230.dtsi audio@0x9140f400, mapped by
 * canaan_k230_audio.c as `sai.base`) either through the on-die Inno codec
 * or straight out to the external I2S pads (BCLK/WS/DOUT), where a board
 * can wire a MAX98357A class-D amp that just listens to raw I2S.
 *
 * audio_i2s_enable_audio_codec() flips audio_in_pdm_conf_0.audio_codec_bypass
 * -- canaan_k230_audio.c -- which is the one register bit that actually
 * decides where the digital audio goes; there is no second sound card and
 * no DAPM path to a MAX98357A codec node here; both destinations share the
 * same physical I2S peripheral output.
 */
static void k230_inno_apply_output_route(struct k230_inno_info *priv)
{
	audio_i2s_in_init();
	audio_i2s_enable_audio_codec(!priv->external_i2s_output);
	audio_i2s_out_init(true, 32);
}

static int k230_inno_external_i2s_get(struct snd_kcontrol *kcontrol,
				      struct snd_ctl_elem_value *ucontrol)
{
	struct snd_soc_card *card = snd_kcontrol_chip(kcontrol);
	struct k230_inno_info *priv = snd_soc_card_get_drvdata(card);

	ucontrol->value.integer.value[0] = priv->external_i2s_output;

	return 0;
}

static int k230_inno_external_i2s_put(struct snd_kcontrol *kcontrol,
				      struct snd_ctl_elem_value *ucontrol)
{
	struct snd_soc_card *card = snd_kcontrol_chip(kcontrol);
	struct k230_inno_info *priv = snd_soc_card_get_drvdata(card);
	bool enable = !!ucontrol->value.integer.value[0];

	if (priv->external_i2s_output == enable)
		return 0;

	priv->external_i2s_output = enable;
	k230_inno_apply_output_route(priv);

	return 1;
}

/*
 * "External I2S Output Switch" is the exact control name LILYGO's own
 * T-Display-K230 launcher drives with `amixer -q cset name='...'` --
 * k230_launcher/k230_phone_ui/src/ui_hardware.c:1736-1751 in
 * Xinyuan-LilyGO/T-Display-K230. Keeping the same name lets that same
 * amixer invocation, and any script written against it, work unmodified.
 */
static const struct snd_kcontrol_new k230_inno_controls[] = {
	SOC_SINGLE_BOOL_EXT("External I2S Output Switch", 0,
			    k230_inno_external_i2s_get,
			    k230_inno_external_i2s_put),
};

static int k230_inno_hw_params(struct snd_pcm_substream *substream,
			       struct snd_pcm_hw_params *params)
{
	return 0;
}

static void k230_inno_shutdown(struct snd_pcm_substream *substream)
{
}

static int k230_inno_startup(struct snd_pcm_substream *substream)
{
	struct snd_soc_pcm_runtime *rtd = snd_soc_substream_to_rtd(substream);
	struct snd_soc_card *card = rtd->card;
	struct k230_inno_info *priv = snd_soc_card_get_drvdata(card);

	/*
	 * Re-assert the selected route on every stream open. The vendor
	 * probe path below runs this once at boot; without repeating it
	 * here a later route change made only via the mixer control (with
	 * no active stream) would not survive a suspend/resume of the SAI
	 * clocks.
	 */
	k230_inno_apply_output_route(priv);

	return 0;
}

static const struct snd_soc_ops canaan_k230_inno_ops = {
	.startup = k230_inno_startup,
	.shutdown = k230_inno_shutdown,
	.hw_params = k230_inno_hw_params,
};

SND_SOC_DAILINK_DEFS(k230_inno, DAILINK_COMP_ARRAY(COMP_EMPTY()),
		     DAILINK_COMP_ARRAY(COMP_CODEC(NULL,
						   "k230-inno-codec-dai")),
		     DAILINK_COMP_ARRAY(COMP_EMPTY()));

static struct snd_soc_dai_link canaan_k230_dailink = {
	.name = "k230-inno-codec",
	.stream_name = "Audio",
	.ops = &canaan_k230_inno_ops,
	.dai_fmt = SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF |
		   SND_SOC_DAIFMT_CBC_CFC,
	SND_SOC_DAILINK_REG(k230_inno),
};

static struct snd_soc_card snd_soc_card_k230 = {
	.name = "CANAAN-K230-I2S",
	.owner = THIS_MODULE,
	.dai_link = &canaan_k230_dailink,
	.num_links = 1,
	.controls = k230_inno_controls,
	.num_controls = ARRAY_SIZE(k230_inno_controls),
};

static int canaan_k230_inno_probe(struct platform_device *pdev)
{
	struct snd_soc_card *card = &snd_soc_card_k230;
	struct device_node *codec_np, *cpu_np;
	struct snd_soc_dai_link *dailink = &canaan_k230_dailink;
	struct device_node *np = pdev->dev.of_node;
	struct k230_inno_info *priv;
	int ret;

	if (!np) {
		dev_err(&pdev->dev, "only device tree supported\n");
		return -EINVAL;
	}

	priv = devm_kzalloc(&pdev->dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;

	mutex_init(&priv->clk_lock);
	priv->external_i2s_output =
		of_property_read_bool(np, "canaan,external-i2s-output-default");

	card->dev = &pdev->dev;
	snd_soc_card_set_drvdata(card, priv);

	codec_np = of_parse_phandle(np, "canaan,k230-audio-codec", 0);
	if (!codec_np) {
		dev_err(&pdev->dev,
			"Property 'canaan,k230-audio-codec' missing or invalid\n");
		return -EINVAL;
	}
	dailink->codecs->of_node = codec_np;
	of_node_put(codec_np);

	cpu_np = of_parse_phandle(np, "canaan,k230-i2s-controller", 0);
	if (!cpu_np) {
		dev_err(&pdev->dev,
			"Property 'canaan,k230-i2s-controller' missing or invalid\n");
		return -EINVAL;
	}

	dailink->cpus->of_node = cpu_np;
	dailink->platforms->of_node = cpu_np;
	of_node_put(cpu_np);

	ret = snd_soc_of_parse_card_name(card, "canaan,model");
	if (ret) {
		dev_err(&pdev->dev, "Soc parse card name failed %d\n", ret);
		return ret;
	}

	ret = devm_snd_soc_register_card(&pdev->dev, card);
	if (ret) {
		dev_err(&pdev->dev, "failed to register card: %d\n", ret);
		return ret;
	}

	k230_inno_apply_output_route(priv);
	dev_info(&pdev->dev, "External I2S output %s by default\n",
		 priv->external_i2s_output ? "enabled" : "disabled");

	return ret;
}

static const struct of_device_id canaan_k230_inno_of_match[] = {
	{
		.compatible = "canaan,k230-audio-inno",
	},
	{},
};

MODULE_DEVICE_TABLE(of, canaan_k230_inno_of_match);

static struct platform_driver canaan_k230_inno_driver = {
	.probe = canaan_k230_inno_probe,
	.driver = {
		.name = DRV_NAME,
		.of_match_table = canaan_k230_inno_of_match,
	},
};

module_platform_driver(canaan_k230_inno_driver);

MODULE_DESCRIPTION("CANAAN k230 inno machine ASoC driver");
MODULE_LICENSE("GPL");
MODULE_ALIAS("platform:" DRV_NAME);
