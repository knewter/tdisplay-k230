/*
 * Host run of the exact stage-1 loop (src/boot_life_stage1.c) against a fake
 * framebuffer and record window.  Prints the published state dump kept in
 * docs/evidence/game-of-life/uboot-state-host.txt.  Host evidence only:
 * it says nothing about U-Boot's caches, the panel, or the real RAM window.
 *
 *   cc -std=c11 -Wall -Wextra -Werror -I src tests/test_boot_life_stage1.c \
 *      src/boot_life_stage1.c src/boot_frame.c src/game_of_life.c -o /tmp/test-boot-life-stage1
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "boot_life_stage1.h"

static int failures, checks;
#define CHECK(c)                                                              \
	do {                                                                  \
		checks++;                                                     \
		if (!(c)) {                                                   \
			failures++;                                           \
			printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); \
		}                                                             \
	} while (0)

#define WINDOW 0x2000u
#define GUARD 64u

struct ctr {
	size_t fb_bytes;
	unsigned flushes, fb_flushes, rec_flushes, delays, delay_ms_total;
	const void *fb, *rec;
};

static void flush(void *ctx, const void *p, size_t n)
{
	struct ctr *c = ctx;

	(void)n;
	c->flushes++;
	if ((const char *)p >= (const char *)c->fb &&
	    (const char *)p < (const char *)c->fb + (size_t)GOL_PANEL_W * 4u * GOL_PANEL_H)
		c->fb_flushes++, c->fb_bytes += n;
	if (p == c->rec)
		c->rec_flushes++;
}

static void delay_ms(void *ctx, unsigned ms)
{
	struct ctr *c = ctx;

	c->delays++;
	c->delay_ms_total += ms;
}

static void hexdump(const uint8_t *p, size_t n)
{
	size_t i;

	for (i = 0; i < n; i += 16) {
		size_t j;

		printf("  %04zx:", i);
		for (j = i; j < i + 16 && j < n; j++)
			printf(" %02x", p[j]);
		printf("\n");
	}
}

int main(void)
{
	static uint8_t fb[GOL_PANEL_H * GOL_PANEL_W * 4u];
	static uint8_t ref[GOL_PANEL_H * GOL_PANEL_W * 4u];
	static uint8_t mem[GUARD + WINDOW + GUARD];
	uint8_t *window = mem + GUARD;
	struct ctr c = { .fb = fb, .rec = window };
	struct boot_life_ops ops = { &c, flush, delay_ms };
	struct boot_life_cfg cfg = { fb, window, WINDOW, 0x1badb002u, 0x4b323330u, 40, 50 };
	struct boot_life_result r;
	struct gol_state dec, ref_state;
	size_t stride = GOL_PANEL_W * 4u;
	size_t i;

	/* A rejected configuration writes nothing at all. */
	memset(mem, 0xee, sizeof mem);
	cfg.boot_instance = 0;
	CHECK(boot_life_stage1_run(&cfg, &ops, &r) == -1);
	cfg.boot_instance = 0x1badb002u;
	cfg.record_window = GOL_RECORD_BYTES - 1u;
	CHECK(boot_life_stage1_run(&cfg, &ops, &r) == -1);
	cfg.record_window = WINDOW;
	for (i = 0; i < sizeof mem; i++)
		if (mem[i] != 0xee) {
			CHECK(0);
			break;
		}

	memset(mem, 0xee, sizeof mem);
	CHECK(boot_life_stage1_run(&cfg, &ops, &r) == 0);
	printf("stage-1 host run: instance 0x%08x seed 0x%08x frames %u frame_ms %u\n",
	       cfg.boot_instance, cfg.seed, cfg.frames, cfg.frame_ms);
	printf("result: generation %u, grid-hash %08x, differential cells redrawn %u\n",
	       r.generation, r.grid_hash, r.cells_redrawn);
	printf("flushed framebuffer bytes: %zu of %zu if every frame were flushed whole\n", c.fb_bytes,
	       (size_t)41 * GOL_PANEL_W * 4u * GOL_PANEL_H);
	CHECK(c.fb_bytes < (size_t)41 * GOL_PANEL_W * 4u * GOL_PANEL_H);
	printf("callbacks: %u flushes (%u framebuffer, %u record), %u delays totalling %u ms\n",
	       c.flushes, c.fb_flushes, c.rec_flushes, c.delays, c.delay_ms_total);
	CHECK(r.generation == 40 && r.instance == 0x1badb002u);
	CHECK(c.delays == 40 && c.delay_ms_total == 2000);
	CHECK(c.fb_flushes == 41 && c.rec_flushes == 42); /* 41 publishes + 1 invalidation */

	/* Window guards untouched; bytes past the record inside the window untouched. */
	for (i = 0; i < GUARD; i++)
		CHECK(mem[i] == 0xee && mem[GUARD + WINDOW + i] == 0xee);
	for (i = GOL_RECORD_BYTES; i < WINDOW; i++)
		if (window[i] != 0xee) {
			CHECK(0);
			break;
		}

	/* What Linux will read back. */
	CHECK(gol_record_decode(&dec, window, WINDOW, cfg.boot_instance) == GOL_OK);
	CHECK(dec.generation == 40 && dec.frame_generation == 40 && dec.owner == GOL_OWNER_UBOOT);
	CHECK(dec.seed == cfg.seed && gol_grid_hash(&dec.grid) == r.grid_hash);
	CHECK(gol_record_decode(&dec, window, WINDOW, cfg.boot_instance + 2u) == GOL_BAD_INSTANCE);

	/* The record equals an uninterrupted engine run, and the framebuffer equals a full redraw. */
	gol_state_init_default(&ref_state, 1, cfg.seed);
	for (i = 0; i < 40; i++)
		gol_state_advance(&ref_state);
	CHECK(memcmp(&ref_state.grid, &dec.grid, sizeof dec.grid) == 0);
	gol_render_xrgb(&ref_state.grid, ref, stride);
	CHECK(gol_frame_hash_xrgb(fb, stride) == gol_frame_hash_xrgb(ref, stride));
	printf("final frame hash %08x (equals a full redraw of generation 40: %s)\n",
	       gol_frame_hash_xrgb(fb, stride),
	       gol_frame_hash_xrgb(fb, stride) == gol_frame_hash_xrgb(ref, stride) ? "yes" : "NO");

	printf("published record header (first 64 bytes of %u):\n", GOL_RECORD_BYTES);
	hexdump(window, 64);
	printf("record fields: magic %.4s abi %u length %u instance 0x%08x generation %u "
	       "frame_generation %u owner %u\n",
	       (const char *)window, window[4], window[8] | window[9] << 8, cfg.boot_instance,
	       dec.generation, dec.frame_generation, dec.owner);

	/* Linux-side fallbacks over this very record. */
	{
		uint8_t bad[GOL_RECORD_BYTES];

		memcpy(bad, window, sizeof bad);
		bad[4] = 2;
		printf("fallback check, version 2: %s\n",
		       gol_status_name(gol_record_decode(&dec, bad, sizeof bad, cfg.boot_instance)));
		CHECK(gol_record_decode(&dec, bad, sizeof bad, cfg.boot_instance) == GOL_BAD_VERSION);
		memcpy(bad, window, sizeof bad);
		bad[GOL_RECORD_HEADER_BYTES + 7] ^= 1;
		printf("fallback check, flipped cell bit: %s\n",
		       gol_status_name(gol_record_decode(&dec, bad, sizeof bad, cfg.boot_instance)));
		CHECK(gol_record_decode(&dec, bad, sizeof bad, cfg.boot_instance) == GOL_BAD_CHECKSUM);
	}

	/* Incremental (cyclic) form: the record is valid and consistent after every frame,
	 * and stopping at any point leaves a resumable state. */
	{
		struct bf_source isrc = { 0 };
		struct bf_session sess;
		struct bf_ops bops = { &c, flush, delay_ms };
		struct bf_cfg bc;
		struct gol_state mid;
		unsigned k, delays_before = c.delays;

		/* Reuse the Life producer through its public entry by running 0 frames first. */
		(void)isrc;
		memset(mem, 0xee, sizeof mem);
		cfg.frames = 0;
		CHECK(boot_life_stage1_run(&cfg, &ops, &r) == 0 && r.generation == 0);
		bc.target.fb = fb;
		bc.target.stride_bytes = stride;
		bc.target.width = GOL_PANEL_W;
		bc.target.height = GOL_PANEL_H;
		bc.record = window;
		bc.record_window = WINDOW;
		bc.boot_instance = 0x77u;
		bc.seed = cfg.seed;
		bc.frames = 5;
		bc.frame_ms = 50;
		CHECK(bf_begin(&sess, &bc, &bops, &boot_life_source) == 0);
		CHECK(gol_record_decode(&mid, window, WINDOW, 0x77u) == GOL_OK && mid.generation == 0);
		for (k = 1; k <= 5; k++) {
			int more = bf_advance(&sess);

			CHECK(more == (k < 5 ? 1 : 0));
			CHECK(gol_record_decode(&mid, window, WINDOW, 0x77u) == GOL_OK && mid.generation == k &&
			      mid.frame_generation == k);
		}
		CHECK(bf_advance(&sess) == 0); /* frames used up: no further drawing */
		CHECK(gol_record_decode(&mid, window, WINDOW, 0x77u) == GOL_OK && mid.generation == 5);
		CHECK(c.delays == delays_before); /* bf_advance never sleeps */
		printf("incremental session: 5 frames, record valid after each, no sleeps in bf_advance\n");
	}

	printf("%d checks, %d failures\n%s\n", checks, failures, failures ? "FAIL" : "PASS");
	return failures ? 1 : 0;
}
