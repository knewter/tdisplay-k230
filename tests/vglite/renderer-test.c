/* Host contract tests: compile the production renderer and pinned wlroots
 * Pixman pass. VG-Lite is an asynchronous, failure-injectable software device.
 * This tests command ownership/geometry, not physical GPU fidelity or caches. */
#include <assert.h>
#include <stdlib.h>
#include <stdarg.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/wait.h>
#include <render/pixman.h>
#include <render/color.h>
#include <vg_lite.h>

static int fail_alloc, fail_clip;
static void *test_malloc(size_t n) { if (fail_alloc && !--fail_alloc) return NULL; return malloc(n); }
static void *test_calloc(size_t n, size_t s) { if (fail_alloc && !--fail_alloc) return NULL; return calloc(n, s); }
static void *test_realloc(void *p, size_t n) { if (fail_alloc && !--fail_alloc) return NULL; return realloc(p, n); }
static pixman_bool_t test_copy(pixman_region32_t *d, const pixman_region32_t *s) {
	if (fail_clip) { fail_clip = 0; return false; } return pixman_region32_copy(d, s);
}
#define malloc test_malloc
#define calloc test_calloc
#define realloc test_realloc
#define pixman_region32_copy test_copy
#define VGLITE_HOST_TEST
#include "../../nix/wlroots-vglite/renderer.c"
#undef malloc
#undef calloc
#undef realloc
#undef pixman_region32_copy

static unsigned broker_calls;
bool k230_vglite_broker_acquire(const char *path) { assert(strcmp(path, "/test/broker") == 0); broker_calls++; return false; }

struct test_buffer {
	struct wlr_buffer base;
	struct wlr_dmabuf_attributes attr;
	uint8_t *data;
	uint32_t format, stride;
	bool dmabuf, accessing;
	struct wlr_pixman_buffer pixman;
};
static struct test_buffer *mapped;
static int gpu_init_calls, gpu_commands, gpu_finishes, gpu_frees, gpu_closes, pixman_passes;
static int fail_init, fail_map, fail_allocate, fail_command, fail_finish;
struct command { vg_lite_buffer_t *source; vg_lite_rectangle_t rect; vg_lite_matrix_t matrix; uint32_t color; };
static struct command queue[128];
static size_t queued;

