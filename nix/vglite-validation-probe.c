/*
 * Bounded K230 VG-Lite validation.  This never calls drmSetMaster,
 * drmModeSetCrtc, framebuffer, plane, or atomic APIs.  It only creates a
 * private dumb buffer so that PRIME export/import can be observed while a
 * compositor continues to own live scanout.
 */
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include <xf86drm.h>
#include <xf86drmMode.h>
#include <pixman.h>
#include "vg_lite.h"

enum { SW = 128, SH = 128, DW = 256, DH = 256, ITERS = 200 };

static uint64_t now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}
static int vg(vg_lite_error_t e, const char *what) {
  if (e == VG_LITE_SUCCESS) return 0;
  fprintf(stderr, "%s: VG-Lite error %d\n", what, e); return -1;
}
static uint16_t p565(const vg_lite_buffer_t *b, unsigned x, unsigned y) {
  uint16_t p; memcpy(&p, b->memory + y * b->stride + x * 2, sizeof p); return p;
}
static void show565(const char *tag, const vg_lite_buffer_t *b, unsigned x, unsigned y) {
  printf("%s x=%u y=%u rgb565=0x%04" PRIx16 "\n", tag, x, y, p565(b, x, y));
}
static int alloc565(vg_lite_buffer_t *b, unsigned w, unsigned h) {
  memset(b, 0, sizeof *b); b->width = w; b->height = h; b->format = VG_LITE_RGB565;
  return vg(vg_lite_allocate(b), "vg_lite_allocate(RGB565)");
}
static int rgb565(void) {
  vg_lite_buffer_t src, dst; vg_lite_matrix_t m;
  vg_lite_rectangle_t left = { 0, 0, SW / 2, SH };
  int rc = 1;
  puts("RGB565_BEGIN");
  if (vg_lite_init(DW, DH) || alloc565(&src, SW, SH) || alloc565(&dst, DW, DH)) goto out;
  if (vg(vg_lite_clear(&src, NULL, 0), "clear source") ||
      vg(vg_lite_clear(&src, &left, 0xff0000ffu), "clear red half") ||
      vg(vg_lite_clear(&dst, NULL, 0xff804030u), "clear target") ||
      vg(vg_lite_identity(&m), "identity") || vg(vg_lite_scale(2, 2, &m), "scale") ||
      vg(vg_lite_blit(&dst, &src, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "blit") ||
      vg(vg_lite_finish(), "finish")) goto out_free;
  show565("source", &src, 0, 0); show565("source", &src, 127, 0);
  show565("target", &dst, 127, 0); show565("target", &dst, 128, 0);
  if (p565(&src, 0, 0) != 0xf800 || p565(&src, 127, 0) != 0 ||
      p565(&dst, 127, 0) != 0xf800 || p565(&dst, 128, 0) != 0) {
    fputs("RGB565_ASSERTION_FAILED exact red/black 2x boundary\n", stderr); goto out_free;
  }
  puts("RGB565_PASS exact 2x boundary"); rc = 0;
out_free: vg_lite_free(&dst); vg_lite_free(&src);
out: vg_lite_close(); puts("RGB565_END"); return rc;
}

static int alpha(void) {
  vg_lite_buffer_t src = {0}, dst = {0}; vg_lite_matrix_t m; uint32_t a, b;
  int rc = 1;
  puts("ALPHA_BEGIN");
  if (vg_lite_init(SW, SH)) goto out;
  src.width=dst.width=SW; src.height=dst.height=SH;
  src.format=dst.format=VG_LITE_RGBA8888;
  if (vg(vg_lite_allocate(&src), "allocate alpha source") || vg(vg_lite_allocate(&dst), "allocate alpha target") ||
      vg(vg_lite_clear(&src, NULL, 0x80402010u), "clear alpha source") ||
      vg(vg_lite_clear(&dst, NULL, 0xff203040u), "clear alpha target") ||
      vg(vg_lite_identity(&m), "identity") ||
      vg(vg_lite_blit(&dst, &src, &m, VG_LITE_BLEND_SRC_OVER, 0, VG_LITE_FILTER_POINT), "alpha src-over") ||
      vg(vg_lite_finish(), "finish alpha")) goto out_free;
  memcpy(&a, src.memory, sizeof a); memcpy(&b, dst.memory, sizeof b);
  printf("ALPHA_SAMPLE source=0x%08" PRIx32 " target-src-over=0x%08" PRIx32 "\n", a, b);
  puts("ALPHA_COMPLETE diagnostic values only"); rc = 0;
out_free: vg_lite_free(&dst); vg_lite_free(&src);
out: vg_lite_close(); puts("ALPHA_END"); return rc;
}

static int dmabuf(const char *node) {
  int fd=-1, prime=-1, rc=1; uint32_t handle=0, pitch=0; uint64_t size=0, offset=0;
  void *map=MAP_FAILED; vg_lite_buffer_t b={0};
  puts("DMABUF_BEGIN");
  fd=open(node, O_RDWR|O_CLOEXEC); if (fd < 0) { perror(node); goto out; }
  if (drmModeCreateDumbBuffer(fd, DW, DH, 16, 0, &handle, &pitch, &size)) { perror("drmModeCreateDumbBuffer"); goto out; }
  if (drmPrimeHandleToFD(fd, handle, DRM_CLOEXEC|DRM_RDWR, &prime)) { perror("drmPrimeHandleToFD"); goto out; }
  if (drmModeMapDumbBuffer(fd, handle, &offset)) { perror("drmModeMapDumbBuffer"); goto out; }
  map=mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, offset);
  if (map == MAP_FAILED) { perror("mmap dumb"); goto out; }
  memset(map, 0, size);
  b.width=DW; b.height=DH; b.stride=pitch; b.format=VG_LITE_RGB565; b.memory=map;
  if (vg_lite_init(DW, DH) || vg(vg_lite_map(&b, VG_LITE_MAP_DMABUF, prime), "vg_lite_map(dmabuf)") ||
      vg(vg_lite_clear(&b, NULL, 0xff0000ffu), "clear imported dumb") || vg(vg_lite_finish(), "finish imported dumb")) goto out_close_vg;
  show565("dmabuf", &b, 0, 0);
  if (p565(&b, 0, 0) != 0xf800) { fputs("DMABUF_ASSERTION_FAILED expected RGB565 red\n", stderr); goto out_unmap; }
  printf("DMABUF_PASS node=%s handle=%" PRIu32 " pitch=%" PRIu32 " size=%" PRIu64 "\n", node, handle, pitch, size); rc=0;
out_unmap: vg_lite_unmap(&b);
out_close_vg: vg_lite_close();
out: if (map != MAP_FAILED) munmap(map, size); if (prime >= 0) close(prime); if (handle && fd >= 0) drmModeDestroyDumbBuffer(fd, handle); if (fd >= 0) close(fd); puts("DMABUF_END"); return rc;
}

