/* Portable text-effect cells, sequence and glyph blitter.  See textfx.h. */
#include "textfx.h"

#define FNV_PRIME 0x01000193u

static unsigned rd16(const uint8_t *p)
{
	return (unsigned)p[0] | ((unsigned)p[1] << 8);
}

static uint32_t rd32(const uint8_t *p)
{
	return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

uint32_t tfx_fnv1a(const void *data, size_t len, uint32_t h)
{
	const uint8_t *p = data;

	while (len--) {
		h ^= *p++;
		h *= FNV_PRIME;
	}
	return h;
}

int tfx_grid_init(struct tfx_grid *g, unsigned cols, unsigned rows)
{
	unsigned i;

	if (!cols || !rows || cols > TFX_MAX_CELLS || rows > TFX_MAX_CELLS ||
	    cols * rows > TFX_MAX_CELLS)
		return -1;
	g->cols = cols;
	g->rows = rows;
	for (i = 0; i < cols * rows; i++) {
		g->cells[i].cp = 0x20;
		g->cells[i].r = g->cells[i].g = g->cells[i].b = 0;
	}
	return 0;
}

uint32_t tfx_grid_hash(const struct tfx_grid *g)
{
	uint32_t h = TFX_FNV_INIT;
	unsigned i;

	for (i = 0; i < g->cols * g->rows; i++) {
		uint8_t b[5];

		b[0] = g->cells[i].cp & 0xff;
		b[1] = g->cells[i].cp >> 8;
		b[2] = g->cells[i].r;
		b[3] = g->cells[i].g;
		b[4] = g->cells[i].b;
		h = tfx_fnv1a(b, 5, h);
	}
	return h;
}

/* ---------------------------------------------------------------- TFXS */

int tfx_seq_open(struct tfx_seq *s, const uint8_t *buf, size_t len)
{
	size_t plen;

	if (len < TFX_SEQ_HEADER || buf[0] != 'T' || buf[1] != 'F' || buf[2] != 'X' || buf[3] != 'S')
		return -1;
	if (rd16(buf + 4) != 1)
		return -1;
	s->cols = rd16(buf + 6);
	s->rows = rd16(buf + 8);
	s->fps = rd16(buf + 10);
	s->nframes = rd32(buf + 12);
	s->seed = rd32(buf + 16);
	s->digest = rd32(buf + 20);
	plen = rd32(buf + 24);
	if (!s->cols || !s->rows || s->cols * s->rows > TFX_MAX_CELLS)
		return -1;
	if (plen > len - TFX_SEQ_HEADER)
		return -1;
	if (tfx_fnv1a(buf + TFX_SEQ_HEADER, plen, TFX_FNV_INIT) != rd32(buf + 28))
		return -1;
	s->payload = buf + TFX_SEQ_HEADER;
	s->payload_len = plen;
	tfx_seq_rewind(s);
	return 0;
}

void tfx_seq_rewind(struct tfx_seq *s)
{
	s->pos = 0;
	s->frame = 0;
}

int tfx_seq_next(struct tfx_seq *s, struct tfx_grid *g, uint16_t *changed, size_t cap)
{
	unsigned n, i, cells = s->cols * s->rows;

	if (s->frame >= s->nframes || g->cols != s->cols || g->rows != s->rows)
		return -1;
	if (s->payload_len - s->pos < 2)
		return -1;
	n = rd16(s->payload + s->pos);
	s->pos += 2;
	if (n > cap || (size_t)n * 7u > s->payload_len - s->pos)
		return -1;
	for (i = 0; i < n; i++) {
		const uint8_t *p = s->payload + s->pos;
		unsigned idx = rd16(p);

		if (idx >= cells)
			return -1;
		g->cells[idx].cp = (uint16_t)rd16(p + 2);
		g->cells[idx].r = p[4];
		g->cells[idx].g = p[5];
		g->cells[idx].b = p[6];
		changed[i] = (uint16_t)idx;
		s->pos += 7;
	}
	s->frame++;
	return (int)n;
}

/* ------------------------------------------------------- live ANSI frames */

static int parse_uint(const uint8_t *p, size_t len, size_t *i, unsigned *out)
{
	unsigned v = 0, digits = 0;

	while (*i < len && p[*i] >= '0' && p[*i] <= '9') {
		v = v * 10u + (p[*i] - '0');
		if (++digits > 3 || v > 255)
			return -1;
		(*i)++;
	}
	if (!digits)
		return -1;
	*out = v;
	return 0;
}

/* Decode one UTF-8 character at p[*i]; BMP only, no overlong or surrogates. */
static int utf8_next(const uint8_t *p, size_t len, size_t *i, unsigned *cp)
{
	unsigned c = p[*i];

	if (c < 0x80) {
		*cp = c;
		*i += 1;
	} else if ((c & 0xe0) == 0xc0 && *i + 1 < len && (p[*i + 1] & 0xc0) == 0x80) {
		*cp = ((c & 0x1fu) << 6) | (p[*i + 1] & 0x3fu);
		if (*cp < 0x80)
			return -1;
		*i += 2;
	} else if ((c & 0xf0) == 0xe0 && *i + 2 < len && (p[*i + 1] & 0xc0) == 0x80 &&
		   (p[*i + 2] & 0xc0) == 0x80) {
		*cp = ((c & 0x0fu) << 12) | ((p[*i + 1] & 0x3fu) << 6) | (p[*i + 2] & 0x3fu);
		if (*cp < 0x800 || (*cp >= 0xd800 && *cp < 0xe000))
			return -1;
		*i += 3;
	} else {
		return -1; /* 4-byte (non-BMP) or malformed */
	}
	return 0;
}

int tfx_parse_frame(struct tfx_grid *g, const uint8_t *buf, size_t len,
		    uint16_t *changed, size_t cap)
{
	/* Parse into a scratch copy of the colour state per cell, committing only
	 * when the whole frame is valid, so g is unchanged on error. */
	static struct tfx_cell next[TFX_MAX_CELLS];
	unsigned row = 0, col = 0, cells = g->cols * g->rows, nchanged = 0, k;
	unsigned fr = 0, fg = 0, fb = 0;
	size_t i = 0;

	if (!cells || cells > TFX_MAX_CELLS)
		return -1;
	while (i < len) {
		unsigned c = buf[i];

		if (c == 0x1b) {
			unsigned a, b, d;

			if (i + 1 >= len || buf[i + 1] != '[')
				return -1;
			i += 2;
			if (i + 1 < len && buf[i] == '0' && buf[i + 1] == 'm') {
				fr = fg = fb = 0;
				i += 2;
				continue;
			}
			if (i + 4 < len && buf[i] == '3' && buf[i + 1] == '8' && buf[i + 2] == ';' &&
			    buf[i + 3] == '2' && buf[i + 4] == ';') {
				i += 5;
				if (parse_uint(buf, len, &i, &a) || i >= len || buf[i++] != ';' ||
				    parse_uint(buf, len, &i, &b) || i >= len || buf[i++] != ';' ||
				    parse_uint(buf, len, &i, &d) || i >= len || buf[i++] != 'm')
					return -1;
				fr = a;
				fg = b;
				fb = d;
				continue;
			}
			return -1;
		}
		if (c == '\n') {
			if (col != g->cols)
				return -1;
			row++;
			col = 0;
			i++;
			continue;
		}
		{
			unsigned cp;

			if (utf8_next(buf, len, &i, &cp))
				return -1;
			if (cp < 0x20 || cp == 0x7f || (cp >= 0x80 && cp < 0xa0))
				return -1;
			/* Double-width ranges (CJK, full-width, wide emoji) are unsupported. */
			if ((cp >= 0x1100 && cp <= 0x115f) || (cp >= 0x2e80 && cp <= 0xa4cf) ||
			    (cp >= 0xac00 && cp <= 0xd7a3) || (cp >= 0xf900 && cp <= 0xfaff) ||
			    (cp >= 0xfe30 && cp <= 0xfe6f) || (cp >= 0xff01 && cp <= 0xff60) ||
			    (cp >= 0xffe0 && cp <= 0xffe6))
				return -1;
			if (row >= g->rows || col >= g->cols)
				return -1;
			k = row * g->cols + col;
			next[k].cp = (uint16_t)cp;
			if (cp == 0x20) {
				next[k].r = next[k].g = next[k].b = 0;
			} else {
				next[k].r = (uint8_t)fr;
				next[k].g = (uint8_t)fg;
				next[k].b = (uint8_t)fb;
			}
			col++;
		}
	}
	if (row + 1 != g->rows || col != g->cols)
		return -1;
	for (k = 0; k < cells; k++) {
		if (next[k].cp != g->cells[k].cp || next[k].r != g->cells[k].r ||
		    next[k].g != g->cells[k].g || next[k].b != g->cells[k].b) {
			if (nchanged >= cap)
				return -1;
			changed[nchanged++] = (uint16_t)k;
		}
	}
	for (k = 0; k < cells; k++)
		g->cells[k] = next[k];
	return (int)nchanged;
}

/* -------------------------------------------------------------- drawing */

static const uint8_t fallback_glyph[16] = {
	0x00, 0x00, 0x00, 0x7e, 0x42, 0x42, 0x42, 0x42,
	0x42, 0x42, 0x42, 0x42, 0x42, 0x7e, 0x00, 0x00,
};

static const uint8_t *glyph_for(uint16_t cp)
{
	unsigned lo = 0, hi = tfx_font_count;

	while (lo < hi) {
		unsigned mid = (lo + hi) / 2;

		if (tfx_font_cp[mid] == cp)
			return tfx_font_bits[mid];
		if (tfx_font_cp[mid] < cp)
			lo = mid + 1;
		else
			hi = mid;
	}
	return fallback_glyph;
}

int tfx_has_glyph(uint16_t cp)
{
	return glyph_for(cp) != fallback_glyph;
}

static unsigned bytes_per_pixel(enum tfx_fmt f)
{
	return f == TFX_RGB565 ? 2u : 4u;
}

static void put_pixel(const struct tfx_surface *s, unsigned x, unsigned y,
		      uint8_t r, uint8_t g, uint8_t b)
{
	uint8_t *p;

	if (s->rot == TFX_ROT_LANDSCAPE) {
		unsigned nx = y, ny = s->width - 1u - x;

		x = nx;
		y = ny;
	}
	p = (uint8_t *)s->pixels + (size_t)y * s->stride_bytes;

	if (s->fmt == TFX_RGB565) {
		uint16_t v = (uint16_t)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));

		p += (size_t)x * 2u;
		p[0] = v & 0xff;
		p[1] = v >> 8;
	} else {
		p += (size_t)x * 4u;
		p[0] = b;
		p[1] = g;
		p[2] = r;
		p[3] = 0;
	}
}

