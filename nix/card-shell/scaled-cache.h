#ifndef CARD_SHELL_SCALED_CACHE_H
#define CARD_SHELL_SCALED_CACHE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Match the pinned wlroots Pixman bilinear, PAD, SRC path for opaque SHM. */
bool card_scale_rgb565(void *dst, size_t dst_stride, int dst_width, int dst_height,
		const void *src, size_t src_stride, int src_width, int src_height, uint32_t src_format);
#endif
