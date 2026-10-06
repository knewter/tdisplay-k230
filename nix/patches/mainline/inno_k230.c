// SPDX-License-Identifier: GPL-2.0-only
/*
 * Forward-ported from the pinned vendor Xuantie tree's
 * sound/soc/codecs/inno_k230.c onto mainline v7.3-rc5
 * (openspec/changes/the-mainline-shell-reaches-parity, task 5.1). ASoC
 * codec component driver for the K230 SoC's on-die Inno codec
 * (inno_codec@0x9140e000 in k230.dtsi, compatible "canaan,k230-inno-codec").
 * Low-level register access lives in inno_k230_reg.c, forward-ported
 * unchanged (plain MMIO + struct bitfields, no kernel-version-sensitive
 * API).
 *
 * Changes from the vendor file:
 *   - struct platform_driver.remove changed from
 *     `int (*)(struct platform_device *)` to `void (*)(...)`, matching
 *     v7.3-rc5's struct platform_device (same fix already applied to this
 *     project's other forward-ports).
 *   - devm_clk_get()+clk_prepare_enable() pairs replaced with
 *     devm_clk_get_enabled() for the two functional mclks ("adc"/"dac",
 *     i.e. K230_LS_CODEC_ADC_RATE/K230_LS_CODEC_DAC_RATE in mainline's
 *     drivers/clk/clk-k230.c) -- behavior-preserving, just the modern
 *     devm helper this project's AGENTS.md asks new clock claims to use.
 *   - Added an explicit, additional claim of K230_LS_CODEC_APB_GATE
 *     (clock-names "apb"). The vendor driver claims only the two mclks.
 *     Checked directly against mainline's drivers/clk/clk-k230.c: the
 *     "adc"/"dac" rate clocks' own parent IS their matching gate
 *     (ls_codec_adc_rate's hw parent is &ls_codec_adc_gate.clk.hw, and
 *     likewise for dac), so claiming them already cascade-enables
 *     K230_LS_CODEC_ADC_GATE/K230_LS_CODEC_DAC_GATE through the common
 *     clock framework's own parent-enable chain -- no separate claim
 *     needed for those two. K230_LS_CODEC_APB_GATE's parent is
 *     ls_apb_src_rate, a completely different branch of the clock tree
 *     that nothing else here claims, so without this explicit claim this
 *     project's mainline clk-k230 driver gates it and every register
 *     access in this file (regmap/MMIO reads in inno_k230_reg.c) hangs.
 *     See docs/research/mainline-audio-port.md.
 */

#include <sound/soc.h>
#include <sound/tlv.h>
#include <sound/soc-dapm.h>
#include <sound/soc-dai.h>
#include <sound/pcm.h>
#include <sound/pcm_params.h>

#include <linux/platform_device.h>
#include <linux/of.h>
#include <linux/clk.h>
#include <linux/regmap.h>
#include <linux/device.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/io.h>
#include "inno_k230_reg.h"

#define INNO_VOLUME_INVERT_VALUE 39

struct k230_inno_codec_priv {
	void __iomem *base;
	struct clk *pclk_adc;
	struct clk *pclk_dac;
	struct clk *pclk_apb;
	struct regmap *regmap;
	struct device *dev;
};

enum snd_inno_k230_ctrl {
	INNO_PCM_PLAYBACK_VOLUME,
	INNO_PCM_PLAYBACK_MUTE,
	INNO_PCM_CAPTURE_VOLUME,
	INNO_PCM_CAPTURE_MUTE,
};

static int inno_capture_info_vol(struct snd_kcontrol *kcontrol,
				 struct snd_ctl_elem_info *uinfo)
{
	uinfo->type = SNDRV_CTL_ELEM_TYPE_INTEGER;
	uinfo->count = 2;
	uinfo->value.integer.min = 0;
	uinfo->value.integer.max = 4;
	return 0;
}

