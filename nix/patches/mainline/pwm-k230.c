// SPDX-License-Identifier: GPL-2.0
/* Copyright (c) 2023, Canaan Bright Sight Co., Ltd
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 * 1. Redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
 * CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
 * INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 * BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 * openspec/changes/the-keyboard-base-types-lights-and-reports-its-battery
 * task 4.2 forward-port, from ruyisdk/linux-xuantie-kernel's
 * drivers/pwm/pwm-k230.c (the pinned vendor tree). Changes from the vendor
 * original:
 *   1. v7.3 chip API: devm_pwmchip_alloc() and pwmchip_get_drvdata()
 *      instead of an embedded struct pwm_chip; no .owner in pwm_ops.
 *   2. Prescale: the vendor picked scale = ilog2(ticks) - 16, which leaves
 *      a 17-bit count in the 16-bit pwmcmp0 for any period of 2^16..2^17
 *      ticks. Here scale is the smallest shift that fits.
 *   3. Polarity: the vendor accepted only PWM_POLARITY_INVERSED, writing
 *      the duty straight into pwmcmpN, and wrote 0 when disabled -- which
 *      for that contract drives the output at its active level, so a
 *      "disabled" LED lit fully. Each channel's output is taken to be high
 *      while the counter is >= pwmcmpN (the vendor's INVERSED-only
 *      contract). NORMAL polarity writes period - duty; INVERSED keeps the
 *      vendor mapping. Disabled drives the inactive level for the state's
 *      polarity. If the board shows the opposite sense, the device tree's
 *      PWM flags select the other mapping without a kernel change.
 *      UNVERIFIED until an LED on the K230 is observed under it.
 *   4. The three channels share pwmcmp0 (the period). A second user may
 *      only request the period already programmed.
 *   5. An optional shared reset (RST_PWM_APB) is deasserted at probe; the
 *      vendor relied on firmware leaving the block out of reset.
 */

#include <linux/bitfield.h>
#include <linux/clk.h>
#include <linux/io.h>
#include <linux/math64.h>
#include <linux/mod_devicetable.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/platform_device.h>
#include <linux/pwm.h>
#include <linux/reset.h>

/* Register offsets */
#define PWM_PWMCFG		0x0
#define PWM_PWMCOUNT		0x8
#define PWM_PWMS		0x10
#define PWM_PWMCMP(i)		(0x20 + 4 * (i))

/* PWMCFG fields */
#define PWM_PWMCFG_SCALE	GENMASK(3, 0)
#define PWM_PWMCFG_ZERO_CMP	BIT(9)
#define PWM_PWMCFG_EN_ALWAYS	BIT(12)

#define PWM_CMPWIDTH		16
/* pwmcmp0 at most this, so pwmcmp0 + 1 ("never high") still fits. */
#define PWM_CMP0_MAX		(BIT(PWM_CMPWIDTH) - 2)

struct k230_pwm {
	void __iomem *regs;
	struct clk *clk;
	struct mutex lock;
	unsigned int users;
	u64 clk_freq;
	u64 period_ns;
	u32 scale;
	u32 cmp0;	/* period in prescaled ticks, minus one */
};

static int k230_pwm_request(struct pwm_chip *chip, struct pwm_device *pwm)
{
	struct k230_pwm *priv = pwmchip_get_drvdata(chip);

	mutex_lock(&priv->lock);
	priv->users++;
	mutex_unlock(&priv->lock);
	return 0;
}

static void k230_pwm_free(struct pwm_chip *chip, struct pwm_device *pwm)
{
	struct k230_pwm *priv = pwmchip_get_drvdata(chip);

	mutex_lock(&priv->lock);
	if (--priv->users == 0) {
		writel(0, priv->regs + PWM_PWMCFG);
		priv->period_ns = 0;
	}
	mutex_unlock(&priv->lock);
}

/* Called with priv->lock held. */
static int k230_pwm_set_period(struct k230_pwm *priv, u64 period_ns)
{
	u64 ticks = mul_u64_u64_div_u64(period_ns, priv->clk_freq, NSEC_PER_SEC);
	u32 scale = 0;

	if (ticks < 2)
		return -EINVAL;
	while ((ticks >> scale) - 1 > PWM_CMP0_MAX) {
		if (++scale > FIELD_MAX(PWM_PWMCFG_SCALE))
			return -EINVAL;
	}

	priv->scale = scale;
	priv->cmp0 = (ticks >> scale) - 1;
	priv->period_ns = period_ns;
	writel(priv->cmp0, priv->regs + PWM_PWMCMP(0));
	writel(PWM_PWMCFG_EN_ALWAYS | PWM_PWMCFG_ZERO_CMP |
	       FIELD_PREP(PWM_PWMCFG_SCALE, scale),
	       priv->regs + PWM_PWMCFG);
	return 0;
}

