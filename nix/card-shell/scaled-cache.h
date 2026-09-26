#ifndef CARD_SHELL_SCALED_CACHE_H
#define CARD_SHELL_SCALED_CACHE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Match the pinned wlroots Pixman PAD, SRC path for opaque SHM. `fast`
 * selects PIXMAN_FILTER_NEAREST (cheap, used while the card is actively
 * animating/dragging) over the default PIXMAN_FILTER_BILINEAR (used once
 * settled/at rest); every other caller keeps getting bilinear results
 * unchanged. */
bool card_scale_rgb565(void *dst, size_t dst_stride, int dst_width, int dst_height,
		const void *src, size_t src_stride, int src_width, int src_height, uint32_t src_format,
		bool fast);
#endif
