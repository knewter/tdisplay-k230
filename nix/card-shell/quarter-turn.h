/* Quarter-turn copy for Pixman's software renderer. The source is copied on
 * every use: client SHM may change in place between commits. Scratch storage
 * is reusable, pixels are not cached. Unsupported input retains the sampler. */
#ifndef K230_QUARTER_TURN_H
#define K230_QUARTER_TURN_H
#include <pixman.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

struct k230_turn_scratch { void *data; size_t bytes; };

static inline void k230_turn_finish(struct k230_turn_scratch *scratch) {
	free(scratch->data);
	*scratch = (struct k230_turn_scratch){0};
}

/* transform is wl_output_transform's 90 (1) or 270 (3). Pixman's texture
 * transform maps destination coordinates into source coordinates, so the
 * copied image turns in the inverse direction. */
static inline int k230_turn_cpp(pixman_format_code_t format) {
	switch (format) {
	case PIXMAN_a8r8g8b8: case PIXMAN_x8r8g8b8:
	case PIXMAN_a8b8g8r8: case PIXMAN_x8b8g8r8: return 4;
	case PIXMAN_r5g6b5: case PIXMAN_b5g6r5: return 2;
	default: return 0;
	}
}

/* Copy directly to an already-mapped target; no intermediate second copy.
 * Reject overlap, format mismatch and invalid geometry before writing. */
static inline bool k230_turn_into(pixman_image_t *destination,
		pixman_image_t *source, int transform) {
	if (!source || !destination || (transform != 1 && transform != 3)) return false;
	pixman_format_code_t format = pixman_image_get_format(source);
	int cpp = k230_turn_cpp(format);
	if (!cpp || pixman_image_get_format(destination) != format) return false;
	int width = pixman_image_get_width(source), height = pixman_image_get_height(source);
	int source_stride = pixman_image_get_stride(source);
	int stride = pixman_image_get_stride(destination);
	uint8_t *src = (uint8_t *)pixman_image_get_data(source);
	uint8_t *dst = (uint8_t *)pixman_image_get_data(destination);
	if (!src || !dst || width <= 0 || height <= 0 || width > 16384 || height > 16384 ||
			pixman_image_get_width(destination) != height ||
			pixman_image_get_height(destination) != width ||
			source_stride < width * cpp || stride < height * cpp ||
			source_stride % cpp || stride % cpp || (uintptr_t)src % cpp || (uintptr_t)dst % cpp)
		return false;
	size_t source_bytes = (size_t)source_stride * height, destination_bytes = (size_t)stride * width;
	if (source_bytes > 64u * 1024u * 1024u || destination_bytes > 64u * 1024u * 1024u)
		return false;
	uintptr_t source_address = (uintptr_t)src, destination_address = (uintptr_t)dst;
	if (source_address <= destination_address ? destination_address - source_address < source_bytes :
			source_address - destination_address < destination_bytes) return false;
	/* Tiles keep both the contiguous source rows and transposed destination
	 * rows hot, instead of touching an entire image's cache lines per row. */
	for (int by = 0; by < height; by += 16) {
		int end_y = by + 16 < height ? by + 16 : height;
		for (int bx = 0; bx < width; bx += 16) {
			int end_x = bx + 16 < width ? bx + 16 : width;
			for (int y = by; y < end_y; y++) {
				for (int x = bx; x < end_x; x++) {
					int dx = transform == 1 ? y : height - 1 - y;
					int dy = transform == 1 ? width - 1 - x : x;
					if (cpp == 4)
						*(uint32_t *)(dst + (size_t)dy * stride + dx * 4) =
							*(uint32_t *)(src + (size_t)y * source_stride + x * 4);
					else
						*(uint16_t *)(dst + (size_t)dy * stride + dx * 2) =
							*(uint16_t *)(src + (size_t)y * source_stride + x * 2);
				}
			}
		}
	}
	return true;
}

static inline pixman_image_t *k230_turn_image(struct k230_turn_scratch *scratch,
		pixman_image_t *source, int transform) {
	if (!source || (transform != 1 && transform != 3)) return NULL;
	pixman_format_code_t format = pixman_image_get_format(source);
	int cpp = k230_turn_cpp(format);
	int width = pixman_image_get_width(source), height = pixman_image_get_height(source);
	if (!cpp || width <= 0 || height <= 0 || width > 16384 || height > 16384) return NULL;
	int stride = (height * cpp + 3) & ~3;
	size_t bytes = (size_t)stride * width;
	if (bytes > 64u * 1024u * 1024u) return NULL;
	if (scratch->bytes < bytes) {
		void *data = realloc(scratch->data, bytes);
		if (!data) return NULL;
		scratch->data = data;
		scratch->bytes = bytes;
	}
	pixman_image_t *image = pixman_image_create_bits_no_clear(format, height, width,
		scratch->data, stride);
	if (!image) return NULL;
	if (!k230_turn_into(image, source, transform)) {
		pixman_image_unref(image);
		return NULL;
	}
	return image;
}
#endif
