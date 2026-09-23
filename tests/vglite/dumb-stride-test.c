/* Compile actual patched wlroots allocator; only DRM and allocation plumbing
 * are fixtures. No device is opened and no ioctl or modeset is performed. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <drm_fourcc.h>
#include <wlr/interfaces/wlr_buffer.h>
#include <wlr/render/drm_format_set.h>
#include <wlr/util/log.h>
#include "render/pixel_format.h"
static unsigned calls, destroyed, unmapped, exported;
static uint32_t requested_width, requested_height, requested_bpp;
static int fail_map;
static void *memory;
static void *fake_mmap(void *a,size_t size,int prot,int flags,int fd,off_t offset) {
	(void)a; assert(prot==(PROT_READ|PROT_WRITE) && flags==MAP_SHARED && fd==77 && offset==0);
	memory=malloc(size); assert(memory); return memory;
}
static int fake_munmap(void *p,size_t n) { assert(p==memory && n>0); free(p); memory=NULL; unmapped++; return 0; }
#define mmap fake_mmap
#define munmap fake_munmap
#include "drm_dumb.c"
#undef mmap
#undef munmap
void _wlr_log(enum wlr_log_importance level,const char *fmt,...) { (void)level; (void)fmt; }
const struct wlr_pixel_format_info *drm_get_pixel_format_info(uint32_t fmt) {
	static const struct wlr_pixel_format_info rgb565={.bytes_per_block=2},argb={.bytes_per_block=4};
	assert(fmt==DRM_FORMAT_RGB565 || fmt==DRM_FORMAT_ARGB8888); return fmt==DRM_FORMAT_RGB565 ? &rgb565 : &argb;
}
uint32_t pixel_format_info_pixels_per_block(const struct wlr_pixel_format_info *info) { (void)info; return 1; }
bool wlr_drm_format_has(const struct wlr_drm_format *fmt,uint64_t modifier) { (void)fmt; return modifier==DRM_FORMAT_MOD_LINEAR; }
void wlr_buffer_init(struct wlr_buffer *b,const struct wlr_buffer_impl *impl,int width,int height) {
	b->impl=impl; b->width=width; b->height=height;
}
void wlr_buffer_finish(struct wlr_buffer *b) { (void)b; }
void wlr_buffer_drop(struct wlr_buffer *b) { b->impl->destroy(b); }
void wlr_dmabuf_attributes_finish(struct wlr_dmabuf_attributes *a) { a->n_planes=0; }
int drmModeCreateDumbBuffer(int fd,uint32_t w,uint32_t h,uint32_t bpp,uint32_t flags,uint32_t *handle,uint32_t *pitch,uint64_t *size) {
	assert(fd==77 && flags==0); calls++; requested_width=w; requested_height=h; requested_bpp=bpp;
	*handle=9; *pitch=w*(bpp/8); *size=(uint64_t)*pitch*h; return 0;
}
int drmModeDestroyDumbBuffer(int fd,uint32_t handle) { assert(fd==77 && handle==9); destroyed++; return 0; }
int drmModeMapDumbBuffer(int fd,uint32_t handle,uint64_t *offset) { assert(fd==77 && handle==9); *offset=0; return fail_map ? -1 : 0; }
int drmPrimeHandleToFD(int fd,uint32_t handle,uint32_t flags,int *prime) { assert(fd==77 && handle==9 && flags==DRM_CLOEXEC); *prime=42; exported++; return 0; }
static void trial(const char *renderer,uint32_t format,int width,unsigned physical) {
	if(renderer) setenv("WLR_RENDERER",renderer,1); else unsetenv("WLR_RENDERER");
	calls=destroyed=unmapped=exported=0; fail_map=0;
	struct wlr_drm_dumb_allocator allocator={.drm_fd=77}; wl_list_init(&allocator.buffers);
	struct wlr_drm_format fmt={.format=format};
	struct wlr_drm_dumb_buffer *b=create_buffer(&allocator,width,1080,&fmt); assert(b);
	unsigned bytes=format==DRM_FORMAT_RGB565 ? 2 : 4;
	assert(calls==1 && exported==1 && requested_width==physical && requested_height==1080 && requested_bpp==bytes*8);
	assert(b->base.width==width && b->base.height==1080 && b->width==(unsigned)width);
	assert(b->dmabuf.width==width && b->dmabuf.height==1080 && b->dmabuf.stride[0]==physical*bytes);
	assert(b->dmabuf.modifier==DRM_FORMAT_MOD_LINEAR && b->dmabuf.offset[0]==0 && b->dmabuf.n_planes==1);
	void *data; uint32_t pixel_format; size_t stride;
	assert(drm_dumb_buffer_begin_data_ptr_access(&b->base,0,&data,&pixel_format,&stride));
	assert(data==memory && stride==physical*bytes && pixel_format==format);
	assert(b->size==stride*1080); wlr_buffer_drop(&b->base);
	assert(destroyed==1 && unmapped==1 && wl_list_empty(&allocator.buffers));
	fail_map=1; assert(!create_buffer(&allocator,width,1080,&fmt));
	assert(calls==2 && destroyed==2 && unmapped==1 && wl_list_empty(&allocator.buffers));
}
int main(void) {
	trial("vglite",DRM_FORMAT_RGB565,568,576);
	trial("vglite",DRM_FORMAT_RGB565,576,576);
	trial("vglite",DRM_FORMAT_RGB565,1,32);
	trial("pixman",DRM_FORMAT_RGB565,568,568);
	trial("vglite-extra",DRM_FORMAT_RGB565,568,568);
	trial(NULL,DRM_FORMAT_RGB565,568,568);
	trial("vglite",DRM_FORMAT_ARGB8888,568,568);
	setenv("WLR_RENDERER","vglite",1); calls=0;
	struct wlr_drm_dumb_allocator allocator={.drm_fd=77}; wl_list_init(&allocator.buffers);
	struct wlr_drm_format fmt={.format=DRM_FORMAT_RGB565};
	assert(!create_buffer(&allocator,INT_MAX,1080,&fmt) && !calls);
	assert(!create_buffer(&allocator,0,1080,&fmt) && !calls);
	puts("PASS: production dumb allocator pads only opt-in RGB565 storage; logical geometry, shared stride, DRM fd and cleanup preserved");
}
