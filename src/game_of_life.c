#include "game_of_life.h"

#include <string.h>

int gol_get(const struct gol_grid *g, unsigned x, unsigned y)
{
	x %= GOL_W;
	y %= GOL_H;
	return (g->bits[y * GOL_ROW_BYTES + x / 8u] >> (x % 8u)) & 1;
}

void gol_set(struct gol_grid *g, unsigned x, unsigned y, int alive)
{
	uint8_t *b;

	x %= GOL_W;
	y %= GOL_H;
	b = &g->bits[y * GOL_ROW_BYTES + x / 8u];
	if (alive)
		*b = (uint8_t)(*b | (1u << (x % 8u)));
	else
		*b = (uint8_t)(*b & ~(1u << (x % 8u)));
}

void gol_step(struct gol_grid *dst, const struct gol_grid *src)
{
	unsigned x, y;

	memset(dst, 0, sizeof(*dst));
	for (y = 0; y < GOL_H; y++) {
		unsigned yu = (y + GOL_H - 1u) % GOL_H;
		unsigned yd = (y + 1u) % GOL_H;

		for (x = 0; x < GOL_W; x++) {
			unsigned xl = (x + GOL_W - 1u) % GOL_W;
			unsigned xr = (x + 1u) % GOL_W;
			unsigned n = (unsigned)gol_get(src, xl, yu) + (unsigned)gol_get(src, x, yu) +
				     (unsigned)gol_get(src, xr, yu) + (unsigned)gol_get(src, xl, y) +
				     (unsigned)gol_get(src, xr, y) + (unsigned)gol_get(src, xl, yd) +
				     (unsigned)gol_get(src, x, yd) + (unsigned)gol_get(src, xr, yd);
			int alive = gol_get(src, x, y);

			if (n == 3u || (alive && n == 2u))
				gol_set(dst, x, y, 1);
		}
	}
}

unsigned gol_population(const struct gol_grid *g)
{
	unsigned n = 0, i;

	for (i = 0; i < GOL_GRID_BYTES; i++) {
		uint8_t b = g->bits[i];

		while (b) {
			n += b & 1u;
			b = (uint8_t)(b >> 1);
		}
	}
	return n;
}

static uint32_t xorshift32(uint32_t *s)
{
	uint32_t x = *s;

	x ^= x << 13;
	x ^= x >> 17;
	x ^= x << 5;
	*s = x;
	return x;
}

void gol_seed_default(struct gol_grid *g, uint32_t seed)
{
	uint32_t rng = seed ? seed : 0x9e3779b9u;
	unsigned x, y;

	memset(g, 0, sizeof(*g));
	/* About 25% soup in the central band so the first frames are busy. */
	for (y = GOL_H / 4u; y < GOL_H - GOL_H / 4u; y++)
		for (x = GOL_W / 6u; x < GOL_W - GOL_W / 6u; x++)
			if ((xorshift32(&rng) & 3u) == 0u)
				gol_set(g, x, y, 1);
	/* R-pentomino at the centre. */
	x = GOL_W / 2u;
	y = GOL_H / 2u;
	gol_set(g, x + 1u, y, 1);
	gol_set(g, x + 2u, y, 1);
	gol_set(g, x, y + 1u, 1);
	gol_set(g, x + 1u, y + 1u, 1);
	gol_set(g, x + 1u, y + 2u, 1);
}

void gol_insert_glider(struct gol_grid *g, unsigned cx, unsigned cy)
{
	unsigned dx, dy;
	/* .#.
	 * ..#
	 * ###  (bit n = column n) */
	static const uint8_t pat[3] = { 0x2, 0x4, 0x7 };

	for (dy = 0; dy < 3u; dy++)
		for (dx = 0; dx < 3u; dx++)
			gol_set(g, cx + GOL_W - 1u + dx, cy + GOL_H - 1u + dy,
				(pat[dy] >> dx) & 1);
}

int gol_pixel_to_cell(unsigned px, unsigned py, unsigned *cx, unsigned *cy)
{
	if (px >= GOL_PANEL_W || py >= GOL_PANEL_H)
		return 0;
	*cx = px / GOL_CELL_PX;
	*cy = py / GOL_CELL_PX;
	return 1;
}

