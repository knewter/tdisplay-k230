// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Kendryte K230 temperature sensor support driver
 *
 * Copyright (C) 2024, Canaan Bright Sight Co., Ltd
 *
 * openspec/changes/the-mainline-shell-reaches-parity forward-port (task
 * 7.1), from the pinned VENDOR tree's own
 * drivers/thermal/canaan_thermal.c (ruyisdk/linux-xuantie-kernel,
 * grounded against
 * /nix/store/hn11x8zd5linl193d8q0k9k99b46zqbm-linux-xuantie-k230-src).
 * Five changes from that vendor file:
 *
 *   1. canaan_get_temp()'s busy-poll loop is bounded and schedulable, the
 *      same fix nix/kernel.nix already applies by sed to the VENDOR
 *      build (see that file's "Bound the thermal sensor read loop"
 *      comment): "while (1)" with a bare "// msleep(2600);" comment and
 *      no timeout became "while (tries++ < 10000)" with
 *      "usleep_range(100, 200)" between reads and *temp pre-zeroed, so a
 *      sensor that never sets bit 12 reports 0 instead of soft-locking
 *      the CPU reading from a workqueue. Baked directly into this file
 *      rather than sed-applied, since this is a new forward-ported file,
 *      not a copy of the vendor source tree.
 *   2. devm_ioremap_resource(&pdev->dev, res) -> devm_platform_ioremap_
 *      resource(pdev, 0): the two-argument (struct device *, struct
 *      resource *) form of devm_ioremap_resource() this 6.6-era vendor
 *      file used no longer exists in v7.3-rc5 -- checked directly
 *      against include/linux/io.h and include/linux/platform_device.h at
 *      this exact pinned tree, which only declares the platform_device-
 *      taking devm_platform_ioremap_resource()/_byname() helpers. Same
 *      fix already applied by nix/patches/mainline/rtc-k230.c.
 *   3. .remove: int (*)(struct platform_device *) -> void (*)(...),
 *      matching v7.3-rc5's struct platform_driver (checked directly
 *      against include/linux/platform_device.h), the same signature
 *      change nix/patches/mainline/rtc-k230.c already carries.
 *   4. The temperature sensor's own functional clock
 *      (K230_SYSCTL_TEMP_SENSOR_RATE, include/dt-bindings/clock/
 *      canaan,k230-clk.h) is claimed with devm_clk_get_optional_enabled()
 *      as an optional "ts" clock. Mainline's unused-clock cleanup gates
 *      any clock no driver has claimed; nix/patches/mainline/rtc-k230.c
 *      already hit this for the PMU APB gate (see that file's own
 *      comment) and the project lesson is to claim every clock a device
 *      touches rather than relying on the bootloader's enable state.
 *      thermal_zone_device_register_with_trips()/
 *      thermal_tripless_zone_device_register() themselves are unchanged
 *      between the vendor's 6.6-era tree and v7.3-rc5 -- checked directly
 *      against include/linux/thermal.h at this pinned tree -- so no probe
 *      API or struct thermal_zone_device_ops change is needed beyond #4.
 *   5. canaan_get_temp()'s `tz->devdata` -> `thermal_zone_device_priv(tz)`:
 *      struct thermal_zone_device is opaque in v7.3-rc5 (only forward-
 *      declared in include/linux/thermal.h; its real definition moved out
 *      of any installed header), so the vendor's direct field access no
 *      longer compiles ("invalid use of undefined type"). Found by a
 *      failed out-of-tree module build against this exact pinned dev
 *      tree, then fixed with the accessor include/linux/thermal.h itself
 *      declares for this purpose.
 */

#include <linux/clk.h>
#include <linux/cpu_cooling.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/kernel.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_device.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/slab.h>
#include <linux/thermal.h>
#include <linux/types.h>

#define TS_CONFIG 0x00
#define TS_DATA 0x04
#define TS_POWERDOWN 0x22
#define TS_POWERON 0x23

