/* C ABI of libk230_ttfx_boot.a (feature "fw"); see nix/ttfx-boot/src/fw.rs.
 * Freestanding riscv64imac, soft-float.  The host provides an arena, a panic hook and
 * (compiler-supplied) memcpy/memset/memcmp. */
#ifndef TTFX_BOOT_H
#define TTFX_BOOT_H
#include <stddef.h>
#include <stdint.h>

struct ttfx_fw_handle;

/* Hand the allocator its arena (>= 64 KiB; the effects peak at 1-13 MiB, see
 * docs/evidence/boot-text-effects/nostd-feasibility.md).  0 on success. */
int ttfx_fw_init(void *arena, size_t len);

/* Start a run of a named effect over `text` (UTF-8) with a seed on a cols x rows
 * canvas.  NULL for an unknown effect, bad text or no memory. */
struct ttfx_fw_handle *ttfx_fw_new(const char *effect, size_t effect_len,
				   const char *text, size_t text_len,
				   uint64_t seed, int cols, int rows, int fps);

/* Next frame: its length (> 0) with *out set to ANSI text valid until the next
 * call (the format tfx_parse_frame in src/textfx.c reads); 0 when complete. */
long ttfx_fw_next(struct ttfx_fw_handle *h, const uint8_t **out);
uint32_t ttfx_fw_frames(const struct ttfx_fw_handle *h);
void ttfx_fw_free(struct ttfx_fw_handle *h);

/* Provided by the host: called on a Rust panic, expected not to return. */
void ttfx_fw_panic(const char *msg, size_t len);
#endif
