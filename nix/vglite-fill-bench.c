/*
 * Shell-style fills on VG-Lite versus the shell's CPU path (cairo/pixman), plus the
 * CPU-then-GPU cache hazard, for the-compositor-rotates-scanout-on-the-gpu follow-up.
 * Private contiguous buffers only; no DRM. ARGB8888 like the shell client's wl_shm
 * frames (premultiplied, byte order B,G,R,A = VG_LITE_BGRA8888).
 *
 * usage: k230-vglite-fill-bench WIDTH HEIGHT [reps] [tess]
 * Ops per frame: gradient (full-frame vertical linear gradient, opaque), cards
 * (rounded rects, alpha 0.95 OVER), image (a grid-sized ARGB layer OVER, the pixman
 * rvv_composite_over_8888_8888 cost that dominates the client profile), scene (all
 * three in that order). Each GPU result is compared with the cairo render.
 * Mixed: CPU gradient, then GPU cards+image into the same buffer, with and without an
 * explicit clean+invalidate between (the hazard of the standalone turn benchmark).
 */
#define _GNU_SOURCE
#include "thead.h"
#include "vg_lite.h"
#include <cairo.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

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

static int W, H, BAND, NCARDS;
static const int CARD_H = 56, CARD_GAP = 8, CARD_R = 14, CARD_MARGIN = 24;
/* Source colours; cards alpha 0.95 */
static const float G0[3] = {0.12f, 0.12f, 0.18f}, G1[3] = {0.25f, 0.12f, 0.25f};
static const float CARD[4] = {0.90f, 0.95f, 1.00f, 0.95f};

/* ---------- CPU (cairo) ---------- */
static void cpu_gradient(cairo_t *cr) {
  cairo_pattern_t *p = cairo_pattern_create_linear(0, 0, 0, H);
  cairo_pattern_add_color_stop_rgb(p, 0, G0[0], G0[1], G0[2]);
  cairo_pattern_add_color_stop_rgb(p, 1, G1[0], G1[1], G1[2]);
  cairo_set_source(cr, p);
  cairo_paint(cr);
  cairo_pattern_destroy(p);
}
static void rrect(cairo_t *cr, double x, double y, double w, double h, double r) {
  cairo_new_sub_path(cr);
  cairo_arc(cr, x + w - r, y + r, r, -M_PI / 2, 0);
  cairo_arc(cr, x + w - r, y + h - r, r, 0, M_PI / 2);
  cairo_arc(cr, x + r, y + h - r, r, M_PI / 2, M_PI);
  cairo_arc(cr, x + r, y + r, r, M_PI, 3 * M_PI / 2);
  cairo_close_path(cr);
}
static void card_xy(int i, double *x, double *y, double *w, double *h) {
  *x = CARD_MARGIN; *y = 16 + i * (CARD_H + CARD_GAP); *w = W - 2 * CARD_MARGIN; *h = CARD_H;
}
static void cpu_cards(cairo_t *cr) {
  cairo_set_source_rgba(cr, CARD[0], CARD[1], CARD[2], CARD[3]);
  for (int i = 0; i < NCARDS; i++) {
    double x, y, w, h;
    card_xy(i, &x, &y, &w, &h);
    rrect(cr, x, y, w, h, CARD_R);
    cairo_fill(cr);
  }
}
static void cpu_image(cairo_t *cr, cairo_surface_t *grid) {
  cairo_set_source_surface(cr, grid, 0, H - BAND);
  cairo_paint(cr);
}

