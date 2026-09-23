#include <assert.h>
#include <drm_fourcc.h>
#include <limits.h>
#include <inttypes.h>
#include <math.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <vg_lite.h>
#include <wlr/render/dmabuf.h>
#include <wlr/render/interface.h>
#include <wlr/render/pixman.h>
#include <wlr/render/vglite.h>
#include <wlr/render/wlr_renderer.h>
#include <wlr/types/wlr_buffer.h>
#include <wlr/util/log.h>
#include "client.h"

/* The vendor library owns one process-global context, including across renderer
 * instances. A failed finish permanently disables it: close is not a reset or a
 * completion guarantee in the pinned SDK. */
static pthread_mutex_t gpu_lock = PTHREAD_MUTEX_INITIALIZER;
static bool gpu_disabled, broker_attempted;
struct vglite_renderer { struct wlr_renderer base; struct wlr_renderer *pixman; };
struct vglite_texture {
	struct wlr_texture base;
	struct wlr_texture *fallback;
	bool cpu_rgb;
};
enum op_kind { OP_RECT, OP_TEXTURE };
struct vglite_op {
	enum op_kind kind;
	struct wlr_render_rect_options rect;
	struct wlr_render_texture_options texture;
	pixman_region32_t clip;
	float alpha, luminance;
	struct wlr_color_primaries primaries;
	bool has_clip, has_primaries, opaque;
	uint8_t *pixels; /* immutable RGBA byte order, also owned through replay */
	uint32_t stride;
};
struct vglite_pass {
	struct wlr_render_pass base;
	struct vglite_renderer *renderer;
	struct wlr_buffer *buffer;
	struct vglite_op *ops;
	size_t len, cap;
	bool gpu_eligible, failed;
	const char *reason;
	size_t reason_op;
	bool has_dmabuf;
	int vg_status;
	struct wlr_dmabuf_attributes target_attributes;
};
static const struct wlr_renderer_impl renderer_impl;
static const struct wlr_texture_impl texture_impl;
static const struct wlr_render_pass_impl pass_impl;

static void finish_op(struct vglite_op *op) {
	if (op->has_clip) pixman_region32_fini(&op->clip);
	if (op->kind == OP_TEXTURE) wlr_texture_destroy(op->texture.texture);
	free(op->pixels);
}
static bool copy_clip(struct vglite_op *op, const pixman_region32_t *src) {
	op->has_clip = src != NULL;
	if (!src) return true;
	pixman_region32_init(&op->clip);
	return pixman_region32_copy(&op->clip, src);
}
static void add_op(struct vglite_pass *p, struct vglite_op *op) {
	if (!p->failed && p->len == p->cap) {
		size_t cap = p->cap ? p->cap * 2 : 16;
		if (cap < p->cap || cap > SIZE_MAX / sizeof(*p->ops)) p->failed = true;
		else {
			void *next = realloc(p->ops, cap * sizeof(*p->ops));
			if (!next) p->failed = true;
			else { p->ops = next; p->cap = cap; }
		}
	}
	if (p->failed) finish_op(op);
	else p->ops[p->len++] = *op;
}
static void reject_gpu(struct vglite_pass *p, const char *reason, size_t op) {
	p->gpu_eligible = false;
	if (!p->reason) { p->reason = reason; p->reason_op = op; }
}
static bool gpu_call(struct vglite_pass *p, vg_lite_error_t status, const char *reason, size_t op) {
	if (status == VG_LITE_SUCCESS) return true;
	if (!p->reason) p->vg_status = status;
	reject_gpu(p, reason, op); return false;
}
/* Fixed schema, no process addresses, fd numbers, client names or content.
 * op=-1 means a pass/target condition rather than an operation condition. */
