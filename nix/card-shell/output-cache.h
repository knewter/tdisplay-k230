/* One logical output image owned by one physical output-buffer wrapper.
 * A failed/interrupted/ordinary pass invalidates contents before reuse. */
#ifndef K230_OUTPUT_CACHE_H
#define K230_OUTPUT_CACHE_H
#include "k230_quarter_turn.h"
#ifndef K230_OUTPUT_ALLOC
#define K230_OUTPUT_ALLOC malloc
#endif
#ifndef K230_OUTPUT_FREE
#define K230_OUTPUT_FREE free
#endif
#ifndef K230_OUTPUT_IMAGE
#define K230_OUTPUT_IMAGE pixman_image_create_bits_no_clear
#endif
struct k230_output_cache {
    pixman_image_t *image;
    void *data;
    size_t bytes;
    int width, height, transform;
    pixman_format_code_t format;
    bool valid;
};
static inline void k230_output_cache_finish(struct k230_output_cache *cache) {
    if (cache->image) pixman_image_unref(cache->image);
    if (cache->data) K230_OUTPUT_FREE(cache->data);
    *cache = (struct k230_output_cache){0};
}
static inline void k230_output_cache_invalidate(struct k230_output_cache *cache) {
    cache->valid = false;
}
static inline pixman_image_t *k230_output_cache_begin(struct k230_output_cache *cache,
        int width, int height, pixman_format_code_t format, int transform, bool *preserved) {
    *preserved = false;
    int cpp = k230_turn_cpp(format);
    if (!cpp || (transform != 1 && transform != 3) || width <= 0 || height <= 0 ||
            width > 16384 || height > 16384) {
        cache->valid = false;
        return NULL;
    }
    int stride = (width*cpp+3)&~3;
    size_t bytes = (size_t)stride*height;
    if (bytes > 64u*1024u*1024u) {
        cache->valid = false;
        return NULL;
    }
    if (cache->image && cache->width == width && cache->height == height &&
            cache->format == format && cache->transform == transform) {
        *preserved = cache->valid;
        cache->valid = false; /* No reuse claim until submit succeeds. */
        return cache->image;
    }
    k230_output_cache_finish(cache);
    void *data = K230_OUTPUT_ALLOC(bytes);
    if (!data) return NULL;
    pixman_image_t *image = K230_OUTPUT_IMAGE(format, width, height, data, stride);
    if (!image) { K230_OUTPUT_FREE(data); return NULL; }
    *cache = (struct k230_output_cache){.image=image, .data=data, .bytes=bytes,
        .width=width, .height=height, .transform=transform, .format=format};
    return image;
}
static inline void k230_output_cache_submitted(struct k230_output_cache *cache, bool okay) {
    cache->valid = okay && cache->image != NULL;
}
#endif
