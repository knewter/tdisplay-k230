// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (C) 2022, Canaan Bright Sight Co., Ltd
 *
 * All enquiries to https://www.canaan-creative.com/
 *
 */

#include <linux/delay.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/errno.h>
#include <linux/fb.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/backlight.h>
#include <linux/of_device.h>
#include <linux/of.h>

#include <linux/gpio/consumer.h>
#include <linux/regulator/consumer.h>

#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>

#include <video/mipi_display.h>
#include <video/of_videomode.h>
#include <video/videomode.h>

#include "../canaan/canaan_dsi.h"

struct canaan_panel_instr {
	char cmd;
	char data;
};

struct canaan_panel_desc {
	const struct canaan_panel_instr *init;
	const size_t init_length;
	//const struct drm_display_mode *mode;
};

struct panel_cmd_header {
	u8 data_type;
	u8 delay;
	u8 payload_length;
} __packed;

struct panel_cmd_desc {
	struct panel_cmd_header header;
	u8 *payload;
};

struct panel_cmd_seq {
	struct panel_cmd_desc *cmds;
	unsigned int cmd_cnt;
};

struct canaan_panel {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi;
	const struct canaan_panel_desc *desc;

	struct regulator *power;
	struct gpio_desc *reset;
	struct gpio_desc *power_on;
	struct videomode vm;
	u32 width_mm;
	u32 height_mm;
	u32 lan_num;
	u32 init_set_v1_flag;
	bool stage1_splash;
	bool prepared;
	bool dsi_command_backlight;
	u32 default_brightness;
	u32 max_brightness;
	struct backlight_device *bl;

	struct panel_cmd_seq *init_seq_v1;
};

static inline struct canaan_panel *
panel_to_canaan_panel(struct drm_panel *panel)
{
	return container_of(panel, struct canaan_panel, panel);
}

static void panel_simple_sleep(unsigned int msec)
{
	if (msec > 20)
		msleep(msec);
	else
		usleep_range(msec * 1000, (msec + 1) * 1000);
}

static int panel_simple_xfer_dsi_cmd_seq(struct canaan_panel *panel,
					 struct panel_cmd_seq *seq)
{
	struct device *dev = panel->panel.dev;
	struct mipi_dsi_device *dsi = panel->dsi;
	unsigned int i;
	int err;

	if (!seq)
		return -EINVAL;

	for (i = 0; i < seq->cmd_cnt; i++) {
		struct panel_cmd_desc *cmd = &seq->cmds[i];

		switch (cmd->header.data_type) {
		case MIPI_DSI_DCS_SHORT_WRITE:
		case MIPI_DSI_DCS_SHORT_WRITE_PARAM:
			err = mipi_dsi_dcs_write_buffer(
				dsi, cmd->payload, cmd->header.payload_length);
			break;
		case MIPI_DSI_DCS_LONG_WRITE:
			err = mipi_dsi_dcs_write_buffer(
				dsi, cmd->payload, cmd->header.payload_length);
			break;
		default:
			return -EINVAL;
		}

		if (err < 0)
			dev_err(dev, "failed to write dcs cmd: %d\n", err);

		if (cmd->header.delay)
			panel_simple_sleep(cmd->header.delay);
	}
	return 0;
}

