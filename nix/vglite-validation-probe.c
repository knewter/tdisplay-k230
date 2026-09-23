/* Bounded VG-Lite validation: no DRM master, modeset, framebuffer or plane API. */
#include "vg_lite.h"
#include <fcntl.h>
#include <inttypes.h>
#include <pixman.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

enum { SW = 128, SH = 128, DW = 256, DH = 256, ITERS = 200, FINISH_ITERS = 20, ROUNDS = 3 };
static const uint16_t quad[4] = {0xf800, 0x07e0, 0x001f, 0x0000};
static const vg_lite_color_t qcolor[4] = {0xff0000ffu, 0xff00ff00u, 0xffff0000u, 0u};
static uint64_t now_ns(clockid_t clock_id) {
  struct timespec t;
  clock_gettime(clock_id, &t);
  return (uint64_t)t.tv_sec * 1000000000ull + t.tv_nsec;
}
static int vg(vg_lite_error_t e, const char *s) {
  if (!e)
    return 0;
  fprintf(stderr, "%s: VG-Lite error %d\n", s, e);
  return -1;
}
static uint16_t get565(const void *p, uint32_t st, unsigned x, unsigned y) {
  uint16_t v;
  memcpy(&v, (const uint8_t *)p + y * st + x * 2, 2);
  return v;
}
static void show565(const char *n, const void *p, uint32_t s, unsigned x, unsigned y) {
  printf("%s x=%u y=%u rgb565=0x%04" PRIx16 "\n", n, x, y, get565(p, s, x, y));
}
static int alloc565(vg_lite_buffer_t *b, unsigned w, unsigned h) {
  memset(b, 0, sizeof *b);
  b->width = w;
  b->height = h;
  /* The SDK maps RGB565/BGR565 to distinct hardware formats (0x21/0x01).
   * Board evidence shows BGR565 is the variant whose bytes are DRM/Pixman
   * little-endian RGB565 (red 0xf800, blue 0x001f). */
  b->format = VG_LITE_BGR565;
  return vg(vg_lite_allocate(b), "allocate BGR565 for DRM RGB565 memory");
}
static int quads_gpu(vg_lite_buffer_t *b, unsigned w, unsigned h) {
  vg_lite_rectangle_t r[4] = {{0, 0, w / 2, h / 2},
                              {w / 2, 0, w - w / 2, h / 2},
                              {0, h / 2, w / 2, h - h / 2},
                              {w / 2, h / 2, w - w / 2, h - h / 2}};
  for (unsigned i = 0; i < 4; i++)
    if (vg(vg_lite_clear(b, &r[i], qcolor[i]), "clear source quadrant"))
      return -1;
  return 0;
}
static int check_quads(const char *n, const void *p, uint32_t st, unsigned w, unsigned h) {
  const unsigned xs[4] = {0, w / 2 - 1, w / 2, w - 1}, ys[4] = {0, h / 2 - 1, h / 2, h - 1};
  int bad = 0;
  for (unsigned y = 0; y < 4; y++)
    for (unsigned x = 0; x < 4; x++) {
      unsigned q = (ys[y] >= h / 2) * 2 + (xs[x] >= w / 2), v = get565(p, st, xs[x], ys[y]);
      show565(n, p, st, xs[x], ys[y]);
      if (v != quad[q])
        bad = 1;
    }
  return bad;
}
static void quads_cpu(uint16_t *p, unsigned w, unsigned h) {
  for (unsigned y = 0; y < h; y++)
    for (unsigned x = 0; x < w; x++)
      p[y * w + x] = quad[(y >= h / 2) * 2 + (x >= w / 2)];
}

