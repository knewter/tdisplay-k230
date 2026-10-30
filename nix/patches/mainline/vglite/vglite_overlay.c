// SPDX-License-Identifier: GPL-2.0
/*
 * Bounded trial helper for the-mainline-kernel-drives-the-vglite-gpu.
 *
 * Applies the embedded device-tree overlay (the same gpu@90800000 node as
 * nix/dts/k230-tdisplay-mainline-drm-common.dtsi) when loaded and removes it
 * when unloaded, so the vglite driver can be probed on a running board
 * without replacing /boot/k230-tdisplay.dtb. Never loaded at boot. Refuses
 * to load when the node already exists in the live tree.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/errno.h>

extern const unsigned char vglite_overlay_dtbo[];
extern const unsigned int vglite_overlay_dtbo_len;

static int ovcs_id = -1;

static int __init vglite_overlay_init(void)
{
	struct device_node *np = of_find_node_by_path("/soc/gpu@90800000");
	int ret;

	if (np) {
		of_node_put(np);
		pr_err("vglite_overlay: /soc/gpu@90800000 already exists; not applying\n");
		return -EEXIST;
	}
	ret = of_overlay_fdt_apply(vglite_overlay_dtbo, vglite_overlay_dtbo_len,
				   &ovcs_id, NULL);
	if (ret) {
		ovcs_id = -1;
		pr_err("vglite_overlay: apply failed: %d\n", ret);
		return ret;
	}
	pr_info("vglite_overlay: applied (id %d)\n", ovcs_id);
	return 0;
}

static void __exit vglite_overlay_exit(void)
{
	if (ovcs_id >= 0)
		of_overlay_remove(&ovcs_id);
	pr_info("vglite_overlay: removed\n");
}

module_init(vglite_overlay_init);
module_exit(vglite_overlay_exit);
MODULE_DESCRIPTION("Trial overlay adding the VG-Lite GPU node at runtime");
MODULE_LICENSE("GPL");