static char decision_log[1024], operation_log[1024];
static char cost_log[2048];
static unsigned cost_logs;
static unsigned attempt_logs;
void _wlr_log(enum wlr_log_importance verbosity, const char *fmt, ...) {
	(void)verbosity;
	char message[2048]; va_list args; va_start(args, fmt);
	vsnprintf(message, sizeof(message), fmt, args); va_end(args);
	const char *decision = strstr(message, "VG-Lite decision ");
	if (decision) {
		assert(strlen(decision) < sizeof(decision_log)); strcpy(decision_log, decision);
		if (strstr(decision, "result=attempt ")) attempt_logs++;
	}
	const char *operation = strstr(message, "VG-Lite operation ");
	if (operation) { assert(strlen(operation) < sizeof(operation_log)); strcpy(operation_log, operation); }
	const char *cost = strstr(message, "VG-Lite cost ");
	if (cost) { assert(strlen(cost) < sizeof(cost_log)); strcpy(cost_log, cost); cost_logs++; }
}
void wlr_renderer_init(struct wlr_renderer *r, const struct wlr_renderer_impl *impl, uint32_t caps) { r->WLR_PRIVATE.impl = impl; r->render_buffer_caps = caps; }
struct wlr_buffer *wlr_buffer_lock(struct wlr_buffer *b) { b->n_locks++; return b; }
void wlr_buffer_unlock(struct wlr_buffer *b) { assert(b->n_locks); b->n_locks--; }
bool wlr_buffer_get_dmabuf(struct wlr_buffer *b, struct wlr_dmabuf_attributes *a) {
	struct test_buffer *t = (struct test_buffer *)b; if (!t->dmabuf) return false;
	*a = t->attr; mapped = t; return true;
}
bool wlr_buffer_begin_data_ptr_access(struct wlr_buffer *b, uint32_t flags, void **data, uint32_t *fmt, size_t *stride) {
	(void)flags; struct test_buffer *t = (struct test_buffer *)b;
	assert(!t->accessing); t->accessing = true;
	*data = t->data; *fmt = t->format; *stride = t->stride; return true;
}
void wlr_buffer_end_data_ptr_access(struct wlr_buffer *b) { struct test_buffer *t=(struct test_buffer *)b; assert(t->accessing); t->accessing=false; }
bool begin_pixman_data_ptr_access(struct wlr_buffer *b, pixman_image_t **image, uint32_t flags) {
	assert(*image); void *data; uint32_t format; size_t stride;
	return wlr_buffer_begin_data_ptr_access(b, flags, &data, &format, &stride);
}
static pixman_format_code_t pixel_format(uint32_t f) {
	switch (f) {
	case DRM_FORMAT_RGB565: return PIXMAN_r5g6b5;
	case DRM_FORMAT_ARGB8888: return PIXMAN_a8r8g8b8;
	case DRM_FORMAT_XRGB8888: return PIXMAN_x8r8g8b8;
	case DRM_FORMAT_ABGR8888: return PIXMAN_a8b8g8r8;
	default: abort();
	}
}
static void pixtex_destroy(struct wlr_texture *b) {
	struct wlr_pixman_texture *t = (struct wlr_pixman_texture *)b;
	pixman_image_unref(t->image); free(t->data); free(t);
}
static bool pixtex_read(struct wlr_texture *b, const struct wlr_texture_read_pixels_options *o) {
	struct wlr_pixman_texture *t = (struct wlr_pixman_texture *)b;
	pixman_image_t *dst = pixman_image_create_bits(pixel_format(o->format), o->src_box.width, o->src_box.height, o->data, o->stride);
	assert(dst); pixman_image_composite32(PIXMAN_OP_SRC, t->image, NULL, dst,
		o->src_box.x, o->src_box.y, 0, 0, 0, 0, o->src_box.width, o->src_box.height);
	pixman_image_unref(dst); return true;
}
static const struct wlr_texture_impl pixtex_impl = { .destroy = pixtex_destroy, .read_pixels = pixtex_read };
bool wlr_texture_is_pixman(struct wlr_texture *b) { return b->impl == &pixtex_impl; }
void wlr_texture_init(struct wlr_texture *b, struct wlr_renderer *r, const struct wlr_texture_impl *impl, uint32_t w, uint32_t h) {
	*b = (struct wlr_texture){.renderer=r, .impl=impl, .width=w, .height=h};
}
struct wlr_texture *wlr_texture_from_pixels(struct wlr_renderer *r, uint32_t fmt, uint32_t stride, uint32_t w, uint32_t h, const void *data) {
	struct wlr_pixman_texture *t = calloc(1, sizeof(*t)); assert(t);
	wlr_texture_init(&t->wlr_texture, r, &pixtex_impl, w, h);
	t->data = malloc((size_t)stride * h); assert(t->data); memcpy(t->data, data, (size_t)stride * h);
	t->image = pixman_image_create_bits(pixel_format(fmt), w, h, t->data, stride); assert(t->image);
	return &t->wlr_texture;
}
struct wlr_texture *wlr_texture_from_buffer(struct wlr_renderer *r, struct wlr_buffer *b) {
	if (r->WLR_PRIVATE.impl == &renderer_impl) return from_buffer(r, b);
	struct test_buffer *t = (struct test_buffer *)b;
	return wlr_texture_from_pixels(r, t->format, t->stride, b->width, b->height, t->data);
}
void wlr_texture_destroy(struct wlr_texture *t) { if (t) t->impl->destroy(t); }
bool wlr_texture_read_pixels(struct wlr_texture *t, const struct wlr_texture_read_pixels_options *o) { return t->impl->read_pixels(t, o); }
uint32_t wlr_texture_preferred_read_format(struct wlr_texture *t) { (void)t; return DRM_FORMAT_ARGB8888; }
bool wlr_texture_update_from_buffer(struct wlr_texture *t, struct wlr_buffer *b, const pixman_region32_t *damage) {
	(void)damage; struct test_buffer *buffer = (struct test_buffer *)b;
	if (t->impl == &texture_impl) return update_texture(t, b, damage);
	struct wlr_pixman_texture *p = (struct wlr_pixman_texture *)t;
	memcpy(p->data, buffer->data, (size_t)buffer->stride * b->height); return true;
}
struct wlr_renderer *wlr_pixman_renderer_create(void) { return calloc(1, sizeof(struct wlr_renderer)); }
void wlr_renderer_destroy(struct wlr_renderer *r) { if (r->WLR_PRIVATE.impl) r->WLR_PRIVATE.impl->destroy(r); else free(r); }
const struct wlr_drm_format_set *wlr_renderer_get_texture_formats(struct wlr_renderer *r, uint32_t c) { (void)r; (void)c; return NULL; }
int wlr_renderer_get_drm_fd(struct wlr_renderer *r) { (void)r; return -1; }
struct wlr_render_pass *wlr_renderer_begin_buffer_pass(struct wlr_renderer *r, struct wlr_buffer *b, const struct wlr_buffer_pass_options *o) {
	if (r->WLR_PRIVATE.impl == &renderer_impl) return begin(r, b, o);
	pixman_passes++; return &begin_pixman_render_pass(&((struct test_buffer *)b)->pixman)->base;
}
vg_lite_error_t vg_lite_init(vg_lite_int32_t w, vg_lite_int32_t h) { assert(w>0 && h>0); gpu_init_calls++; return fail_init ? VG_LITE_GENERIC_IO : VG_LITE_SUCCESS; }
vg_lite_error_t vg_lite_map(vg_lite_buffer_t *b, vg_lite_map_flag_t f, vg_lite_int32_t fd) {
	assert(f == VG_LITE_MAP_DMABUF && fd == 17 && b->memory == mapped->data); if (fail_map) return VG_LITE_GENERIC_IO;
	b->handle = mapped; b->memory = mapped->data; return VG_LITE_SUCCESS;
}
vg_lite_error_t vg_lite_unmap(vg_lite_buffer_t *b) { assert(!queued && b->handle); b->handle = NULL; return VG_LITE_SUCCESS; }
vg_lite_error_t vg_lite_close(void) { assert(!queued); gpu_closes++; return VG_LITE_SUCCESS; }
vg_lite_error_t vg_lite_allocate(vg_lite_buffer_t *b) {
	if (fail_allocate && !--fail_allocate) return VG_LITE_OUT_OF_MEMORY;
	assert(b->format == VG_LITE_BGR565);
	b->stride = (b->width * 2 + 63) & ~63; b->memory = calloc(b->height, b->stride); assert(b->memory); b->handle = b->memory; return VG_LITE_SUCCESS;
}
vg_lite_error_t vg_lite_free(vg_lite_buffer_t *b) { assert(!queued); gpu_frees++; free(b->memory); b->handle = NULL; return VG_LITE_SUCCESS; }
vg_lite_error_t vg_lite_clear(vg_lite_buffer_t *b, vg_lite_rectangle_t *r, vg_lite_color_t c) {
	assert(b->format == VG_LITE_BGR565 && queued < 128);
	queue[queued++] = (struct command){.rect=*r, .color=c}; gpu_commands++;
	return fail_command == gpu_commands ? VG_LITE_GENERIC_IO : VG_LITE_SUCCESS;
}
vg_lite_error_t vg_lite_blit(vg_lite_buffer_t *d, vg_lite_buffer_t *s, vg_lite_matrix_t *m, vg_lite_blend_t blend, vg_lite_color_t c, vg_lite_filter_t f) {
	(void)c; assert(d->format == VG_LITE_BGR565 && s->format == VG_LITE_BGR565);
	assert(blend == VG_LITE_BLEND_NONE && f == VG_LITE_FILTER_POINT && queued < 128);
	queue[queued++] = (struct command){.source=s, .matrix=*m}; gpu_commands++;
	return fail_command == gpu_commands ? VG_LITE_GENERIC_IO : VG_LITE_SUCCESS;
}
static uint16_t rgb565(unsigned r, unsigned g, unsigned b) { return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3); }
vg_lite_error_t vg_lite_finish(void) {
	gpu_finishes++; if (fail_finish) return VG_LITE_TIMEOUT;
	for (size_t i=0; i<queued; i++) {
		struct command *c=&queue[i];
		int x=c->rect.x, y=c->rect.y, w=c->rect.width, h=c->rect.height;
		if (c->source) { x=c->matrix.m[0][2]; y=c->matrix.m[1][2]; w=c->source->width*c->matrix.m[0][0]; h=c->source->height*c->matrix.m[1][1]; }
		for (int row=0; row<h; row++) for (int col=0; col<w; col++) {
			uint32_t v=c->color;
			uint16_t pixel=rgb565(v&255, (v>>8)&255, (v>>16)&255);
			if (c->source) {
				int sx=floor((col+0.5)/c->matrix.m[0][0]), sy=floor((row+0.5)/c->matrix.m[1][1]);
				memcpy(&pixel, (uint8_t *)c->source->memory+(size_t)sy*c->source->stride+sx*2, 2);
			}
			memcpy(mapped->data+(size_t)(y+row)*mapped->stride+(x+col)*2, &pixel, 2);
		}
	}
	queued=0; return VG_LITE_SUCCESS;
}
static void buffer_init(struct test_buffer *b, int w, int h, uint32_t format, bool dmabuf) {
	*b=(struct test_buffer){.base={.width=w,.height=h},.format=format,.dmabuf=dmabuf};
	b->stride = ((w*(format==DRM_FORMAT_RGB565?2:4))+63)&~63;
	b->data=malloc((size_t)b->stride*h); assert(b->data); memset(b->data, 0x57, (size_t)b->stride*h);
	b->attr=(struct wlr_dmabuf_attributes){.width=w,.height=h,.format=format,.modifier=DRM_FORMAT_MOD_LINEAR,.n_planes=1,.fd={17},.stride={b->stride}};
	b->pixman.buffer=&b->base;
	b->pixman.image=pixman_image_create_bits(pixel_format(format), w,h,(uint32_t *)b->data,b->stride); assert(b->pixman.image);
}
static void buffer_finish(struct test_buffer *b) { assert(!b->base.n_locks && !b->accessing); pixman_image_unref(b->pixman.image); free(b->data); }
static void reset_gpu(void) {
	assert(!queued); gpu_disabled=false; broker_attempted=false; broker_calls=0; unsetenv("K230_VGLITE_BROKER"); attempt_logs=0; decision_log[0]=operation_log[0]=0; gpu_init_calls=gpu_commands=gpu_finishes=gpu_frees=gpu_closes=pixman_passes=0;
	fail_init=fail_map=fail_allocate=fail_command=fail_finish=fail_alloc=fail_clip=0;
	setenv("K230_VGLITE_ALLOW_UNPROVEN_CACHE","1",1);
}
static struct wlr_render_rect_options bg = {.color={.r=.25,.g=.75,.b=.5,.a=1}};
static void assert_same(struct test_buffer *a, struct test_buffer *b) {
	assert(a->stride==b->stride); if (memcmp(a->data,b->data,(size_t)a->stride*a->base.height)) {
		for (int y=0;y<a->base.height;y++) for(int x=0;x<a->base.width;x++) {
			uint16_t av,bv; memcpy(&av,a->data+y*a->stride+x*2,2); memcpy(&bv,b->data+y*b->stride+x*2,2);
			if(av!=bv) fprintf(stderr,"mismatch %d,%d gpu=%04x pixman=%04x\n",x,y,av,bv);
		} abort();
	}
}
static void comparison(bool gpu, bool crop, bool alpha, bool partial_clip, bool partial_damage, bool scene_color) {
	reset_gpu(); if (!gpu) setenv("K230_VGLITE_ALLOW_UNPROVEN_CACHE","0",1);
	struct test_buffer a,b,src; buffer_init(&a,12,10,DRM_FORMAT_RGB565,true); buffer_init(&b,12,10,DRM_FORMAT_RGB565,true);
	buffer_init(&src,5,4,DRM_FORMAT_ARGB8888,false);
	for(int y=0;y<4;y++) for(int x=0;x<5;x++) {
		uint32_t v=alpha?0x80402010u:0xff000000u|(uint32_t)(x*51)<<16|(uint32_t)(y*63)<<8|0x37;
		memcpy(src.data+y*src.stride+x*4,&v,4);
	}
	struct wlr_renderer *r=wlr_vglite_renderer_create(); struct vglite_renderer *vr=(struct vglite_renderer *)r;
	struct wlr_texture *t=wlr_texture_from_buffer(r,&src.base), *ref=wlr_texture_from_buffer(vr->pixman,&src.base);
	struct wlr_render_pass *p=begin(r,&a.base,NULL), *q=wlr_renderer_begin_buffer_pass(vr->pixman,&b.base,NULL);
	pixman_region32_t full,clip; pixman_region32_init_rect(&full,0,0,12,10); pixman_region32_init_rect(&clip,partial_clip?3:0,0,partial_clip?4:12,10);
	struct wlr_render_rect_options background=bg; background.clip=partial_damage?&clip:&full;
	add_rect(p,&background); wlr_render_pass_add_rect(q,&background);
	float opacity=alpha?.5:1;
	struct wlr_render_texture_options o={.texture=t,.dst_box={2,2,10,8},.alpha=&opacity,.clip=&clip,.filter_mode=WLR_SCALE_FILTER_NEAREST};
	struct wlr_color_primaries primaries;
	wlr_color_primaries_from_named(&primaries,WLR_COLOR_NAMED_PRIMARIES_SRGB);
	struct wlr_color_luminances from,to;
	wlr_color_transfer_function_get_default_luminance(WLR_COLOR_TRANSFER_FUNCTION_GAMMA22,&from);
	wlr_color_transfer_function_get_default_luminance(WLR_COLOR_TRANSFER_FUNCTION_SRGB,&to);
	float luminance=(to.reference/from.reference)*(from.max/to.max); assert(luminance==1);
	if(scene_color) { o.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_GAMMA22; o.primaries=&primaries; o.luminance_multiplier=&luminance; }
	if(crop) { o.src_box=(struct wlr_fbox){1,1,3,2}; o.dst_box=(struct wlr_box){3,3,6,4}; }
	if(partial_damage) o.dst_box=(struct wlr_box){3,3,4,4};
	add_texture(p,&o); o.texture=ref; wlr_render_pass_add_texture(q,&o);
	/* Mutate all caller-owned storage and destroy the original texture before
	 * submitting: the renderer must have captured a complete immutable pass. */
	opacity=0; luminance=0; memset(&primaries,0,sizeof(primaries)); pixman_region32_clear(&clip); pixman_region32_clear(&full); memset(src.data,0,(size_t)src.stride*4);
	wlr_texture_destroy(t); wlr_texture_destroy(ref);
	assert(wlr_render_pass_submit(q)); assert(submit(p)); assert_same(&a,&b);
	if(gpu && !alpha && !partial_clip && !partial_damage) assert(gpu_commands==2 && gpu_finishes==1 && gpu_frees==1);
	else assert(gpu_commands==0);
	pixman_region32_fini(&clip); pixman_region32_fini(&full); wlr_renderer_destroy(r); buffer_finish(&src); buffer_finish(&a); buffer_finish(&b);
}
static void profile_reporting(void) {
	const char *disabled[] = {"0", "01", "true"};
	for(size_t i=0;i<sizeof(disabled)/sizeof(disabled[0]);i++) {
		setenv("K230_VGLITE_PROFILE",disabled[i],1); cost_logs=0;
		comparison(true,false,false,false,false,false); assert(cost_logs==0);
	}
	setenv("K230_VGLITE_PROFILE","1",1);
	for(int gpu=0;gpu<2;gpu++) {
		cost_logs=0; comparison(gpu,false,false,false,false,false); assert(cost_logs==1);
		assert(strstr(cost_log,gpu ? "result=gpu ok=1" : "result=pixman ok=1"));
		uint64_t wall=0,cpu=0,snapshot=0;
		assert(sscanf(strstr(cost_log,"total_wall_ns="),"total_wall_ns=%" SCNu64 " total_cpu_ns=%" SCNu64,&wall,&cpu)==2);
		assert(sscanf(strstr(cost_log,"snapshot_cpu_ns="),"snapshot_cpu_ns=%" SCNu64,&snapshot)==1);
		assert(wall>0 && cpu>0 && snapshot>0 && snapshot<=cpu);
		if(gpu) assert(strstr(cost_log,"replay_wall_ns=0 replay_cpu_ns=0"));
		else assert(strstr(cost_log,"init_wall_ns=0 init_cpu_ns=0"));
	}
	unsetenv("K230_VGLITE_PROFILE");
}
static void failures(void) {
	for(int kind=0;kind<7;kind++) {
		reset_gpu(); struct test_buffer b; buffer_init(&b,8,8,DRM_FORMAT_RGB565,true);
		struct wlr_renderer *r=wlr_vglite_renderer_create(); struct wlr_render_pass *p=begin(r,&b.base,NULL);
		pixman_region32_t clip; pixman_region32_init_rect(&clip,0,0,8,8); struct wlr_render_rect_options o=bg; o.clip=&clip;
		if(kind==0) fail_alloc=1;
		if(kind==1) fail_clip=1;
		add_rect(p,&o);
		if(kind==2) fail_command=1;
		if(kind==3) fail_init=1;
		if(kind==4) fail_map=1;
		if(kind==5) b.attr.stride[0]=2;
		if(kind==6) setenv("K230_VGLITE_ALLOW_UNPROVEN_CACHE","yes",1);
		bool ok=submit(p);
		if(kind<=2) { assert(!ok && pixman_passes==0); if(kind<2) assert(!gpu_commands); }
		else assert(ok && pixman_passes==1 && !gpu_commands);
		if(kind>=2 && kind<=4) {
			assert(attempt_logs==1);
			assert(strstr(decision_log,kind==2 ? "reason=gpu_clear " : kind==3 ? "reason=gpu_init " : "reason=target_map "));
			char status_field[40]; snprintf(status_field,sizeof(status_field),"vg_status=%d",VG_LITE_GENERIC_IO);
			assert(strstr(decision_log,status_field));
		}
		if(kind==2) { assert(gpu_disabled && gpu_finishes==1); p=begin(r,&b.base,NULL); add_rect(p,&bg); assert(submit(p)); assert(pixman_passes==1); }
		pixman_region32_fini(&clip); wlr_renderer_destroy(r); buffer_finish(&b);
	}
}
/* Background damage excludes the opaque scene buffer, as wlr_scene.c does.
 * Non-null regions, default PREMULTIPLIED and unscaled BILINEAR must not make
 * this ordinary full redraw permanently ineligible. */
