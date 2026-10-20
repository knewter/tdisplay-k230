#ifndef K230_RGB565_PIXELS_H
#define K230_RGB565_PIXELS_H
#include <stdint.h>
static inline uint16_t k230_rgb565_pixel(uint32_t p) {
    return (uint16_t)(((p >> 8) & 0xf800) | ((p >> 5) & 0x07e0) | ((p >> 3) & 0x001f));
}
/* Two independent RGB lanes, first pixel in the low16 bits. */
static inline uint32_t k230_rgb565_pair(uint32_t first, uint32_t second) {
    uint64_t p = (uint64_t)first | (uint64_t)second << 32;
    uint64_t v = ((p >> 8) & UINT64_C(0x0000f8000000f800)) |
        ((p >> 5) & UINT64_C(0x000007e0000007e0)) |
        ((p >> 3) & UINT64_C(0x0000001f0000001f));
    return (uint32_t)v | (uint32_t)(v >> 16);
}
#endif
