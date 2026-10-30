/*
 * Harness for tests/test_textfx.py.  Reads a TFXS file and the matching
 * `ttfx --parity-dump` stream, checks that the sequence path and the live ANSI
 * parser reach the same cell grid for every frame, and prints the hashes of
 * the grid and of the rendered surface at the requested frames.
 *
 *   textfx_harness <seq.tfxs> <dump.bin> <scale> <frame,frame,...|all>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "textfx.h"

#define PANEL_W 568u
#define PANEL_H 1232u

static uint8_t *slurp(const char *path, size_t *len)
{
	FILE *f = fopen(path, "rb");
	uint8_t *b;
	long n;

	if (!f)
		return NULL;
	fseek(f, 0, SEEK_END);
	n = ftell(f);
	fseek(f, 0, SEEK_SET);
	b = malloc((size_t)n + 1);
	if (!b || fread(b, 1, (size_t)n, f) != (size_t)n)
		return NULL;
	fclose(f);
	*len = (size_t)n;
	return b;
}

static int wanted(const char *spec, unsigned frame)
{
	char tmp[4096], *tok;

	if (!strcmp(spec, "all"))
		return 1;
	strncpy(tmp, spec, sizeof tmp - 1);
	tmp[sizeof tmp - 1] = 0;
	for (tok = strtok(tmp, ","); tok; tok = strtok(NULL, ","))
		if ((unsigned)atoi(tok) == frame)
			return 1;
	return 0;
}

static struct tfx_grid ga, gb;
static uint16_t changed[TFX_MAX_CELLS], changed2[TFX_MAX_CELLS];

int main(int argc, char **argv)
{
	size_t slen, dlen, pos = 0;
	uint8_t *sb, *db;
	struct tfx_seq seq;
	unsigned scale, frame = 0, bad = 0;
	static uint8_t xr[PANEL_W * PANEL_H * 4u], inc[PANEL_W * PANEL_H * 4u];
	static uint8_t r5[PANEL_W * PANEL_H * 2u];
	struct tfx_surface sx, si, s5;

	if (argc != 5)
		return 2;
	sb = slurp(argv[1], &slen);
	db = slurp(argv[2], &dlen);
	if (!sb || !db || tfx_seq_open(&seq, sb, slen)) {
		puts("ERROR open");
		return 1;
	}
	scale = (unsigned)atoi(argv[3]);
	tfx_grid_init(&ga, seq.cols, seq.rows);
	tfx_grid_init(&gb, seq.cols, seq.rows);
	sx = (struct tfx_surface){ xr, PANEL_W * 4u, PANEL_W, PANEL_H, TFX_XRGB8888, scale,
				   (PANEL_W - seq.cols * TFX_GLYPH_W * scale) / 2,
				   (PANEL_H - seq.rows * TFX_GLYPH_H * scale) / 2 };
	si = sx;
	si.pixels = inc;
	s5 = sx;
	s5.pixels = r5;
	s5.stride_bytes = PANEL_W * 2u;
	s5.fmt = TFX_RGB565;
	tfx_clear(&si);
	for (;;) {
		int n1 = tfx_seq_next(&seq, &ga, changed, TFX_MAX_CELLS);
		unsigned i, len = 0;
		int n2;

		if (n1 < 0)
			break;
		/* next length-prefixed live frame */
		while (pos < dlen && db[pos] != '\n')
			len = len * 10u + (db[pos++] - '0');
		pos++;
		n2 = tfx_parse_frame(&gb, db + pos, len, changed2, TFX_MAX_CELLS);
		pos += len + 1;
		if (n2 < 0 || tfx_grid_hash(&ga) != tfx_grid_hash(&gb) || n1 != n2) {
			printf("MISMATCH frame %u n1=%d n2=%d\n", frame, n1, n2);
			bad++;
		}
		for (i = 0; i < (unsigned)n1; i++)
			tfx_draw_cell(&ga, changed[i], &si);
		if (wanted(argv[4], frame)) {
			uint32_t hx, h5;

			tfx_draw_all(&ga, &sx);
			tfx_draw_all(&ga, &s5);
			hx = tfx_surface_hash(&sx);
			h5 = tfx_surface_hash(&s5);
			if (tfx_surface_hash(&si) != hx) {
				printf("INCREMENTAL-MISMATCH frame %u\n", frame);
				bad++;
			}
			printf("frame %u cell=0x%08x xrgb=0x%08x rgb565=0x%08x changed=%d\n",
			       frame, tfx_grid_hash(&ga), hx, h5, n1);
		}
		frame++;
	}
	printf("frames=%u live_bytes_consumed=%zu of %zu bad=%u\n", frame, pos, dlen, bad);
	return bad ? 1 : 0;
}
