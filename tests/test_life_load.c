/*
 * Host test of the early-Linux state validation (nix/drm-splash/life.c):
 * a valid same-boot record continues; every invalid, mismatched or absent
 * record falls back to the deterministic default and logs why.
 *
 *   cc -std=c11 -Wall -Wextra -Werror -D_POSIX_C_SOURCE=200809L -I src -I nix/drm-splash \
 *      tests/test_life_load.c nix/drm-splash/life.c src/game_of_life.c -o /tmp/test-life-load
 *   /tmp/test-life-load <scratch-dir>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "life.h"

static int failures, checks;
#define CHECK(c)                                                              \
	do {                                                                  \
		checks++;                                                     \
		if (!(c)) {                                                   \
			failures++;                                           \
			printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); \
		}                                                             \
	} while (0)

static char dir[512];

static void write_file(const char *name, const void *p, size_t n)
{
	char path[600];
	FILE *f;

	snprintf(path, sizeof path, "%s/%s", dir, name);
	f = fopen(path, "wb");
	if (!f || fwrite(p, 1, n, f) != n)
		exit(2);
	fclose(f);
}

static void write_instance(uint32_t v)
{
	uint8_t b[4] = { (uint8_t)(v >> 24), (uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v };

	write_file("instance", b, 4);
}

static void load(struct life *l, int with_state, int with_instance)
{
	struct life_opts o = { 0 };
	static char sp[600], ip[600], rp[600];

	snprintf(sp, sizeof sp, "%s/state", dir);
	snprintf(ip, sizeof ip, "%s/instance", dir);
	snprintf(rp, sizeof rp, "%s/report", dir);
	o.state_path = with_state ? sp : "/nonexistent/state";
	o.instance_path = with_instance ? ip : "/nonexistent/instance";
	o.report_path = rp;
	o.seed = 0x4b323330u;
	o.interval_ms = 200;
	life_load(l, &o);
}

int main(int argc, char **argv)
{
	static uint8_t rec[GOL_RECORD_BYTES + 100];
	struct gol_state s, ref;
	struct life l;
	unsigned i;

	if (argc != 2) {
		fprintf(stderr, "usage: %s scratch-dir\n", argv[0]);
		return 2;
	}
	snprintf(dir, sizeof dir, "%s", argv[1]);

	gol_state_init_default(&s, 0xdeadbee1u, 0x4b323330u);
	for (i = 0; i < 40; i++)
		gol_state_advance(&s);
	s.owner = GOL_OWNER_UBOOT;
	s.frame_generation = 40;
	gol_record_encode(&s, rec);
	/* Real window is 8 KiB; trailing bytes are whatever the RAM held. */
	memset(rec + GOL_RECORD_BYTES, 0xa5, sizeof rec - GOL_RECORD_BYTES);

	/* 1. valid: continues from generation 40 and matches an uninterrupted run. */
	write_file("state", rec, sizeof rec);
	write_instance(0xdeadbee1u);
	remove("/dev/null.unused");
	load(&l, 1, 1);
	CHECK(l.from_record && l.reject == GOL_OK && l.st.generation == 40);
	CHECK(l.st.owner == GOL_OWNER_LINUX);
	gol_state_init_default(&ref, 1, 0x4b323330u);
	for (i = 0; i < 40; i++)
		gol_state_advance(&ref);
	CHECK(memcmp(&ref.grid, &l.st.grid, sizeof ref.grid) == 0);
	for (i = 0; i < 5; i++) {
		life_tick(&l);
		gol_state_advance(&ref);
	}
	CHECK(l.st.generation == 45 && memcmp(&ref.grid, &l.st.grid, sizeof ref.grid) == 0);

	/* 2. instance mismatch (a stale record from an earlier boot). */
	write_instance(0x11111111u);
	load(&l, 1, 1);
	CHECK(!l.from_record && l.reject == GOL_BAD_INSTANCE && l.st.generation == 0);
	CHECK(gol_grid_hash(&l.st.grid) == 0x1f4282cfu); /* the default pattern */

	/* 3. version mismatch. */
	write_instance(0xdeadbee1u);
	rec[4] = 2;
	write_file("state", rec, sizeof rec);
	load(&l, 1, 1);
	CHECK(!l.from_record && l.reject == GOL_BAD_VERSION && l.st.generation == 0);
	rec[4] = 1;

	/* 4. checksum failure. */
	rec[GOL_RECORD_HEADER_BYTES + 3] ^= 0x40;
	write_file("state", rec, sizeof rec);
	load(&l, 1, 1);
	CHECK(!l.from_record && l.reject == GOL_BAD_CHECKSUM);
	rec[GOL_RECORD_HEADER_BYTES + 3] ^= 0x40;

	/* 5. truncated, 6. all zero (RAM cleared), 7. absent state, 8. absent instance. */
	write_file("state", rec, 100);
	load(&l, 1, 1);
	CHECK(!l.from_record && (l.reject == GOL_BAD_LENGTH));
	memset(rec, 0, sizeof rec);
	write_file("state", rec, sizeof rec);
	load(&l, 1, 1);
	CHECK(!l.from_record && l.reject == GOL_BAD_MAGIC);
	load(&l, 0, 1);
	CHECK(!l.from_record && l.st.generation == 0);
	gol_record_encode(&s, rec);
	write_file("state", rec, GOL_RECORD_BYTES);
	load(&l, 1, 0);
	CHECK(!l.from_record && l.st.generation == 0);

	/* No touch device in a directory without events is not an error. */
	l.opts.input_dir = dir;
	CHECK(life_touch_open(&l) == 0);
	CHECK(life_touch_poll(&l) == 0);

	/* The report names each outcome. */
	{
		char path[600];
		char line[400];
		FILE *f;
		int seen_cont = 0, seen_pause = 0, seen_ver = 0, seen_sum = 0, seen_inst = 0, seen_notouch = 0;

		snprintf(path, sizeof path, "%s/report", dir);
		f = fopen(path, "r");
		CHECK(f != NULL);
		while (f && fgets(line, sizeof line, f)) {
			seen_cont |= strstr(line, "continuing the stage-1 grid at generation 40") != NULL;
			seen_pause |= strstr(line, "ownership pause") != NULL;
			seen_ver |= strstr(line, "rejected (bad-version)") != NULL;
			seen_sum |= strstr(line, "rejected (bad-checksum)") != NULL;
			seen_inst |= strstr(line, "rejected (bad-instance)") != NULL;
			seen_notouch |= strstr(line, "no multitouch device") != NULL;
		}
		if (f) {
			rewind(f);
			printf("--- report file ---\n");
			while (fgets(line, sizeof line, f))
				fputs(line, stdout);
			fclose(f);
		}
		CHECK(seen_cont && seen_pause && seen_ver && seen_sum && seen_inst && seen_notouch);
	}
	printf("%d checks, %d failures\n%s\n", checks, failures, failures ? "FAIL" : "PASS");
	return failures ? 1 : 0;
}