static void log_decision(struct vglite_pass *p, const char *result) {
	struct wlr_dmabuf_attributes *a = &p->target_attributes;
	wlr_log(WLR_DEBUG, "VG-Lite decision v=1 result=%s reason=%s op=%zd ops=%zu target=%dx%d dmabuf=%d format=0x%08" PRIx32 " modifier=0x%016" PRIx64 " planes=%d stride=%" PRIu32 " offset=%" PRIu32 " vg_status=%d",
		result, p->reason ? p->reason : "eligible", p->reason_op == SIZE_MAX ? (ssize_t)-1 : (ssize_t)p->reason_op,
		p->len, p->buffer->width, p->buffer->height, p->has_dmabuf,
		a->format, a->modifier, a->n_planes, a->stride[0], a->offset[0], p->vg_status);
	if (p->reason_op < p->len) {
		struct vglite_op *op = &p->ops[p->reason_op];
		if (op->kind == OP_TEXTURE) {
			struct wlr_render_texture_options *t = &op->texture;
			wlr_log(WLR_DEBUG, "VG-Lite operation v=1 op=%zu kind=texture alpha=%g opaque=%d blend=%d filter=%d transform=%d transfer=%d primaries=%d luminance=%g encoding=%d range=%d src=%g,%g,%g,%g dst=%d,%d,%d,%d clip_rects=%d",
				p->reason_op, (double)op->alpha, op->opaque, t->blend_mode, t->filter_mode, t->transform,
				t->transfer_function, op->has_primaries, (double)op->luminance, t->color_encoding, t->color_range,
				t->src_box.x,t->src_box.y,t->src_box.width,t->src_box.height,
				t->dst_box.x,t->dst_box.y,t->dst_box.width,t->dst_box.height,
				op->has_clip ? pixman_region32_n_rects(&op->clip) : -1);
		} else wlr_log(WLR_DEBUG, "VG-Lite operation v=1 op=%zu kind=rect alpha=%g blend=%d clip_rects=%d",
			p->reason_op, (double)op->rect.color.a, op->rect.blend_mode,
			op->has_clip ? pixman_region32_n_rects(&op->clip) : -1);
	}
}
static bool valid_color(struct wlr_render_color c) {
	return isfinite(c.a) && c.a >= 0 && c.a <= 1 &&
		isfinite(c.r) && c.r >= 0 && c.r <= c.a &&
		isfinite(c.g) && c.g >= 0 && c.g <= c.a &&
		isfinite(c.b) && c.b >= 0 && c.b <= c.a;
}
static void add_rect(struct wlr_render_pass *base, const struct wlr_render_rect_options *o) {
	struct vglite_pass *p = (struct vglite_pass *)base;
	if (p->failed) return;
	struct vglite_op op = { .kind = OP_RECT, .rect = *o };
	if (!copy_clip(&op, o->clip)) p->failed = true;
	wlr_render_rect_options_get_box(o, p->buffer, &op.rect.box);
	if (!valid_color(o->color) || (o->blend_mode != WLR_RENDER_BLEND_MODE_NONE &&
			o->blend_mode != WLR_RENDER_BLEND_MODE_PREMULTIPLIED)) p->failed = true;
	/* Alpha rectangles remain Pixman until RGB565 blending is board-proved. */
	if (o->color.a != 1) reject_gpu(p, "rect_alpha", p->len);
	add_op(p, &op);
}
/* The pinned scene assigns this exact tuple to ordinary wl_surfaces. On the
 * untransformed RGB565 target, pinned Pixman copies their encoded RGB values
 * unchanged. This admits only that default tuple, not color management. */