static int canaan_panel_prepare(struct drm_panel *panel)
{
	struct canaan_panel *p = panel_to_canaan_panel(panel);
	int ret;

	if (p->stage1_splash &&
	    canaan_dsi_stage1_handoff_active(p->dsi)) {
		dev_info(panel->dev, "canaan_panel_prepare: left as stage 1 set it\n");
		p->stage1_splash = false;
		return 0;
	}

	// set power on
	if (p->power_on) {
		gpiod_set_value_cansleep(p->power_on, 1);
		panel_simple_sleep(10);
	}
	// set rst
	if (p->reset) {
		// gpiod_direction_output(p->reset, 1);

		// gpiod_set_value_cansleep(p->reset, 1);
		// panel_simple_sleep(200);
		// gpiod_set_value_cansleep(p->reset, 0);
		// panel_simple_sleep(200);
		// gpiod_set_value_cansleep(p->reset, 1);
		// panel_simple_sleep(200);
	}

	dev_info(panel->dev, "canaan_panel_prepare: entered, init_set_v1_flag=%u\n", p->init_set_v1_flag);
	if (p->reset) {
		ret = gpiod_direction_output(p->reset, 1);
		if (ret) {
			dev_err(panel->dev, "failed to set panel reset output: %d\n", ret);
			return ret;
		}
		gpiod_set_value_cansleep(p->reset, 1);
		panel_simple_sleep(20);
		gpiod_set_value_cansleep(p->reset, 0);
		panel_simple_sleep(20);
		gpiod_set_value_cansleep(p->reset, 1);
		panel_simple_sleep(120);
	}

	if (p->init_set_v1_flag) {
		// config screen
		panel_simple_xfer_dsi_cmd_seq(p, p->init_seq_v1);
	}

	if (p->stage1_splash) {
		dev_warn(panel->dev, "stage 1 splash: mode mismatch; reinitializing panel\n");
		p->stage1_splash = false;
	}

	/*
	 * Ask the panel whether any of that landed.
	 *
	 * The controller reports every DCS write as successful and the screen
	 * stays dark, so "accepted" has told us nothing for six hypotheses
	 * running. RDDID (0x04) returns the manufacturer/version bytes and
	 * RDDPM (0x0A) returns the power mode, whose bit 2 is display-on and
	 * bit 4 is sleep-out -- exactly what the tail of the init sequence
	 * (0x11 then 0x29) is supposed to have set.
	 *
	 * A reply means the panel is alive and listening and the fault is
	 * downstream. A timeout means the sequence never reaches it despite
	 * the controller's success. Diagnostic only: failures are logged and
	 * ignored, never fatal to prepare().
	 */
	if (p->dsi) {
		u8 id[3] = { 0, 0, 0 };
		u8 pm = 0;
		int r;

		r = mipi_dsi_dcs_read(p->dsi, 0x04, id, sizeof(id));
		if (r < 0)
			dev_err(panel->dev, "RDDID (0x04) failed: %d\n", r);
		else
			dev_info(panel->dev,
				 "RDDID (0x04) = %02x %02x %02x (%d bytes)\n",
				 id[0], id[1], id[2], r);

		r = mipi_dsi_dcs_read(p->dsi, 0x0A, &pm, 1);
		if (r < 0)
			dev_err(panel->dev, "RDDPM (0x0A) failed: %d\n", r);
		else
			dev_info(panel->dev,
				 "RDDPM (0x0A) = 0x%02x (sleep_out=%d display_on=%d)\n",
				 pm, (pm >> 4) & 1, (pm >> 2) & 1);
	}

	return 0;
}

static int canaan_panel_enable(struct drm_panel *panel)
{
	struct canaan_panel *p = panel_to_canaan_panel(panel);

	p->prepared = true;

	return 0;
}

static int canaan_panel_disable(struct drm_panel *panel)
{
	struct canaan_panel *p = panel_to_canaan_panel(panel);

	p->prepared = false;

	return 0;
}

static int canaan_panel_unprepare(struct drm_panel *panel)
{
	struct canaan_panel *p = panel_to_canaan_panel(panel);
	// int err = 0;

	if (p->stage1_splash) {
		dev_info(panel->dev, "stage 1 splash: panel disabled before handoff; reinitializing later\n");
		p->stage1_splash = false;
	}

	if (p->power_on)
		gpiod_set_value_cansleep(p->power_on, 0);
	if (p->reset)
		gpiod_set_value_cansleep(p->reset, 0);

	panel_simple_sleep(500);

	return 0;
}

static int canaan_panel_apply_brightness(struct canaan_panel *p, u16 brightness)
{

	u8 val = (u8)brightness;
	int ret;

	dev_info(p->panel.dev, "canaan_panel: DCS write 0x51 (brightness=%u)\n", val);
	ret = mipi_dsi_dcs_write(p->dsi, MIPI_DCS_SET_DISPLAY_BRIGHTNESS, &val, 1);
	dev_info(p->panel.dev, "canaan_panel: DCS write 0x51 returned %d\n", ret);
	if (ret < 0)
		dev_err(p->panel.dev, "failed to set display brightness: %d\n", ret);

	return ret;
}

static int canaan_panel_bl_update_status(struct backlight_device *bl)
{
	struct canaan_panel *p = bl_get_data(bl);
	int ret;

	if (!p->prepared)
		return 0;

	ret = canaan_panel_apply_brightness(p, backlight_get_brightness(bl));
	return ret < 0 ? ret : 0;
}

static const struct backlight_ops canaan_panel_bl_ops = {
	.update_status = canaan_panel_bl_update_status,
};

