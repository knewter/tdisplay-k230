/* Linux-hosted freestanding bench of the bare-metal ttfx staticlib (rv64imac, soft-float).
 * Runs on the board as a static executable with raw syscalls: the same machine code that
 * would be linked into U-Boot, minus U-Boot.  usage: bench <effect> <seed> <cols> <rows> <fps> [textfile]
 * prints: effect frames bytes_fnv1a ms heap_peak_hint */
#include <stddef.h>
#include <stdint.h>

static long sc(long n, long a, long b, long c, long d, long e, long f)
{
	register long a7 __asm__("a7") = n, a0 __asm__("a0") = a, a1 __asm__("a1") = b,
		      a2 __asm__("a2") = c, a3 __asm__("a3") = d, a4 __asm__("a4") = e, a5 __asm__("a5") = f;
	__asm__ volatile("ecall" : "+r"(a0) : "r"(a7), "r"(a1), "r"(a2), "r"(a3), "r"(a4), "r"(a5) : "memory");
	return a0;
}
#define SYS_read 63
#define SYS_openat 56
#define SYS_close 57
#define SYS_write 64
#define SYS_exit 93
#define SYS_mmap 222
#define SYS_clock_gettime 113

void *memcpy(void *d, const void *s, size_t n) { char *p = d; const char *q = s; while (n--) *p++ = *q++; return d; }
void *memset(void *d, int c, size_t n) { char *p = d; while (n--) *p++ = (char)c; return d; }
int memcmp(const void *a, const void *b, size_t n) { const unsigned char *p = a, *q = b; while (n--) { if (*p != *q) return *p - *q; p++; q++; } return 0; }
void *memmove(void *d, const void *s, size_t n) { char *p = d; const char *q = s; if (p < q) while (n--) *p++ = *q++; else { p += n; q += n; while (n--) *--p = *--q; } return d; }
int bcmp(const void *a, const void *b, size_t n) { return memcmp(a, b, n); }
size_t strlen(const char *s) { size_t n = 0; while (s[n]) n++; return n; }

extern int ttfx_fw_init(void *arena, size_t len);
extern void *ttfx_fw_new(const char *e, size_t el, const char *t, size_t tl, uint64_t seed, int cols, int rows, int fps);
extern long ttfx_fw_next(void *h, const uint8_t **out);
extern void ttfx_fw_free(void *h);

void ttfx_fw_panic(const char *m, size_t n)
{
	sc(SYS_write, 2, (long)"PANIC: ", 7, 0, 0, 0);
	sc(SYS_write, 2, (long)m, (long)n, 0, 0, 0);
	sc(SYS_write, 2, (long)"\n", 1, 0, 0, 0);
	sc(SYS_exit, 99, 0, 0, 0, 0, 0);
}

static void put(const char *s) { sc(SYS_write, 1, (long)s, (long)strlen(s), 0, 0, 0); }
static void putnum(unsigned long v)
{
	char b[24]; int i = 23; b[i] = 0;
	do { b[--i] = '0' + v % 10; v /= 10; } while (v);
	put(b + i);
}
static void puthex(uint32_t v)
{
	char b[9]; for (int i = 0; i < 8; i++) b[i] = "0123456789abcdef"[(v >> (28 - 4 * i)) & 15]; b[8] = 0; put(b);
}
static long atoi_(const char *s) { long v = 0; while (*s >= '0' && *s <= '9') v = v * 10 + *s++ - '0'; return v; }
static uint64_t now_ns(void) { long ts[2]; sc(SYS_clock_gettime, 1, (long)ts, 0, 0, 0, 0); return (uint64_t)ts[0] * 1000000000ull + ts[1]; }

static char textbuf[4096];
static const char *banner =
	"\xe2\x96\x88\xe2\x96\x88\xe2\x95\x97  \xe2\x96\x88\xe2\x96\x88\xe2\x95\x97\n"
	"\xe2\x96\x88\xe2\x96\x88\xe2\x95\x91 \xe2\x96\x88\xe2\x96\x88\xe2\x95\x94\xe2\x95\x9d\n"
	"\xe2\x96\x88\xe2\x96\x88\xe2\x96\x88\xe2\x96\x88\xe2\x96\x88\xe2\x95\x94\xe2\x95\x9d\n";

void bench_main(long argc, char **argv)
{
	size_t arena_len = 48u << 20;
	void *arena = (void *)sc(SYS_mmap, 0, (long)arena_len, 3, 0x22, -1, 0);
	size_t tl;
	void *h;
	const uint8_t *f;
	long n, frames = 0, bytes = 0;
	uint32_t hash = 0x811c9dc5u;
	uint64_t t0, t1;

	if (argc < 6) { put("usage\n"); sc(SYS_exit, 2, 0, 0, 0, 0, 0); }
	if (argc >= 7) {
		long fd = sc(SYS_openat, -100, (long)argv[6], 0, 0, 0, 0);
		long r = sc(SYS_read, fd, (long)textbuf, sizeof textbuf, 0, 0, 0);
		if (fd < 0 || r <= 0) { put("cannot read text\n"); sc(SYS_exit, 2, 0, 0, 0, 0, 0); }
		tl = (size_t)r;
		sc(SYS_close, fd, 0, 0, 0, 0, 0);
	} else {
		tl = strlen(banner);
		memcpy(textbuf, banner, tl);
	}
	if (ttfx_fw_init(arena, arena_len)) { put("init failed\n"); sc(SYS_exit, 3, 0, 0, 0, 0, 0); }
	t0 = now_ns();
	h = ttfx_fw_new(argv[1], strlen(argv[1]), textbuf, tl, (uint64_t)atoi_(argv[2]), (int)atoi_(argv[3]), (int)atoi_(argv[4]), (int)atoi_(argv[5]));
	if (!h) { put("new failed\n"); sc(SYS_exit, 4, 0, 0, 0, 0, 0); }
	while ((n = ttfx_fw_next(h, &f)) > 0) {
		for (long i = 0; i < n; i++) { hash ^= f[i]; hash *= 0x01000193u; }
		frames++; bytes += n;
	}
	t1 = now_ns();
	ttfx_fw_free(h);
	put(argv[1]); put(" frames="); putnum((unsigned long)frames); put(" bytes="); putnum((unsigned long)bytes);
	put(" fnv=0x"); puthex(hash); put(" ms="); putnum((unsigned long)((t1 - t0) / 1000000)); put("\n");
	sc(SYS_exit, 0, 0, 0, 0, 0, 0);
}

__asm__(".globl _start\n_start:\n  ld a0, 0(sp)\n  addi a1, sp, 8\n  andi sp, sp, -16\n  call bench_main\n");
