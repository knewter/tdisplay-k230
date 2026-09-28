// SPDX-License-Identifier: GPL-2.0-only
/*
 * Kendryte K230 PMU power key input driver
 * Adapted from Xinyuan-LILYGO/T-Display-K230 patch 0064 at
 * commit 9991ebe362bdd0b21f880545ad0c325ff21eedce.
 *
 * The register flow mirrors the RT-Thread PMU pwrkey driver:
 * route PMU KEY_EDGE to CPU IRQ 175, start with rising-edge detection,
 * then toggle to falling-edge detection until the key is released. A long
 * input edges are reported to Linux; userspace owns all display and
 * destructive power policy, including long-hold confirmation.
 */

#include <linux/bits.h>
#include <linux/delay.h>
#include <linux/input.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/ioport.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/notifier.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/workqueue.h>

#define PMU_STATUS				0x3c
#define PMU_INT0_TO_CTL_REGISTER		0x40
#define PMU_INT1_TO_CTL_REGISTER		0x44
#define PMU_INT0_TO_CPU_REGISTER		0x48
#define PMU_INT_DETECT_EN			0x4c
#define PMU_INT_DETECT_TYP			0x50
#define PMU_INT_DETECT_CLR			0x54
#define PMU_INT0_LONG_PRESS_TRIGGER_VAL		0x58
#define PMU_INT0_LEVEL_DEBOUNCE_VAL		0x64
#define PMU_SYSCTRL_REG			0x78
#define PMU_OUT_EVENT_CTRL			0xa4
#define PMU_OUT_LOGIC_CTRL			0xa8
#define PMU_INT_STATE_REG			0xac

#define PWR_PMU_PWR_ISO_CTRL_REG		0x158

#define PMU_SYSCTRL_TO_CTRL_0_REG_O		BIT(0)
#define PMU_SYSCTRL_TO_CTRL_1_REG_O		BIT(1)
#define PMU_OUT_EVENT_TO_CTRL_0_INT_LOGIC	BIT(2)
#define PMU_OUT_EVENT_TO_CTRL_0_INT8		BIT(3)
#define PMU_OUT_EVENT_TO_CTRL_0_SW_REG		BIT(4)
#define PMU_OUT_LOGIC_TO_CTRL_1_LOGIC_AND	BIT(0)
#define PMU_OUT_LOGIC_TO_CTRL_1_INT_LOGIC	BIT(1)
#define PMU_OUT_LOGIC_TO_CTRL_1_INT8		BIT(2)
#define PMU_OUT_LOGIC_TO_CTRL_1_SW_REG		BIT(3)
#define PMU_ISO_ACCESS_MASK			BIT(5)

#define PMU_CPU_IRQ_MASK			0x0fffU
#define PMU_DET_SOURCE_MASK			0x1fffU

#define PMU_IRQ_KEY_LONG			BIT(11)
#define PMU_IRQ_KEY_SHORT			BIT(10)
#define PMU_IRQ_KEY_EDGE			BIT(9)
#define PMU_IRQ_KEY_SHUTDOWN			BIT(0)
#define PMU_IRQ_KEY_MASK			\
	(PMU_IRQ_KEY_LONG | PMU_IRQ_KEY_SHORT | PMU_IRQ_KEY_EDGE | \
	 PMU_IRQ_KEY_SHUTDOWN)

#define PMU_DET_KEY_SHUTDOWN			BIT(12)
#define PMU_DET_KEY_LONG			BIT(11)
#define PMU_DET_KEY_SHORT			BIT(10)
#define PMU_DET_KEY_EDGE			BIT(9)
#define PMU_DET_KEY_MASK			\
	(PMU_DET_KEY_SHUTDOWN | PMU_DET_KEY_LONG | PMU_DET_KEY_SHORT | \
	 PMU_DET_KEY_EDGE)

#define PMU_CLR_KEY_LONG			0x0200U
#define PMU_CLR_KEY_SHUTDOWN			0x0100U
#define PMU_CLR_KEY_SHORT			0x0080U
#define PMU_CLR_KEY_EDGE			0x0040U