static int canaan_panel_get_modes(struct drm_panel *panel,
				  struct drm_connector *connector)
{
	struct canaan_panel *ctx = panel_to_canaan_panel(panel);
	struct drm_display_mode *mode;

	mode = drm_mode_create(connector->dev);
	if (!mode) {
		dev_err(panel->dev, "failed to create a new display mode\n");
		return 0;
	}

	drm_display_mode_from_videomode(&ctx->vm, mode);
	mode->width_mm = ctx->width_mm;
	mode->height_mm = ctx->height_mm;
	connector->display_info.width_mm = mode->width_mm;
	connector->display_info.height_mm = mode->height_mm;

	mode->type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED;
	drm_mode_probed_add(connector, mode);

	return 1;
}

static const struct drm_panel_funcs canaan_panel_funcs = {
	.prepare = canaan_panel_prepare,
	.unprepare = canaan_panel_unprepare,
	.enable = canaan_panel_enable,
	.disable = canaan_panel_disable,
	.get_modes = canaan_panel_get_modes,
};

static int panel_simple_parse_cmd_seq(struct device *dev, const u8 *data,
				      int length, struct panel_cmd_seq *seq)
{
	struct panel_cmd_header *header;
	struct panel_cmd_desc *desc;
	char *buf, *d;
	unsigned int i, cnt, len;

	if (!seq)
		return -EINVAL;

	buf = devm_kmemdup(dev, data, length, GFP_KERNEL);
	if (!buf)
		return -ENOMEM;

	d = buf;
	len = length;
	cnt = 0;
	while (len > sizeof(*header)) {
		header = (struct panel_cmd_header *)d;

		d += sizeof(*header);
		len -= sizeof(*header);

		if (header->payload_length > len)
			return -EINVAL;

		d += header->payload_length;
		len -= header->payload_length;
		cnt++;
	}

	if (len)
		return -EINVAL;

	seq->cmd_cnt = cnt;
	seq->cmds = devm_kcalloc(dev, cnt, sizeof(*desc), GFP_KERNEL);
	if (!seq->cmds)
		return -ENOMEM;

	d = buf;
	len = length;
	for (i = 0; i < cnt; i++) {
		header = (struct panel_cmd_header *)d;
		len -= sizeof(*header);
		d += sizeof(*header);

		desc = &seq->cmds[i];
		desc->header = *header;
		desc->payload = d;

		d += header->payload_length;
		len -= header->payload_length;
	}

	return 0;
}

static int canaan_panel_parse_dt(struct canaan_panel *ctx)
{
	struct device *dev = &ctx->dsi->dev;
	struct device_node *np = dev->of_node;
	const void *data;
	int ret, err;
	int len;

	// get display timing
	ret = of_get_videomode(np, &ctx->vm, 0);
	if (ret < 0)
		return ret;

	// get width && heidth
	of_property_read_u32(np, "panel-width-mm", &ctx->width_mm);
	of_property_read_u32(np, "panel-height-mm", &ctx->height_mm);
	of_property_read_u32(np, "panel-dsi-lane", &ctx->lan_num);

	ctx->default_brightness = 254;
	ctx->max_brightness = 255;
	of_property_read_u32(np, "default-brightness", &ctx->default_brightness);
	of_property_read_u32(np, "max-brightness", &ctx->max_brightness);
	ctx->dsi_command_backlight = of_property_read_bool(np, "canaan,dsi-command-backlight");

	// get screen data
	data = of_get_property(np, "panel-init-sequence", &len);
	if (data) {
		ctx->init_seq_v1 = devm_kzalloc(dev, sizeof(*ctx->init_seq_v1),
						GFP_KERNEL);
		if (!ctx->init_seq_v1)
			return -ENOMEM;

		err = panel_simple_parse_cmd_seq(dev, data, len,
						 ctx->init_seq_v1);
		if (err) {
			dev_err(dev, "failed to parse init sequence v1\n");
			return err;
		}
		ctx->init_set_v1_flag = 1;
	}

	return 0;
}

