/*
 * Source-built offscreen-only VG-Lite diagnostic for the K230.
 *
 * It opens only /dev/vg_lite through libvg_lite, allocates two private DMA
 * buffers, clears one, scales it into the other, waits for completion, and
 * checks the destination changed.  It never opens /dev/dri, /dev/fb0, or a
 * display buffer.
 */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "vg_lite.h"

static int check(vg_lite_error_t result, const char *operation)
{
  if (result == VG_LITE_SUCCESS)
    return 0;
  fprintf(stderr, "%s: VG-Lite error %d\n", operation, result);
  return 1;
}

static uint32_t pixel_at(const vg_lite_buffer_t *buffer, uint32_t x, uint32_t y)
{
  uint32_t pixel;
  const uint8_t *address = buffer->memory + y * buffer->stride + x * 4;

  memcpy(&pixel, address, sizeof(pixel));
  return pixel;
}

static void print_pixel(const char *name, const vg_lite_buffer_t *buffer,
                        uint32_t x, uint32_t y)
{
  uint32_t pixel = pixel_at(buffer, x, y);
  const uint8_t *bytes = (const uint8_t *)&pixel;

  printf("%s x=%" PRIu32 " y=%" PRIu32 " raw=0x%08" PRIx32
         " bytes=%02" PRIx8 ":%02" PRIx8 ":%02" PRIx8 ":%02" PRIx8 "\n",
         name, x, y, pixel, bytes[0], bytes[1], bytes[2], bytes[3]);
}

int main(void)
{
  enum { source_width = 128, source_height = 128,
         target_width = 256, target_height = 256 };
  const vg_lite_color_t red = 0xffd02020u;
  vg_lite_buffer_t source = { 0 };
  vg_lite_buffer_t target = { 0 };
  vg_lite_matrix_t matrix;
  vg_lite_rectangle_t source_left = { 0, 0, source_width / 2, source_height };
  uint32_t source_red;
  uint32_t source_black;
  static const uint32_t rows[] = { 0, 63, 127, 255 };
  int rc = 1;

  if (check(vg_lite_init(target_width, target_height), "vg_lite_init"))
    goto out;

  source.width = source_width;
  source.height = source_height;
  source.format = VG_LITE_RGBA8888;
  if (check(vg_lite_allocate(&source), "vg_lite_allocate(source)"))
    goto out_close;

  target.width = target_width;
  target.height = target_height;
  target.format = VG_LITE_RGBA8888;
  if (check(vg_lite_allocate(&target), "vg_lite_allocate(target)"))
    goto out_source;

  if (check(vg_lite_clear(&source, NULL, 0), "vg_lite_clear(source)"))
    goto out_target;
  if (check(vg_lite_clear(&source, &source_left, red),
            "vg_lite_clear(source left half)"))
    goto out_target;
  if (check(vg_lite_clear(&target, NULL, 0xff304080u),
            "vg_lite_clear(target)"))
    goto out_target;
  if (check(vg_lite_identity(&matrix), "vg_lite_identity"))
    goto out_target;
  if (check(vg_lite_scale(2.0f, 2.0f, &matrix), "vg_lite_scale"))
    goto out_target;
  if (check(vg_lite_blit(&target, &source, &matrix, VG_LITE_BLEND_NONE, 0,
                         VG_LITE_FILTER_POINT), "vg_lite_blit"))
    goto out_target;
  if (check(vg_lite_finish(), "vg_lite_finish"))
    goto out_target;

  source_red = pixel_at(&source, 0, 0);
  source_black = pixel_at(&source, source_width - 1, 0);
  print_pixel("source", &source, 0, 0);
  print_pixel("source", &source, source_width - 1, 0);
  for (size_t i = 0; i < sizeof(rows) / sizeof(rows[0]); i++) {
    uint32_t y = rows[i];
    print_pixel("target", &target, 0, y);
    print_pixel("target", &target, 126, y);
    print_pixel("target", &target, 127, y);
    print_pixel("target", &target, 128, y);
    print_pixel("target", &target, 129, y);
    print_pixel("target", &target, 255, y);
  }
  if (source_red == 0 || source_black != 0) {
    fprintf(stderr, "source pattern did not contain red-left/black-right pixels\n");
    goto out_target;
  }
  for (size_t i = 0; i < sizeof(rows) / sizeof(rows[0]); i++) {
    uint32_t y = rows[i];
    if (pixel_at(&target, 0, y) != source_red ||
        pixel_at(&target, 127, y) != source_red ||
        pixel_at(&target, 128, y) != source_black ||
        pixel_at(&target, 255, y) != source_black) {
      fprintf(stderr, "scaled boundary mismatch on target row %" PRIu32 "\n", y);
      goto out_target;
    }
  }

  printf("VG-Lite offscreen RGBA 2x blit-scale completed (boundary verified)\n");
  rc = 0;

out_target:
  vg_lite_free(&target);
out_source:
  vg_lite_free(&source);
out_close:
  vg_lite_close();
out:
  return rc;
}