static void scene_regions(void) {
	reset_gpu(); struct test_buffer a,b,src;
	buffer_init(&a,12,10,DRM_FORMAT_RGB565,true); buffer_init(&b,12,10,DRM_FORMAT_RGB565,true);
	buffer_init(&src,5,4,DRM_FORMAT_XRGB8888,false);
	struct wlr_renderer *r=wlr_vglite_renderer_create(); struct vglite_renderer *vr=(struct vglite_renderer *)r;
	struct wlr_texture *t=wlr_texture_from_buffer(r,&src.base), *ref=wlr_texture_from_buffer(vr->pixman,&src.base);
	struct wlr_render_pass *p=begin(r,&a.base,NULL), *q=wlr_renderer_begin_buffer_pass(vr->pixman,&b.base,NULL);
	pixman_region32_t background,opaque;
	pixman_region32_init_rect(&background,0,0,12,10); pixman_region32_init_rect(&opaque,3,3,5,4);
	assert(pixman_region32_subtract(&background,&background,&opaque));
	struct wlr_render_rect_options rect=bg; rect.clip=&background;
	add_rect(p,&rect); wlr_render_pass_add_rect(q,&rect);
	float alpha=1, luminance=1;
	struct wlr_render_texture_options o={.texture=t,.dst_box={3,3,5,4},.clip=&opaque,.alpha=&alpha,.luminance_multiplier=&luminance};
	add_texture(p,&o); o.texture=ref; wlr_render_pass_add_texture(q,&o);
	assert(submit(p)); assert(wlr_render_pass_submit(q)); assert_same(&a,&b);
	assert(gpu_commands==5 && gpu_finishes==1 && pixman_passes==1);
	wlr_texture_destroy(t); wlr_texture_destroy(ref); pixman_region32_fini(&background); pixman_region32_fini(&opaque);
	wlr_renderer_destroy(r); buffer_finish(&a); buffer_finish(&b); buffer_finish(&src);
}
static void texture_failures(void) {
	for(int kind=0;kind<6;kind++) {
		reset_gpu(); struct test_buffer b,src;
		buffer_init(&b,8,8,DRM_FORMAT_RGB565,true); buffer_init(&src,2,2,DRM_FORMAT_XRGB8888,false);
		struct wlr_renderer *r=wlr_vglite_renderer_create(); struct wlr_texture *t=wlr_texture_from_buffer(r,&src.base);
		struct wlr_render_pass *p=begin(r,&b.base,NULL);
		if(kind!=1) add_rect(p,&bg);
		struct wlr_render_texture_options o={.texture=t,.dst_box={0,0,8,8},.filter_mode=WLR_SCALE_FILTER_NEAREST};
		if(kind==2) fail_alloc=1;
		if(kind==3) o.wait_timeline=(void *)1;
		if(kind==4) {
			for(int i=1;i<16;i++) add_rect(p,&bg);
			fail_alloc=1; add_rect(p,&bg);
		}
		add_texture(p,&o);
		if(kind<2) fail_allocate=1;
		if(kind==5) fail_command=2;
		bool ok=submit(p);
		if(kind==1) assert(ok && pixman_passes==1 && !gpu_commands);
		else assert(!ok && !pixman_passes);
		if(kind>=2 && kind<=4) assert(!gpu_commands);
		if(kind==0 || kind==5) assert(gpu_finishes==1 && gpu_disabled);
		wlr_texture_destroy(t); wlr_renderer_destroy(r); buffer_finish(&b); buffer_finish(&src);
	}
}
static void rejected_contracts(void) {
	for(int kind=0;kind<9;kind++) {
		reset_gpu(); struct test_buffer b; buffer_init(&b,8,8,DRM_FORMAT_RGB565,true);
		struct wlr_renderer *r=wlr_vglite_renderer_create();
		struct wlr_buffer_pass_options options={0};
		if(kind==0) options.signal_timeline=(void *)1;
		if(kind==1) options.color_transform=(void *)1;
		if(kind==2) options.timer=(void *)1;
		struct wlr_render_pass *p=begin(r,&b.base,&options);
		if(kind<3) assert(!p);
		else {
			if(kind==3) b.attr.n_planes=2;
			if(kind==4) b.attr.offset[0]=4;
			if(kind==5) b.attr.modifier=DRM_FORMAT_MOD_INVALID;
			if(kind==6) b.attr.width++;
			if(kind==7) b.attr.fd[0]=-1;
			if(kind==8) b.attr.format=DRM_FORMAT_ARGB8888;
			add_rect(p,&bg); assert(submit(p)); assert(pixman_passes==1 && !gpu_init_calls);
		}
		wlr_renderer_destroy(r); buffer_finish(&b);
	}
}
static void completion_quarantine(void) {
	reset_gpu(); struct test_buffer b,src; buffer_init(&b,8,8,DRM_FORMAT_RGB565,true); buffer_init(&src,2,2,DRM_FORMAT_XRGB8888,false);
	struct wlr_renderer *r=wlr_vglite_renderer_create(); struct wlr_texture *t=wlr_texture_from_buffer(r,&src.base);
	struct wlr_render_pass *p=begin(r,&b.base,NULL); add_rect(p,&bg);
	struct wlr_render_texture_options o={.texture=t,.dst_box={0,0,8,8},.filter_mode=WLR_SCALE_FILTER_NEAREST}; add_texture(p,&o);
	fail_finish=1; assert(!submit(p));
	assert(gpu_disabled && b.base.n_locks==1 && b.accessing && gpu_finishes==1 && !gpu_frees && !gpu_closes && !pixman_passes && queued==2);
	/* Child exits without reclaiming resources the GPU might still own. */
}
static void clipped_scene(int kind) {
	reset_gpu(); struct test_buffer a,b,src;
	buffer_init(&a,568,16,DRM_FORMAT_RGB565,true); buffer_init(&b,568,16,DRM_FORMAT_RGB565,true);
	assert(a.stride==1152); buffer_init(&src,590,22,DRM_FORMAT_ARGB8888,false);
	for(int y=0;y<22;y++) for(int x=0;x<590;x++) {
		uint32_t pixel=0xff000000u|((uint32_t)(x*37)&255)<<16|((uint32_t)(y*51)&255)<<8|((uint32_t)(x^y)&255);
		memcpy(src.data+y*src.stride+x*4,&pixel,4);
	}
	struct wlr_renderer *r=wlr_vglite_renderer_create(); struct vglite_renderer *vr=(struct vglite_renderer *)r;
	struct wlr_texture *t=wlr_texture_from_buffer(r,&src.base),*ref=wlr_texture_from_buffer(vr->pixman,&src.base);
	struct wlr_render_pass *p=begin(r,&a.base,NULL),*q=wlr_renderer_begin_buffer_pass(vr->pixman,&b.base,NULL);
	pixman_region32_t clip,hole,empty;
	pixman_region32_init_rect(&clip,kind==4 ? -3 : 0,kind==4 ? -2 : 0,kind==4 ? 574 : 568,kind==4 ? 20 : 16);
	pixman_region32_init_rect(&hole,100,4,101,8); pixman_region32_init(&empty);
	assert(pixman_region32_subtract(&clip,&clip,&hole));
	assert(pixman_region32_n_rects(&clip)==4);
	if(kind==1) { pixman_region32_t damage; pixman_region32_init_rect(&damage,1,0,567,16);
		assert(pixman_region32_intersect(&clip,&clip,&damage)); pixman_region32_fini(&damage); }
	struct wlr_render_rect_options clear=bg; clear.clip=kind==3 ? NULL : &empty;
	add_rect(p,&clear); wlr_render_pass_add_rect(q,&clear);
	struct wlr_color_primaries primaries; wlr_color_primaries_from_named(&primaries,WLR_COLOR_NAMED_PRIMARIES_SRGB);
	struct wlr_render_texture_options o={.texture=t,.src_box={11,3,kind==2 ? 284 : 568,kind==2 ? 8 : 16},
		.dst_box={0,0,568,16},.clip=kind==3 ? &empty : &clip,
		.filter_mode=kind==2 ? WLR_SCALE_FILTER_NEAREST : WLR_SCALE_FILTER_BILINEAR,
		.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_GAMMA22,.primaries=&primaries};
	add_texture(p,&o); o.texture=ref; wlr_render_pass_add_texture(q,&o);
	struct wlr_render_rect_options child={.box={100,4,101,8},.color={.b=1,.a=1}};
	add_rect(p,&child); wlr_render_pass_add_rect(q,&child);
	if(kind==5) fail_allocate=3; /* two uploaded pieces already queued */
	if(kind==6) fail_allocate=1; /* no GPU command submitted yet */
	if(kind==7) fail_finish=1;
	bool ok=submit(p); assert(wlr_render_pass_submit(q));
	if(kind==7) {
		assert(!ok && gpu_disabled && queued==5 && gpu_frees==0 && gpu_finishes==1);
		assert(a.base.n_locks==1 && a.accessing); _exit(0); /* process-lifetime quarantine */
	}
	if(kind==5) {
		assert(!ok && gpu_disabled && gpu_commands==2 && gpu_finishes==1 && gpu_frees==2 && pixman_passes==1);
	} else {
		assert(ok); assert_same(&a,&b);
		if(kind==1 || kind==2 || kind==6) assert(!gpu_commands && pixman_passes==2);
		else assert(gpu_commands==(kind==3 ? 2 : 5) && gpu_frees==(kind==3 ? 0 : 4) && gpu_finishes==1 && pixman_passes==1);
		if(kind==1) assert(strstr(decision_log,"reason=incomplete_coverage "));
		if(kind==2) assert(strstr(decision_log,"reason=texture_clip_scaled "));
	}
	wlr_texture_destroy(t); wlr_texture_destroy(ref); wlr_renderer_destroy(r);
	pixman_region32_fini(&clip); pixman_region32_fini(&hole); pixman_region32_fini(&empty);
	buffer_finish(&a); buffer_finish(&b); buffer_finish(&src);
}

