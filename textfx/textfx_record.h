/*
 * Hand-off record payload for the text-effects source (id 2) and the per-boot
 * selection helpers (openspec change the-boot-plays-terminal-text-effects,
 * design decisions D5 and D11).  Freestanding C: <stdint.h>, <stddef.h> only.
 *
 * The 40-byte common prefix of the generic boot-frame record (magic, ABI
 * version, length, boot-instance token, source id at byte 30, checksum) belongs
 * to src/boot_frame.h and is written around this payload by that code.
 *
 * Payload, little-endian, 60 bytes:
 *    0 u64 seed             8 u16 cols      10 u16 rows     12 u16 fps
 *   14 u16 flags           16 u32 last frame drawn
 *   20 u32 cell-grid hash of that frame (tfx_grid_hash)
 *   24 u32 engine id        28 u32 text hash (FNV-1a of the text bytes)
 *   32 u16 text id (index into the build-time list, 0xffff = from the environment)
 *   34 u16 orientation (0 portrait, 1 landscape: see enum tfx_rot)
 *   36 char effect[24], NUL padded
 */
#ifndef TEXTFX_RECORD_H
#define TEXTFX_RECORD_H

#include <stddef.h>
#include <stdint.h>

#define TFX_REC_PAYLOAD_BYTES 60u
#define TFX_REC_EFFECT_LEN 24u
#define TFX_REC_TEXT_ENV 0xffffu

/* Orientation of the picture on the panel, decided by stage 1 from the keyboard base:
 * portrait with no base, the landscape of the shell's `transform 270` with one. */
#define TFX_REC_ORIENT_PORTRAIT 0u
#define TFX_REC_ORIENT_LANDSCAPE 1u

#define TFX_REC_FLAG_REPLAY 0x0001u   /* stage 1 played the pre-rendered fallback */
#define TFX_REC_FLAG_OVERRIDE 0x0002u /* effect, text or seed came from the environment */

struct tfx_run_desc {
	uint64_t seed;
	uint16_t cols, rows, fps, flags;
	uint32_t last_frame, cell_hash, engine_id, text_hash;
	uint16_t text_id;
	uint16_t orientation; /* TFX_REC_ORIENT_* */
	char effect[TFX_REC_EFFECT_LEN];
};

/* Returns TFX_REC_PAYLOAD_BYTES, or 0 if max is too small or effect is not NUL-terminated. */
size_t tfx_rec_encode(const struct tfx_run_desc *d, uint8_t *out, size_t max);
/* 0 on success; -1 if len is wrong, dimensions are zero or the effect name is unterminated/empty. */
int tfx_rec_decode(struct tfx_run_desc *d, const uint8_t *in, size_t len);

/* ---- per-boot selection ---- */

/* The seed for a boot: a splitmix64 mix of a timer reading, a clock reading and an
 * environment value (any may be 0).  Never returns 0. */
uint64_t tfx_seed_mix(uint64_t ticks, uint64_t clock, uint64_t env);

struct tfx_choice {
	unsigned effect_index, text_index;
};
/* Indices into lists of n_effects and n_texts entries (both > 0), a pure function of seed. */
void tfx_select(uint64_t seed, unsigned n_effects, unsigned n_texts, struct tfx_choice *out);

/* A list of texts in one buffer: entries separated by a line holding only "%%". */
struct tfx_text {
	const char *text;
	size_t len; /* without the separator line, with the final newline kept */
};
/* Fills out[] (capacity max) and returns the number of entries; empty entries are skipped. */
unsigned tfx_texts_parse(const char *buf, size_t len, struct tfx_text *out, unsigned max);
uint32_t tfx_text_hash(const char *text, size_t len);

#endif
