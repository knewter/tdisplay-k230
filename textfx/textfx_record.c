/* Record payload codec and per-boot selection.  See textfx_record.h. */
#include "textfx_record.h"

static void wr16(uint8_t *p, uint16_t v) { p[0] = v & 0xff; p[1] = v >> 8; }
static void wr32(uint8_t *p, uint32_t v) { wr16(p, v & 0xffff); wr16(p + 2, v >> 16); }
static void wr64(uint8_t *p, uint64_t v) { wr32(p, (uint32_t)v); wr32(p + 4, (uint32_t)(v >> 32)); }
static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t rd32(const uint8_t *p) { return rd16(p) | ((uint32_t)rd16(p + 2) << 16); }
static uint64_t rd64(const uint8_t *p) { return rd32(p) | ((uint64_t)rd32(p + 4) << 32); }

static int effect_ok(const char *e)
{
	unsigned i;

	if (!e[0])
		return 0;
	for (i = 0; i < TFX_REC_EFFECT_LEN; i++)
		if (!e[i])
			return 1;
	return 0;
}

size_t tfx_rec_encode(const struct tfx_run_desc *d, uint8_t *out, size_t max)
{
	unsigned i;

	if (max < TFX_REC_PAYLOAD_BYTES || !effect_ok(d->effect))
		return 0;
	wr64(out, d->seed);
	wr16(out + 8, d->cols);
	wr16(out + 10, d->rows);
	wr16(out + 12, d->fps);
	wr16(out + 14, d->flags);
	wr32(out + 16, d->last_frame);
	wr32(out + 20, d->cell_hash);
	wr32(out + 24, d->engine_id);
	wr32(out + 28, d->text_hash);
	wr16(out + 32, d->text_id);
	wr16(out + 34, 0);
	for (i = 0; i < TFX_REC_EFFECT_LEN; i++)
		out[36 + i] = (uint8_t)d->effect[i];
	return TFX_REC_PAYLOAD_BYTES;
}

int tfx_rec_decode(struct tfx_run_desc *d, const uint8_t *in, size_t len)
{
	unsigned i;

	if (len != TFX_REC_PAYLOAD_BYTES)
		return -1;
	d->seed = rd64(in);
	d->cols = rd16(in + 8);
	d->rows = rd16(in + 10);
	d->fps = rd16(in + 12);
	d->flags = rd16(in + 14);
	d->last_frame = rd32(in + 16);
	d->cell_hash = rd32(in + 20);
	d->engine_id = rd32(in + 24);
	d->text_hash = rd32(in + 28);
	d->text_id = rd16(in + 32);
	for (i = 0; i < TFX_REC_EFFECT_LEN; i++)
		d->effect[i] = (char)in[36 + i];
	if (!d->cols || !d->rows || !d->fps || !effect_ok(d->effect))
		return -1;
	return 0;
}

static uint64_t splitmix(uint64_t z)
{
	z += 0x9e3779b97f4a7c15ull;
	z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
	z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
	return z ^ (z >> 31);
}

uint64_t tfx_seed_mix(uint64_t ticks, uint64_t clock, uint64_t env)
{
	uint64_t s = splitmix(ticks);

	s = splitmix(s ^ ((clock << 17) | (clock >> 47)));
	s = splitmix(s ^ env);
	return s ? s : 1;
}

void tfx_select(uint64_t seed, unsigned n_effects, unsigned n_texts, struct tfx_choice *out)
{
	out->effect_index = (unsigned)(splitmix(seed) % n_effects);
	out->text_index = (unsigned)(splitmix(seed ^ 0xa5a5a5a5a5a5a5a5ull) % n_texts);
}

static unsigned add_entry(struct tfx_text *out, unsigned n, unsigned max, const char *buf, size_t from, size_t to)
{
	size_t k;

	if (n >= max)
		return n;
	for (k = from; k < to; k++)
		if (buf[k] != '\n' && buf[k] != ' ') {
			out[n].text = buf + from;
			out[n].len = to - from;
			return n + 1;
		}
	return n; /* blank entry */
}

unsigned tfx_texts_parse(const char *buf, size_t len, struct tfx_text *out, unsigned max)
{
	unsigned n = 0;
	size_t pos = 0, entry = 0;

	for (;;) {
		size_t eol = pos;
		int sep, last;

		while (eol < len && buf[eol] != '\n')
			eol++;
		sep = eol - pos == 2 && buf[pos] == '%' && buf[pos + 1] == '%';
		last = eol >= len;
		if (sep || last) {
			n = add_entry(out, n, max, buf, entry, sep ? pos : len);
			entry = eol + 1;
		}
		if (last)
			break;
		pos = eol + 1;
	}
	return n;
}

uint32_t tfx_text_hash(const char *text, size_t len)
{
	uint32_t h = 0x811c9dc5u;

	while (len--) {
		h ^= (uint8_t)*text++;
		h *= 0x01000193u;
	}
	return h;
}
