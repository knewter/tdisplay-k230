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

int main(void)
{
  enum { source_width = 128, source_height = 128,
         target_width = 256, target_height = 256 };
  const vg_lite_color_t red = 0xffd02020u;
  vg_lite_buffer_t source = { 0 };
  vg_lite_buffer_t target = { 0 };
  vg_lite_matrix_t matrix;
  uint32_t first_pixel;
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

  if (check(vg_lite_clear(&source, NULL, red), "vg_lite_clear(source)"))
    goto out_target;
  if (check(vg_lite_clear(&target, NULL, 0), "vg_lite_clear(target)"))
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

  memcpy(&first_pixel, target.memory, sizeof(first_pixel));
  if (first_pixel == 0) {
    fprintf(stderr, "offscreen target remained zero after completed blit\n");
    goto out_target;
  }

  printf("VG-Lite offscreen RGBA blit-scale completed (first pixel 0x%08" PRIx32 ")\n",
         first_pixel);
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