static int inno_capture_get_vol(struct snd_kcontrol *kcontrol,
				struct snd_ctl_elem_value *ucontrol)
{
	return 0;
}

static int inno_capture_put_vol(struct snd_kcontrol *kcontrol,
				struct snd_ctl_elem_value *ucontrol)
{
	return 0;
}

static const struct snd_kcontrol_new inno_snd_capture_volume_control = {
	.iface = SNDRV_CTL_ELEM_IFACE_MIXER,
	.name = "Capture Volume",
	.info = inno_capture_info_vol,
	.get = inno_capture_get_vol,
	.put = inno_capture_put_vol,
};

static int inno_playback_info_vol(struct snd_kcontrol *kcontrol,
				  struct snd_ctl_elem_info *uinfo)
{
	uinfo->type = SNDRV_CTL_ELEM_TYPE_INTEGER;
	uinfo->count = 2;
	uinfo->value.integer.min = -39 + INNO_VOLUME_INVERT_VALUE;
	uinfo->value.integer.max = 6 + INNO_VOLUME_INVERT_VALUE;
	return 0;
}

static int inno_playback_get_vol(struct snd_kcontrol *kcontrol,
				 struct snd_ctl_elem_value *ucontrol)
{
	int value;

	audio_codec_dac_get_hpoutl_gain(&value);
	ucontrol->value.integer.value[1] = ucontrol->value.integer.value[0] =
		value + INNO_VOLUME_INVERT_VALUE;
	return 0;
}

static int inno_playback_put_vol(struct snd_kcontrol *kcontrol,
				 struct snd_ctl_elem_value *ucontrol)
{
	audio_codec_dac_set_hpoutl_gain(ucontrol->value.integer.value[0] -
					INNO_VOLUME_INVERT_VALUE);
	audio_codec_dac_set_hpoutr_gain(ucontrol->value.integer.value[0] -
					INNO_VOLUME_INVERT_VALUE);
	return 0;
}

static const struct snd_kcontrol_new inno_snd_playback_volume_control = {
	.iface = SNDRV_CTL_ELEM_IFACE_MIXER,
	.name = "Master Playback Volume",
	.info = inno_playback_info_vol,
	.get = inno_playback_get_vol,
	.put = inno_playback_put_vol,
};

static int snd_inno_ctl_vol(struct snd_kcontrol *kcontrol,
			    struct snd_ctl_elem_info *uinfo)
{
	if (kcontrol->private_value == INNO_PCM_PLAYBACK_VOLUME) {
		uinfo->type = SNDRV_CTL_ELEM_TYPE_INTEGER;
		uinfo->count = 1;
		uinfo->value.integer.min = -39 + INNO_VOLUME_INVERT_VALUE;
		uinfo->value.integer.max = 6 + INNO_VOLUME_INVERT_VALUE;
		uinfo->value.integer.step = 3;
	} else if (kcontrol->private_value == INNO_PCM_PLAYBACK_MUTE) {
		uinfo->type = SNDRV_CTL_ELEM_TYPE_BOOLEAN;
		uinfo->count = 1;
		uinfo->value.integer.min = 0;
		uinfo->value.integer.max = 1;
	} else if (kcontrol->private_value == INNO_PCM_CAPTURE_VOLUME) {
		uinfo->type = SNDRV_CTL_ELEM_TYPE_INTEGER;
		uinfo->count = 1;
		uinfo->value.integer.min = 0;
		uinfo->value.integer.max = 30;
		uinfo->value.integer.step = 10;
	} else if (kcontrol->private_value == INNO_PCM_CAPTURE_MUTE) {
		uinfo->type = SNDRV_CTL_ELEM_TYPE_BOOLEAN;
		uinfo->count = 1;
		uinfo->value.integer.min = 0;
		uinfo->value.integer.max = 1;
	}
	return 0;
}

