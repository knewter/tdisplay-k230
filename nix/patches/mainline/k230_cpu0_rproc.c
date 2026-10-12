// SPDX-License-Identifier: GPL-2.0
/*
 * Canaan K230 CPU0 (the small C908 core) as a remote processor.
 *
 * READ-ONLY SKELETON (openspec/changes/the-small-core-runs-as-a-coprocessor
 * task 4.2). It binds the node, takes the CPU0 reset line, maps the boot
 * vector register and the firmware carveout, and reports what it can read.
 * It performs no reset, vector or power write: .start and .stop refuse, the
 * remoteproc sysfs files are read-only and auto-boot is off. Starting CPU0
 * from Linux is task 5.1 (vector write, then reset_control_reset()).
 *
 * Binding (docs/evidence/second-core/mainline-reset-binding-decision.md):
 *
 *	remoteproc@91102100 {
 *		compatible = "canaan,k230-cpu0-rproc";
 *		reg = <0x0 0x91102100 0x0 0x4>;	   CPU0 boot vector
 *		resets = <&rst RST_CPU0>;
 *		memory-region = <&cpu0_firmware>;   no-map carveout
 *	};
 *
 * The reset specifier must be exactly RST_CPU0. RST_CPU1 resets the core
 * Linux runs on, so any other index is refused at probe. RST_CPU0 supports
 * only .reset (a pulse; reset-k230.c returns -EOPNOTSUPP for assert and
 * deassert, and the RMU's cpu0_reset_req bit is write-one-to-toggle), so a
 * clean stop cannot come from the reset framework; see the decision note.
 *
 * Why no mailbox yet (task 4.3): the K230 TRM (section 2.9) publishes the
 * mailbox register map at 0x91104000, but not which interrupt-count group
 * drives which of its two interrupt lines, the interlock semantics, or how
 * CPU0's interrupt controller sees it (docs/research/second-core-feasibility.md,
 * all UNVERIFIED). No driver is written against an unverified map. Until
 * then CPU0 and Linux talk through the carveout's slot page by polling, as
 * the echo payload does (docs/evidence/second-core/echo-physical-2026-10-12/).
 * When a firmware image speaks virtio/rpmsg, the plan (design.md Decisions 1
 * and 5) is a poll-mode mailbox controller (txdone_poll, no IRQ) whose
 * channel this driver requests in probe and drives from .kick; the
 * remoteproc core's vdev/vring handling then works unchanged, and the
 * hardware mailbox can replace the poll controller later without touching
 * this driver.
 */

#include <linux/io.h>
#include <linux/mod_devicetable.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_reserved_mem.h>
#include <linux/platform_device.h>
#include <linux/remoteproc.h>
#include <linux/reset.h>

/* include/dt-bindings/reset/canaan,k230-rst.h */
#define K230_RST_CPU0		0

/* Echo/heartbeat slot page, carveout + 0x2000 (tools/small-core-echo.S). */
#define K230_SLOT_OFFSET	0x2000
#define K230_SLOT_MAGIC		0x58
#define K230_ECHO_MAGIC		0x4f484345

struct k230_cpu0_rproc {
	struct device *dev;
	struct reset_control *reset;
	void __iomem *vector;
	void *carveout;
	struct resource carveout_res;
	int reset_status;
};

static int k230_cpu0_rproc_start(struct rproc *rproc)
{
	dev_warn(&rproc->dev, "read-only skeleton: CPU0 start not implemented\n");
	return -EOPNOTSUPP;
}

static int k230_cpu0_rproc_stop(struct rproc *rproc)
{
	return -EOPNOTSUPP;
}

static const struct rproc_ops k230_cpu0_rproc_ops = {
	.start = k230_cpu0_rproc_start,
	.stop = k230_cpu0_rproc_stop,
};

