#include <assert.h>
#include <stdio.h>
#include "quarter-turn.h"

static void pixels(int width, int height, int cpp, int turn, int offset, int pad) {
	int ss = ((width * cpp + 3) & ~3) + pad;
	int ds = ((height * cpp + 3) & ~3) + pad;
	size_t sb = (size_t)ss * height, db = (size_t)ds * width;
	uint8_t *sr = malloc(sb + 64), *dr = malloc(db + 64), *expect = malloc(db + 64);
	assert(sr && dr && expect);
	memset(sr, 0x6d, sb + 64); memset(dr, 0xa7, db + 64); memset(expect, 0xa7, db + 64);
	uint8_t *src = sr + 16 + offset, *dst = dr + 16 + offset, *ref = expect + 16 + offset;
	pixman_format_code_t format = cpp == 2 ? PIXMAN_r5g6b5 : PIXMAN_a8r8g8b8;
	pixman_image_t *source = pixman_image_create_bits_no_clear(format, width, height, (uint32_t *)src, ss);
	pixman_image_t *target = pixman_image_create_bits_no_clear(format, height, width, (uint32_t *)dst, ds);
	assert(source && target);
	for (int frame = 0; frame < 3; frame++) {
		for (int y = 0; y < height; y++) for (int x = 0; x < width; x++) {
			uint32_t value = 0x5e000000u + (unsigned)(x * 953 + y * 1123 + frame * 9973);
			memcpy(src + (size_t)y * ss + x * cpp, &value, (size_t)cpp);
			int dx = turn == 1 ? y : height - 1 - y;
			int dy = turn == 1 ? width - 1 - x : x;
			memcpy(ref + (size_t)dy * ds + dx * cpp, &value, (size_t)cpp);
		}
		assert(k230_turn_into(target, source, turn));
		/* Include every row's padding and both allocation guards. */
		assert(memcmp(dr, expect, db + 64) == 0);
	}
	assert(!k230_turn_into(source, source, turn));
	assert(!k230_turn_into(target, source, 0));
	assert(!k230_turn_into(target, source, 2));
	assert(!k230_turn_into(NULL, source, turn));
	assert(!k230_turn_into(target, NULL, turn));
	pixman_image_unref(source); pixman_image_unref(target);
	free(sr); free(dr); free(expect);
}

int main(void) {
	int sizes[][2] = {{1,1},{2,3},{3,2},{7,19},{16,16},{17,31},{31,17},{1232,568},{568,1232}};
	unsigned cases = 0;
	for (unsigned i = 0; i < sizeof(sizes) / sizeof(sizes[0]); i++)
	for (int cpp = 2; cpp <= 4; cpp += 2)
	for (int turn = 1; turn <= 3; turn += 2)
	for (int offset = 0; offset <= 4; offset += 4)
	for (int pad = 0; pad <= 12; pad += 4) {
		pixels(sizes[i][0], sizes[i][1], cpp, turn, offset, pad); cases++;
	}
	printf("PASS panel paint: %u guarded multi-frame rotation cases\n", cases);
	return 0;
}