#define PMU_INT_TRIGGER_MASK			0x7U
#define PMU_INT_TRIGGER_TYPE_MASK		0x1U
#define PMU_INT_TRIGGER_EDGE_MASK		0x2U
#define PMU_KEY_EDGE_OFFSET			16U

#define PMU_PWRKEY_LONG_PRESS_TICKS		96000U
#define PMU_PWRKEY_DEBOUNCE_TICKS		256U
#define PMU_RUNTIME_CHECK_MS			1000U

struct k230_pmu_pwrkey {
	struct device *dev;
	struct input_dev *input;
	void __iomem *base;
	void __iomem *pwr_base;
	struct delayed_work runtime_check_work;
	spinlock_t lock;
	bool pressed;
	unsigned int keycode;
};

static u32 k230_pmu_readl(struct k230_pmu_pwrkey *pwrkey, u32 reg)
{
	return readl(pwrkey->base + reg);
}

static void k230_pmu_writel(struct k230_pmu_pwrkey *pwrkey, u32 val, u32 reg)
{
	writel(val, pwrkey->base + reg);
}

static u32 k230_pwr_readl(struct k230_pmu_pwrkey *pwrkey, u32 reg)
{
	return readl(pwrkey->pwr_base + reg);
}

static void k230_pwr_writel(struct k230_pmu_pwrkey *pwrkey, u32 val, u32 reg)
{
	writel(val, pwrkey->pwr_base + reg);
}

static int k230_pmu_pwrkey_ensure_access(struct k230_pmu_pwrkey *pwrkey)
{
	u32 val;

	if (!pwrkey->pwr_base)
		return 0;

	val = k230_pwr_readl(pwrkey, PWR_PMU_PWR_ISO_CTRL_REG);
	if (val & PMU_ISO_ACCESS_MASK)
		k230_pwr_writel(pwrkey, val & ~PMU_ISO_ACCESS_MASK,
				PWR_PMU_PWR_ISO_CTRL_REG);

	return 0;
}

static u32 k230_pmu_pwrkey_edge_mode(struct k230_pmu_pwrkey *pwrkey)
{
	return (k230_pmu_readl(pwrkey, PMU_INT_DETECT_TYP) >>
		PMU_KEY_EDGE_OFFSET) & PMU_INT_TRIGGER_MASK;
}

static bool k230_pmu_pwrkey_waits_press_edge(u32 edge_mode)
{
	return edge_mode == PMU_INT_TRIGGER_TYPE_MASK;
}

static bool k230_pmu_pwrkey_waits_release_edge(u32 edge_mode)
{
	return edge_mode ==
	       (PMU_INT_TRIGGER_TYPE_MASK | PMU_INT_TRIGGER_EDGE_MASK);
}

static u32 k230_pmu_edge_rising(u32 offset)
{
	return PMU_INT_TRIGGER_TYPE_MASK << offset;
}

static u32 k230_pmu_edge_falling(u32 offset)
{
	return (PMU_INT_TRIGGER_TYPE_MASK | PMU_INT_TRIGGER_EDGE_MASK) <<
	       offset;
}

static void k230_pmu_pwrkey_set_edge(struct k230_pmu_pwrkey *pwrkey,
				     bool falling)
{
	u32 val;

	val = k230_pmu_readl(pwrkey, PMU_INT_DETECT_TYP);
	val &= ~(PMU_INT_TRIGGER_MASK << PMU_KEY_EDGE_OFFSET);
	val |= falling ? k230_pmu_edge_falling(PMU_KEY_EDGE_OFFSET) :
			 k230_pmu_edge_rising(PMU_KEY_EDGE_OFFSET);
	k230_pmu_writel(pwrkey, val, PMU_INT_DETECT_TYP);
}