static bool default_scene_color(const struct wlr_render_texture_options *o, float luminance) {
	if (o->transfer_function != WLR_COLOR_TRANSFER_FUNCTION_GAMMA22 || !o->primaries || luminance != 1)
		return false;
	struct wlr_color_primaries srgb;
	wlr_color_primaries_from_named(&srgb, WLR_COLOR_NAMED_PRIMARIES_SRGB);
	const struct wlr_color_primaries *p = o->primaries;
	return p->red.x == srgb.red.x && p->red.y == srgb.red.y &&
		p->green.x == srgb.green.x && p->green.y == srgb.green.y &&
		p->blue.x == srgb.blue.x && p->blue.y == srgb.blue.y &&
		p->white.x == srgb.white.x && p->white.y == srgb.white.y;
}
static void add_texture(struct wlr_render_pass *base, const struct wlr_render_texture_options *o) {
	struct vglite_pass *p = (struct vglite_pass *)base;
	if (p->failed) return;
	assert(o->texture->impl == &texture_impl);
	struct vglite_texture *t = (struct vglite_texture *)o->texture;
	struct vglite_op op = { .kind = OP_TEXTURE, .texture = *o,
		.alpha = o->alpha ? *o->alpha : 1,
		.luminance = o->luminance_multiplier ? *o->luminance_multiplier : 1,
		.has_primaries = o->primaries != NULL };
	op.texture.texture = NULL;
	if (o->primaries) op.primaries = *o->primaries;
	if (!copy_clip(&op, o->clip)) p->failed = true;
	/* Neither this renderer nor paired Pixman implements explicit sync. Do not
	 * read a source before its producer's unimplemented wait. */
	if (o->wait_timeline || !isfinite(op.alpha) || op.alpha < 0 || op.alpha > 1 ||
		(o->blend_mode != WLR_RENDER_BLEND_MODE_NONE &&
		 o->blend_mode != WLR_RENDER_BLEND_MODE_PREMULTIPLIED)) p->failed = true;
	uint32_t width = t->base.width, height = t->base.height;
	if (!width || !height || width > INT_MAX / 4 || height > INT_MAX ||
		(size_t)width * 4 > SIZE_MAX / height) p->failed = true;
	if (!p->failed) {
		op.stride = width * 4;
		op.pixels = malloc((size_t)op.stride * height);
		struct wlr_texture_read_pixels_options read = {
			.data = op.pixels, .format = DRM_FORMAT_ABGR8888, .stride = op.stride,
			.src_box = {0, 0, width, height},
		};
		if (!op.pixels || !wlr_texture_read_pixels(t->fallback, &read)) p->failed = true;
	}
	if (!p->failed) {
		op.texture.texture = wlr_texture_from_pixels(p->renderer->pixman,
			DRM_FORMAT_ABGR8888, op.stride, width, height, op.pixels);
		if (!op.texture.texture) p->failed = true;
		op.opaque = true;
		for (size_t i = 3; i < (size_t)op.stride * height; i += 4)
			if (op.pixels[i] != 255) { op.opaque = false; break; }
		wlr_render_texture_options_get_src_box(o, &op.texture.src_box);
		wlr_render_texture_options_get_dst_box(o, &op.texture.dst_box);
		struct wlr_fbox box = op.texture.src_box;
		if (!isfinite(box.x) || !isfinite(box.y) || !isfinite(box.width) || !isfinite(box.height) ||
			box.x < 0 || box.y < 0 || box.width <= 0 || box.height <= 0 ||
			box.x + box.width > width || box.y + box.height > height) p->failed = true;
	}
	if (!t->cpu_rgb) reject_gpu(p, "texture_source", p->len);
	if (o->transform != WL_OUTPUT_TRANSFORM_NORMAL) reject_gpu(p, "texture_transform", p->len);
	if (o->filter_mode != WLR_SCALE_FILTER_NEAREST &&
		!(o->filter_mode == WLR_SCALE_FILTER_BILINEAR && op.texture.src_box.width == op.texture.dst_box.width &&
		  op.texture.src_box.height == op.texture.dst_box.height)) reject_gpu(p, "texture_filter", p->len);
	if (op.alpha != 1) reject_gpu(p, "texture_alpha", p->len);
	if (o->color_encoding != WLR_COLOR_ENCODING_NONE || o->color_range != WLR_COLOR_RANGE_NONE)
		reject_gpu(p, "texture_encoding", p->len);
	bool default_color = default_scene_color(o, op.luminance);
	if (o->transfer_function != 0 && !default_color) reject_gpu(p, "texture_transfer", p->len);
	if (o->primaries && !default_color) reject_gpu(p, "texture_primaries", p->len);
	if (op.luminance != 1) reject_gpu(p, "texture_luminance", p->len);
	/* SRC_OVER on the RGB565 imported target still needs hardware comparison. */
	if (!op.opaque && o->blend_mode != WLR_RENDER_BLEND_MODE_NONE) reject_gpu(p, "texture_blend", p->len);
	add_op(p, &op);
}
static void replay(struct vglite_pass *p, struct wlr_render_pass *dst) {
	for (size_t i = 0; i < p->len; i++) {
		struct vglite_op *op = &p->ops[i];
		if (op->kind == OP_RECT) {
			struct wlr_render_rect_options o = op->rect;
			o.clip = op->has_clip ? &op->clip : NULL;
			wlr_render_pass_add_rect(dst, &o);
		} else {
			struct wlr_render_texture_options o = op->texture;
			o.clip = op->has_clip ? &op->clip : NULL;
			o.alpha = &op->alpha; o.luminance_multiplier = &op->luminance;
			o.primaries = op->has_primaries ? &op->primaries : NULL;
			wlr_render_pass_add_texture(dst, &o);
		}
	}
}
/* Intersection in 64 bits avoids signed overflow from caller coordinates. */
static bool clipped_box(struct wlr_box b, struct wlr_buffer *target, struct wlr_box *out) {
	int64_t x1 = b.x > 0 ? b.x : 0, y1 = b.y > 0 ? b.y : 0;
	int64_t x2 = (int64_t)b.x + b.width, y2 = (int64_t)b.y + b.height;
	if (x2 > target->width) x2 = target->width;
	if (y2 > target->height) y2 = target->height;
	if (x2 <= x1 || y2 <= y1) return false;
	*out = (struct wlr_box){x1, y1, x2 - x1, y2 - y1}; return true;
}
static bool op_region(struct vglite_op *op, struct wlr_buffer *buffer, pixman_region32_t *region) {
	struct wlr_box box = op->kind == OP_RECT ? op->rect.box : op->texture.dst_box;
	pixman_region32_init(region);
	if (!clipped_box(box, buffer, &box)) return true;
	if (!pixman_region32_union_rect(region, region, box.x, box.y, box.width, box.height)) return false;
	return !op->has_clip || pixman_region32_intersect(region, region, &op->clip);
}
static bool gpu_preflight(struct vglite_pass *p) {
	pixman_region32_t coverage; pixman_region32_init(&coverage);
	bool ok = true;
	for (size_t i = 0; ok && i < p->len; i++) {
		struct vglite_op *op = &p->ops[i];
		pixman_region32_t region;
		ok = op_region(op, p->buffer, &region);
		if (ok && op->kind == OP_TEXTURE && pixman_region32_not_empty(&region)) {
			struct wlr_fbox s = op->texture.src_box;
			struct wlr_box d = op->texture.dst_box;
			/* Integer crops and integer upscales have unambiguous nearest samples.
			 * General/downscale fractional rounding remains a Pixman operation. */
			ok = isfinite(s.x) && isfinite(s.y) && isfinite(s.width) && isfinite(s.height) &&
				s.x >= 0 && s.y >= 0 && s.width > 0 && s.height > 0 &&
				s.x == floor(s.x) && s.y == floor(s.y) && s.width == floor(s.width) && s.height == floor(s.height) &&
				s.width <= 16384 && s.height <= 16384 &&
				s.x + s.width <= op->texture.texture->width && s.y + s.height <= op->texture.texture->height &&
				d.x >= 0 && d.y >= 0 && d.width > 0 && d.height > 0 &&
				(int64_t)d.x + d.width <= p->buffer->width && (int64_t)d.y + d.height <= p->buffer->height &&
				fmod(d.width, s.width) == 0 && fmod(d.height, s.height) == 0;
			pixman_box32_t full = {d.x, d.y, (int64_t)d.x + d.width, (int64_t)d.y + d.height};
			if (!ok) reject_gpu(p, "texture_geometry", i);
			if (ok && pixman_region32_contains_rectangle(&region, &full) != PIXMAN_REGION_IN) {
				ok = false; reject_gpu(p, "texture_clip", i);
			}
		}
		/* Every eligible operation is an opaque replacement. Require a complete
		 * redraw so the trial never relies on unproved target preservation. */
		if (ok) ok = pixman_region32_union(&coverage, &coverage, &region);
		pixman_region32_fini(&region);
		if (!ok && !p->reason) reject_gpu(p, "region_allocation", i);
	}
	pixman_box32_t full = {0, 0, p->buffer->width, p->buffer->height};
	if (ok && pixman_region32_contains_rectangle(&coverage, &full) != PIXMAN_REGION_IN) {
		ok = false; reject_gpu(p, "incomplete_coverage", SIZE_MAX);
	}
	pixman_region32_fini(&coverage); return ok;
}
/* Same C908 clean/invalidate sequence as the source-built VG-Lite package.
 * Clean CPU writes before transferring this imported target to the GPU. The
 * SDK finish path handles GPU-to-CPU invalidation; physical correctness is
 * still guarded by the explicitly unproven-cache trial flag. */