static int snd_inno_ctl_get(struct snd_kcontrol *kcontrol,
			    struct snd_ctl_elem_value *ucontrol)
{
	int value;
	bool mute;

	if (kcontrol->private_value == INNO_PCM_PLAYBACK_VOLUME) {
		audio_codec_dac_get_hpoutl_gain(&value);
		ucontrol->value.integer.value[0] =
			value + INNO_VOLUME_INVERT_VALUE;
	} else if (kcontrol->private_value == INNO_PCM_PLAYBACK_MUTE) {
		audio_codec_dac_get_hpoutl_mute(&mute);
		ucontrol->value.integer.value[0] = !mute;
	} else if (kcontrol->private_value == INNO_PCM_CAPTURE_VOLUME) {
		audio_codec_adc_get_micl_gain(&value);
		if (value == 6)
			value = 10;
		ucontrol->value.integer.value[0] = value;
	} else if (kcontrol->private_value == INNO_PCM_CAPTURE_MUTE) {
		audio_codec_adc_get_micl_mute(&mute);
		ucontrol->value.integer.value[0] = !mute;
	}
	return 0;
}

static int snd_inno_ctl_put(struct snd_kcontrol *kcontrol,
			    struct snd_ctl_elem_value *ucontrol)
{
	if (kcontrol->private_value == INNO_PCM_PLAYBACK_VOLUME) {
		audio_codec_dac_set_hpoutl_gain(
			ucontrol->value.integer.value[0] -
			INNO_VOLUME_INVERT_VALUE);
		audio_codec_dac_set_hpoutr_gain(
			ucontrol->value.integer.value[0] -
			INNO_VOLUME_INVERT_VALUE);
	} else if (kcontrol->private_value == INNO_PCM_PLAYBACK_MUTE) {
		audio_codec_dac_hpoutl_mute(!ucontrol->value.integer.value[0]);
		audio_codec_dac_hpoutr_mute(!ucontrol->value.integer.value[0]);
	} else if (kcontrol->private_value == INNO_PCM_CAPTURE_VOLUME) {
		audio_codec_adc_set_micl_gain(ucontrol->value.integer.value[0]);
		audio_codec_adc_set_micl_gain(ucontrol->value.integer.value[0]);

	} else if (kcontrol->private_value == INNO_PCM_CAPTURE_MUTE) {
		audio_codec_adc_micl_mute(!ucontrol->value.integer.value[0]);
		audio_codec_adc_micr_mute(!ucontrol->value.integer.value[0]);
	}
	return 0;
}

static const struct snd_kcontrol_new inno_snd_control[] = {
	{
		.iface = SNDRV_CTL_ELEM_IFACE_MIXER,
		.name = "PCM Playback Volume",
		.info = snd_inno_ctl_vol,
		.get = snd_inno_ctl_get,
		.put = snd_inno_ctl_put,
		.private_value = INNO_PCM_PLAYBACK_VOLUME,
	},
	{
		.iface = SNDRV_CTL_ELEM_IFACE_MIXER,
		.name = "PCM Playback Switch",
		.info = snd_inno_ctl_vol,
		.get = snd_inno_ctl_get,
		.put = snd_inno_ctl_put,
		.private_value = INNO_PCM_PLAYBACK_MUTE,
	},
	{
		.iface = SNDRV_CTL_ELEM_IFACE_MIXER,
		.name = "Mic Capture Volume",
		.info = snd_inno_ctl_vol,
		.get = snd_inno_ctl_get,
		.put = snd_inno_ctl_put,
		.private_value = INNO_PCM_CAPTURE_VOLUME,
	},
	{
		.iface = SNDRV_CTL_ELEM_IFACE_MIXER,
		.name = "Mic Capture Switch",
		.info = snd_inno_ctl_vol,
		.get = snd_inno_ctl_get,
		.put = snd_inno_ctl_put,
		.private_value = INNO_PCM_CAPTURE_MUTE,
	},

};

