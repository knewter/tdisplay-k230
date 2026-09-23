#include <assert.h>
#include <drm_fourcc.h>
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

struct vglite_renderer;
struct vglite_texture {
	struct wlr_texture base;
	struct wlr_texture *fallback;
	uint8_t *pixels;
	uint32_t stride;
	/* This is deliberately an opt-in path until the K230 cache/import gate is
	 * measured on the target.  Pixels are normalized to premultiplied RGBA. */
	bool shm_upload_ready;
};
enum op_kind { OP_RECT, OP_TEXTURE };
struct vglite_op {
	enum op_kind kind;
	struct wlr_render_rect_options rect;
	struct wlr_render_texture_options texture;
	pixman_region32_t clip;
	bool has_clip;
};
struct vglite_pass {
	struct wlr_render_pass base;
	struct vglite_renderer *renderer;
	struct wlr_buffer *buffer;
	struct wlr_buffer_pass_options options;
	struct vglite_op *ops;
	size_t len, cap;
	bool gpu_eligible;
};
struct vglite_renderer {
	struct wlr_renderer base;
	struct wlr_renderer *pixman;
	pthread_mutex_t lock;
};

static const struct wlr_renderer_impl renderer_impl;
static const struct wlr_texture_impl texture_impl;
static const struct wlr_render_pass_impl pass_impl;

static struct vglite_renderer *renderer_from_base(struct wlr_renderer *r) {
	return (struct vglite_renderer *)r;
}
static struct vglite_texture *texture_from_base(struct wlr_texture *t) {
	return (struct vglite_texture *)t;
}
static struct vglite_pass *pass_from_base(struct wlr_render_pass *p) {
	return (struct vglite_pass *)p;
}

static bool add_op(struct vglite_pass *p, struct vglite_op *op) {
	if (p->len == p->cap) {
		size_t cap = p->cap ? p->cap * 2 : 16;
		void *next = realloc(p->ops, cap * sizeof(*p->ops));
		if (!next) { p->gpu_eligible = false; return false; }
		p->ops = next; p->cap = cap;
	}
	p->ops[p->len++] = *op;
	return true;
}

static void copy_clip(pixman_region32_t *dst, const pixman_region32_t *src, bool *has) {
	*has = src != NULL;
	if (src) pixman_region32_init(dst), pixman_region32_copy(dst, src);
}

static void add_rect(struct wlr_render_pass *base, const struct wlr_render_rect_options *o) {
	struct vglite_pass *p = pass_from_base(base); struct vglite_op op = { .kind = OP_RECT, .rect = *o };
	copy_clip(&op.clip, o->clip, &op.has_clip);
	if (op.has_clip || o->blend_mode != WLR_RENDER_BLEND_MODE_NONE) p->gpu_eligible = false;
	if (!add_op(p, &op) && op.has_clip) pixman_region32_fini(&op.clip);
}
static void add_texture(struct wlr_render_pass *base, const struct wlr_render_texture_options *o) {
	struct vglite_pass *p = pass_from_base(base); struct vglite_op op = { .kind = OP_TEXTURE, .texture = *o };
	struct vglite_texture *t = texture_from_base(o->texture);
	copy_clip(&op.clip, o->clip, &op.has_clip);
	/* The first GPU texture contract is intentionally narrow: an exact full
	 * SHM upload, normal orientation, opaque copy, and no clip. Everything
	 * else is replayed by Pixman as one complete pass. */
	if (!t->shm_upload_ready || op.has_clip || o->transform != WL_OUTPUT_TRANSFORM_NORMAL ||
		o->blend_mode != WLR_RENDER_BLEND_MODE_NONE || o->filter_mode != WLR_SCALE_FILTER_NEAREST ||
		o->alpha != NULL || o->color_encoding != WLR_COLOR_ENCODING_NONE ||
		o->wait_timeline != NULL)
		p->gpu_eligible = false;
	if (!add_op(p, &op) && op.has_clip) pixman_region32_fini(&op.clip);
}

static void replay(struct vglite_pass *p, struct wlr_render_pass *dst) {
	for (size_t i = 0; i < p->len; i++) {
		struct vglite_op *op = &p->ops[i];
		if (op->kind == OP_RECT) {
			if (op->has_clip) op->rect.clip = &op->clip;
			wlr_render_pass_add_rect(dst, &op->rect);
		} else {
			struct vglite_texture *t = texture_from_base(op->texture.texture);
			if (!t->fallback) continue;
			struct wlr_render_texture_options o = op->texture;
			o.texture = t->fallback; if (op->has_clip) o.clip = &op->clip;
			wlr_render_pass_add_texture(dst, &o);
		}
	}
}