/* ---------- GPU (VG-Lite) ---------- */
static float *rrect_path(float *p, float x, float y, float w, float h, float r) {
  const float k = 0.5522847498f * r;
  uint32_t *op;
#define OP(v) do { op = (uint32_t *)p; *op = (v); p++; } while (0)
#define PT(a, b) do { *p++ = (a); *p++ = (b); } while (0)
  OP(VLC_OP_MOVE); PT(x + r, y);
  OP(VLC_OP_LINE); PT(x + w - r, y);
  OP(VLC_OP_CUBIC); PT(x + w - r + k, y); PT(x + w, y + r - k); PT(x + w, y + r);
  OP(VLC_OP_LINE); PT(x + w, y + h - r);
  OP(VLC_OP_CUBIC); PT(x + w, y + h - r + k); PT(x + w - r + k, y + h); PT(x + w - r, y + h);
  OP(VLC_OP_LINE); PT(x + r, y + h);
  OP(VLC_OP_CUBIC); PT(x + r - k, y + h); PT(x, y + h - r + k); PT(x, y + h - r);
  OP(VLC_OP_LINE); PT(x, y + r);
  OP(VLC_OP_CUBIC); PT(x, y + r - k); PT(x + r - k, y); PT(x + r, y);
  OP(VLC_OP_CLOSE);
  OP(VLC_OP_END);
  return p;
}
static vg_lite_color_t abgr(float r, float g, float b, float a) {
  /* premultiplied, 0xAABBGGRR as the SDK probe uses */
  uint32_t R = (uint32_t)(r * a * 255 + .5f), G = (uint32_t)(g * a * 255 + .5f),
           B = (uint32_t)(b * a * 255 + .5f), A = (uint32_t)(a * 255 + .5f);
  return (A << 24) | (B << 16) | (G << 8) | R;
}
static vg_lite_float_t *paths_buf;
static vg_lite_path_t card_paths[64];
static vg_lite_path_t rect_path;
static float rect_data[32];
static vg_lite_linear_gradient_t grad;

static int gpu_setup(void) {
  uint32_t ramps[2] = {0xff000000u | ((uint32_t)(G0[2] * 255 + .5f) << 16) | ((uint32_t)(G0[1] * 255 + .5f) << 8) | (uint32_t)(G0[0] * 255 + .5f),
                       0xff000000u | ((uint32_t)(G1[2] * 255 + .5f) << 16) | ((uint32_t)(G1[1] * 255 + .5f) << 8) | (uint32_t)(G1[0] * 255 + .5f)};
  uint32_t stops[2] = {0, 255};
  vg_lite_matrix_t *m;
  float *p = rect_data;
  uint32_t *op;
  OP(VLC_OP_MOVE); PT(0, 0);
  OP(VLC_OP_LINE); PT((float)W, 0);
  OP(VLC_OP_LINE); PT((float)W, (float)H);
  OP(VLC_OP_LINE); PT(0, (float)H);
  OP(VLC_OP_CLOSE);
  OP(VLC_OP_END);
  if (vg(vg_lite_init_path(&rect_path, VG_LITE_FP32, VG_LITE_HIGH, (uint32_t)((char *)p - (char *)rect_data),
                           rect_data, 0, 0, (float)W, (float)H), "init rect path"))
    return -1;
  paths_buf = calloc((size_t)NCARDS, 48 * sizeof(float));
  for (int i = 0; i < NCARDS; i++) {
    double x, y, w, h;
    float *s = (float *)((char *)paths_buf + (size_t)i * 48 * sizeof(float)), *e;
    card_xy(i, &x, &y, &w, &h);
    e = rrect_path(s, (float)x, (float)y, (float)w, (float)h, (float)CARD_R);
    if (vg(vg_lite_init_path(&card_paths[i], VG_LITE_FP32, VG_LITE_HIGH, (uint32_t)((char *)e - (char *)s), s,
                             (float)x, (float)y, (float)(x + w), (float)(y + h)), "init card path"))
      return -1;
  }
  memset(&grad, 0, sizeof grad);
  if (vg(vg_lite_init_grad(&grad), "init grad") || vg(vg_lite_set_grad(&grad, 2, ramps, stops), "set grad") ||
      vg(vg_lite_update_grad(&grad), "update grad"))
    return -1;
  m = vg_lite_get_grad_matrix(&grad);
  vg_lite_identity(m);
  /* gradient space x in [0,255] -> screen y in [0,H) ; x' unused */
  m->m[0][0] = 0; m->m[0][1] = -1; m->m[0][2] = 0;
  m->m[1][0] = (float)H / 256.0f; m->m[1][1] = 0; m->m[1][2] = 0;
  return 0;
}
static int gpu_gradient(vg_lite_buffer_t *d) {
  vg_lite_matrix_t id;
  vg_lite_identity(&id);
  return vg(vg_lite_draw_gradient(d, &rect_path, VG_LITE_FILL_NON_ZERO, &id, &grad, VG_LITE_BLEND_NONE), "draw gradient");
}
static int gpu_cards(vg_lite_buffer_t *d) {
  vg_lite_matrix_t id;
  vg_lite_color_t c = abgr(CARD[0], CARD[1], CARD[2], CARD[3]);
  vg_lite_identity(&id);
  for (int i = 0; i < NCARDS; i++)
    if (vg(vg_lite_draw(d, &card_paths[i], VG_LITE_FILL_NON_ZERO, &id, VG_LITE_BLEND_SRC_OVER, c), "draw card"))
      return -1;
  return 0;
}
static int gpu_image(vg_lite_buffer_t *d, vg_lite_buffer_t *g) {
  vg_lite_matrix_t m;
  vg_lite_identity(&m);
  vg_lite_translate(0, (float)(H - BAND), &m);
  return vg(vg_lite_blit(d, g, &m, VG_LITE_BLEND_SRC_OVER, 0, VG_LITE_FILTER_POINT), "blit image");
}