static bool k230_pmu_pwrkey_runtime_ok(struct k230_pmu_pwrkey *pwrkey,
				       u32 ctl0, u32 ctl1, u32 cpu_route,
				       u32 detect_en, u32 detect_typ)
{
	unsigned long flags;
	bool pressed;
	u32 edge_mode;

	spin_lock_irqsave(&pwrkey->lock, flags);
	pressed = pwrkey->pressed;
	spin_unlock_irqrestore(&pwrkey->lock, flags);

	edge_mode = (detect_typ >> PMU_KEY_EDGE_OFFSET) &
		    PMU_INT_TRIGGER_MASK;

	if ((ctl0 & PMU_CPU_IRQ_MASK) || (ctl1 & PMU_CPU_IRQ_MASK))
		return false;
	if ((cpu_route & PMU_CPU_IRQ_MASK) != PMU_IRQ_KEY_EDGE)
		return false;
	if ((detect_en & PMU_DET_SOURCE_MASK) != PMU_DET_KEY_EDGE)
		return false;
	if (pressed)
		return k230_pmu_pwrkey_waits_release_edge(edge_mode);

	return k230_pmu_pwrkey_waits_press_edge(edge_mode);
}

static u32 k230_pmu_pwrkey_clear_mask(u32 status)
{
	u32 clear = 0;

	if (status & PMU_IRQ_KEY_LONG)
		clear |= PMU_CLR_KEY_LONG;
	if (status & PMU_IRQ_KEY_SHORT)
		clear |= PMU_CLR_KEY_SHORT;
	if (status & PMU_IRQ_KEY_EDGE)
		clear |= PMU_CLR_KEY_EDGE;
	if (status & PMU_IRQ_KEY_SHUTDOWN)
		clear |= PMU_CLR_KEY_SHUTDOWN;

	return clear;
}

static void k230_pmu_pwrkey_clear_status(struct k230_pmu_pwrkey *pwrkey,
					 u32 status)
{
	u32 clear = k230_pmu_pwrkey_clear_mask(status);

	if (clear)
		k230_pmu_writel(pwrkey, clear, PMU_INT_DETECT_CLR);
}

static void k230_pmu_pwrkey_config_runtime(struct k230_pmu_pwrkey *pwrkey,
					   bool clear_pending)
{
	unsigned long flags;
	bool pressed;
	u32 val;

	k230_pmu_pwrkey_ensure_access(pwrkey);

	val = k230_pmu_readl(pwrkey, PMU_INT0_TO_CTL_REGISTER);
	val &= ~PMU_CPU_IRQ_MASK;
	k230_pmu_writel(pwrkey, val, PMU_INT0_TO_CTL_REGISTER);

	val = k230_pmu_readl(pwrkey, PMU_INT1_TO_CTL_REGISTER);
	val &= ~PMU_CPU_IRQ_MASK;
	k230_pmu_writel(pwrkey, val, PMU_INT1_TO_CTL_REGISTER);

	val = k230_pmu_readl(pwrkey, PMU_INT0_TO_CPU_REGISTER);
	val &= ~PMU_CPU_IRQ_MASK;
	val |= PMU_IRQ_KEY_EDGE;
	k230_pmu_writel(pwrkey, val, PMU_INT0_TO_CPU_REGISTER);

	val = k230_pmu_readl(pwrkey, PMU_INT_DETECT_EN);
	val &= ~PMU_DET_SOURCE_MASK;
	val |= PMU_DET_KEY_EDGE;
	k230_pmu_writel(pwrkey, val, PMU_INT_DETECT_EN);

	spin_lock_irqsave(&pwrkey->lock, flags);
	pressed = pwrkey->pressed;
	spin_unlock_irqrestore(&pwrkey->lock, flags);
	k230_pmu_pwrkey_set_edge(pwrkey, pressed);

	if (clear_pending)
		k230_pmu_pwrkey_clear_status(pwrkey, PMU_IRQ_KEY_MASK);
}

static void k230_pmu_pwrkey_report(struct k230_pmu_pwrkey *pwrkey,
				   bool pressed)
{
	if (pwrkey->pressed == pressed)
		return;

	pwrkey->pressed = pressed;
	input_report_key(pwrkey->input, pwrkey->keycode, pressed);
	input_sync(pwrkey->input);
}

