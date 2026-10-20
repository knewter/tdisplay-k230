/* Bounds of actual immutable label texels. Keep layout/ellipsis at the full
 * authored size; zero ARGB margins contribute nothing to an unscaled OVER. */
#ifndef CARD_LABEL_INK_H
#define CARD_LABEL_INK_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
struct card_label_ink { int x, y, width, height; };
static inline bool card_label_ink_find(struct card_label_ink *ink,
        const void *pixels, size_t stride, int width, int height) {
    if (!ink || !pixels || width <= 0 || height <= 0 || width > 16384 ||
            height > 16384 || stride < (size_t)width * 4 ||
            stride > 64u*1024u*1024u/(unsigned)height) return false;
    int left = width, top = height, right = 0, bottom = 0;
    for (int y = 0; y < height; y++) {
        const uint8_t *row = (const uint8_t *)pixels + (size_t)y * stride;
        for (int x = 0; x < width; x++) {
            uint32_t pixel;
            memcpy(&pixel, row + (size_t)x * 4, sizeof(pixel));
            /* Test all channels, including malformed alpha-zero RGB. */
            if (!pixel) continue;
            if (x < left) left = x;
            if (y < top) top = y;
            if (x + 1 > right) right = x + 1;
            bottom = y + 1;
        }
    }
    *ink = right ? (struct card_label_ink){left, top, right-left, bottom-top} :
        (struct card_label_ink){0};
    return true;
}
#endif
