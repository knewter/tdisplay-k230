/* Harness for tests/test_textfx_record.py.
 *   textfx_record_harness codec            round-trips a descriptor, prints the payload hex
 *   textfx_record_harness seed T C E       prints tfx_seed_mix
 *   textfx_record_harness select S NE NT   prints tfx_select
 *   textfx_record_harness texts FILE       prints the parsed entries (len, hash)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "textfx_record.h"

int main(int argc, char **argv)
{
	if (argc >= 2 && !strcmp(argv[1], "codec")) {
		struct tfx_run_desc d = { 0x0123456789abcdefull, 35, 38, 30, 3, 40, 0xdeadbeefu, 0x11223344u, 0x55667788u, 2, 1, "wipe" }, e;
		uint8_t buf[TFX_REC_PAYLOAD_BYTES + 4];
		size_t n = tfx_rec_encode(&d, buf, sizeof buf);
		unsigned i;

		for (i = 0; i < n; i++)
			printf("%02x", buf[i]);
		printf("\n");
		if (tfx_rec_decode(&e, buf, n) || e.seed != d.seed || e.cols != d.cols || e.rows != d.rows ||
		    e.fps != d.fps || e.flags != d.flags || e.last_frame != d.last_frame ||
		    e.cell_hash != d.cell_hash || e.engine_id != d.engine_id || e.text_hash != d.text_hash ||
		    e.text_id != d.text_id || e.orientation != d.orientation || strcmp(e.effect, d.effect))
			return 1;
		return tfx_rec_decode(&e, buf, n - 1) == 0; /* a short payload must be refused */
	}
	if (argc == 5 && !strcmp(argv[1], "seed")) {
		printf("%016llx\n", (unsigned long long)tfx_seed_mix(strtoull(argv[2], 0, 0), strtoull(argv[3], 0, 0), strtoull(argv[4], 0, 0)));
		return 0;
	}
	if (argc == 5 && !strcmp(argv[1], "select")) {
		struct tfx_choice c;

		tfx_select(strtoull(argv[2], 0, 0), (unsigned)atoi(argv[3]), (unsigned)atoi(argv[4]), &c);
		printf("%u %u\n", c.effect_index, c.text_index);
		return 0;
	}
	if (argc == 3 && !strcmp(argv[1], "texts")) {
		static char buf[8192];
		struct tfx_text t[16];
		FILE *f = fopen(argv[2], "rb");
		size_t n = f ? fread(buf, 1, sizeof buf, f) : 0;
		unsigned k, c = tfx_texts_parse(buf, n, t, 16);

		for (k = 0; k < c; k++)
			printf("%zu 0x%08x %zu\n", t[k].len, tfx_text_hash(t[k].text, t[k].len), (size_t)(t[k].text - buf));
		return 0;
	}
	return 2;
}