static void k230_pmu_pwrkey_runtime_check_work(struct work_struct *work)
{
	struct delayed_work *dwork = to_delayed_work(work);
	struct k230_pmu_pwrkey *pwrkey =
		container_of(dwork, struct k230_pmu_pwrkey,
			     runtime_check_work);

	u32 ctl0;
	u32 ctl1;
	u32 cpu_route;
	u32 detect_en;
	u32 detect_typ;
	u32 raw_status;

	ctl0 = k230_pmu_readl(pwrkey, PMU_INT0_TO_CTL_REGISTER);
	ctl1 = k230_pmu_readl(pwrkey, PMU_INT1_TO_CTL_REGISTER);
	cpu_route = k230_pmu_readl(pwrkey, PMU_INT0_TO_CPU_REGISTER);
	detect_en = k230_pmu_readl(pwrkey, PMU_INT_DETECT_EN);
	detect_typ = k230_pmu_readl(pwrkey, PMU_INT_DETECT_TYP);
	raw_status = k230_pmu_readl(pwrkey, PMU_INT_STATE_REG);

	if (!k230_pmu_pwrkey_runtime_ok(pwrkey, ctl0, ctl1, cpu_route,
					detect_en, detect_typ)) {
		dev_warn(pwrkey->dev,
			 "PMU runtime config repaired ctl0=0x%08x ctl1=0x%08x cpu=0x%08x en=0x%08x typ=0x%08x state=0x%08x\n",
			 ctl0, ctl1, cpu_route, detect_en, detect_typ,
			 raw_status);
		k230_pmu_pwrkey_config_runtime(pwrkey, true);
	}

	mod_delayed_work(system_wq, &pwrkey->runtime_check_work,
			 msecs_to_jiffies(PMU_RUNTIME_CHECK_MS));
}

static irqreturn_t k230_pmu_pwrkey_irq(int irq, void *dev_id)
{
	struct k230_pmu_pwrkey *pwrkey = dev_id;
	unsigned long flags;
	u32 raw_status;
	u32 cpu_route;
	u32 status;
	u32 clear;
	u32 edge_mode;
	int log_state = -1;

	raw_status = k230_pmu_readl(pwrkey, PMU_INT_STATE_REG);
	cpu_route = k230_pmu_readl(pwrkey, PMU_INT0_TO_CPU_REGISTER) &
		    PMU_CPU_IRQ_MASK;
	status = raw_status & cpu_route & PMU_IRQ_KEY_MASK;
	if (!status)
		return IRQ_NONE;

	clear = k230_pmu_pwrkey_clear_mask(status);
	if (clear)
		k230_pmu_writel(pwrkey, clear, PMU_INT_DETECT_CLR);

	if (!(status & PMU_IRQ_KEY_EDGE)) {
		dev_warn(pwrkey->dev,
			 "PMU non-edge status=0x%08x raw=0x%08x cpu=0x%08x, restoring runtime config\n",
			 status, raw_status, cpu_route);
		k230_pmu_pwrkey_config_runtime(pwrkey, true);
		return IRQ_HANDLED;
	}

	spin_lock_irqsave(&pwrkey->lock, flags);
	edge_mode = k230_pmu_pwrkey_edge_mode(pwrkey);
	if (k230_pmu_pwrkey_waits_press_edge(edge_mode)) {
		k230_pmu_pwrkey_report(pwrkey, true);
		k230_pmu_pwrkey_set_edge(pwrkey, true);
		log_state = 1;
	} else if (k230_pmu_pwrkey_waits_release_edge(edge_mode)) {
		k230_pmu_pwrkey_report(pwrkey, false);
		k230_pmu_pwrkey_set_edge(pwrkey, false);
		log_state = 0;
	} else {
		k230_pmu_pwrkey_report(pwrkey, !pwrkey->pressed);
		k230_pmu_pwrkey_set_edge(pwrkey, pwrkey->pressed);
		log_state = pwrkey->pressed ? 1 : 0;
	}
	spin_unlock_irqrestore(&pwrkey->lock, flags);

	if (log_state >= 0)
		dev_info(pwrkey->dev, "INT0 %s\n",
			 log_state ? "press" : "release");

	return IRQ_HANDLED;
}