static int k230_inno_codec_probe(struct snd_soc_component *component)
{
	snd_soc_add_component_controls(component, inno_snd_control,
				       ARRAY_SIZE(inno_snd_control));
	return 0;
}

static void k230_inno_codec_remove(struct snd_soc_component *component)
{
}

static int k230_inno_codec_set_bias_level(struct snd_soc_component *component,
					  enum snd_soc_bias_level level)
{
	return 0;
}

static const struct snd_soc_dapm_route k230_inno_codec_dapm_routes[] = {
};

static const struct snd_soc_dapm_widget k230_inno_codec_dapm_widgets[] = {};

static int k230_inno_codec_open(struct snd_soc_component *component,
				struct snd_pcm_substream *substream)
{
	return 0;
}

static const struct snd_soc_component_driver k230_inno_codec_driver = {
	.open = k230_inno_codec_open,
	.probe = k230_inno_codec_probe,
	.remove = k230_inno_codec_remove,
	.set_bias_level = k230_inno_codec_set_bias_level,
	.dapm_routes = k230_inno_codec_dapm_routes,
	.num_dapm_routes = ARRAY_SIZE(k230_inno_codec_dapm_routes),
	.dapm_widgets = k230_inno_codec_dapm_widgets,
	.num_dapm_widgets = ARRAY_SIZE(k230_inno_codec_dapm_widgets),
	.idle_bias_on = 1,
	.use_pmdown_time = 1,
	.endianness = 1,
	.legacy_dai_naming = 1,
};

static int k230_inno_codec_dai_set_fmt(struct snd_soc_dai *dai,
				       unsigned int fmt)
{
	return 0;
}

static int k230_inno_codec_dai_hw_params(struct snd_pcm_substream *substream,
					 struct snd_pcm_hw_params *hw_params,
					 struct snd_soc_dai *dai)
{
	struct k230_inno_codec_priv *priv = snd_soc_dai_get_drvdata(dai);
	uint32_t i2s_ws = 16;
	uint32_t sample_rate = 0;
	uint32_t chn_cnt = 0;
	int ret = 0;
	struct snd_soc_component *component = dai->component;

	sample_rate = params_rate(hw_params);
	switch (params_format(hw_params)) {
	case SNDRV_PCM_FORMAT_S16_LE:
		i2s_ws = 16;
		break;
	case SNDRV_PCM_FORMAT_S24_LE:
		i2s_ws = 24;
		break;
	case SNDRV_PCM_FORMAT_S32_LE:
		i2s_ws = 32;
		break;
	default:
		dev_err(component->dev, "k230_inno_codec: unsupported PCM fmt");
		return -EINVAL;
	}

	if (substream->stream == SNDRV_PCM_STREAM_CAPTURE) {
		ret = clk_set_rate(priv->pclk_adc, sample_rate * 256);
		if (ret) {
			dev_err(priv->dev,
				"Can't set inno codec clock rate: %d\n", ret);
			return ret;
		}

		audio_codec_adc_init(K_STANDARD_MODE, i2s_ws);
	} else {
		ret = clk_set_rate(priv->pclk_dac, sample_rate * 256);
		if (ret) {
			dev_err(priv->dev,
				"Can't set inno codec clock rate: %d\n", ret);
			return ret;
		}

		audio_codec_dac_init(K_STANDARD_MODE, i2s_ws);
	}

	chn_cnt = params_channels(hw_params);

	return 0;
}

static int k230_inno_codec_dai_startup(struct snd_pcm_substream *substream,
				       struct snd_soc_dai *cpu_dai)
{
	return 0;
}

#define K230_INNO_CODEC_RATES                                                \
	(SNDRV_PCM_RATE_8000 | SNDRV_PCM_RATE_16000 | SNDRV_PCM_RATE_32000 | \
	 SNDRV_PCM_RATE_44100 | SNDRV_PCM_RATE_48000)

