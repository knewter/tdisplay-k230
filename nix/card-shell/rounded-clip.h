/* Pixman rounded destination clipping. Included by the pinned wlroots
 * Pixman render pass and by the host pixel oracle. No app pixels are copied
 * or modified: the existing texture is composited through four small A8
 * corner masks, with ordinary unmasked draws over the interior. */
#ifndef K230_ROUNDED_CLIP_H
#define K230_ROUNDED_CLIP_H
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <pixman.h>

struct k230_round_box { int x, y, width, height; };
#define K230_ROUND_MAX_RADIUS 256
#define K230_ROUND_CACHE_SLOTS 8
struct k230_round_mask {
	int radius;
	uint16_t alpha;
	uint64_t used;
	uint8_t *data;
	pixman_image_t *image;
};
struct k230_round_cache {
	struct k230_round_mask slots[K230_ROUND_CACHE_SLOTS];
	uint64_t clock;
};
static inline void k230_round_cache_finish(struct k230_round_cache *cache) {
	for (int i = 0; i < K230_ROUND_CACHE_SLOTS; i++) {
		if (cache->slots[i].image) pixman_image_unref(cache->slots[i].image);
		free(cache->slots[i].data);
	}
	*cache = (struct k230_round_cache){0};
}
static inline pixman_image_t *k230_round_mask_get(struct k230_round_cache *cache,
		int radius, uint16_t alpha) {
	struct k230_round_mask *slot = &cache->slots[0];
	for (int i = 0; i < K230_ROUND_CACHE_SLOTS; i++) {
		struct k230_round_mask *candidate = &cache->slots[i];
		if (candidate->image && candidate->radius == radius && candidate->alpha == alpha) {
			candidate->used = ++cache->clock;
			return candidate->image;
		}
		if (candidate->used < slot->used) slot = candidate;
	}
	int stride = radius * 4; /* Four oriented corners in one aligned atlas. */
	uint8_t *data = calloc((size_t)stride, (size_t)radius);
	if (!data) return NULL;
	pixman_image_t *image = pixman_image_create_bits(PIXMAN_a8, stride, radius,
		(uint32_t *)data, stride);
	if (!image) { free(data); return NULL; }
	for (int y = 0; y < radius; y++) {
		for (int x = 0; x < radius; x++) {
			unsigned inside = 0;
			/* Exact integer 4x4 coverage at subpixel centers. */
			for (int sy = 1; sy < 8; sy += 2) for (int sx = 1; sx < 8; sx += 2) {
				int dx = radius * 8 - (x * 8 + sx);
				int dy = radius * 8 - (y * 8 + sy);
				inside += dx * dx + dy * dy <= radius * radius * 64;
			}
			uint8_t a = (uint8_t)((inside * (uint32_t)alpha * 255 + 16u * 65535 / 2) /
				(16u * 65535));
			data[y * stride + x] = a;
			data[y * stride + 2 * radius - 1 - x] = a;
			data[(radius - 1 - y) * stride + 2 * radius + x] = a;
			data[(radius - 1 - y) * stride + 4 * radius - 1 - x] = a;
		}
	}
	if (slot->image) pixman_image_unref(slot->image);
	free(slot->data);
	*slot = (struct k230_round_mask){radius, alpha, ++cache->clock, data, image};
	return image;
}
static inline void k230_round_part(pixman_op_t op, pixman_image_t *source,
		pixman_image_t *mask, pixman_image_t *dest, int sx, int sy,
		struct k230_round_box dst, struct k230_round_box part, int mx, int my) {
	int x = dst.x > part.x ? dst.x : part.x;
	int y = dst.y > part.y ? dst.y : part.y;
	int right = dst.x + dst.width < part.x + part.width ?
		dst.x + dst.width : part.x + part.width;
	int bottom = dst.y + dst.height < part.y + part.height ?
		dst.y + dst.height : part.y + part.height;
	if (right <= x || bottom <= y) return;
	pixman_image_composite32(op, source, mask, dest,
		sx + x - dst.x, sy + y - dst.y,
		mx + x - part.x, my + y - part.y, x, y, right - x, bottom - y);
}
static inline bool k230_round_composite(struct k230_round_cache *cache, pixman_op_t op,
		pixman_image_t *source, pixman_image_t *alpha_mask, pixman_image_t *dest,
		int sx, int sy, struct k230_round_box dst, struct k230_round_box round,
		int radius, uint16_t alpha) {
	if (round.width <= 0 || round.height <= 0) {
		pixman_image_composite32(op, source, alpha_mask, dest, sx, sy, 0, 0,
			dst.x, dst.y, dst.width, dst.height);
		return true;
	}
	if (radius > round.width / 2) radius = round.width / 2;
	if (radius > round.height / 2) radius = round.height / 2;
	if (radius < 0 || radius > K230_ROUND_MAX_RADIUS) return false;
	if (radius == 0) {
		k230_round_part(op, source, alpha_mask, dest, sx, sy, dst, round, 0, 0);
		return true;
	}
	pixman_image_t *corners = k230_round_mask_get(cache, radius, alpha);
	if (!corners) return false;
	/* Three disjoint interior rectangles, then four disjoint corner squares.
	 * The destination's existing damage clip remains active for every draw. */
	struct k230_round_box middle = {round.x, round.y + radius,
		round.width, round.height - 2 * radius};
	struct k230_round_box top = {round.x + radius, round.y,
		round.width - 2 * radius, radius};
	struct k230_round_box bottom = {top.x, round.y + round.height - radius,
		top.width, radius};
	k230_round_part(op, source, alpha_mask, dest, sx, sy, dst, middle, 0, 0);
	k230_round_part(op, source, alpha_mask, dest, sx, sy, dst, top, 0, 0);
	k230_round_part(op, source, alpha_mask, dest, sx, sy, dst, bottom, 0, 0);
	for (int i = 0; i < 4; i++) {
		struct k230_round_box corner = {
			round.x + (i & 1 ? round.width - radius : 0),
			round.y + (i & 2 ? round.height - radius : 0), radius, radius};
		/* OVER is mandatory here even for an opaque source: coverage must
		 * preserve the already-rendered wallpaper, including at alpha zero. */
		k230_round_part(PIXMAN_OP_OVER, source, corners, dest, sx, sy, dst,
			corner, i * radius, 0);
	}
	return true;
}
#endif
