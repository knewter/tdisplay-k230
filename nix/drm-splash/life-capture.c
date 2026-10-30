/*
 * Copy the stage-1 Game of Life record window out of the no-map splash
 * reservation into a file the unprivileged splash owner can read.  The
 * window is read once, read-only, through an mmap of /dev/mem (a read() of
 * a no-map range fails with EFAULT).  Nothing is written to the window.
 *
 *   k230-life-capture --phys 0x102ac000 --size 0x2000 --out /run/k230-life/state
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

int main(int argc, char **argv)
{
	unsigned long long phys = 0, size = 0;
	const char *out = NULL;
	int fd, ofd;
	long page = sysconf(_SC_PAGESIZE);
	void *map;

	for (int i = 1; i + 1 < argc; i += 2) {
		if (!strcmp(argv[i], "--phys")) phys = strtoull(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--size")) size = strtoull(argv[i + 1], NULL, 0);
		else if (!strcmp(argv[i], "--out")) out = argv[i + 1];
		else { fprintf(stderr, "k230-life-capture: unknown option %s\n", argv[i]); return 2; }
	}
	if (!phys || !size || !out || phys % (unsigned long long)page || size % (unsigned long long)page) {
		fprintf(stderr, "usage: %s --phys ADDR --size BYTES --out FILE (page aligned)\n", argv[0]);
		return 2;
	}
	fd = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC);
	if (fd < 0) { fprintf(stderr, "k230-life-capture: open /dev/mem: %s\n", strerror(errno)); return 1; }
	map = mmap(NULL, size, PROT_READ, MAP_SHARED, fd, (off_t)phys);
	if (map == MAP_FAILED) {
		fprintf(stderr, "k230-life-capture: mmap 0x%llx: %s\n", phys, strerror(errno));
		return 1;
	}
	ofd = open(out, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0640);
	if (ofd < 0) { fprintf(stderr, "k230-life-capture: open %s: %s\n", out, strerror(errno)); return 1; }
	for (size_t at = 0; at < size;) {
		ssize_t n = write(ofd, (const char *)map + at, size - at);
		if (n < 0 && errno == EINTR) continue;
		if (n <= 0) { fprintf(stderr, "k230-life-capture: write: %s\n", strerror(errno)); return 1; }
		at += (size_t)n;
	}
	fsync(ofd);
	close(ofd);
	fprintf(stderr, "k230-life-capture: copied %llu bytes from 0x%llx to %s\n", size, phys, out);
	return 0;
}