static int rgb565(void) {
  vg_lite_buffer_t s = {0}, d = {0};
  vg_lite_matrix_t m;
  int init = 0, rc = 1;
  puts("RGB565_BEGIN");
  if (vg(vg_lite_init(DW, DH), "init RGB565"))
    goto out;
  init = 1;
  if (alloc565(&s, SW, SH) || alloc565(&d, DW, DH) || quads_gpu(&s, SW, SH) ||
      vg(vg_lite_clear(&d, NULL, 0xff804030u), "clear target") ||
      vg(vg_lite_identity(&m), "identity") || vg(vg_lite_scale(2, 2, &m), "scale") ||
      vg(vg_lite_blit(&d, &s, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "blit") ||
      vg(vg_lite_finish(), "finish"))
    goto out;
  if (check_quads("rgb565-source", s.memory, s.stride, SW, SH) ||
      check_quads("rgb565-target", d.memory, d.stride, DW, DH)) {
    fputs("RGB565_ASSERTION_FAILED multi-row exact quadrants\n", stderr);
    goto out;
  }
  puts("RGB565_PASS exact multi-row 2x quadrants");
  rc = 0;
out:
  if (d.handle)
    vg_lite_free(&d);
  if (s.handle)
    vg_lite_free(&s);
  if (init)
    vg_lite_close();
  puts("RGB565_END");
  return rc;
}

static void bytes(uint32_t v, uint8_t o[4]) { memcpy(o, &v, 4); }
static uint8_t over_alpha(uint8_t s, uint8_t d, uint8_t a) {
  return (uint8_t)(s + ((unsigned)d * (255 - a) + 127) / 255);
}
static int alpha(void) {
  vg_lite_buffer_t s = {0}, d = {0};
  vg_lite_matrix_t m;
  uint32_t sv, d0, d1;
  uint8_t a[4], b[4], c[4], straight[4], premult[4];
  int init = 0, rc = 1;
  puts("ALPHA_BEGIN");
  if (vg(vg_lite_init(SW, SH), "init alpha"))
    goto out;
  init = 1;
  s.width = d.width = SW;
  s.height = d.height = SH;
  s.format = d.format = VG_LITE_RGBA8888;
  if (vg(vg_lite_allocate(&s), "allocate alpha source") ||
      vg(vg_lite_allocate(&d), "allocate alpha target") ||
      vg(vg_lite_clear(&s, NULL, 0x80402010u), "clear alpha source") ||
      vg(vg_lite_clear(&d, NULL, 0xff203040u), "clear alpha target") ||
      vg(vg_lite_finish(), "finish alpha clears"))
    goto out;
  memcpy(&sv, s.memory, 4);
  memcpy(&d0, d.memory, 4);
  bytes(sv, a);
  bytes(d0, b);
  if (vg(vg_lite_identity(&m), "alpha identity") ||
      vg(vg_lite_blit(&d, &s, &m, VG_LITE_BLEND_SRC_OVER, 0, VG_LITE_FILTER_POINT),
         "alpha src-over") ||
      vg(vg_lite_finish(), "finish alpha blend"))
    goto out;
  memcpy(&d1, d.memory, 4);
  bytes(d1, c);
  for (unsigned i = 0; i < 3; i++) {
    straight[i] = (uint8_t)(((unsigned)a[i] * a[3] + (unsigned)b[i] * (255 - a[3]) + 127) / 255);
    premult[i] = (uint8_t)(a[i] + ((unsigned)b[i] * (255 - a[3]) + 127) / 255);
  }
  straight[3] = over_alpha(a[3], b[3], a[3]);
  premult[3] = straight[3];
  printf("ALPHA_SAMPLE source=0x%08" PRIx32 " target-initial=0x%08" PRIx32
         " target-src-over=0x%08" PRIx32 "\n",
         sv, d0, d1);
  printf("ALPHA_MODEL straight=%02x:%02x:%02x:%02x premult=%02x:%02x:%02x:%02x "
         "observed=%02x:%02x:%02x:%02x\n",
         straight[0], straight[1], straight[2], straight[3], premult[0], premult[1], premult[2],
         premult[3], c[0], c[1], c[2], c[3]);
  if (!memcmp(c, straight, 4)) {
    puts("ALPHA_PASS straight model");
    rc = 0;
  } else if (!memcmp(c, premult, 4)) {
    puts("ALPHA_PASS premultiplied model");
    rc = 0;
  } else
    fputs("ALPHA_MODEL_MISMATCH blocker: neither expected model matched\n", stderr);
out:
  if (d.handle)
    vg_lite_free(&d);
  if (s.handle)
    vg_lite_free(&s);
  if (init)
    vg_lite_close();
  puts("ALPHA_END");
  return rc;
}

static int dmabuf(const char *n) {
  int fd = -1, prime = -1, init = 0, mapped = 0, rc = 1;
  uint32_t h = 0, pitch = 0;
  uint64_t size = 0, off = 0;
  void *cpu = MAP_FAILED;
  vg_lite_buffer_t b = {0};
  puts("DMABUF_BEGIN");
  fd = open(n, O_RDWR | O_CLOEXEC);
  if (fd < 0) {
    perror(n);
    goto out;
  }
  if (drmModeCreateDumbBuffer(fd, DW, DH, 16, 0, &h, &pitch, &size)) {
    perror("drmModeCreateDumbBuffer");
    goto out;
  }
  if (drmPrimeHandleToFD(fd, h, DRM_CLOEXEC | DRM_RDWR, &prime)) {
    perror("drmPrimeHandleToFD");
    goto out;
  }
  if (drmModeMapDumbBuffer(fd, h, &off)) {
    perror("drmModeMapDumbBuffer");
    goto out;
  }
  cpu = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, off);
  if (cpu == MAP_FAILED) {
    perror("mmap dumb");
    goto out;
  }
  memset(cpu, 0, size);
  b.width = DW;
  b.height = DH;
  b.stride = pitch;
  b.format = VG_LITE_BGR565;
  b.memory = cpu;
  if (vg(vg_lite_init(DW, DH), "init dmabuf"))
    goto out;
  init = 1;
  if (vg(vg_lite_map(&b, VG_LITE_MAP_DMABUF, prime), "map dmabuf"))
    goto out;
  mapped = 1;
  if (vg(vg_lite_clear(&b, NULL, 0xff0000ffu), "clear imported dumb") ||
      vg(vg_lite_finish(), "finish imported dumb"))
    goto out;
  show565("dmabuf-cpu-map", cpu, pitch, 0, 0);
  show565("dmabuf-cpu-map", cpu, pitch, DW - 1, 0);
  show565("dmabuf-cpu-map", cpu, pitch, 0, DH - 1);
  show565("dmabuf-cpu-map", cpu, pitch, DW - 1, DH - 1);
  for (unsigned y = 0; y < DH; y++)
    for (unsigned x = 0; x < DW; x++)
      if (get565(cpu, pitch, x, y) != 0xf800) {
        fputs("DMABUF_ASSERTION_FAILED original CPU mapping not full red\n", stderr);
        goto out;
      }
  puts("DMABUF_PASS original CPU mapping exact full red");
  printf("DMABUF_DETAILS node=%s handle=%" PRIu32 " pitch=%" PRIu32 " size=%" PRIu64 "\n", n, h,
         pitch, size);
  rc = 0;
out:
  if (mapped)
    vg_lite_unmap(&b);
  if (init)
    vg_lite_close();
  if (cpu != MAP_FAILED)
    munmap(cpu, size);
  if (prime >= 0)
    close(prime);
  if (h && fd >= 0)
    drmModeDestroyDumbBuffer(fd, h);
  if (fd >= 0)
    close(fd);
  puts("DMABUF_END");
  return rc;
}