static void scene_color_pixel_matrix(void) {
	/* All 256 input values for each RGB channel, plus mixed colors. Compile
	 * and call the real pinned color/Pixman code; do not emulate its metadata. */
	for(int kind=0;kind<23;kind++) for(int blend=0;blend<2;blend++) {
		reset_gpu(); struct test_buffer gpu,ref,src;
		buffer_init(&gpu,256,4,DRM_FORMAT_RGB565,true); buffer_init(&ref,256,4,DRM_FORMAT_RGB565,true);
		buffer_init(&src,256,4,blend ? DRM_FORMAT_XRGB8888 : DRM_FORMAT_ARGB8888,false);
		for(int y=0;y<4;y++) for(int x=0;x<256;x++) {
			uint32_t rgb=y==0 ? (uint32_t)x<<16 : y==1 ? (uint32_t)x<<8 : y==2 ? (uint32_t)x :
				(uint32_t)x<<16 | (uint32_t)(255-x)<<8 | (uint32_t)(x^0x55);
			uint32_t pixel=0xff000000u|rgb; memcpy(src.data+y*src.stride+x*4,&pixel,4);
		}
		struct wlr_renderer *r=wlr_vglite_renderer_create(); struct vglite_renderer *vr=(struct vglite_renderer *)r;
		struct wlr_texture *t=wlr_texture_from_buffer(r,&src.base), *reference=wlr_texture_from_buffer(vr->pixman,&src.base);
		struct wlr_render_pass *p=begin(r,&gpu.base,NULL), *q=wlr_renderer_begin_buffer_pass(vr->pixman,&ref.base,NULL);
		add_rect(p,&bg); wlr_render_pass_add_rect(q,&bg);
		struct wlr_color_primaries primaries;
		wlr_color_primaries_from_named(&primaries,WLR_COLOR_NAMED_PRIMARIES_SRGB);
		float luminance=1,alpha=1;
		struct wlr_render_texture_options o={.texture=t,.dst_box={0,0,256,4},.alpha=&alpha,
			.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_GAMMA22,.primaries=&primaries,
			.luminance_multiplier=&luminance,.filter_mode=WLR_SCALE_FILTER_BILINEAR,
			.blend_mode=blend ? WLR_RENDER_BLEND_MODE_NONE : WLR_RENDER_BLEND_MODE_PREMULTIPLIED};
		switch(kind) {
		case 1: o.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_SRGB; break;
		case 2: o.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ; break;
		case 3: o.primaries=NULL; break;
		case 4: wlr_color_primaries_from_named(&primaries,WLR_COLOR_NAMED_PRIMARIES_BT2020); break;
		case 5: luminance=.5; break;
		case 6: luminance=NAN; break;
		case 7: o.color_encoding=WLR_COLOR_ENCODING_BT709; break;
		case 8: o.color_range=WLR_COLOR_RANGE_FULL; break;
		case 9: alpha=.5; break;
		case 10: o.transform=WL_OUTPUT_TRANSFORM_180; break;
		case 11: o.transfer_function=0; break;
		case 20: primaries.white.x=NAN; break;
		case 21: luminance=nextafterf(1,2); break;
		case 22: o.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_GAMMA22|WLR_COLOR_TRANSFER_FUNCTION_SRGB; break;
		default:
			if(kind>=12 && kind<=19) {
				float *coordinates[]={&primaries.red.x,&primaries.red.y,&primaries.green.x,&primaries.green.y,
					&primaries.blue.x,&primaries.blue.y,&primaries.white.x,&primaries.white.y};
				*coordinates[kind-12]=nextafterf(*coordinates[kind-12],1);
			}
		}
		add_texture(p,&o); o.texture=reference; wlr_render_pass_add_texture(q,&o);
		assert(submit(p)); assert(wlr_render_pass_submit(q)); assert_same(&gpu,&ref);
		assert(gpu_init_calls==(kind==0 ? 1 : 0));
		assert(gpu_commands==(kind==0 ? 2 : 0));
		assert(pixman_passes==(kind==0 ? 1 : 2)); /* explicit reference plus fallback */
		wlr_texture_destroy(t); wlr_texture_destroy(reference); wlr_renderer_destroy(r);
		buffer_finish(&src); buffer_finish(&gpu); buffer_finish(&ref);
	}
}

