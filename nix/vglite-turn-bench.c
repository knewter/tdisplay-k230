/*
 * Standalone output-turn benchmark for the-compositor-rotates-scanout-on-the-gpu
 * task 1.1. Private buffers only: no DRM master, modeset, framebuffer or plane
 * API. The destination is a DRM dumb buffer (the same kind of memory sway's
 * scanout buffers are) that is created, written, imported by VG-Lite and freed
 * here; it is never attached to a CRTC.
 *
 * Compares, for one full 1232x568 RGB565 frame turned into 568x1232:
 *   cpu_heap   k230_turn_copy_rect (the compositor's CPU turn) into heap memory
 *   cpu_dumb   the same into the dumb buffer's CPU mapping (scanout-like memory)
 *   gpu        vg_lite_blit with a 90 degree matrix from a contiguous VG-Lite
 *              source (dirtied by the CPU before each pass, as a freshly
 *              composited scratch image would be) into the imported dumb buffer
 * The GPU output is compared byte for byte against the CPU turn first.
 * The SDK's vg_lite_blit cleans the source cache and vg_lite_finish
 * invalidates the target; both are inside the timings.
 */
#define _GNU_SOURCE
#include "quarter-turn.h"
#include "vg_lite.h"
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

enum { SW = 1232, SH = 568, DW = 568, DH = 1232, PADW = 576, ROUNDS = 3 };

static uint64_t now_ns(clockid_t c) {
  struct timespec t;
  clock_gettime(c, &t);
  return (uint64_t)t.tv_sec * 1000000000ull + t.tv_nsec;
}

static int vg(vg_lite_error_t e, const char *s) {
  if (!e)
    return 0;
  fprintf(stderr, "%s: VG-Lite error %d\n", s, e);
  return -1;
}

struct acc {
  uint64_t wall, cpu, submit, finish;
};

static void report(const char *mode, unsigned round, unsigned reps, const struct acc *a) {
  printf("TURN_BENCH mode=%s round=%u reps=%u wall_ns_per_frame=%" PRIu64
         " cpu_ns_per_frame=%" PRIu64 " submit_ns=%" PRIu64 " finish_ns=%" PRIu64 "\n",
         mode, round, reps, a->wall / reps, a->cpu / reps, a->submit / reps, a->finish / reps);
}

/* Touch every 64-byte line so a freshly CPU-written scratch image is dirty. */
static void dirty(uint8_t *p, size_t n, unsigned salt) {
  for (size_t i = 0; i < n; i += 64)
    p[i] = (uint8_t)(i + salt);
}