static int bench(unsigned dw, unsigned dh) {
  unsigned sw = dw / 2, sh = dh / 2;
  vg_lite_buffer_t s = {0}, d = {0};
  vg_lite_matrix_t m;
  uint16_t *ps = NULL, *pd = NULL;
  pixman_image_t *si = NULL, *di = NULL;
  pixman_transform_t t;
  uint64_t wall_start, cpu_start;
  int init = 0, rc = 1;
  ps = calloc((size_t)sw * sh, 2);
  pd = calloc((size_t)dw * dh, 2);
  if (!ps || !pd)
    goto out;
  quads_cpu(ps, sw, sh);
  if (vg(vg_lite_init(dw, dh), "bench init"))
    goto out;
  init = 1;
  if (alloc565(&s, sw, sh) || alloc565(&d, dw, dh) || quads_gpu(&s, sw, sh) ||
      vg(vg_lite_identity(&m), "bench identity") || vg(vg_lite_scale(2, 2, &m), "bench scale"))
    goto out;
  si = pixman_image_create_bits(PIXMAN_r5g6b5, sw, sh, (uint32_t *)ps, sw * 2);
  di = pixman_image_create_bits(PIXMAN_r5g6b5, dw, dh, (uint32_t *)pd, dw * 2);
  if (!si || !di) {
    fputs("pixman allocation failed\n", stderr);
    goto out;
  }
  pixman_transform_init_scale(&t, pixman_double_to_fixed(.5), pixman_double_to_fixed(.5));
  pixman_image_set_transform(si, &t);
  pixman_image_set_filter(si, PIXMAN_FILTER_NEAREST, NULL, 0);
  if (vg(vg_lite_blit(&d, &s, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "GPU warmup") ||
      vg(vg_lite_finish(), "GPU warmup finish"))
    goto out;
  pixman_image_composite32(PIXMAN_OP_SRC, si, NULL, di, 0, 0, 0, 0, 0, 0, dw, dh);
  if (check_quads("bench-gpu", d.memory, d.stride, dw, dh) ||
      check_quads("bench-pixman", pd, dw * 2, dw, dh)) {
    fputs("BENCHMARK_ASSERTION_FAILED matched nonuniform nearest output\n", stderr);
    goto out;
  }
  for (unsigned round = 1; round <= ROUNDS; round++) {
    uint64_t finish_wall, finish_cpu, batch_wall, batch_cpu, pix_wall, pix_cpu;

    wall_start = now_ns(CLOCK_MONOTONIC);
    cpu_start = now_ns(CLOCK_PROCESS_CPUTIME_ID);
    for (int i = 0; i < FINISH_ITERS; i++) {
      if (vg(vg_lite_blit(&d, &s, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT),
             "GPU latency blit") ||
          vg(vg_lite_finish(), "GPU latency finish"))
        goto out;
    }
    finish_wall = now_ns(CLOCK_MONOTONIC) - wall_start;
    finish_cpu = now_ns(CLOCK_PROCESS_CPUTIME_ID) - cpu_start;

    wall_start = now_ns(CLOCK_MONOTONIC);
    cpu_start = now_ns(CLOCK_PROCESS_CPUTIME_ID);
    for (int i = 0; i < ITERS; i++)
      if (vg(vg_lite_blit(&d, &s, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT),
             "GPU batch blit"))
        goto out;
    if (vg(vg_lite_finish(), "GPU batch finish"))
      goto out;
    batch_wall = now_ns(CLOCK_MONOTONIC) - wall_start;
    batch_cpu = now_ns(CLOCK_PROCESS_CPUTIME_ID) - cpu_start;

    wall_start = now_ns(CLOCK_MONOTONIC);
    cpu_start = now_ns(CLOCK_PROCESS_CPUTIME_ID);
    for (int i = 0; i < ITERS; i++)
      pixman_image_composite32(PIXMAN_OP_SRC, si, NULL, di, 0, 0, 0, 0, 0, 0, dw, dh);
    pix_wall = now_ns(CLOCK_MONOTONIC) - wall_start;
    pix_cpu = now_ns(CLOCK_PROCESS_CPUTIME_ID) - cpu_start;

    printf("BENCHMARK round=%u geometry=%ux%u-to-%ux%u "
           "gpu_finish_wall_ns_per_op=%" PRIu64 " gpu_finish_cpu_ns_per_op=%" PRIu64 " "
           "gpu_batch_wall_ns_per_op=%" PRIu64 " gpu_batch_cpu_ns_per_op=%" PRIu64 " "
           "pixman_wall_ns_per_op=%" PRIu64 " pixman_cpu_ns_per_op=%" PRIu64 "\n",
           round, sw, sh, dw, dh, finish_wall / FINISH_ITERS, finish_cpu / FINISH_ITERS,
           batch_wall / ITERS, batch_cpu / ITERS, pix_wall / ITERS, pix_cpu / ITERS);
  }
  rc = 0;
out:
  if (di)
    pixman_image_unref(di);
  if (si)
    pixman_image_unref(si);
  if (d.handle)
    vg_lite_free(&d);
  if (s.handle)
    vg_lite_free(&s);
  if (init)
    vg_lite_close();
  free(pd);
  free(ps);
  return rc;
}
static int benchmark(void) {
  int rc;
  puts("BENCHMARK_BEGIN");
  rc = bench(DW, DH) | bench(568, 1232);
  puts(rc ? "BENCHMARK_END failure" : "BENCHMARK_END pass");
  return rc;
}
int main(int ac, char **av) {
  const char *m = ac > 1 ? av[1] : "all", *n = ac > 2 ? av[2] : "/dev/dri/renderD128";
  int bad = 0;
  printf("VGLITE_VALIDATION_BEGIN mode=%s\n", m);
  if (!strcmp(m, "rgb565") || !strcmp(m, "all"))
    bad |= rgb565();
  if (!strcmp(m, "alpha") || !strcmp(m, "all"))
    bad |= alpha();
  if (!strcmp(m, "dmabuf") || !strcmp(m, "all"))
    bad |= dmabuf(n);
  if (!strcmp(m, "benchmark") || !strcmp(m, "all"))
    bad |= benchmark();
  if (strcmp(m, "all") && strcmp(m, "rgb565") && strcmp(m, "alpha") && strcmp(m, "dmabuf") &&
      strcmp(m, "benchmark")) {
    fputs("usage: k230-vglite-validation [all|rgb565|alpha|dmabuf|benchmark] [drm-node]\n", stderr);
    bad = 1;
  }
  printf("VGLITE_VALIDATION_%s\n", bad ? "FAIL" : "PASS");
  return !!bad;
}