static void target_cache_to_gpu(void *memory, size_t bytes) {
#ifdef VGLITE_HOST_TEST
	(void)memory; (void)bytes; /* no cache-coherency claim in the host device */
#elif defined(__riscv)
	register uintptr_t address __asm__("a0") = (uintptr_t)memory;
	int64_t remaining = bytes + address % 64;
	__asm volatile("fence iorw, iorw" ::: "memory");
	while (remaining > 0) {
		__asm volatile(".word 0x0275000b" : "+r"(address) :: "memory");
		address += 64; remaining -= 64;
	}
	__asm volatile(".word 0x0190000b" ::: "memory");
	__asm volatile("fence iorw, iorw" ::: "memory");
	__asm volatile("fence.i" ::: "memory");
#else
#error "The experimental VG-Lite renderer requires the K230 C908 cache contract"
#endif
}
enum gpu_result { GPU_FALLBACK, GPU_OK, GPU_FAILED };
static enum gpu_result gpu_pass(struct vglite_pass *p) {
	p->has_dmabuf = wlr_buffer_get_dmabuf(p->buffer, &p->target_attributes);
	const char *allow = getenv("K230_VGLITE_ALLOW_UNPROVEN_CACHE");
	if (gpu_disabled) { p->reason = "gpu_disabled"; p->reason_op = SIZE_MAX; return GPU_FALLBACK; }
	if (!allow || strcmp(allow, "1")) { p->reason = "opt_in_disabled"; p->reason_op = SIZE_MAX; return GPU_FALLBACK; }
	if (!p->gpu_eligible || !gpu_preflight(p)) return GPU_FALLBACK;
	struct wlr_dmabuf_attributes a = p->target_attributes;
	if (!p->has_dmabuf || a.n_planes != 1 ||
		a.width != p->buffer->width || a.height != p->buffer->height || a.fd[0] < 0 ||
		a.format != DRM_FORMAT_RGB565 || a.modifier != DRM_FORMAT_MOD_LINEAR || a.offset[0] != 0 ||
		a.stride[0] < (uint32_t)p->buffer->width * 2 || a.stride[0] > INT_MAX || a.stride[0] % 64 ||
		(uint64_t)a.stride[0] * p->buffer->height > INT_MAX) {
		reject_gpu(p, "target_attributes", SIZE_MAX); return GPU_FALLBACK;
	}
	vg_lite_buffer_t target = { .width = p->buffer->width, .height = p->buffer->height,
		.stride = a.stride[0], .format = VG_LITE_BGR565 };
	/* Keep every allocation alive until finish, including after an API error.
	 * Source storage is padded to the SDK allocation stride; upload_buffer in
	 * this SDK copies destination stride bytes per row, not the source stride. */
	vg_lite_buffer_t *sources = calloc(p->len, sizeof(*sources));
	if (!sources) { reject_gpu(p, "source_allocation", SIZE_MAX); return GPU_FALLBACK; }
	/* vg_lite_map requires a real CPU mapping even for a dma-buf. Obtain it
	 * from the supplied wlroots buffer and keep that access alive through
	 * completion; never open DRM or invent a placeholder address. */
	uint32_t format; size_t stride;
	if (!wlr_buffer_begin_data_ptr_access(p->buffer,
			WLR_BUFFER_DATA_PTR_ACCESS_READ | WLR_BUFFER_DATA_PTR_ACCESS_WRITE,
			&target.memory, &format, &stride)) { reject_gpu(p, "target_cpu_access", SIZE_MAX); free(sources); return GPU_FALLBACK; }
	if (!target.memory || format != a.format || stride != a.stride[0]) {
		reject_gpu(p, "target_cpu_layout", SIZE_MAX);
		wlr_buffer_end_data_ptr_access(p->buffer); free(sources); return GPU_FALLBACK;
	}
	log_decision(p, "attempt");
	target_cache_to_gpu(target.memory, stride * target.height);
	if (!gpu_call(p, vg_lite_init(target.width, target.height), "gpu_init", SIZE_MAX)) {
		gpu_disabled = true; wlr_buffer_end_data_ptr_access(p->buffer); free(sources); return GPU_FALLBACK;
	}
	bool ok = gpu_call(p, vg_lite_map(&target, VG_LITE_MAP_DMABUF, a.fd[0]), "target_map", SIZE_MAX);
	bool started = false;
	for (size_t i = 0; ok && i < p->len; i++) {
		struct vglite_op *op = &p->ops[i];
		pixman_region32_t region;
		ok = op_region(op, p->buffer, &region);
		if (!ok) reject_gpu(p, "region_allocation", i);
		if (!ok || !pixman_region32_not_empty(&region)) { pixman_region32_fini(&region); continue; }
		if (op->kind == OP_RECT) {
			struct wlr_render_color c = op->rect.color;
			vg_lite_color_t color = 0xff000000 | (((uint32_t)(c.b * 65535) >> 8) << 16) |
				(((uint32_t)(c.g * 65535) >> 8) << 8) | ((uint32_t)(c.r * 65535) >> 8);
			int n; pixman_box32_t *boxes = pixman_region32_rectangles(&region, &n);
			for (int j = 0; ok && j < n; j++) {
				vg_lite_rectangle_t r = {boxes[j].x1, boxes[j].y1, boxes[j].x2 - boxes[j].x1, boxes[j].y2 - boxes[j].y1};
				started = true; ok = gpu_call(p, vg_lite_clear(&target, &r, color), "gpu_clear", i);
			}
		} else {
			vg_lite_buffer_t *s = &sources[i];
			struct wlr_fbox src = op->texture.src_box; struct wlr_box dst = op->texture.dst_box;
			s->width = src.width; s->height = src.height;
			s->format = VG_LITE_RGBA8888;
			ok = gpu_call(p, vg_lite_allocate(s), "gpu_allocate", i);
			if (ok) {
				ok = s->memory && s->stride >= s->width * 4 && s->height == (int)src.height;
				if (!ok) reject_gpu(p, "upload_layout", i);
				if (ok) {
					memset(s->memory, 0, (size_t)s->stride * s->height);
					for (int y = 0; y < s->height; y++) memcpy((uint8_t *)s->memory + (size_t)y * s->stride,
						op->pixels + ((size_t)y + (size_t)src.y) * op->stride + (size_t)src.x * 4, (size_t)s->width * 4);
				}
			}
			if (ok) {
				/* Crop during the CPU upload. Pinned blit() cleans the source cache;
				 * blit_rect() omits that operation. The matrix maps this crop's
				 * local origin to dst, without scaling the destination translation. */
				vg_lite_matrix_t m = {{{dst.width / src.width, 0, dst.x}, {0, dst.height / src.height, dst.y}, {0, 0, 1}}};
				started = true;
				ok = gpu_call(p, vg_lite_blit(&target, s, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "gpu_blit", i);
			}
		}
		pixman_region32_fini(&region);
	}
	/* blit/clear may auto-submit as the command buffer fills, even on error. */
	if (started && !gpu_call(p, vg_lite_finish(), "gpu_finish", SIZE_MAX)) {
		log_decision(p, "failed");
		gpu_disabled = true;
		/* Deliberately quarantine the mapped target, source allocations and its
		 * existing wlr_buffer lock and data access for process lifetime. Neither free, unmap nor
		 * close in this SDK establishes quiescence after a failed finish. */
		p->buffer = NULL;
		wlr_log(WLR_ERROR, "VG-Lite completion failed; target quarantined, GPU disabled; restart session to recover resources");
		return GPU_FAILED;
	}
	for (size_t i = 0; i < p->len; i++) if (sources[i].handle && !gpu_call(p, vg_lite_free(&sources[i]), "gpu_free", i)) ok = false;
	free(sources);
	if (target.handle && !gpu_call(p, vg_lite_unmap(&target), "target_unmap", SIZE_MAX)) ok = false;
	if (!gpu_call(p, vg_lite_close(), "gpu_close", SIZE_MAX)) ok = false;
	wlr_buffer_end_data_ptr_access(p->buffer);
	if (!ok) {
		if (started) log_decision(p, "failed");
		gpu_disabled = true;
		wlr_log(WLR_ERROR, "VG-Lite failure; GPU disabled, frame %s", started ? "discarded" : "replayed with Pixman");
		return started ? GPU_FAILED : GPU_FALLBACK;
	}
	log_decision(p, "gpu");
	wlr_log(WLR_DEBUG, "VG-Lite full frame submitted (%zu operations)", p->len);
	return GPU_OK;
}
static bool submit(struct wlr_render_pass *base) {
	struct vglite_pass *p = (struct vglite_pass *)base; bool ok = false;
	if (!p->failed) {
		pthread_mutex_lock(&gpu_lock);
		enum gpu_result result = gpu_pass(p);
		pthread_mutex_unlock(&gpu_lock);
		if (result == GPU_OK) ok = true;
		else if (result == GPU_FALLBACK) {
			log_decision(p, "pixman");
			struct wlr_render_pass *fallback = wlr_renderer_begin_buffer_pass(p->renderer->pixman, p->buffer, NULL);
			if (fallback) { replay(p, fallback); ok = wlr_render_pass_submit(fallback); }
			wlr_log(WLR_DEBUG, "VG-Lite full pass replayed with Pixman (%zu operations)", p->len);
		}
	}
	for (size_t i = 0; i < p->len; i++) finish_op(&p->ops[i]);
	if (p->buffer) wlr_buffer_unlock(p->buffer);
	free(p->ops); free(p); return ok;
}
static const struct wlr_render_pass_impl pass_impl = { .submit = submit, .add_rect = add_rect, .add_texture = add_texture };
static struct wlr_render_pass *begin(struct wlr_renderer *base, struct wlr_buffer *b, const struct wlr_buffer_pass_options *o) {
	/* Pixman does not implement these contracts either; do not silently drop them. */
	if ((o && (o->color_transform || o->signal_timeline || o->timer)) ||
		b->width <= 0 || b->height <= 0 || b->width > 16384 || b->height > 16384) return NULL;
	struct vglite_pass *p = calloc(1, sizeof(*p)); if (!p) return NULL;
	wlr_render_pass_init(&p->base, &pass_impl);
	p->renderer = (struct vglite_renderer *)base; p->buffer = wlr_buffer_lock(b); p->gpu_eligible = true; p->reason_op = SIZE_MAX;
	return &p->base;
}
static bool cpu_rgb_buffer(struct wlr_buffer *b) {
	struct wlr_dmabuf_attributes a;
	if (wlr_buffer_get_dmabuf(b, &a)) return false;
	void *data; uint32_t format; size_t stride;
	if (!wlr_buffer_begin_data_ptr_access(b, WLR_BUFFER_DATA_PTR_ACCESS_READ, &data, &format, &stride)) return false;
	bool ok = (format == DRM_FORMAT_XRGB8888 || format == DRM_FORMAT_ARGB8888) &&
		b->width > 0 && stride >= (size_t)b->width * 4;
	wlr_buffer_end_data_ptr_access(b); return ok;
}
static void destroy_texture(struct wlr_texture *base) {
	struct vglite_texture *t = (struct vglite_texture *)base;
	wlr_texture_destroy(t->fallback); free(t);
}
static bool update_texture(struct wlr_texture *base, struct wlr_buffer *b, const pixman_region32_t *d) {
	struct vglite_texture *t = (struct vglite_texture *)base;
	if (!wlr_texture_update_from_buffer(t->fallback, b, d)) return false;
	t->cpu_rgb = cpu_rgb_buffer(b); return true;
}
static bool read_texture(struct wlr_texture *b, const struct wlr_texture_read_pixels_options *o) { return wlr_texture_read_pixels(((struct vglite_texture *)b)->fallback, o); }
static uint32_t preferred_texture_format(struct wlr_texture *b) { return wlr_texture_preferred_read_format(((struct vglite_texture *)b)->fallback); }
static const struct wlr_texture_impl texture_impl = { .update_from_buffer = update_texture, .read_pixels = read_texture, .preferred_read_format = preferred_texture_format, .destroy = destroy_texture };
static struct wlr_texture *from_buffer(struct wlr_renderer *base, struct wlr_buffer *b) {
	struct vglite_renderer *r = (struct vglite_renderer *)base;
	struct wlr_texture *fallback = wlr_texture_from_buffer(r->pixman, b); if (!fallback) return NULL;
	struct vglite_texture *t = calloc(1, sizeof(*t)); if (!t) { wlr_texture_destroy(fallback); return NULL; }
	wlr_texture_init(&t->base, base, &texture_impl, fallback->width, fallback->height);
	t->fallback = fallback; t->cpu_rgb = cpu_rgb_buffer(b); return &t->base;
}
static const struct wlr_drm_format_set *texture_formats(struct wlr_renderer *b, uint32_t c) { return wlr_renderer_get_texture_formats(((struct vglite_renderer *)b)->pixman, c); }
static const struct wlr_drm_format_set *render_formats(struct wlr_renderer *b) { return wlr_renderer_get_texture_formats(((struct vglite_renderer *)b)->pixman, WLR_BUFFER_CAP_DATA_PTR); }
static int drm_fd(struct wlr_renderer *b) { return wlr_renderer_get_drm_fd(((struct vglite_renderer *)b)->pixman); }
static void destroy(struct wlr_renderer *b) { struct vglite_renderer *r = (struct vglite_renderer *)b; wlr_renderer_destroy(r->pixman); free(r); }
static const struct wlr_renderer_impl renderer_impl = { .get_texture_formats = texture_formats, .get_render_formats = render_formats, .destroy = destroy, .get_drm_fd = drm_fd, .texture_from_buffer = from_buffer, .begin_buffer_pass = begin };
struct wlr_renderer *wlr_vglite_renderer_create(void) {
	const char *broker = getenv("K230_VGLITE_BROKER");
	const char *allow = getenv("K230_VGLITE_ALLOW_UNPROVEN_CACHE");
	pthread_mutex_lock(&gpu_lock);
	if (broker && allow && strcmp(allow, "1") == 0 && !broker_attempted && !gpu_disabled) {
		broker_attempted = true;
		if (!k230_vglite_broker_acquire(broker)) {
			gpu_disabled = true;
			wlr_log(WLR_ERROR, "VG-Lite broker denied access; retaining Pixman for this process");
		}
	}
	pthread_mutex_unlock(&gpu_lock);
	struct vglite_renderer *r = calloc(1, sizeof(*r)); if (!r) return NULL;
	r->pixman = wlr_pixman_renderer_create(); if (!r->pixman) { free(r); return NULL; }
	wlr_renderer_init(&r->base, &renderer_impl, WLR_BUFFER_CAP_DMABUF | WLR_BUFFER_CAP_DATA_PTR); return &r->base;
}