static int k230_pwm_apply(struct pwm_chip *chip, struct pwm_device *pwm,
			  const struct pwm_state *state)
{
	struct k230_pwm *priv = pwmchip_get_drvdata(chip);
	u64 period_ticks, high;
	u32 cmp;
	int ret = 0;

	mutex_lock(&priv->lock);
	if (state->period != priv->period_ns) {
		if (priv->users > 1 && priv->period_ns) {
			ret = -EBUSY;
			goto out;
		}
		ret = k230_pwm_set_period(priv, state->period);
		if (ret)
			goto out;
	}

	period_ticks = (u64)priv->cmp0 + 1;
	high = 0;
	if (state->enabled) {
		/* Ticks the output spends at its active level. */
		high = mul_u64_u64_div_u64(state->duty_cycle, priv->clk_freq,
					   NSEC_PER_SEC) >> priv->scale;
		high = min(high, period_ticks);
	}
	/*
	 * Output is high while count >= cmp: NORMAL wants high for `high`
	 * ticks, so cmp = period - high; INVERSED wants low for `high` ticks.
	 * A disabled channel has high = 0, the inactive level either way.
	 */
	if (state->polarity == PWM_POLARITY_NORMAL)
		cmp = period_ticks - high;
	else
		cmp = high;
	writel(cmp, priv->regs + PWM_PWMCMP(pwm->hwpwm + 1));
out:
	mutex_unlock(&priv->lock);
	return ret;
}

static int k230_pwm_get_state(struct pwm_chip *chip, struct pwm_device *pwm,
			      struct pwm_state *state)
{
	struct k230_pwm *priv = pwmchip_get_drvdata(chip);
	u32 cfg = readl(priv->regs + PWM_PWMCFG);
	u32 scale = FIELD_GET(PWM_PWMCFG_SCALE, cfg);
	u64 period_ticks = ((u64)readl(priv->regs + PWM_PWMCMP(0)) + 1) << scale;
	u64 cmp = (u64)readl(priv->regs + PWM_PWMCMP(pwm->hwpwm + 1)) << scale;
	u64 high;

	cmp = min(cmp, period_ticks);
	high = period_ticks - cmp;
	state->enabled = (cfg & PWM_PWMCFG_EN_ALWAYS) && high;
	state->polarity = PWM_POLARITY_NORMAL;
	state->period = DIV64_U64_ROUND_UP(period_ticks * NSEC_PER_SEC,
					   priv->clk_freq);
	state->duty_cycle = DIV64_U64_ROUND_UP(high * NSEC_PER_SEC,
					       priv->clk_freq);
	return 0;
}

static const struct pwm_ops k230_pwm_ops = {
	.request = k230_pwm_request,
	.free = k230_pwm_free,
	.apply = k230_pwm_apply,
	.get_state = k230_pwm_get_state,
};

static int k230_pwm_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct pwm_chip *chip;
	struct k230_pwm *priv;
	int ret;

	chip = devm_pwmchip_alloc(dev, 3, sizeof(*priv));
	if (IS_ERR(chip))
		return PTR_ERR(chip);
	priv = pwmchip_get_drvdata(chip);

	priv->regs = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(priv->regs))
		return PTR_ERR(priv->regs);

	ret = PTR_ERR_OR_ZERO(devm_reset_control_get_optional_shared_deasserted(dev, NULL));
	if (ret)
		return dev_err_probe(dev, ret, "reset\n");

	priv->clk = devm_clk_get_enabled(dev, NULL);
	if (IS_ERR(priv->clk))
		return dev_err_probe(dev, PTR_ERR(priv->clk), "no clock\n");
	priv->clk_freq = clk_get_rate(priv->clk);
	if (!priv->clk_freq)
		return dev_err_probe(dev, -EINVAL, "clock rate is 0\n");

	mutex_init(&priv->lock);
	chip->ops = &k230_pwm_ops;
	dev_info(dev, "%llu Hz\n", priv->clk_freq);
	return devm_pwmchip_add(dev, chip);
}

static const struct of_device_id k230_pwm_of_match[] = {
	{ .compatible = "canaan,k230-pwm" },
	{}
};
MODULE_DEVICE_TABLE(of, k230_pwm_of_match);

static struct platform_driver k230_pwm_driver = {
	.probe = k230_pwm_probe,
	.driver = {
		.name = "k230-pwm",
		.of_match_table = k230_pwm_of_match,
	},
};
module_platform_driver(k230_pwm_driver);

MODULE_AUTHOR("Canaan SDK Team");
MODULE_DESCRIPTION("Canaan Kendryte K230 PWM driver");
MODULE_LICENSE("GPL");