int main(int argc, char **argv) {
  int transform = argc > 1 ? atoi(argv[1]) : 1;
  const char *node = argc > 2 ? argv[2] : "/dev/dri/card0";
  unsigned reps = argc > 3 ? (unsigned)atoi(argv[3]) : 100;
  int rc = 1, fd = -1, prime = -1, init = 0, mapped = 0;
  uint32_t h = 0, pitch = 0;
  uint64_t size = 0, off = 0;
  uint8_t *dumb = MAP_FAILED, *heap_src = NULL, *heap_dst = NULL, *golden = NULL;
  vg_lite_buffer_t src = {0}, dst = {0}, land = {0};
  vg_lite_matrix_t m;
  pixman_box32_t box = {0, 0, SW, SH};
  size_t src_stride;

  if (transform != 1 && transform != 3) {
    fputs("usage: k230-vglite-turn-bench [1|3] [drm-node] [reps]\n", stderr);
    return 2;
  }
  puts("TURN_BENCH_BEGIN");
  printf("TURN_BENCH_CONFIG transform=%d src=%dx%d dst=%dx%d padded_storage_width=%d reps=%u\n",
         transform, SW, SH, DW, DH, PADW, reps);

  fd = open(node, O_RDWR | O_CLOEXEC);
  if (fd < 0) {
    perror(node);
    goto out;
  }
  if (drmModeCreateDumbBuffer(fd, PADW, DH, 16, 0, &h, &pitch, &size) ||
      drmPrimeHandleToFD(fd, h, DRM_CLOEXEC | DRM_RDWR, &prime) ||
      drmModeMapDumbBuffer(fd, h, &off)) {
    perror("dumb buffer");
    goto out;
  }
  dumb = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, off);
  if (dumb == MAP_FAILED) {
    perror("mmap dumb");
    goto out;
  }
  printf("TURN_BENCH_DUMB pitch=%" PRIu32 " size=%" PRIu64 "\n", pitch, size);
  if (!getenv("BENCH_NOCLEAR"))
    memset(dumb, 0, size);

  if (vg(vg_lite_init(DW, DH), "init"))
    goto out;
  init = 1;
  src.width = SW;
  src.height = SH;
  src.format = VG_LITE_BGR565;
  if (vg(vg_lite_allocate(&src), "allocate source"))
    goto out;
  src_stride = src.stride;
  dst.width = DW;
  dst.height = DH;
  dst.stride = pitch;
  dst.format = VG_LITE_BGR565;
  dst.memory = dumb;
  if (vg(vg_lite_map(&dst, VG_LITE_MAP_DMABUF, prime), "map dumb"))
    goto out;
  mapped = 1;
  printf("TURN_BENCH_SOURCE stride=%zu\n", src_stride);
  land.width = SW;
  land.height = SH;
  land.format = VG_LITE_BGR565;
  if (vg(vg_lite_allocate(&land), "allocate landscape control"))
    goto out;

  heap_src = aligned_alloc(64, src_stride * SH);
  heap_dst = aligned_alloc(64, (size_t)pitch * DH);
  golden = aligned_alloc(64, (size_t)pitch * DH);
  if (!heap_src || !heap_dst || !golden)
    goto out;
  for (size_t i = 0; i < src_stride * SH; i++)
    ((uint8_t *)src.memory)[i] = heap_src[i] = (uint8_t)((i * 2654435761u) >> 13);
  memset(heap_dst, 0, (size_t)pitch * DH);

  /* Reference turn and correctness: GPU must equal the CPU turn exactly. */
  k230_turn_copy_rect(golden, heap_src, SW, SH, 2, (int)pitch, (int)src_stride, transform, box);
  vg_lite_identity(&m);
  if (transform == 1) { /* dx = y, dy = W-1-x */
    m.m[0][0] = 0; m.m[0][1] = 1; m.m[0][2] = 0;
    m.m[1][0] = -1; m.m[1][1] = 0; m.m[1][2] = (float)SW;
  } else { /* dx = H-1-y, dy = x */
    m.m[0][0] = 0; m.m[0][1] = -1; m.m[0][2] = (float)SH;
    m.m[1][0] = 1; m.m[1][1] = 0; m.m[1][2] = 0;
  }
  if (!getenv("BENCH_NOCLEAR"))
    memset(dumb, 0, size);
  if ((!getenv("BENCH_NOCLEAR") && vg(vg_lite_clear(&dst, NULL, 0), "clear dst")) ||
      vg(vg_lite_blit(&dst, &src, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "warmup blit") ||
      vg(vg_lite_finish(), "warmup finish"))
    goto out;
  {
    size_t bad = 0, row_first_bad = (size_t)-1;
    for (size_t y = 0; y < DH; y++)
      if (memcmp(golden + y * pitch, dumb + y * pitch, DW * 2)) {
        bad++;
        if (row_first_bad == (size_t)-1)
          row_first_bad = y;
      }
    printf("TURN_BENCH_CHECK gpu_vs_cpu_turn bad_rows=%zu of %d first_bad_row=%zd\n", bad, DH,
           (ssize_t)row_first_bad);
    if (bad) {
      size_t shown = 0;
      for (size_t y = 0; y < DH && shown < 3; y++)
        if (memcmp(golden + y * pitch, dumb + y * pitch, DW * 2)) {
          size_t px = 0, firstx = (size_t)-1;
          for (size_t x = 0; x < DW; x++)
            if (memcmp(golden + y * pitch + x * 2, dumb + y * pitch + x * 2, 2)) {
              px++;
              if (firstx == (size_t)-1)
                firstx = x;
            }
          printf("TURN_BENCH_CHECK_ROW y=%zu bad_pixels=%zu first_bad_x=%zd\n", y, px, (ssize_t)firstx);
          if (firstx != (size_t)-1) {
            uint16_t g, d;
            memcpy(&g, golden + y * pitch + firstx * 2, 2);
            memcpy(&d, dumb + y * pitch + firstx * 2, 2);
            printf("TURN_BENCH_CHECK_PIXEL y=%zu x=%zu cpu=0x%04x gpu_buffer=0x%04x\n", y, firstx, g, d);
          }
          shown++;
        }
    }
    if (bad) {
      fputs("TURN_BENCH_FAIL GPU turn differs from CPU turn\n", stderr);
      goto out;
    }
  }

  for (unsigned round = 1; round <= ROUNDS; round++) {
    struct acc a;
    uint64_t w, c;

    memset(&a, 0, sizeof a);
    w = now_ns(CLOCK_MONOTONIC); c = now_ns(CLOCK_PROCESS_CPUTIME_ID);
    for (unsigned i = 0; i < reps; i++)
      k230_turn_copy_rect(heap_dst, heap_src, SW, SH, 2, (int)pitch, (int)src_stride, transform, box);
    a.wall = now_ns(CLOCK_MONOTONIC) - w; a.cpu = now_ns(CLOCK_PROCESS_CPUTIME_ID) - c;
    report("cpu_heap", round, reps, &a);

    memset(&a, 0, sizeof a);
    w = now_ns(CLOCK_MONOTONIC); c = now_ns(CLOCK_PROCESS_CPUTIME_ID);
    for (unsigned i = 0; i < reps; i++)
      k230_turn_copy_rect(dumb, heap_src, SW, SH, 2, (int)pitch, (int)src_stride, transform, box);
    a.wall = now_ns(CLOCK_MONOTONIC) - w; a.cpu = now_ns(CLOCK_PROCESS_CPUTIME_ID) - c;
    report("cpu_dumb", round, reps, &a);

    /* GPU, source dirtied by the CPU before each pass (dirtying not timed). */
    memset(&a, 0, sizeof a);
    for (unsigned i = 0; i < reps; i++) {
      uint64_t w0, c0, w1, w2, c2;
      dirty(src.memory, src_stride * SH, i);
      w0 = now_ns(CLOCK_MONOTONIC); c0 = now_ns(CLOCK_PROCESS_CPUTIME_ID);
      if (vg(vg_lite_blit(&dst, &src, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "blit"))
        goto out;
      w1 = now_ns(CLOCK_MONOTONIC);
      if (vg(vg_lite_finish(), "finish"))
        goto out;
      w2 = now_ns(CLOCK_MONOTONIC); c2 = now_ns(CLOCK_PROCESS_CPUTIME_ID);
      a.wall += w2 - w0; a.cpu += c2 - c0; a.submit += w1 - w0; a.finish += w2 - w1;
    }
    report("gpu_dirty_source", round, reps, &a);

    /* GPU, source untouched since the last pass (SDK clean has nothing to write back). */
    memset(&a, 0, sizeof a);
    for (unsigned i = 0; i < reps; i++) {
      uint64_t w0, c0, w1, w2, c2;
      w0 = now_ns(CLOCK_MONOTONIC); c0 = now_ns(CLOCK_PROCESS_CPUTIME_ID);
      if (vg(vg_lite_blit(&dst, &src, &m, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "blit"))
        goto out;
      w1 = now_ns(CLOCK_MONOTONIC);
      if (vg(vg_lite_finish(), "finish"))
        goto out;
      w2 = now_ns(CLOCK_MONOTONIC); c2 = now_ns(CLOCK_PROCESS_CPUTIME_ID);
      a.wall += w2 - w0; a.cpu += c2 - c0; a.submit += w1 - w0; a.finish += w2 - w1;
    }
    report("gpu_clean_source", round, reps, &a);
  }
  /* Control: same-size landscape copy (no rotation) to separate rotation cost from
   * raw read/write bandwidth. */
  {
    vg_lite_matrix_t id;
    vg_lite_identity(&id);
    for (unsigned round = 1; round <= ROUNDS; round++) {
      struct acc a;
      memset(&a, 0, sizeof a);
      for (unsigned i = 0; i < reps; i++) {
        uint64_t w0, c0, w1, w2, c2;
        w0 = now_ns(CLOCK_MONOTONIC); c0 = now_ns(CLOCK_PROCESS_CPUTIME_ID);
        if (vg(vg_lite_blit(&land, &src, &id, VG_LITE_BLEND_NONE, 0, VG_LITE_FILTER_POINT), "ctl blit"))
          goto out;
        w1 = now_ns(CLOCK_MONOTONIC);
        if (vg(vg_lite_finish(), "ctl finish"))
          goto out;
        w2 = now_ns(CLOCK_MONOTONIC); c2 = now_ns(CLOCK_PROCESS_CPUTIME_ID);
        a.wall += w2 - w0; a.cpu += c2 - c0; a.submit += w1 - w0; a.finish += w2 - w1;
      }
      report("gpu_landscape_copy_control", round, reps, &a);
    }
  }
  rc = 0;
out:
  if (land.handle)
    vg_lite_free(&land);
  if (mapped)
    vg_lite_unmap(&dst);
  if (src.handle)
    vg_lite_free(&src);
  if (init)
    vg_lite_close();
  if (dumb != MAP_FAILED)
    munmap(dumb, size);
  if (prime >= 0)
    close(prime);
  if (h && fd >= 0)
    drmModeDestroyDumbBuffer(fd, h);
  if (fd >= 0)
    close(fd);
  free(heap_src); free(heap_dst); free(golden);
  puts(rc ? "TURN_BENCH_END failure" : "TURN_BENCH_END pass");
  return rc;
}