#define K230_INNO_CODEC_FMTS (SNDRV_PCM_FMTBIT_S16_LE | SNDRV_PCM_FMTBIT_S32_LE)

static const struct snd_soc_dai_ops k230_inno_codec_dai_ops = {
	.startup = k230_inno_codec_dai_startup,
	.set_fmt = k230_inno_codec_dai_set_fmt,
	.hw_params = k230_inno_codec_dai_hw_params,
};

static struct snd_soc_dai_driver k230_inno_codec_dai_driver[] = {
	{
		.name = "k230-inno-codec-dai",
		.playback = {
			.stream_name = "Playback",
			.channels_min = 1,
			.channels_max = 2,
			.rates = K230_INNO_CODEC_RATES,
			.formats = K230_INNO_CODEC_FMTS,
		},
		.capture = {
			.stream_name = "Capture",
			.channels_min = 1,
			.channels_max = 2,
			.rates = K230_INNO_CODEC_RATES,
			.formats = K230_INNO_CODEC_FMTS,
		},
		.ops = &k230_inno_codec_dai_ops,
		.symmetric_rate = 1,
	},
};

static int inno_k230_codec_platform_probe(struct platform_device *pdev)
{
	struct k230_inno_codec_priv *priv;
	void __iomem *base;
	int ret;

	priv = devm_kzalloc(&pdev->dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;

	base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(base))
		return PTR_ERR(base);

	priv->base = base;

	/*
	 * K230_LS_CODEC_APB_GATE, clock-names "apb". Not present on the
	 * vendor DT node at all (nix/dts/k230-tdisplay.dts's vendor-tree
	 * sibling only ever listed "adc"/"dac"); optional here so this
	 * driver still probes against a device tree written before this
	 * clock was added, but requested whenever the DT offers it -- see
	 * this file's header comment and docs/research/mainline-audio-port.md
	 * for why this gate does not cascade-enable from "adc"/"dac" the
	 * way the matching ADC/DAC gates do.
	 */
	priv->pclk_apb = devm_clk_get_optional_enabled(&pdev->dev, "apb");
	if (IS_ERR(priv->pclk_apb))
		return PTR_ERR(priv->pclk_apb);

	priv->pclk_adc = devm_clk_get_enabled(&pdev->dev, "adc");
	if (IS_ERR(priv->pclk_adc))
		return PTR_ERR(priv->pclk_adc);

	priv->pclk_dac = devm_clk_get_enabled(&pdev->dev, "dac");
	if (IS_ERR(priv->pclk_dac))
		return PTR_ERR(priv->pclk_dac);

	priv->dev = &pdev->dev;
	dev_set_drvdata(&pdev->dev, priv);

	ret = devm_snd_soc_register_component(
		&pdev->dev, &k230_inno_codec_driver, k230_inno_codec_dai_driver,
		ARRAY_SIZE(k230_inno_codec_dai_driver));
	if (ret) {
		dev_set_drvdata(&pdev->dev, NULL);
		return ret;
	}

	audio_codec_reg_init(priv->base);
	audio_codec_powerup_init();

	return 0;
}

static void inno_k230_codec_platform_remove(struct platform_device *pdev)
{
}

static const struct of_device_id inno_k230_codec_of_match[] = {
	{
		.compatible = "canaan,k230-inno-codec",
	},
	{}
};
MODULE_DEVICE_TABLE(of, inno_k230_codec_of_match);

static struct platform_driver inno_k230_platform_driver = {
	.driver = {
		.name = "canaan,k230-inno-codec",
		.of_match_table = inno_k230_codec_of_match,
	},
	.probe = inno_k230_codec_platform_probe,
	.remove = inno_k230_codec_platform_remove,
};

module_platform_driver(inno_k230_platform_driver);

MODULE_DESCRIPTION("ASoC inno codec driver");
MODULE_LICENSE("GPL");
