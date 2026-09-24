#include "sway/card_shell_scaled_cache.h"
#include <drm_fourcc.h>
#include <limits.h>
#include <pixman.h>

bool card_scale_rgb565(void *dst, size_t dst_stride, int dst_width, int dst_height,
		const void *src, size_t src_stride, int src_width, int src_height, uint32_t src_format) {
	if (!dst || !src || dst_width <= 0 || dst_height <= 0 || src_width <= 0 || src_height <= 0 ||
		(dst_stride & 3) || (src_stride & 3) || dst_stride > INT_MAX || src_stride > INT_MAX ||
		(size_t)dst_width > SIZE_MAX / 2 || dst_stride < (size_t)dst_width * 2 ||
		src_stride < (size_t)src_width * (src_format == DRM_FORMAT_RGB565 ? 2 : 4))
		return false;
	pixman_format_code_t format;
	if (src_format == DRM_FORMAT_XRGB8888)
		format = PIXMAN_x8r8g8b8;
	else if (src_format == DRM_FORMAT_RGB565)
		format = PIXMAN_r5g6b5;
	else
		return false;
	pixman_image_t *source = pixman_image_create_bits(format, src_width, src_height,
		(uint32_t *)src, (int)src_stride);
	pixman_image_t *target = pixman_image_create_bits(PIXMAN_r5g6b5, dst_width, dst_height,
		(uint32_t *)dst, (int)dst_stride);
	if (!source || !target) {
		if (source) pixman_image_unref(source);
		if (target) pixman_image_unref(target);
		return false;
	}
	struct pixman_transform transform;
	pixman_transform_init_identity(&transform);
	pixman_transform_scale(&transform, NULL,
		pixman_double_to_fixed((double)src_width / dst_width),
		pixman_double_to_fixed((double)src_height / dst_height));
	pixman_image_set_transform(source, &transform);
	pixman_image_set_repeat(source, PIXMAN_REPEAT_PAD);
	pixman_image_set_filter(source, PIXMAN_FILTER_BILINEAR, NULL, 0);
	pixman_image_composite32(PIXMAN_OP_SRC, source, NULL, target, 0, 0, 0, 0, 0, 0,
		dst_width, dst_height);
	pixman_image_unref(target);
	pixman_image_unref(source);
	return true;
}
