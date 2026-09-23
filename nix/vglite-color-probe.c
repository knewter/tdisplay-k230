/* Private allocations only: no DRM, scanout, service or renderer changes.
 * This is a format diagnostic, not a compositor/cache/performance acceptance. */
#include <vg_lite.h>
#include <pixman.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum { WIDTH = 256, HEIGHT = 8, ROUNDS = 3 };

static int checked(vg_lite_error_t error, const char *operation) {
  if (error) fprintf(stderr, "%s failed: %d\n", operation, error);
  return error != VG_LITE_SUCCESS;
}

static uint32_t pixel(unsigned x, unsigned y, unsigned round, unsigned alpha) {
  unsigned v = (x + 37 * round) % 256;
  unsigned r = 0, g = 0, b = 0;
  switch (y) {
    case 0: r = v; break;
    case 1: g = v; break;
    case 2: b = v; break;
    case 3: r = g = b = v; break;
    case 4: r = v; g = 255 - v; b = (v * 29) % 256; break;
    case 5: r = 32; g = 112; b = 176; break;
    case 6: r = 224; g = 144; b = 32; break;
    case 7: r = g = b = x % 2 ? 255 : 0; break;
  }
  /* Native little-endian RGBA bytes, same upload layout as the renderer. */
  return alpha << 24 | b << 16 | g << 8 | r;
}

static int run_case(vg_lite_buffer_format_t format, const char *name,
                    unsigned alpha, unsigned round, unsigned *mismatches) {
  vg_lite_buffer_t source = { .width = WIDTH, .height = HEIGHT, .format = format };
  vg_lite_buffer_t target = { .width = WIDTH, .height = HEIGHT, .format = VG_LITE_BGR565 };
  uint32_t input[WIDTH * HEIGHT];
  uint16_t expected[WIDTH * HEIGHT];
  pixman_image_t *cpu_source = NULL, *cpu_target = NULL;
  vg_lite_matrix_t matrix;
  int rc = 1;
  if (checked(vg_lite_allocate(&source), "allocate source") ||
      checked(vg_lite_allocate(&target), "allocate target")) goto out;
  if (!source.memory || !target.memory || source.stride < WIDTH * 4 ||
      target.stride < WIDTH * 2 || source.height != HEIGHT || target.height != HEIGHT) {
    fprintf(stderr, "unexpected allocation layout\n");
    goto out;
  }
  memset(source.memory, 0, (size_t)source.stride * HEIGHT);
  for (unsigned y = 0; y < HEIGHT; y++) {
    for (unsigned x = 0; x < WIDTH; x++) input[y * WIDTH + x] = pixel(x, y, round, alpha);
    memcpy((uint8_t *)source.memory + y * source.stride, input + y * WIDTH, WIDTH * 4);
  }
  memset(expected, 0, sizeof expected);
  cpu_source = pixman_image_create_bits_no_clear(PIXMAN_a8b8g8r8, WIDTH, HEIGHT, input, WIDTH * 4);
  cpu_target = pixman_image_create_bits_no_clear(PIXMAN_r5g6b5, WIDTH, HEIGHT,
                                               (uint32_t *)expected, WIDTH * 2);
  if (!cpu_source || !cpu_target) goto out;
  pixman_image_composite32(PIXMAN_OP_SRC, cpu_source, NULL, cpu_target,
                          0, 0, 0, 0, 0, 0, WIDTH, HEIGHT);
  /* SDK blit cleans the CPU-uploaded source; finish invalidates its target.
   * Never dirty the GPU target from the CPU before submission. */
  if (checked(vg_lite_identity(&matrix), "identity") ||
      checked(vg_lite_blit(&target, &source, &matrix, VG_LITE_BLEND_NONE, 0,
                           VG_LITE_FILTER_POINT), "blit")) {
    if (checked(vg_lite_finish(), "finish after blit error")) return 2;
    goto out;
  }
  /* A failed finish does not prove quiescence: let the bounded process exit
   * without freeing possibly in-flight allocations. */
  if (checked(vg_lite_finish(), "finish")) return 2;
  unsigned bad = 0;
  printf("{\"format\":\"%s\",\"alpha\":%u,\"round\":%u,\"first_mismatches\":[", name, alpha, round);
  for (unsigned y = 0; y < HEIGHT; y++) {
    for (unsigned x = 0; x < WIDTH; x++) {
      uint16_t actual;
      memcpy(&actual, (uint8_t *)target.memory + y * target.stride + x * 2, sizeof actual);
      if (actual != expected[y * WIDTH + x]) {
        if (bad < 8) printf("%s{\"x\":%u,\"y\":%u,\"rgba\":%u,\"expected\":%u,\"actual\":%u}",
                            bad ? "," : "", x, y, input[y * WIDTH + x], expected[y * WIDTH + x], actual);
        bad++;
      }
    }
  }
  printf("],\"pixels\":%u,\"mismatches\":%u,\"source_stride\":%d,\"target_stride\":%d}\n",
         WIDTH * HEIGHT, bad, source.stride, target.stride);
  fflush(stdout);
  *mismatches += bad;
  rc = 0;
out:
  if (cpu_source) pixman_image_unref(cpu_source);
  if (cpu_target) pixman_image_unref(cpu_target);
  if (source.handle && checked(vg_lite_free(&source), "free source")) rc = 1;
  if (target.handle && checked(vg_lite_free(&target), "free target")) rc = 1;
  return rc;
}

int main(void) {
  unsigned mismatches = 0;
  const unsigned alphas[] = {255, 128, 0};
  if (checked(vg_lite_init(WIDTH, HEIGHT), "init")) return 1;
  for (unsigned round = 0; round < ROUNDS; round++) {
    for (unsigned a = 0; a < sizeof alphas / sizeof alphas[0]; a++) {
      for (unsigned format = 0; format < 2; format++) {
        int rc = run_case(format ? VG_LITE_RGBX8888 : VG_LITE_RGBA8888,
                          format ? "RGBX8888" : "RGBA8888", alphas[a], round, &mismatches);
        if (rc) {
          if (rc != 2) checked(vg_lite_close(), "close after failure");
          return rc;
        }
      }
    }
  }
  if (checked(vg_lite_close(), "close")) return 1;
  printf("{\"diagnostic\":\"completed\",\"cases\":18,\"total_mismatches\":%u}\n", mismatches);
  return mismatches ? 3 : 0;
}