static bool gpu_pass(struct vglite_pass *p) {
	if (!p->gpu_eligible || !getenv("K230_VGLITE_ALLOW_UNPROVEN_CACHE")) return false;
	struct wlr_dmabuf_attributes a = {0};
	if (!wlr_buffer_get_dmabuf(p->buffer, &a) || a.n_planes != 1 ||
		a.format != DRM_FORMAT_RGB565 || a.modifier != DRM_FORMAT_MOD_LINEAR || a.offset[0] != 0)
		return false;
	vg_lite_buffer_t target = {0}; target.width = p->buffer->width; target.height = p->buffer->height;
	target.stride = a.stride[0]; target.format = VG_LITE_BGR565;
	if (vg_lite_init(target.width, target.height) != VG_LITE_SUCCESS) return false;
	bool ok = vg_lite_map(&target, VG_LITE_MAP_DMABUF, a.fd[0]) == VG_LITE_SUCCESS;
	bool submitted = false;
	for (size_t i = 0; ok && i < p->len; i++) {
		if (p->ops[i].kind == OP_RECT) {
			struct wlr_render_rect_options *o = &p->ops[i].rect;
			vg_lite_rectangle_t r = {o->box.x, o->box.y, o->box.width, o->box.height};
			vg_lite_color_t c = ((vg_lite_color_t)(o->color.a * 255.0f) << 24) |
				((vg_lite_color_t)(o->color.b * 255.0f) << 16) |
				((vg_lite_color_t)(o->color.g * 255.0f) << 8) |
				(vg_lite_color_t)(o->color.r * 255.0f);
			submitted = true;
			ok = vg_lite_clear(&target, &r, c) == VG_LITE_SUCCESS;
			continue;
		}
		struct wlr_render_texture_options *o = &p->ops[i].texture;
		struct vglite_texture *t = texture_from_base(o->texture);
		vg_lite_buffer_t source = {0};
		source.width = t->base.width; source.height = t->base.height;
		source.stride = t->stride; source.format = VG_LITE_RGBA8888;
		ok = vg_lite_allocate(&source) == VG_LITE_SUCCESS;
		if (ok) {
			vg_lite_uint8_t *planes[3] = {t->pixels, NULL, NULL};
			vg_lite_uint32_t strides[3] = {t->stride, 0, 0};
			ok = vg_lite_upload_buffer(&source, planes, strides) == VG_LITE_SUCCESS;
		}
		if (ok) {
			struct wlr_fbox src = o->src_box;
			if (src.width <= 0 || src.height <= 0) src = (struct wlr_fbox){0, 0, t->base.width, t->base.height};
			struct wlr_box dst = o->dst_box;
			if (dst.width <= 0 || dst.height <= 0) dst = (struct wlr_box){0, 0, t->base.width, t->base.height};
			vg_lite_matrix_t matrix; vg_lite_identity(&matrix);
			ok = vg_lite_scale((float)dst.width / src.width, (float)dst.height / src.height, &matrix) == VG_LITE_SUCCESS;
			if (ok) ok = vg_lite_translate(dst.x, dst.y, &matrix) == VG_LITE_SUCCESS;
			vg_lite_rectangle_t rect = {src.x, src.y, src.width, src.height};
			if (ok) {
				submitted = true;
				ok = vg_lite_blit_rect(&target, &source, &rect, &matrix, VG_LITE_BLEND_NONE, 0xffffffff, VG_LITE_FILTER_POINT) == VG_LITE_SUCCESS;
			}
		}
		if (source.handle) vg_lite_free(&source);
	}
	if (ok) ok = vg_lite_finish() == VG_LITE_SUCCESS;
	else if (submitted) {
		/* A failed command may already be queued. Drain it before Pixman writes
		 * the same mapped target, otherwise stale GPU work can race the replay. */
		vg_lite_finish();
		wlr_log(WLR_ERROR, "VG-Lite pass failed; drained queued work before Pixman replay");
	}
	if (target.handle) vg_lite_unmap(&target); vg_lite_close();
	return ok;
}

static bool submit(struct wlr_render_pass *base) {
	struct vglite_pass *p = pass_from_base(base); bool ok = false;
	pthread_mutex_lock(&p->renderer->lock);
	ok = gpu_pass(p);
	pthread_mutex_unlock(&p->renderer->lock);
	if (!ok) {
		struct wlr_render_pass *fallback = wlr_renderer_begin_buffer_pass(
			p->renderer->pixman, p->buffer, &p->options);
		if (!fallback) goto out;
		replay(p, fallback); ok = wlr_render_pass_submit(fallback);
	}
out:
	for (size_t i = 0; i < p->len; i++) if (p->ops[i].has_clip) pixman_region32_fini(&p->ops[i].clip);
	free(p->ops); free(p); return ok;
}
static const struct wlr_render_pass_impl pass_impl = { .submit = submit, .add_rect = add_rect, .add_texture = add_texture };