static void k230_pmu_pwrkey_init_output_state(struct k230_pmu_pwrkey *pwrkey)
{
	u32 val;

	val = k230_pmu_readl(pwrkey, PMU_OUT_EVENT_CTRL);
	val |= PMU_OUT_EVENT_TO_CTRL_0_INT_LOGIC;
	val |= PMU_OUT_EVENT_TO_CTRL_0_SW_REG;
	val &= ~PMU_OUT_EVENT_TO_CTRL_0_INT8;
	k230_pmu_writel(pwrkey, val, PMU_OUT_EVENT_CTRL);

	val = k230_pmu_readl(pwrkey, PMU_OUT_LOGIC_CTRL);
	val |= PMU_OUT_LOGIC_TO_CTRL_1_INT_LOGIC;
	val |= PMU_OUT_LOGIC_TO_CTRL_1_SW_REG;
	val &= ~PMU_OUT_LOGIC_TO_CTRL_1_INT8;
	val &= ~PMU_OUT_LOGIC_TO_CTRL_1_LOGIC_AND;
	k230_pmu_writel(pwrkey, val, PMU_OUT_LOGIC_CTRL);

	val = k230_pmu_readl(pwrkey, PMU_SYSCTRL_REG);
	val |= PMU_SYSCTRL_TO_CTRL_1_REG_O;
	k230_pmu_writel(pwrkey, val, PMU_SYSCTRL_REG);
}

static void k230_pmu_pwrkey_hw_init(struct k230_pmu_pwrkey *pwrkey)
{
	u32 val;

	k230_pmu_pwrkey_ensure_access(pwrkey);
	k230_pmu_pwrkey_init_output_state(pwrkey);

	k230_pmu_writel(pwrkey, PMU_PWRKEY_LONG_PRESS_TICKS,
			PMU_INT0_LONG_PRESS_TRIGGER_VAL);
	k230_pmu_writel(pwrkey, PMU_PWRKEY_DEBOUNCE_TICKS,
			PMU_INT0_LEVEL_DEBOUNCE_VAL);

	val = k230_pmu_readl(pwrkey, PMU_INT0_TO_CTL_REGISTER);
	val &= ~PMU_IRQ_KEY_MASK;
	k230_pmu_writel(pwrkey, val, PMU_INT0_TO_CTL_REGISTER);

	val = k230_pmu_readl(pwrkey, PMU_INT1_TO_CTL_REGISTER);
	val &= ~PMU_IRQ_KEY_MASK;
	k230_pmu_writel(pwrkey, val, PMU_INT1_TO_CTL_REGISTER);

	val = k230_pmu_readl(pwrkey, PMU_INT0_TO_CPU_REGISTER);
	val &= ~PMU_IRQ_KEY_MASK;
	val |= PMU_IRQ_KEY_EDGE;
	k230_pmu_writel(pwrkey, val, PMU_INT0_TO_CPU_REGISTER);

	val = k230_pmu_readl(pwrkey, PMU_INT_DETECT_EN);
	val &= ~PMU_DET_SOURCE_MASK;
	val |= PMU_DET_KEY_EDGE;
	k230_pmu_writel(pwrkey, val, PMU_INT_DETECT_EN);

	k230_pmu_writel(pwrkey, PMU_CLR_KEY_LONG | PMU_CLR_KEY_SHUTDOWN |
			PMU_CLR_KEY_SHORT | PMU_CLR_KEY_EDGE,
			PMU_INT_DETECT_CLR);
	k230_pmu_pwrkey_config_runtime(pwrkey, false);
	pwrkey->pressed = false;
}

