/* Host test of src/game_of_life.c.  See docs/evidence/game-of-life/host-engine.txt. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "game_of_life.h"

static int failures;
static int checks;

#define CHECK(cond)                                                        \
	do {                                                               \
		checks++;                                                  \
		if (!(cond)) {                                             \
			failures++;                                        \
			printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
		}                                                          \
	} while (0)

/* Golden values for seed GOL_TEST_SEED. */
#define GOL_TEST_SEED 0x4b323330u
/* Grid hashes were cross-checked against an independent numpy implementation. */
static const uint32_t gold_g[] = { 0x1f4282cfu, 0x1fe9ba21u, 0x423d0509u, 0xbffecefeu, 0x4c333a18u };
static const uint32_t gold_f[] = { 0xe2b0edc5u, 0x70718dc5u, 0x1da5cec5u, 0x8ffbdbc5u, 0xe21bf5c5u };

static struct gol_grid ga, gb;
static struct gol_state st, st2;
static uint8_t rec[GOL_RECORD_BYTES];
static uint8_t fb[GOL_PANEL_H * GOL_PANEL_W * 4u];
static uint8_t fb16[GOL_PANEL_H * GOL_PANEL_W * 2u];

static void run_n(struct gol_state *s, unsigned n)
{
	while (n--)
		gol_state_advance(s);
}

static void test_rules(void)
{
	unsigned x, y;

	/* Block is a still life. */
	memset(&ga, 0, sizeof ga);
	gol_set(&ga, 10, 10, 1); gol_set(&ga, 11, 10, 1);
	gol_set(&ga, 10, 11, 1); gol_set(&ga, 11, 11, 1);
	gol_step(&gb, &ga);
	CHECK(memcmp(&ga, &gb, sizeof ga) == 0);

	/* Blinker has period 2 and is not static. */
	memset(&ga, 0, sizeof ga);
	for (x = 20; x < 23; x++)
		gol_set(&ga, x, 30, 1);
	gol_step(&gb, &ga);
	CHECK(memcmp(&ga, &gb, sizeof ga) != 0);
	CHECK(gol_get(&gb, 21, 29) && gol_get(&gb, 21, 30) && gol_get(&gb, 21, 31));
	CHECK(gol_population(&gb) == 3);
	gol_step(&ga, &gb);
	CHECK(gol_get(&ga, 20, 30) && gol_get(&ga, 21, 30) && gol_get(&ga, 22, 30));

	/* Glider moves (+1,+1) every 4 generations, across the torus seam. */
	memset(&ga, 0, sizeof ga);
	gol_insert_glider(&ga, GOL_W - 1u, GOL_H - 1u);
	CHECK(gol_population(&ga) == 5);
	st.grid = ga;
	st.generation = 0;
	run_n(&st, 4);
	memset(&gb, 0, sizeof gb);
	gol_insert_glider(&gb, 0, 0);
	CHECK(memcmp(&st.grid, &gb, sizeof gb) == 0);
	run_n(&st, 4);
	CHECK(gol_population(&st.grid) == 5);

	/* Edges wrap in both axes: a blinker straddling x=0. */
	memset(&ga, 0, sizeof ga);
	gol_set(&ga, GOL_W - 1u, 5, 1); gol_set(&ga, 0, 5, 1); gol_set(&ga, 1, 5, 1);
	gol_step(&gb, &ga);
	CHECK(gol_get(&gb, 0, 4) && gol_get(&gb, 0, 5) && gol_get(&gb, 0, 6));
	CHECK(gol_population(&gb) == 3);
	/* Bits beyond GOL_W in each row stay clear after any step. */
	for (y = 0; y < GOL_H; y++)
		CHECK((gb.bits[y * GOL_ROW_BYTES + GOL_ROW_BYTES - 1u] >> (GOL_W % 8u)) == 0);
}

static void test_seed(void)
{
	struct gol_grid a, b, c;

	gol_seed_default(&a, GOL_TEST_SEED);
	gol_seed_default(&b, GOL_TEST_SEED);
	gol_seed_default(&c, GOL_TEST_SEED + 1u);
	CHECK(memcmp(&a, &b, sizeof a) == 0);
	CHECK(memcmp(&a, &c, sizeof a) != 0);
	CHECK(gol_population(&a) > 1000);
	/* seed 0 is remapped, not an empty grid. */
	gol_seed_default(&c, 0);
	CHECK(gol_population(&c) > 1000);
}