static struct wlr_render_pass *begin(struct wlr_renderer *base, struct wlr_buffer *b, const struct wlr_buffer_pass_options *o) {
	struct vglite_renderer *r = renderer_from_base(base); struct vglite_pass *p = calloc(1, sizeof(*p));
	if (!p) return NULL; wlr_render_pass_init(&p->base, &pass_impl); p->renderer = r; p->buffer = b;
	p->gpu_eligible = o && !o->color_transform && !o->signal_timeline; if (o) p->options = *o; return &p->base;
}
static bool refresh_shm_pixels(struct vglite_texture *t) {
	free(t->pixels); t->pixels = NULL; t->shm_upload_ready = false;
	t->stride = t->base.width * 4;
	if (t->base.width == 0 || t->base.height == 0) return false;
	t->pixels = calloc(t->base.height, t->stride);
	if (!t->pixels) return false;
	struct wlr_texture_read_pixels_options o = {
		.data = t->pixels, .format = DRM_FORMAT_ARGB8888, .stride = t->stride,
		.src_box = {0, 0, t->base.width, t->base.height},
	};
	if (!wlr_texture_read_pixels(t->fallback, &o)) { free(t->pixels); t->pixels = NULL; return false; }
	t->shm_upload_ready = true;
	return true;
}
static void destroy_texture(struct wlr_texture *base) { struct vglite_texture *t = texture_from_base(base); if (t->fallback) wlr_texture_destroy(t->fallback); free(t->pixels); free(t); }
static bool update_texture(struct wlr_texture *base, struct wlr_buffer *b, const pixman_region32_t *d) {
	struct vglite_texture *t = texture_from_base(base);
	if (!wlr_texture_update_from_buffer(t->fallback, b, d)) return false;
	return refresh_shm_pixels(t);
}
static bool read_texture(struct wlr_texture *base, const struct wlr_texture_read_pixels_options *o) { return wlr_texture_read_pixels(texture_from_base(base)->fallback, o); }
static uint32_t preferred_texture_format(struct wlr_texture *base) { return wlr_texture_preferred_read_format(texture_from_base(base)->fallback); }
static const struct wlr_texture_impl texture_impl = { .update_from_buffer = update_texture, .read_pixels = read_texture, .preferred_read_format = preferred_texture_format, .destroy = destroy_texture };
static struct wlr_texture *from_buffer(struct wlr_renderer *base, struct wlr_buffer *b) {
	struct vglite_renderer *r = renderer_from_base(base); struct wlr_texture *fallback = wlr_texture_from_buffer(r->pixman, b); if (!fallback) return NULL;
	struct vglite_texture *t = calloc(1, sizeof(*t)); if (!t) { wlr_texture_destroy(fallback); return NULL; }
	wlr_texture_init(&t->base, base, &texture_impl, fallback->width, fallback->height); t->fallback = fallback;
	refresh_shm_pixels(t); return &t->base;
}
static const struct wlr_drm_format_set *texture_formats(struct wlr_renderer *b, uint32_t c) { return wlr_renderer_get_texture_formats(renderer_from_base(b)->pixman, c); }
static const struct wlr_drm_format_set *render_formats(struct wlr_renderer *b) { return wlr_renderer_get_texture_formats(renderer_from_base(b)->pixman, WLR_BUFFER_CAP_DATA_PTR); }
static int drm_fd(struct wlr_renderer *b) { return wlr_renderer_get_drm_fd(renderer_from_base(b)->pixman); }
static void destroy(struct wlr_renderer *b) { struct vglite_renderer *r = renderer_from_base(b); wlr_renderer_destroy(r->pixman); pthread_mutex_destroy(&r->lock); free(r); }
static const struct wlr_renderer_impl renderer_impl = { .get_texture_formats = texture_formats, .get_render_formats = render_formats, .destroy = destroy, .get_drm_fd = drm_fd, .texture_from_buffer = from_buffer, .begin_buffer_pass = begin };
struct wlr_renderer *wlr_vglite_renderer_create(void) {
	struct vglite_renderer *r = calloc(1, sizeof(*r)); if (!r) return NULL; r->pixman = wlr_pixman_renderer_create(); if (!r->pixman) { free(r); return NULL; }
	pthread_mutex_init(&r->lock, NULL); wlr_renderer_init(&r->base, &renderer_impl, WLR_BUFFER_CAP_DMABUF | WLR_BUFFER_CAP_DATA_PTR); return &r->base;
}