static void scene_default_diagnostics(void) {
	/* Pinned types/scene/surface.c:290 supplies GAMMA22 + SRGB for ordinary
	 * wl_surfaces. Only this exact tuple is now eligible;
	 * primaries without its transfer function remain rejected. */
	for (int kind=0; kind<5; kind++) {
		reset_gpu(); struct test_buffer b,src; buffer_init(&b,8,8,DRM_FORMAT_RGB565,true);
		buffer_init(&src,8,8,DRM_FORMAT_XRGB8888,false);
		struct wlr_renderer *r=wlr_vglite_renderer_create();
		struct wlr_texture *t=wlr_texture_from_buffer(r,&src.base);
		struct wlr_render_pass *p=begin(r,&b.base,NULL);
		struct wlr_render_rect_options clear={.color={.a=kind==3 ? 0 : 1}};
		add_rect(p,&clear);
		struct wlr_color_primaries srgb;
		wlr_color_primaries_from_named(&srgb,WLR_COLOR_NAMED_PRIMARIES_SRGB);
		float luminance=1;
		struct wlr_render_texture_options o={.texture=t,.dst_box={0,0,8,8},
			.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_GAMMA22,.primaries=&srgb,
			.luminance_multiplier=&luminance,.filter_mode=WLR_SCALE_FILTER_BILINEAR};
		if (kind==1) o.transfer_function=0;
		if (kind<2) add_texture(p,&o);
		if (kind==4) b.attr.stride[0]=65;
		assert(submit(p));
		const char *reason=kind==0 ? "eligible" : kind==1 ? "texture_primaries" :
			kind==3 ? "rect_alpha" : kind==4 ? "target_attributes" : "eligible";
		char expected[80]; snprintf(expected,sizeof(expected),"reason=%s ",reason);
		assert(strstr(decision_log,expected));
		assert(strstr(decision_log,"v=1 result="));
		assert(strstr(decision_log,"target=8x8 dmabuf=1 format=0x36314752 modifier=0x0000000000000000 planes=1 stride="));
		assert(attempt_logs==((kind==0 || kind==2) ? 1u : 0u));
		if (kind==1) {
			assert(strstr(decision_log,"op=1 ops=2 "));
			assert(strstr(operation_log,"kind=texture alpha=1 opaque=1 "));
			assert(strstr(operation_log,"primaries=1 luminance=1 encoding=0 range=0 "));
		}
		wlr_texture_destroy(t); wlr_renderer_destroy(r); buffer_finish(&src); buffer_finish(&b);
	}
}
static void denied_broker(void) {
	reset_gpu(); setenv("K230_VGLITE_BROKER", "/test/broker", 1);
	struct test_buffer b; buffer_init(&b,8,8,DRM_FORMAT_RGB565,true);
	for (int i=0;i<2;i++) {
		struct wlr_renderer *r=wlr_vglite_renderer_create(); assert(r);
		struct wlr_render_pass *p=begin(r,&b.base,NULL); add_rect(p,&bg); assert(submit(p));
		wlr_renderer_destroy(r);
	}
	assert(broker_calls==1 && gpu_disabled && !gpu_init_calls && pixman_passes==2);
	buffer_finish(&b); reset_gpu();
}
int main(void) {
	unsetenv("K230_VGLITE_PROFILE");
	profile_reporting();
	for(int i=0;i<7;i++) clipped_scene(i);
	pid_t clipped_child=fork(); assert(clipped_child>=0);
	if(!clipped_child) { clipped_scene(7); _exit(99); }
	int clipped_status; assert(waitpid(clipped_child,&clipped_status,0)==clipped_child &&
		WIFEXITED(clipped_status) && WEXITSTATUS(clipped_status)==0);
	scene_color_pixel_matrix();
	scene_default_diagnostics();
	denied_broker();
	comparison(true,false,false,false,false,false);
	comparison(true,false,false,false,false,true);
	comparison(true,true,false,false,false,false);
	comparison(true,true,false,false,false,true);
	comparison(true,true,true,false,false,false);
	comparison(true,true,true,false,false,true);
	comparison(true,false,false,true,false,false);
	comparison(true,false,false,true,false,true);
	comparison(true,false,false,true,true,false);
	comparison(true,false,false,true,true,true);
	comparison(false,true,false,false,false,false);
	comparison(false,true,false,false,false,true);
	failures();
	scene_regions();
	texture_failures();
	rejected_contracts();
	pid_t child=fork(); assert(child>=0); if(!child) { completion_quarantine(); _exit(0); }
	int status; assert(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0);
	puts("PASS: exact scene-default color identity and rejected metadata matrix, production renderer snapshots, RGB channel order, padded upload, crop/scale translation, alpha/clip/partial-damage replay, exact opt-in, record/map/init/command/finish failures, completion quarantine; real pinned Pixman output comparison");
}