static void test_pixels(void)
{
	unsigned cx = 99, cy = 99;

	CHECK(gol_pixel_to_cell(0, 0, &cx, &cy) && cx == 0 && cy == 0);
	CHECK(gol_pixel_to_cell(567, 1231, &cx, &cy) && cx == 141 && cy == 307);
	CHECK(gol_pixel_to_cell(283, 600, &cx, &cy) && cx == 70 && cy == 150);
	cx = cy = 99;
	CHECK(!gol_pixel_to_cell(568, 0, &cx, &cy) && cx == 99 && cy == 99);
	CHECK(!gol_pixel_to_cell(0, 1232, &cx, &cy));
	CHECK(GOL_PANEL_W == 568u && GOL_PANEL_H == 1232u);
}

static void test_record(void)
{
	enum gol_status r;
	uint8_t bad[GOL_RECORD_BYTES];

	gol_state_init_default(&st, 0xabcd1234u, GOL_TEST_SEED);
	run_n(&st, 7);
	st.owner = GOL_OWNER_UBOOT;
	st.frame_generation = 7;
	gol_record_encode(&st, rec);
	CHECK(rec[0] == 'K' && rec[1] == '2' && rec[2] == '3' && rec[3] == 'L');

	r = gol_record_decode(&st2, rec, sizeof rec, 0xabcd1234u);
	CHECK(r == GOL_OK);
	CHECK(st2.generation == 7 && st2.frame_generation == 7 && st2.seed == GOL_TEST_SEED);
	CHECK(st2.owner == GOL_OWNER_UBOOT && st2.boot_instance == 0xabcd1234u);
	CHECK(memcmp(&st.grid, &st2.grid, sizeof st.grid) == 0);
	/* Continuation: resumed state equals uninterrupted run. */
	run_n(&st, 5);
	run_n(&st2, 5);
	CHECK(memcmp(&st.grid, &st2.grid, sizeof st.grid) == 0 && st.generation == 12);

	/* Every invalid case is rejected with a specific status. */
	gol_record_encode(&st, rec);
	CHECK(gol_record_decode(&st2, rec, sizeof rec, 0x1u) == GOL_BAD_INSTANCE);
	CHECK(gol_record_decode(&st2, rec, GOL_RECORD_BYTES - 1u, 0) == GOL_BAD_LENGTH);
	CHECK(gol_record_decode(&st2, rec, 8, 0) == GOL_BAD_MAGIC);
	memcpy(bad, rec, sizeof bad); bad[0] ^= 1;
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_MAGIC);
	memcpy(bad, rec, sizeof bad); bad[4] = 2;
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_VERSION);
	memcpy(bad, rec, sizeof bad); bad[8] ^= 4;
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_LENGTH);
	memcpy(bad, rec, sizeof bad); bad[24] ^= 1;
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_DIMENSIONS);
	memcpy(bad, rec, sizeof bad); bad[GOL_RECORD_HEADER_BYTES + 100] ^= 0x10;
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_CHECKSUM);
	memcpy(bad, rec, sizeof bad); bad[16] ^= 1;
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_CHECKSUM);
	memset(bad, 0, sizeof bad);
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_MAGIC);
	memset(bad, 0xff, sizeof bad);
	CHECK(gol_record_decode(&st2, bad, sizeof bad, 0) == GOL_BAD_MAGIC);
	/* A zero boot instance is never a valid same-boot record. */
	st.boot_instance = 0;
	gol_record_encode(&st, rec);
	CHECK(gol_record_decode(&st2, rec, sizeof rec, 0) == GOL_BAD_INSTANCE);
}