struct acc { uint64_t wall, cpu, submit, finish; };
static void rep(const char *op, const char *impl, unsigned reps, const struct acc *a) {
  printf("FILL_BENCH geometry=%dx%d op=%s impl=%s reps=%u wall_ns=%" PRIu64 " cpu_ns=%" PRIu64 " submit_ns=%" PRIu64
         " finish_ns=%" PRIu64 "\n", W, H, op, impl, reps, a->wall / reps, a->cpu / reps, a->submit / reps, a->finish / reps);
}

/* compare ARGB8888 frames; tolerance per channel */
static void compare(const char *tag, const uint8_t *a, const uint8_t *b, int stride_a, int stride_b, int tol, int y0, int y1) {
  size_t bad = 0, total = 0;
  int maxd = 0;
  for (int y = y0; y < y1; y++)
    for (int x = 0; x < W * 4; x++) {
      int d = abs((int)a[(size_t)y * stride_a + x] - (int)b[(size_t)y * stride_b + x]);
      total++;
      if (d > maxd) maxd = d;
      if (d > tol) bad++;
    }
  printf("FILL_CHECK geometry=%dx%d %s tol=%d bad_bytes=%zu of %zu max_diff=%d\n", W, H, tag, tol, bad, total, maxd);
}

int main(int argc, char **argv) {
  unsigned reps, tess;
  vg_lite_buffer_t dst = {0}, grid = {0};
  cairo_surface_t *refs = NULL, *cs = NULL, *gs = NULL;
  cairo_t *rc = NULL;
  uint8_t *ref = NULL;
  int ok = 1;

  if (argc < 3) { fputs("usage: k230-vglite-fill-bench W H [reps] [tess]\n", stderr); return 2; }
  W = atoi(argv[1]); H = atoi(argv[2]);
  reps = argc > 3 ? (unsigned)atoi(argv[3]) : 30;
  tess = argc > 4 ? (unsigned)atoi(argv[4]) : 256;
  BAND = H > 420 ? 418 : H;
  NCARDS = (H - 32) / (CARD_H + CARD_GAP);
  if (NCARDS > 60) NCARDS = 60;
  printf("FILL_BENCH_CONFIG geometry=%dx%d cards=%d grid_band=%d reps=%u tess=%u\n", W, H, NCARDS, BAND, reps, tess);

  if (vg(vg_lite_init(tess, tess), "init")) return 1;
  dst.width = W; dst.height = H; dst.format = VG_LITE_BGRA8888;
  grid.width = W; grid.height = BAND; grid.format = VG_LITE_BGRA8888;
  if (vg(vg_lite_allocate(&dst), "alloc dst") || vg(vg_lite_allocate(&grid), "alloc grid")) goto out;
  {
    int pm = argc > 5 ? atoi(argv[5]) : 1;
    printf("FILL_BENCH_PREMULTIPLY src=%d dst=%d\n", pm, pm);
    if (vg(vg_lite_set_premultiply((vg_lite_uint8_t)pm, (vg_lite_uint8_t)pm), "set premultiply")) goto out;
  }
  if (gpu_setup()) goto out;
  printf("FILL_BENCH_BUFFERS stride=%u grid_stride=%u\n", dst.stride, grid.stride);

  /* grid layer: sparse 96x96 discs with alpha, premultiplied by cairo */
  gs = cairo_image_surface_create_for_data(grid.memory, CAIRO_FORMAT_ARGB32, W, BAND, grid.stride);
  {
    cairo_t *g = cairo_create(gs);
    cairo_set_operator(g, CAIRO_OPERATOR_CLEAR); cairo_paint(g); cairo_set_operator(g, CAIRO_OPERATOR_OVER);
    for (int gy = 0; gy < BAND / 112; gy++)
      for (int gx = 0; gx < W / 112; gx++) {
        cairo_set_source_rgba(g, 0.2 + 0.1 * (gx % 5), 0.6, 0.9 - 0.1 * (gy % 4), 0.85);
        cairo_arc(g, gx * 112 + 56, gy * 112 + 56, 40, 0, 2 * M_PI);
        cairo_fill(g);
      }
    cairo_destroy(g);
  }
  cairo_surface_flush(gs);
  vg_lite_buffer_t *gp = &grid;
  thead_csi_dcache_clean_invalid_range(grid.memory, (uint64_t)grid.stride * BAND);

  cs = cairo_image_surface_create_for_data(dst.memory, CAIRO_FORMAT_ARGB32, W, H, dst.stride);
  rc = cairo_create(cs);
  ref = aligned_alloc(64, (size_t)dst.stride * H);
  refs = cairo_image_surface_create_for_data(ref, CAIRO_FORMAT_ARGB32, W, H, dst.stride);
  {
    cairo_t *r = cairo_create(refs);
    cpu_gradient(r); cpu_cards(r); cpu_image(r, gs);
    cairo_destroy(r);
    cairo_surface_flush(refs);
  }

  /* correctness, per op then scene */
  {
    const char *names[4] = {"gradient", "cards", "image", "scene"};
    for (int k = 0; k < 4; k++) {
      cairo_t *r = cairo_create(refs);
      memset(ref, 0, (size_t)dst.stride * H);
      if (k >= 1) { if (k != 3) { cairo_set_source_rgb(r, G0[0], G0[1], G0[2]); cairo_paint(r); } }
      if (k == 0 || k == 3) cpu_gradient(r);
      if (k == 1 || k == 3) cpu_cards(r);
      if (k == 2 || k == 3) cpu_image(r, gs);
      cairo_destroy(r); cairo_surface_flush(refs);
      /* GPU: start from the same background */
      if (k == 1 || k == 2) {
        vg_lite_color_t bg = abgr(G0[0], G0[1], G0[2], 1.0f);
        if (vg(vg_lite_clear(&dst, NULL, bg), "bg clear")) goto out;
      } else {
        vg_lite_clear(&dst, NULL, 0);
      }
      if ((k == 0 || k == 3) && gpu_gradient(&dst)) goto out;
      if ((k == 1 || k == 3) && gpu_cards(&dst)) goto out;
      if ((k == 2 || k == 3) && gpu_image(&dst, gp)) goto out;
      if (vg(vg_lite_finish(), "finish")) goto out;
      compare(names[k], dst.memory, ref, dst.stride, dst.stride, 6, 0, H);
    }
  }

  /* timing */
  {
    const char *ops[4] = {"gradient", "cards", "image", "scene"};
    for (int k = 0; k < 4; k++) {
      struct acc a;
      uint64_t w, c;
      memset(&a, 0, sizeof a);
      w = now_ns(CLOCK_MONOTONIC); c = now_ns(CLOCK_PROCESS_CPUTIME_ID);
      for (unsigned i = 0; i < reps; i++) {
        if (k == 0 || k == 3) cpu_gradient(rc);
        if (k == 1 || k == 3) cpu_cards(rc);
        if (k == 2 || k == 3) cpu_image(rc, gs);
        cairo_surface_flush(cs);
      }
      a.wall = now_ns(CLOCK_MONOTONIC) - w; a.cpu = now_ns(CLOCK_PROCESS_CPUTIME_ID) - c;
      rep(ops[k], "cpu_cairo", reps, &a);

      memset(&a, 0, sizeof a);
      for (unsigned i = 0; i < reps; i++) {
        uint64_t w0 = now_ns(CLOCK_MONOTONIC), c0 = now_ns(CLOCK_PROCESS_CPUTIME_ID), w1, w2, c2;
        if ((k == 0 || k == 3) && gpu_gradient(&dst)) goto out;
        if ((k == 1 || k == 3) && gpu_cards(&dst)) goto out;
        if ((k == 2 || k == 3) && gpu_image(&dst, gp)) goto out;
        w1 = now_ns(CLOCK_MONOTONIC);
        if (vg(vg_lite_finish(), "finish")) goto out;
        w2 = now_ns(CLOCK_MONOTONIC); c2 = now_ns(CLOCK_PROCESS_CPUTIME_ID);
        a.wall += w2 - w0; a.cpu += c2 - c0; a.submit += w1 - w0; a.finish += w2 - w1;
      }
      rep(ops[k], "gpu_vglite", reps, &a);
    }
  }

  /* mixed CPU+GPU hazard: CPU gradient, then GPU cards+image on the same buffer */
  for (int variant = 0; variant < 2; variant++) {
    int bad_runs = 0;
    for (int run = 0; run < 5; run++) {
      cairo_t *r = cairo_create(refs);
      memset(ref, 0, (size_t)dst.stride * H);
      cpu_gradient(r); cpu_cards(r); cpu_image(r, gs);
      cairo_destroy(r); cairo_surface_flush(refs);
      cpu_gradient(rc);                 /* CPU writes the whole buffer */
      cairo_surface_flush(cs);
      if (variant == 1)
        thead_csi_dcache_clean_invalid_range(dst.memory, (uint64_t)dst.stride * H);
      if (gpu_cards(&dst) || gpu_image(&dst, gp) || vg(vg_lite_finish(), "finish")) goto out;
      {
        size_t bad = 0;
        for (int y = 0; y < H; y++)
          for (int x = 0; x < W * 4; x++)
            if (abs((int)((uint8_t *)dst.memory)[(size_t)y * dst.stride + x] - (int)ref[(size_t)y * dst.stride + x]) > 6) bad++;
        printf("FILL_MIXED geometry=%dx%d variant=%s run=%d bad_bytes=%zu\n", W, H,
               variant ? "explicit_clean_between" : "no_clean_between", run, bad);
        if (bad > (size_t)W * H / 20) bad_runs++;
      }
    }
    printf("FILL_MIXED_SUMMARY geometry=%dx%d variant=%s runs_with_large_mismatch=%d of 5\n", W, H,
           variant ? "explicit_clean_between" : "no_clean_between", bad_runs);
  }
  ok = 0;
out:
  if (grad.image.handle) vg_lite_clear_grad(&grad);
  if (rc) cairo_destroy(rc);
  if (cs) cairo_surface_destroy(cs);
  if (gs) cairo_surface_destroy(gs);
  if (refs) cairo_surface_destroy(refs);
  free(ref); free(paths_buf);
  if (dst.handle) vg_lite_free(&dst);
  if (grid.handle) vg_lite_free(&grid);
  vg_lite_close();
  puts(ok ? "FILL_BENCH_END failure" : "FILL_BENCH_END pass");
  return ok;
}