static int k230_pmu_pwrkey_probe(struct platform_device *pdev)
{
	struct k230_pmu_pwrkey *pwrkey;
	struct input_dev *input;
	unsigned int keycode = KEY_POWER;
	struct resource *res;
	struct resource *pwr_res;
	int irq;
	int ret;

	pwrkey = devm_kzalloc(&pdev->dev, sizeof(*pwrkey), GFP_KERNEL);
	if (!pwrkey)
		return -ENOMEM;

	res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!res)
		return -ENODEV;

	/*
	 * PMUIOMUX lives inside the PMU register block on K230 and may already
	 * request a subrange such as 0x91000080. Map the PMU block without
	 * claiming exclusive ownership so the power-key logic can coexist with
	 * the IOMUX driver.
	 */
	pwrkey->base = devm_ioremap(&pdev->dev, res->start,
				    resource_size(res));
	if (!pwrkey->base)
		return -ENOMEM;

	pwr_res = platform_get_resource(pdev, IORESOURCE_MEM, 1);
	if (pwr_res) {
		pwrkey->pwr_base = devm_ioremap(&pdev->dev, pwr_res->start,
						resource_size(pwr_res));
		if (!pwrkey->pwr_base)
			return -ENOMEM;
	}

	irq = platform_get_irq(pdev, 0);
	if (irq < 0)
		return irq;

	of_property_read_u32(pdev->dev.of_node, "linux,code", &keycode);

	input = devm_input_allocate_device(&pdev->dev);
	if (!input)
		return -ENOMEM;

	pwrkey->dev = &pdev->dev;
	pwrkey->input = input;
	pwrkey->keycode = keycode;
	INIT_DELAYED_WORK(&pwrkey->runtime_check_work,
			  k230_pmu_pwrkey_runtime_check_work);
	spin_lock_init(&pwrkey->lock);

	input->name = "K230 PMU Power Key";
	input->phys = "k230-pmu-pwrkey/input0";
	input->id.bustype = BUS_HOST;
	input_set_capability(input, EV_KEY, pwrkey->keycode);

	platform_set_drvdata(pdev, pwrkey);
	k230_pmu_pwrkey_hw_init(pwrkey);

	ret = input_register_device(input);
	if (ret)
		return ret;

	ret = devm_request_irq(&pdev->dev, irq, k230_pmu_pwrkey_irq, 0,
			       dev_name(&pdev->dev), pwrkey);
	if (ret)
		return ret;

	device_init_wakeup(&pdev->dev, true);
	mod_delayed_work(system_wq, &pwrkey->runtime_check_work,
			 msecs_to_jiffies(PMU_RUNTIME_CHECK_MS));
	dev_info(&pdev->dev,
		 "K230 PMU power key input registered on IRQ %d\n", irq);

	return 0;
}

static int k230_pmu_pwrkey_remove(struct platform_device *pdev)
{
	struct k230_pmu_pwrkey *pwrkey = platform_get_drvdata(pdev);

	if (pwrkey->pressed) {
		input_report_key(pwrkey->input, pwrkey->keycode, 0);
		input_sync(pwrkey->input);
	}

	cancel_delayed_work_sync(&pwrkey->runtime_check_work);
	device_init_wakeup(&pdev->dev, false);
	return 0;
}

static const struct of_device_id k230_pmu_pwrkey_of_match[] = {
	{ .compatible = "canaan,k230-pmu-pwrkey" },
	{ }
};
MODULE_DEVICE_TABLE(of, k230_pmu_pwrkey_of_match);

static struct platform_driver k230_pmu_pwrkey_driver = {
	.probe = k230_pmu_pwrkey_probe,
	.remove = k230_pmu_pwrkey_remove,
	.driver = {
		.name = "k230-pmu-pwrkey",
		.of_match_table = k230_pmu_pwrkey_of_match,
	},
};
module_platform_driver(k230_pmu_pwrkey_driver);

MODULE_DESCRIPTION("Kendryte K230 PMU power key input driver");
MODULE_AUTHOR("OpenAI Codex");
MODULE_LICENSE("GPL");