static int canaan_panel_dsi_probe(struct mipi_dsi_device *dsi)
{
	struct canaan_panel *ctx;
	int ret;

	/*
	 * openspec/changes/the-board-runs-a-mainline-kernel forward-port:
	 * drm_panel_init() was replaced upstream, after this file's 6.6-era
	 * origin, by a refcounted allocation model -- devm_drm_panel_alloc()
	 * both allocates *ctx (replacing this devm_kzalloc) and initializes
	 * ctx->panel in one call, so the separate drm_panel_init() call
	 * later in this function is removed, not just renamed. Confirmed
	 * against mainline's own already-migrated panel-ebbg-ft8719.c
	 * (drivers/gpu/drm/panel/), the closest structurally-similar
	 * reference: a mipi_dsi_driver panel with the same
	 * devm_drm_panel_alloc(dev, TYPE, panel, funcs, connector_type)
	 * call shape.
	 */
	ctx = devm_drm_panel_alloc(&dsi->dev, struct canaan_panel, panel,
				   &canaan_panel_funcs, DRM_MODE_CONNECTOR_DSI);
	if (IS_ERR(ctx))
		return PTR_ERR(ctx);

	ctx->init_set_v1_flag = 0;

	mipi_dsi_set_drvdata(dsi, ctx);

	ctx->stage1_splash = of_property_read_bool(of_chosen, "canaan,stage1-splash");

	ctx->reset = devm_gpiod_get(&dsi->dev, "dsi_reset",
				    ctx->stage1_splash ? GPIOD_ASIS : GPIOD_OUT_LOW);
	if (IS_ERR(ctx->reset)) {
		dev_err(&dsi->dev, "Couldn't get our reset GPIO, error: %ld\n",
			PTR_ERR(ctx->reset));
		ctx->reset = NULL;
	} else if (!ctx->stage1_splash) {
		gpiod_direction_output(ctx->reset, 1);
		panel_simple_sleep(200);
		gpiod_set_value_cansleep(ctx->reset, 0);
		panel_simple_sleep(200);
		gpiod_set_value_cansleep(ctx->reset, 1);
	}

	ctx->power_on =
		devm_gpiod_get(&dsi->dev, "backlight_gpio", GPIOD_OUT_LOW);
	if (IS_ERR(ctx->power_on)) {
		dev_err(&dsi->dev,
			"Couldn't get our backlight_gpio GPIO, error: %ld\n",
			PTR_ERR(ctx->power_on));
		ctx->power_on = NULL;
	} else {
		gpiod_direction_output(ctx->power_on, 1);
	}

	ctx->dsi = dsi;
	ctx->desc = of_device_get_match_data(&dsi->dev);

	ret = canaan_panel_parse_dt(ctx);
	if (ret < 0)
		return ret;

	// Panel Device Tree Read..

	dsi->mode_flags = MIPI_DSI_MODE_VIDEO_SYNC_PULSE | MIPI_DSI_MODE_LPM;
	dsi->format = MIPI_DSI_FMT_RGB888;
	dsi->lanes = ctx->lan_num;

	if (ctx->dsi_command_backlight) {
		const struct backlight_properties bl_props = {
			.type = BACKLIGHT_RAW,
			.brightness = ctx->default_brightness,
			.max_brightness = ctx->max_brightness,
		};

		ctx->bl = devm_backlight_device_register(&dsi->dev,
				"canaan-dsi-backlight", &dsi->dev, ctx,
				&canaan_panel_bl_ops, &bl_props);
		if (IS_ERR(ctx->bl)) {
			dev_err(&dsi->dev, "failed to register backlight: %ld\n",
				PTR_ERR(ctx->bl));
			ctx->bl = NULL;
		} else {
			ctx->panel.backlight = ctx->bl;
		}
	}

	drm_panel_add(&ctx->panel);

	ret = mipi_dsi_attach(dsi);
	if (ret)
		drm_panel_remove(&ctx->panel);

	return ret;
}

static void canaan_panel_dsi_remove(struct mipi_dsi_device *dsi)
{
	struct canaan_panel *ctx = mipi_dsi_get_drvdata(dsi);

	mipi_dsi_detach(dsi);
	drm_panel_remove(&ctx->panel);
}

static const struct of_device_id canaan_panel_of_match[] = {
	{
		.compatible = "canaan,universal",
	},
	{}
};
MODULE_DEVICE_TABLE(of, canaan_panel_of_match);

static struct mipi_dsi_driver canaan_panel_driver = {
	.probe		= canaan_panel_dsi_probe,
	.remove		= canaan_panel_dsi_remove,
	.driver = {
		.name		= "canaan-panel-dsi",
		.of_match_table	= canaan_panel_of_match,
	},
};
module_mipi_dsi_driver(canaan_panel_driver);

MODULE_AUTHOR("");
MODULE_DESCRIPTION("Canaan K230 Panel Driver");
MODULE_LICENSE("GPL");
