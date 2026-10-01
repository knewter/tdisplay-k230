// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Copyright (c) 2022, Canaan Bright Sight Co., Ltd
 *
 * Forward-ported from drivers/soc/canaan/k230-power-domains.c in
 * ruyisdk/linux-xuantie-kernel, 7d4e1f444f461dbe3833bd99a4640e7b6c2cd529.
 * Preserve its five-domain ABI, register table and bounded power/repair
 * sequences. State is per-controller; unused vendor hardlock reads are gone.
 */
#include <linux/delay.h>
#include <linux/err.h>
#include <linux/io.h>
#include <linux/of.h>
#include <linux/pm_domain.h>
#include <linux/platform_device.h>

#include <dt-bindings/soc/canaan,k230_pm_domains.h>

enum k230_pm_reg {
	REG_PM_PWR_EN,
	REG_PM_PWR_STAT,
	REG_PM_REPAIR_EN,
	REG_PM_REPAIR_STAT,
	REG_PM_ARRAY_SIZE,
};

struct k230_power;

struct k230_pm_domain {
	struct generic_pm_domain genpd;
	struct k230_power *controller;
	const u16 *reg_offset;
	bool repair_enable;
};

struct k230_power {
	void __iomem *base;
	struct device *dev;
	struct genpd_onecell_data data;
	struct generic_pm_domain *domains[K230_PM_DOMAIN_MAX];
	struct k230_pm_domain domain[K230_PM_DOMAIN_MAX];
	unsigned int initialized;
	bool registered;
};

static const u16 k230_offsets[K230_PM_DOMAIN_MAX][REG_PM_ARRAY_SIZE] = {
	{ 0x18, 0x1c, 0x18, 0x160 },
	{ 0x28, 0x2c, 0x28, 0x160 },
	{ 0x3c, 0x40, 0x3c, 0x160 },
	{ 0x7c, 0x80, 0x7c, 0x160 },
	{ 0x108, 0x10c, 0x108, 0x160 },
};

static const char * const k230_names[K230_PM_DOMAIN_MAX] = {
	"cpu1_domain", "ai_domain", "disp_domain", "vpu_domain", "dpu_domain",
};

static int k230_power_on(struct generic_pm_domain *domain)
{
	struct k230_pm_domain *pd = container_of(domain, struct k230_pm_domain, genpd);
	void __iomem *base = pd->controller->base;
	unsigned int loop = 1000;
	u32 val;

	if (readl(base + pd->reg_offset[REG_PM_PWR_STAT]) & BIT(1))
		return 0;

	/* Vendor power-on bit 1, with on/off write-enable bits 17/16. */
	writel(BIT(1) | BIT(17) | BIT(16), base + pd->reg_offset[REG_PM_PWR_EN]);

	if (pd->repair_enable) {
		/* Only AI uses the vendor bit 4/write-enable bit 20 repair. */
		writel(BIT(4) | BIT(20), base + pd->reg_offset[REG_PM_REPAIR_EN]);
		do {
			udelay(1);
			val = readl(base + pd->reg_offset[REG_PM_REPAIR_STAT]) & 0x7;
		} while (--loop && !val);
		if (!loop)
			return -EIO;
	}

	loop = 1000;
	do {
		udelay(1);
		val = readl(base + pd->reg_offset[REG_PM_PWR_STAT]) & BIT(1);
	} while (--loop && !val);
	return loop ? 0 : -EIO;
}

static int k230_power_off(struct generic_pm_domain *domain)
{
	struct k230_pm_domain *pd = container_of(domain, struct k230_pm_domain, genpd);
	void __iomem *base = pd->controller->base;
	unsigned int loop = 1000;
	u32 val;

	if (readl(base + pd->reg_offset[REG_PM_PWR_STAT]) & BIT(0))
		return 0;

	writel(BIT(0) | BIT(17) | BIT(16), base + pd->reg_offset[REG_PM_PWR_EN]);
	do {
		udelay(1);
		val = readl(base + pd->reg_offset[REG_PM_PWR_STAT]) & BIT(0);
	} while (--loop && !val);
	return loop ? 0 : -EIO;
}

static void k230_power_cleanup(void *data)
{
	struct k230_power *power = data;
	int ret;

	if (power->registered)
		of_genpd_del_provider(power->dev->of_node);
	while (power->initialized) {
		ret = pm_genpd_remove(power->domains[--power->initialized]);
		if (ret)
			dev_warn(power->dev, "cannot remove power domain: %d\n", ret);
	}
}

static int k230_power_domain_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct k230_power *power;
	unsigned int i;
	int ret;

	power = devm_kzalloc(dev, sizeof(*power), GFP_KERNEL);
	if (!power)
		return -ENOMEM;
	power->dev = dev;
	power->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(power->base))
		return PTR_ERR(power->base);

	ret = devm_add_action_or_reset(dev, k230_power_cleanup, power);
	if (ret)
		return ret;

	for (i = 0; i < K230_PM_DOMAIN_MAX; i++) {
		struct k230_pm_domain *pd = &power->domain[i];
		bool is_off = i == K230_PM_DOMAIN_DISP || i == K230_PM_DOMAIN_VPU;

		pd->controller = power;
		pd->reg_offset = k230_offsets[i];
		pd->repair_enable = i == K230_PM_DOMAIN_AI;
		pd->genpd.name = k230_names[i];
		pd->genpd.power_on = k230_power_on;
		pd->genpd.power_off = k230_power_off;
		/* Preserve vendor CPU1/AI/DPU always-on policy and initial states. */
		if (!is_off)
			pd->genpd.flags |= GENPD_FLAG_ALWAYS_ON;
		ret = pm_genpd_init(&pd->genpd, NULL, is_off);
		if (ret)
			return dev_err_probe(dev, ret, "cannot initialize domain %u\n", i);
		power->domains[i] = &pd->genpd;
		power->initialized++;
	}

	power->data.domains = power->domains;
	power->data.num_domains = K230_PM_DOMAIN_MAX;
	ret = of_genpd_add_provider_onecell(dev->of_node, &power->data);
	if (ret)
		return dev_err_probe(dev, ret, "cannot register power domains\n");
	power->registered = true;
	dev_info(dev, "powerdomain init ok\n");
	return 0;
}

static const struct of_device_id k230_pm_domain_matches[] = {
	{ .compatible = "canaan, k230-sysctl-power" },
	{ },
};

static struct platform_driver k230_power_domain_driver = {
	.driver = {
		.name = "k230-powerdomain",
		.of_match_table = k230_pm_domain_matches,
		/* A built-in SoC controller cannot be safely unbound with consumers. */
		.suppress_bind_attrs = true,
	},
	.probe = k230_power_domain_probe,
};

static int __init k230_power_domain_init(void)
{
	return platform_driver_register(&k230_power_domain_driver);
}
subsys_initcall(k230_power_domain_init);