#define TS_READ_MAX_TRIES	10000

struct canaan_thermal_data {
	struct thermal_zone_device *tz;
	void __iomem *base;
	struct clk *clk;
};

static int canaan_get_temp(struct thermal_zone_device *tz, int *temp)
{
	struct canaan_thermal_data *data = thermal_zone_device_priv(tz);
	u32 val = 0;
	int tries = 0;

	*temp = 0;

	iowrite32(TS_POWERDOWN, data->base + TS_CONFIG);
	iowrite32(TS_POWERON, data->base + TS_CONFIG);
	msleep(20);

	/*
	 * Bounded and schedulable: see this file's header comment #1. The
	 * vendor original busy-polled "while (1)" with no timeout, no
	 * iteration cap and a commented-out msleep(2600), which the board
	 * has already been observed to soft-lock on (22s CPU#0 stuck,
	 * kworker reading this thermal zone) when the sensor never sets
	 * bit 12.
	 */
	while (tries++ < TS_READ_MAX_TRIES) {
		val = ioread32(data->base + TS_DATA);
		usleep_range(100, 200);

		if (val >> 12) {
			*temp = val;
			break;
		}
	}

	return 0;
}

static const struct thermal_zone_device_ops canaan_tz_ops = {
	.get_temp = canaan_get_temp,
};

static const struct of_device_id of_canaan_thermal_match[] = {
	{ .compatible = "canaan,k230-tsensor" },
	{ /* end */ }
};
MODULE_DEVICE_TABLE(of, of_canaan_thermal_match);

static int canaan_thermal_probe(struct platform_device *pdev)
{
	struct canaan_thermal_data *data;
	int ret;

	dev_vdbg(&pdev->dev, "[TS]: %s %d\n", __func__, __LINE__);

	data = devm_kzalloc(&pdev->dev, sizeof(*data), GFP_KERNEL);
	if (!data)
		return -ENOMEM;

	/*
	 * Keep the temperature sensor's functional clock on past late
	 * unused-clock cleanup -- same pattern as
	 * nix/patches/mainline/rtc-k230.c's "pclk". Optional so probe still
	 * succeeds if a board DT omits it (console-only profile).
	 */
	data->clk = devm_clk_get_optional_enabled(&pdev->dev, "ts");
	if (IS_ERR(data->clk))
		return dev_err_probe(&pdev->dev, PTR_ERR(data->clk),
				     "failed to enable ts clock\n");

	data->base = devm_platform_ioremap_resource(pdev, 0);
	if (IS_ERR(data->base))
		return PTR_ERR(data->base);

	platform_set_drvdata(pdev, data);

	data->tz = thermal_tripless_zone_device_register(
		"canaan_thermal_zone", data, &canaan_tz_ops, NULL);

	if (IS_ERR(data->tz)) {
		ret = PTR_ERR(data->tz);
		dev_err(&pdev->dev,
			"failed to register thermal zone device %d\n", ret);
		return ret;
	}

	iowrite32(TS_POWERDOWN, data->base + TS_CONFIG);
	iowrite32(TS_POWERON, data->base + TS_CONFIG);
	msleep(20);

	dev_vdbg(&pdev->dev, "[TS]: %s %d\n", __func__, __LINE__);

	return 0;
}

static void canaan_thermal_remove(struct platform_device *pdev)
{
	struct canaan_thermal_data *data = platform_get_drvdata(pdev);

	thermal_zone_device_unregister(data->tz);
}

static struct platform_driver canaan_thermal = {
	.driver = {
		.name = "canaan_thermal",
		.of_match_table = of_canaan_thermal_match,
	},
	.probe = canaan_thermal_probe,
	.remove = canaan_thermal_remove,
};
module_platform_driver(canaan_thermal);

MODULE_DESCRIPTION("Thermal driver for canaan k230 Soc");
MODULE_LICENSE("GPL");