uint32_t gol_fnv1a(const void *data, size_t len, uint32_t h)
{
	const uint8_t *p = data;

	while (len--) {
		h ^= *p++;
		h *= 0x01000193u;
	}
	return h;
}

uint32_t gol_grid_hash(const struct gol_grid *g)
{
	return gol_fnv1a(g->bits, sizeof(g->bits), GOL_FNV_INIT);
}

static void put32(uint8_t *p, uint32_t v)
{
	p[0] = (uint8_t)v;
	p[1] = (uint8_t)(v >> 8);
	p[2] = (uint8_t)(v >> 16);
	p[3] = (uint8_t)(v >> 24);
}

static uint32_t get32(const uint8_t *p)
{
	return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 |
	       (uint32_t)p[3] << 24;
}

static void put16(uint8_t *p, unsigned v)
{
	p[0] = (uint8_t)v;
	p[1] = (uint8_t)(v >> 8);
}

static unsigned get16(const uint8_t *p)
{
	return (unsigned)p[0] | (unsigned)p[1] << 8;
}

/* Byte-wise stores: no alignment assumption on the framebuffer pointer. */
void gol_render_xrgb(const struct gol_grid *g, void *fb, size_t stride_bytes)
{
	uint8_t *base = fb;
	unsigned cx, cy, k;
	uint8_t on[4], off[4];

	put32(on, GOL_COLOR_ON);
	put32(off, GOL_COLOR_OFF);
	for (cy = 0; cy < GOL_H; cy++) {
		uint8_t *row0 = base + (size_t)cy * GOL_CELL_PX * stride_bytes;

		for (cx = 0; cx < GOL_W; cx++) {
			const uint8_t *c = gol_get(g, cx, cy) ? on : off;

			for (k = 0; k < GOL_CELL_PX; k++)
				memcpy(row0 + (size_t)(cx * GOL_CELL_PX + k) * 4u, c, 4u);
		}
		for (k = 1; k < GOL_CELL_PX; k++)
			memcpy(row0 + (size_t)k * stride_bytes, row0, GOL_PANEL_W * 4u);
	}
}

unsigned gol_render_xrgb_diff(const struct gol_grid *prev, const struct gol_grid *cur,
			      void *fb, size_t stride_bytes)
{
	uint8_t *base = fb;
	unsigned cx, cy, k, j, n = 0;
	uint8_t on[4], off[4];

	put32(on, GOL_COLOR_ON);
	put32(off, GOL_COLOR_OFF);
	for (cy = 0; cy < GOL_H; cy++) {
		for (cx = 0; cx < GOL_W; cx++) {
			const uint8_t *c;

			if (gol_get(prev, cx, cy) == gol_get(cur, cx, cy))
				continue;
			c = gol_get(cur, cx, cy) ? on : off;
			for (j = 0; j < GOL_CELL_PX; j++)
				for (k = 0; k < GOL_CELL_PX; k++)
					memcpy(base + (size_t)(cy * GOL_CELL_PX + j) * stride_bytes +
						       (size_t)(cx * GOL_CELL_PX + k) * 4u, c, 4u);
			n++;
		}
	}
	return n;
}

void gol_render_rgb565(const struct gol_grid *g, void *fb, size_t stride_bytes)
{
	uint8_t *base = fb;
	unsigned cx, cy, k;
	/* GOL_COLOR_ON 0xe8f0ff: r>>3, g>>2, b>>3 */
	const unsigned on = ((0xe8u >> 3) << 11) | ((0xf0u >> 2) << 5) | (0xffu >> 3);

	for (cy = 0; cy < GOL_H; cy++) {
		uint8_t *row0 = base + (size_t)cy * GOL_CELL_PX * stride_bytes;

		for (cx = 0; cx < GOL_W; cx++) {
			unsigned v = gol_get(g, cx, cy) ? on : 0u;

			for (k = 0; k < GOL_CELL_PX; k++)
				put16(row0 + (size_t)(cx * GOL_CELL_PX + k) * 2u, v);
		}
		for (k = 1; k < GOL_CELL_PX; k++)
			memcpy(row0 + (size_t)k * stride_bytes, row0, GOL_PANEL_W * 2u);
	}
}