static int benchmark(void) {
  vg_lite_buffer_t src, dst; vg_lite_matrix_t m; uint64_t begin, gpu_ns, pix_ns; int rc=1;
  uint16_t *ps=calloc(SW*SH,2), *pd=calloc(DW*DH,2); pixman_image_t *si=NULL,*di=NULL;
  puts("BENCHMARK_BEGIN");
  if (!ps || !pd || vg_lite_init(DW,DH) || alloc565(&src,SW,SH) || alloc565(&dst,DW,DH) ||
      vg(vg_lite_clear(&src,NULL,0xff0000ffu),"bench clear") || vg(vg_lite_identity(&m),"bench identity") || vg(vg_lite_scale(2,2,&m),"bench scale")) goto out;
  begin=now_ns(); for (int i=0;i<ITERS;i++) if (vg(vg_lite_blit(&dst,&src,&m,VG_LITE_BLEND_NONE,0,VG_LITE_FILTER_POINT),"bench blit")) goto out_gpu;
  if (vg(vg_lite_finish(),"bench finish")) goto out_gpu;
  gpu_ns=now_ns()-begin;
  si=pixman_image_create_bits(PIXMAN_r5g6b5,SW,SH,(uint32_t *)ps,SW*2); di=pixman_image_create_bits(PIXMAN_r5g6b5,DW,DH,(uint32_t *)pd,DW*2);
  if (!si || !di) { fputs("pixman image allocation failed\n",stderr); goto out_gpu; }
  begin=now_ns();
  for (int i=0;i<ITERS;i++)
    pixman_image_composite32(PIXMAN_OP_SRC,si,NULL,di,0,0,0,0,0,0,DW,DH);
  pix_ns=now_ns()-begin;
  printf("BENCHMARK iterations=%d geometry=%dx%d-to-%dx%d gpu_submit_finish_ns=%" PRIu64 " gpu_ns_per_op=%" PRIu64 " pixman_ns=%" PRIu64 " pixman_ns_per_op=%" PRIu64 "\n", ITERS,SW,SH,DW,DH,gpu_ns,gpu_ns/ITERS,pix_ns,pix_ns/ITERS);
  puts("BENCHMARK_COMPLETE diagnostic timing only"); rc=0;
  pixman_image_unref(di); pixman_image_unref(si);
out_gpu: vg_lite_free(&dst); vg_lite_free(&src); vg_lite_close();
out: free(pd); free(ps); puts("BENCHMARK_END"); return rc;
}

int main(int argc, char **argv) {
  const char *mode=argc>1?argv[1]:"all"; const char *node=argc>2?argv[2]:"/dev/dri/renderD128"; int bad=0;
  printf("VGLITE_VALIDATION_BEGIN mode=%s\n",mode);
  if (!strcmp(mode,"rgb565") || !strcmp(mode,"all")) bad |= rgb565();
  if (!strcmp(mode,"alpha") || !strcmp(mode,"all")) bad |= alpha();
  if (!strcmp(mode,"dmabuf") || !strcmp(mode,"all")) bad |= dmabuf(node);
  if (!strcmp(mode,"benchmark") || !strcmp(mode,"all")) bad |= benchmark();
  if (strcmp(mode,"all") && strcmp(mode,"rgb565") && strcmp(mode,"alpha") && strcmp(mode,"dmabuf") && strcmp(mode,"benchmark")) { fputs("usage: k230-vglite-validation [all|rgb565|alpha|dmabuf|benchmark] [drm-node]\n",stderr); bad=1; }
  printf("VGLITE_VALIDATION_%s\n",bad?"FAIL":"PASS"); return !!bad;
}
