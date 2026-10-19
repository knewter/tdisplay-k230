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
/* Full-precision cache, preserving premultiplied alpha before output rotation. */
bool card_scale_pixels(void *dst, size_t dst_stride, int dst_width, int dst_height,
        uint32_t dst_format, const void *src, size_t src_stride, int src_width,
        int src_height, uint32_t src_format, bool fast);
bool card_cache_logical_output(int transform, bool rotate_once,
        bool software_cursor, bool damage_highlight);
#endif