void tfx_draw_cell(const struct tfx_grid *g, unsigned idx, const struct tfx_surface *s)
{
	const struct tfx_cell *c = &g->cells[idx];
	const uint8_t *glyph = glyph_for(c->cp);
	unsigned cx = idx % g->cols, cy = idx / g->cols;
	unsigned gy, gx, sy, sx;
	unsigned px0 = s->x0 + cx * TFX_GLYPH_W * s->scale;
	unsigned py0 = s->y0 + cy * TFX_GLYPH_H * s->scale;

	for (gy = 0; gy < TFX_GLYPH_H; gy++) {
		for (gx = 0; gx < TFX_GLYPH_W; gx++) {
			int on = c->cp != 0x20 && (glyph[gy] & (0x80u >> gx));
			uint8_t r = on ? c->r : 0, gg = on ? c->g : 0, b = on ? c->b : 0;

			for (sy = 0; sy < s->scale; sy++) {
				unsigned y = py0 + gy * s->scale + sy;

				if (y >= s->height)
					break;
				for (sx = 0; sx < s->scale; sx++) {
					unsigned x = px0 + gx * s->scale + sx;

					if (x < s->width)
						put_pixel(s, x, y, r, gg, b);
				}
			}
		}
	}
}

void tfx_draw_all(const struct tfx_grid *g, const struct tfx_surface *s)
{
	unsigned i;

	for (i = 0; i < g->cols * g->rows; i++)
		tfx_draw_cell(g, i, s);
}

void tfx_clear(const struct tfx_surface *s)
{
	unsigned x, y;

	for (y = 0; y < s->height; y++)
		for (x = 0; x < s->width; x++)
			put_pixel(s, x, y, 0, 0, 0);
}

uint32_t tfx_surface_hash(const struct tfx_surface *s)
{
	uint32_t h = TFX_FNV_INIT;
	unsigned y, nw = s->rot == TFX_ROT_LANDSCAPE ? s->height : s->width;
	unsigned nh = s->rot == TFX_ROT_LANDSCAPE ? s->width : s->height;

	for (y = 0; y < nh; y++)
		h = tfx_fnv1a((const uint8_t *)s->pixels + (size_t)y * s->stride_bytes,
			      (size_t)nw * bytes_per_pixel(s->fmt), h);
	return h;
}