/* Refuse any reset specifier other than a single <&rst RST_CPU0>. */
static int k230_cpu0_check_reset_spec(struct device *dev)
{
	struct of_phandle_args args;
	int count, ret;

	count = of_count_phandle_with_args(dev->of_node, "resets", "#reset-cells");
	if (count != 1)
		return dev_err_probe(dev, -EINVAL, "need exactly one reset, found %d\n", count);

	ret = of_parse_phandle_with_args(dev->of_node, "resets", "#reset-cells", 0, &args);
	if (ret)
		return dev_err_probe(dev, ret, "cannot parse resets\n");
	of_node_put(args.np);

	if (args.args_count != 1 || args.args[0] != K230_RST_CPU0)
		return dev_err_probe(dev, -EINVAL,
				     "reset must be RST_CPU0; refusing (RST_CPU1 is the Linux core)\n");
	return 0;
}

static ssize_t cpu0_status_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct k230_cpu0_rproc *priv = dev_get_drvdata(dev);
	u32 vector = readl(priv->vector);
	u32 magic = READ_ONCE(*(u32 *)(priv->carveout + K230_SLOT_OFFSET + K230_SLOT_MAGIC));

	return sysfs_emit(buf,
			  "boot_vector 0x%08x\nreset_status %d\ncarveout %pR\nslot_magic 0x%08x%s\n",
			  vector, priv->reset_status, &priv->carveout_res, magic,
			  magic == K230_ECHO_MAGIC ? " (echo payload)" : "");
}
static DEVICE_ATTR_RO(cpu0_status);

static struct attribute *k230_cpu0_rproc_attrs[] = {
	&dev_attr_cpu0_status.attr,
	NULL
};
ATTRIBUTE_GROUPS(k230_cpu0_rproc);

static int k230_cpu0_rproc_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct k230_cpu0_rproc *priv;
	struct rproc *rproc;
	int ret;

	ret = k230_cpu0_check_reset_spec(dev);
	if (ret)
		return ret;

	rproc = devm_rproc_alloc(dev, "k230-cpu0", &k230_cpu0_rproc_ops, NULL, sizeof(*priv));
	if (!rproc)
		return -ENOMEM;
	rproc->auto_boot = false;
	rproc->sysfs_read_only = true;

	priv = rproc->priv;
	priv->dev = dev;
	platform_set_drvdata(pdev, priv);

	priv->reset = devm_reset_control_get_exclusive(dev, NULL);
	if (IS_ERR(priv->reset))
		return dev_err_probe(dev, PTR_ERR(priv->reset), "cannot get CPU0 reset\n");

	/* Read-only query; reset-k230.c registers no .status, so expect an error. */
	priv->reset_status = reset_control_status(priv->reset);

	priv->vector = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(priv->vector))
		return dev_err_probe(dev, PTR_ERR(priv->vector), "cannot map boot vector\n");

	ret = of_reserved_mem_region_to_resource(dev->of_node, 0, &priv->carveout_res);
	if (ret)
		return dev_err_probe(dev, ret, "no memory-region carveout\n");
	priv->carveout = devm_memremap(dev, priv->carveout_res.start,
				       resource_size(&priv->carveout_res), MEMREMAP_WC);
	if (IS_ERR(priv->carveout))
		return dev_err_probe(dev, PTR_ERR(priv->carveout), "cannot map carveout\n");

	ret = devm_rproc_add(dev, rproc);
	if (ret)
		return dev_err_probe(dev, ret, "rproc_add failed\n");

	dev_info(dev, "CPU0 read-only: vector 0x%08x, reset status %d, carveout %pR\n",
		 readl(priv->vector), priv->reset_status, &priv->carveout_res);
	return 0;
}

static const struct of_device_id k230_cpu0_rproc_of_match[] = {
	{ .compatible = "canaan,k230-cpu0-rproc" },
	{ }
};
MODULE_DEVICE_TABLE(of, k230_cpu0_rproc_of_match);

static struct platform_driver k230_cpu0_rproc_driver = {
	.probe = k230_cpu0_rproc_probe,
	.driver = {
		.name = "k230-cpu0-rproc",
		.of_match_table = k230_cpu0_rproc_of_match,
		.dev_groups = k230_cpu0_rproc_groups,
	},
};
module_platform_driver(k230_cpu0_rproc_driver);

MODULE_DESCRIPTION("Canaan K230 CPU0 remoteproc (read-only skeleton)");
MODULE_LICENSE("GPL");
