// SPDX-License-Identifier: GPL-2.0
/*
 * Canaan K230 CPU0 (the small C908 core) as a remote processor.
 *
 * Start path (openspec/changes/the-small-core-runs-as-a-coprocessor task
 * 5.1). remoteproc's standard "start" loads the firmware image as a raw
 * binary at the base of the no-map carveout (it is linked to run there;
 * tools/small-core-echo.ld), writes that base to the CPU0 boot vector and
 * pulses the CPU0 reset with reset_control_reset(). Nothing else is written:
 * no power register and no other reset line. .stop still refuses, because
 * RST_CPU0 has no held reset (task 5.2). Auto-boot stays off; userspace
 * picks the firmware through the standard sysfs files.
 *
 * Until a mailbox exists, the cpu0_echo attribute exercises the echo
 * payload's slot page by polling: writing a value posts one request and
 * waits (bounded) for its response; reading reports the last exchange.
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

#include <linux/delay.h>
#include <linux/firmware.h>
#include <linux/io.h>
#include <linux/ktime.h>
#include <linux/mod_devicetable.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/of_reserved_mem.h>
#include <linux/platform_device.h>
#include <linux/remoteproc.h>
#include <linux/reset.h>

/* include/dt-bindings/reset/canaan,k230-rst.h */
#define K230_RST_CPU0		0

/* Echo/heartbeat slot page, carveout + 0x2000 (tools/small-core-echo.S). */
#define K230_SLOT_OFFSET	0x2000
#define K230_SLOT_SIZE		0x1000
#define K230_SLOT_REQ_SEQ	0x00
#define K230_SLOT_REQ_VALUE	0x04
#define K230_SLOT_MAGIC		0x58
#define K230_SLOT_SERVED	0x5c
#define K230_SLOT_RSP(seq)	(0x100 + 0x40 * ((seq) & 7))
#define K230_ECHO_MAGIC		0x4f484345
#define K230_ECHO_TIMEOUT_US	100000

struct k230_cpu0_rproc {
	struct device *dev;
	struct reset_control *reset;
	void __iomem *vector;
	void *carveout;
	struct resource carveout_res;
	int reset_status;
	struct mutex echo_lock;		/* one request in flight */
	u32 echo_seq;
	char echo_last[160];
};

static u32 *k230_slot(struct k230_cpu0_rproc *priv, unsigned int off)
{
	return priv->carveout + K230_SLOT_OFFSET + off;
}

/*
 * Copy the raw image to the carveout base and clear the slot page, so a
 * magic word seen later was written by this boot of CPU0. The mapping is
 * MEMREMAP_WC (non-cacheable through Svpbmt), and the region is no-map, so
 * CPU1 holds no cached alias of it.
 */
static int k230_cpu0_rproc_load(struct rproc *rproc, const struct firmware *fw)
{
	struct k230_cpu0_rproc *priv = rproc->priv;

	if (fw->size > K230_SLOT_OFFSET) {
		dev_err(&rproc->dev, "image is %zu bytes; the slot page starts at 0x%x\n",
			fw->size, K230_SLOT_OFFSET);
		return -EFBIG;
	}
	memcpy(priv->carveout, fw->data, fw->size);
	memset(priv->carveout + fw->size, 0, K230_SLOT_OFFSET + K230_SLOT_SIZE - fw->size);
	wmb();
	priv->echo_seq = 0;
	return 0;
}

static int k230_cpu0_rproc_start(struct rproc *rproc)
{
	struct k230_cpu0_rproc *priv = rproc->priv;
	u64 entry = priv->carveout_res.start;
	int ret;

	if (upper_32_bits(entry))
		return -ERANGE;

	writel(lower_32_bits(entry), priv->vector);
	if (readl(priv->vector) != lower_32_bits(entry)) {
		dev_err(&rproc->dev, "boot vector did not take 0x%08llx\n", entry);
		return -EIO;
	}
	ret = reset_control_reset(priv->reset);
	if (ret) {
		dev_err(&rproc->dev, "CPU0 reset pulse failed: %d\n", ret);
		return ret;
	}
	dev_info(&rproc->dev, "CPU0 released at 0x%08llx\n", entry);
	return 0;
}

static int k230_cpu0_rproc_stop(struct rproc *rproc)
{
	/* No held reset on RST_CPU0; a cooperative park is task 5.2. */
	return -EOPNOTSUPP;
}