uint32_t gol_frame_hash_xrgb(const void *fb, size_t stride_bytes)
{
	const uint8_t *base = fb;
	uint32_t h = GOL_FNV_INIT;
	unsigned y;

	for (y = 0; y < GOL_PANEL_H; y++)
		h = gol_fnv1a(base + (size_t)y * stride_bytes, GOL_PANEL_W * 4u, h);
	return h;
}

void gol_state_init_default(struct gol_state *s, uint32_t boot_instance, uint32_t seed)
{
	memset(s, 0, sizeof(*s));
	s->boot_instance = boot_instance;
	s->seed = seed;
	s->owner = GOL_OWNER_NONE;
	gol_seed_default(&s->grid, seed);
}

void gol_state_advance(struct gol_state *s)
{
	struct gol_grid next;

	gol_step(&next, &s->grid);
	s->grid = next;
	s->generation++;
}

void gol_record_encode(const struct gol_state *s, uint8_t *out)
{
	uint32_t sum;

	memset(out, 0, GOL_RECORD_HEADER_BYTES);
	put32(out + 0, GOL_RECORD_MAGIC);
	put32(out + 4, GOL_ABI_VERSION);
	put32(out + 8, GOL_RECORD_BYTES);
	put32(out + 12, s->boot_instance);
	put32(out + 16, s->generation);
	put32(out + 20, s->seed);
	put16(out + 24, GOL_W);
	put16(out + 26, GOL_H);
	out[28] = GOL_CELL_PX;
	out[29] = s->owner;
	out[30] = 1; /* BF_SOURCE_LIFE */
	put32(out + 32, s->frame_generation);
	memcpy(out + GOL_RECORD_HEADER_BYTES, s->grid.bits, GOL_GRID_BYTES);
	sum = gol_fnv1a(out, 36, GOL_FNV_INIT);
	sum = gol_fnv1a(out + GOL_RECORD_HEADER_BYTES, GOL_GRID_BYTES, sum);
	put32(out + 36, sum);
}

enum gol_status gol_record_decode(struct gol_state *s, const uint8_t *buf, size_t len,
				  uint32_t expect_instance)
{
	uint32_t sum;

	if (len < GOL_RECORD_HEADER_BYTES || get32(buf) != GOL_RECORD_MAGIC)
		return GOL_BAD_MAGIC;
	if (get32(buf + 4) != GOL_ABI_VERSION)
		return GOL_BAD_VERSION;
	if (get32(buf + 8) != GOL_RECORD_BYTES || len < GOL_RECORD_BYTES)
		return GOL_BAD_LENGTH;
	if (buf[30] > 1)
		return GOL_BAD_MAGIC; /* another producer's record */
	if (get16(buf + 24) != GOL_W || get16(buf + 26) != GOL_H || buf[28] != GOL_CELL_PX)
		return GOL_BAD_DIMENSIONS;
	sum = gol_fnv1a(buf, 36, GOL_FNV_INIT);
	sum = gol_fnv1a(buf + GOL_RECORD_HEADER_BYTES, GOL_GRID_BYTES, sum);
	if (sum != get32(buf + 36))
		return GOL_BAD_CHECKSUM;
	if (get32(buf + 12) == 0u || (expect_instance && get32(buf + 12) != expect_instance))
		return GOL_BAD_INSTANCE;
	s->boot_instance = get32(buf + 12);
	s->generation = get32(buf + 16);
	s->seed = get32(buf + 20);
	s->owner = buf[29];
	s->frame_generation = get32(buf + 32);
	memcpy(s->grid.bits, buf + GOL_RECORD_HEADER_BYTES, GOL_GRID_BYTES);
	return GOL_OK;
}

const char *gol_status_name(enum gol_status st)
{
	switch (st) {
	case GOL_OK: return "ok";
	case GOL_BAD_MAGIC: return "bad-magic";
	case GOL_BAD_VERSION: return "bad-version";
	case GOL_BAD_LENGTH: return "bad-length";
	case GOL_BAD_DIMENSIONS: return "bad-dimensions";
	case GOL_BAD_CHECKSUM: return "bad-checksum";
	case GOL_BAD_INSTANCE: return "bad-instance";
	}
	return "unknown";
}