static void test_render(void)
{
	unsigned i;
	size_t stride = GOL_PANEL_W * 4u;
	uint32_t h1, h2;

	gol_state_init_default(&st, 1, GOL_TEST_SEED);
	gol_render_xrgb(&st.grid, fb, stride);
	h1 = gol_frame_hash_xrgb(fb, stride);
	gol_render_xrgb(&st.grid, fb, stride);
	h2 = gol_frame_hash_xrgb(fb, stride);
	CHECK(h1 == h2);
	/* Cell (0,0) block pixels and a known live cell render as the colours. */
	for (i = 0; i < GOL_PANEL_W * GOL_PANEL_H; i++) {
		unsigned px = i % GOL_PANEL_W, py = i / GOL_PANEL_W;
		unsigned live = (unsigned)gol_get(&st.grid, px / GOL_CELL_PX, py / GOL_CELL_PX);
		const uint8_t *p = fb + (size_t)py * stride + (size_t)px * 4u;
		uint32_t v = (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 |
			     (uint32_t)p[3] << 24;

		if (v != (live ? GOL_COLOR_ON : GOL_COLOR_OFF)) {
			CHECK(0);
			break;
		}
	}
	/* Padding bytes in a wider stride do not change the hash. */
	{
		static uint8_t wide[GOL_PANEL_H * (GOL_PANEL_W * 4u + 64u)];
		size_t ws = GOL_PANEL_W * 4u + 64u;

		memset(wide, 0xa5, sizeof wide);
		gol_render_xrgb(&st.grid, wide, ws);
		CHECK(gol_frame_hash_xrgb(wide, ws) == h1);
	}
	/* Differential redraw equals a full redraw, over several generations. */
	{
		struct gol_state d;
		unsigned g, redrawn = 0;

		gol_state_init_default(&d, 1, GOL_TEST_SEED);
		gol_render_xrgb(&d.grid, fb, stride);
		for (g = 0; g < 12; g++) {
			struct gol_grid before = d.grid;

			gol_state_advance(&d);
			redrawn += gol_render_xrgb_diff(&before, &d.grid, fb, stride);
		}
		h1 = gol_frame_hash_xrgb(fb, stride);
		gol_render_xrgb(&d.grid, fb, stride);
		CHECK(h1 == gol_frame_hash_xrgb(fb, stride));
		CHECK(redrawn > 0 && redrawn < 12u * GOL_W * GOL_H / 4u);
	}
	gol_render_rgb565(&st.grid, fb16, GOL_PANEL_W * 2u);
	CHECK(fb16[0] == (uint8_t)(((0xe8u >> 3) << 11 | (0xf0u >> 2) << 5 | 0xffu >> 3) & 0xff) ||
	      !gol_get(&st.grid, 0, 0));
}

int main(void)
{
	size_t stride = GOL_PANEL_W * 4u;
	static const unsigned marks[] = { 0, 1, 10, 100, 500 };
	unsigned m, gen = 0;

	test_rules();
	test_seed();
	test_pixels();
	test_record();
	test_render();

	/* Reproducible frame hashes for the default build seed. */
	gol_state_init_default(&st, 1, GOL_TEST_SEED);
	printf("engine: grid %ux%u cells, %u px/cell, panel %ux%u, record %u bytes, abi %u\n",
	       GOL_W, GOL_H, GOL_CELL_PX, GOL_PANEL_W, GOL_PANEL_H, GOL_RECORD_BYTES,
	       GOL_ABI_VERSION);
	printf("seed 0x%08x\n", GOL_TEST_SEED);
	for (m = 0; m < sizeof marks / sizeof marks[0]; m++) {
		uint32_t gh, fh;

		run_n(&st, marks[m] - gen);
		gen = marks[m];
		gol_render_xrgb(&st.grid, fb, stride);
		gh = gol_grid_hash(&st.grid);
		fh = gol_frame_hash_xrgb(fb, stride);
		printf("gen %4u pop %5u grid-hash %08x frame-hash %08x\n", gen,
		       gol_population(&st.grid), gh, fh);
		CHECK(gh == gold_g[m]);
		CHECK(fh == gold_f[m]);
	}
	/* Same run again from scratch must give identical hashes (determinism). */
	{
		struct gol_state a;
		uint32_t h;

		gol_state_init_default(&a, 99, GOL_TEST_SEED);
		run_n(&a, 100);
		h = gol_grid_hash(&a.grid);
		gol_state_init_default(&st, 1, GOL_TEST_SEED);
		run_n(&st, 100);
		CHECK(h == gol_grid_hash(&st.grid));
	}
	printf("%d checks, %d failures\n", checks, failures);
	printf(failures ? "FAIL\n" : "PASS\n");
	return failures ? 1 : 0;
}