static const struct rproc_ops k230_cpu0_rproc_ops = {
	.load = k230_cpu0_rproc_load,
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
	u32 magic = READ_ONCE(*k230_slot(priv, K230_SLOT_MAGIC));

	return sysfs_emit(buf,
			  "boot_vector 0x%08x\nreset_status %d\ncarveout %pR\nslot_magic 0x%08x%s\nserved %u\n",
			  vector, priv->reset_status, &priv->carveout_res, magic,
			  magic == K230_ECHO_MAGIC ? " (echo payload)" : "",
			  READ_ONCE(*k230_slot(priv, K230_SLOT_SERVED)));
}
static DEVICE_ATTR_RO(cpu0_status);

/* Post one echo request and poll its response line; see tools/small-core-echo.S. */
static ssize_t cpu0_echo_store(struct device *dev, struct device_attribute *attr,
			       const char *buf, size_t count)
{
	struct k230_cpu0_rproc *priv = dev_get_drvdata(dev);
	u32 value, seq, rsp_seq = 0, rsp_value, rsp_inv, rsp_served;
	ktime_t t0;
	s64 us;
	int ret;

	ret = kstrtou32(buf, 0, &value);
	if (ret)
		return ret;

	mutex_lock(&priv->echo_lock);
	if (READ_ONCE(*k230_slot(priv, K230_SLOT_MAGIC)) != K230_ECHO_MAGIC) {
		ret = -ENODEV;
		goto out;
	}
	seq = ++priv->echo_seq;
	if (!seq)
		seq = ++priv->echo_seq;

	WRITE_ONCE(*k230_slot(priv, K230_SLOT_REQ_VALUE), value);
	wmb();
	t0 = ktime_get();
	WRITE_ONCE(*k230_slot(priv, K230_SLOT_REQ_SEQ), seq);
	wmb();

	do {
		rsp_seq = READ_ONCE(*k230_slot(priv, K230_SLOT_RSP(seq)));
		us = ktime_us_delta(ktime_get(), t0);
		if (rsp_seq == seq)
			break;
		usleep_range(10, 50);
	} while (us < K230_ECHO_TIMEOUT_US);

	if (rsp_seq != seq) {
		snprintf(priv->echo_last, sizeof(priv->echo_last),
			 "seq %u value 0x%08x TIMEOUT after %lld us (rsp_seq %u)\n",
			 seq, value, us, rsp_seq);
		ret = -ETIMEDOUT;
		goto out;
	}
	rmb();
	rsp_value = READ_ONCE(*k230_slot(priv, K230_SLOT_RSP(seq) + 4));
	rsp_inv = READ_ONCE(*k230_slot(priv, K230_SLOT_RSP(seq) + 8));
	rsp_served = READ_ONCE(*k230_slot(priv, K230_SLOT_RSP(seq) + 12));
	ret = (rsp_value == value + 1 && rsp_inv == ~value) ? 0 : -EIO;
	snprintf(priv->echo_last, sizeof(priv->echo_last),
		 "seq %u value 0x%08x rsp 0x%08x inv 0x%08x served %u latency_us %lld %s\n",
		 seq, value, rsp_value, rsp_inv, rsp_served, us, ret ? "MISMATCH" : "OK");
out:
	mutex_unlock(&priv->echo_lock);
	return ret ? ret : count;
}

static ssize_t cpu0_echo_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	struct k230_cpu0_rproc *priv = dev_get_drvdata(dev);
	ssize_t n;

	mutex_lock(&priv->echo_lock);
	n = sysfs_emit(buf, "%s", priv->echo_last[0] ? priv->echo_last : "none\n");
	mutex_unlock(&priv->echo_lock);
	return n;
}
static DEVICE_ATTR_RW(cpu0_echo);

static struct attribute *k230_cpu0_rproc_attrs[] = {
	&dev_attr_cpu0_status.attr,
	&dev_attr_cpu0_echo.attr,
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

	priv = rproc->priv;
	priv->dev = dev;
	mutex_init(&priv->echo_lock);
	platform_set_drvdata(pdev, priv);

	priv->reset = devm_reset_control_get_exclusive(dev, NULL);
	if (IS_ERR(priv->reset))
		return dev_err_probe(dev, PTR_ERR(priv->reset), "cannot get CPU0 reset\n");

	/* reset-k230.c registers no .status, so expect an error here. */
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

	dev_info(dev, "CPU0: vector 0x%08x, reset status %d, carveout %pR\n",
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

MODULE_DESCRIPTION("Canaan K230 CPU0 remoteproc");
MODULE_LICENSE("GPL");
