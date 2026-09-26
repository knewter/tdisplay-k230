#include "sway/card_shell_scaled_cache.h"
#include <assert.h>
#include <drm_fourcc.h>
#include <pixman.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void compare(int sw, int sh, int dw, int dh, uint32_t format) {
	uint32_t source[37 * 29];
	uint16_t direct[80 * 64], cached[80 * 64], scaled[60 * 50], previous[60 * 50];
	for (int i = 0; i < sw * sh; i++) source[i] =
		format == DRM_FORMAT_RGB565 ? (uint16_t)(i * 3911) : 0xff000000u | (uint32_t)(i * 109123);
	for (int cycle = 0; cycle < 2; cycle++) {
		memset(direct, 0x5a, sizeof(direct));
		memcpy(cached, direct, sizeof(direct));
		memset(scaled, 0, sizeof(scaled));
		int ss = format == DRM_FORMAT_RGB565 ? sw * 2 : sw * 4;
		assert(card_scale_rgb565(scaled, dw * 2, dw, dh, source, ss, sw, sh, format, false));
		if (cycle) assert(memcmp(previous, scaled, (size_t)dw * dh * 2) != 0);
		else memcpy(previous, scaled, (size_t)dw * dh * 2);
		pixman_format_code_t sf = format == DRM_FORMAT_RGB565 ? PIXMAN_r5g6b5 : PIXMAN_x8r8g8b8;
		pixman_image_t *src = pixman_image_create_bits(sf, sw, sh, source, ss);
		pixman_image_t *out = pixman_image_create_bits(PIXMAN_r5g6b5, 80, 64, (uint32_t *)direct, 160);
		pixman_image_t *cache = pixman_image_create_bits(PIXMAN_r5g6b5, dw, dh, (uint32_t *)scaled, dw * 2);
		pixman_image_t *out2 = pixman_image_create_bits(PIXMAN_r5g6b5, 80, 64, (uint32_t *)cached, 160);
		struct pixman_transform transform;
		pixman_transform_init_identity(&transform);
		pixman_transform_scale(&transform, NULL, pixman_double_to_fixed((double)sw / dw),
			pixman_double_to_fixed((double)sh / dh));
		pixman_image_set_transform(src, &transform);
		pixman_image_set_repeat(src, PIXMAN_REPEAT_PAD);
		pixman_image_set_filter(src, PIXMAN_FILTER_BILINEAR, NULL, 0);
		pixman_image_composite32(PIXMAN_OP_SRC, src, NULL, out, 0, 0, 0, 0, 7, 11, dw, dh);
		pixman_image_composite32(PIXMAN_OP_SRC, cache, NULL, out2, 0, 0, 0, 0, 7, 11, dw, dh);
		assert(memcmp(direct, cached, sizeof(direct)) == 0);
		pixman_image_unref(out2); pixman_image_unref(cache);
		pixman_image_unref(out); pixman_image_unref(src);
		/* Same source allocation and SHM identity, different committed pixels. */
		for (int i = 0; i < sw * sh; i++) source[i] ^= 0x001f03e0u;
	}
}
int main(void) {
	compare(37, 29, 18, 14, DRM_FORMAT_XRGB8888);
	compare(37, 29, 56, 43, DRM_FORMAT_XRGB8888);
	compare(36, 28, 18, 14, DRM_FORMAT_RGB565);
	uint32_t source[4] = {0}; uint16_t dest[4] = {0};
	assert(!card_scale_rgb565(dest, 4, 2, 2, source, 8, 2, 2, DRM_FORMAT_ARGB8888, false));
	/* fast=true selects nearest-neighbor, a genuinely different filter from
	 * the default bilinear -- the two must disagree on at least one pixel
	 * for a non-integer downscale ratio (used while a card is animating). */
	{
		uint32_t src2[37 * 29];
		for (int i = 0; i < 37 * 29; i++) src2[i] = 0xff000000u | (uint32_t)(i * 109123);
		uint16_t bilinear[18 * 14], nearest[18 * 14];
		assert(card_scale_rgb565(bilinear, 18 * 2, 18, 14, src2, 37 * 4, 37, 29,
			DRM_FORMAT_XRGB8888, false));
		assert(card_scale_rgb565(nearest, 18 * 2, 18, 14, src2, 37 * 4, 37, 29,
			DRM_FORMAT_XRGB8888, true));
		assert(memcmp(bilinear, nearest, sizeof(bilinear)) != 0);
	}
	puts("PASS scaled opaque RGB565 pixels and reused SHM contents");
}
