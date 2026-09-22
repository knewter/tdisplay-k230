/* Read-only K230 display register snapshot for splash handoff comparison.
 * Addresses: pinned k230.dtsi, canaan_vo_regs.h and canaan_dsi.c.
 * Run as root on the board. No register is written.
 */
#define _FILE_OFFSET_BITS 64
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>

static int snapshot(int fd, const char *name, off_t base,
                    const unsigned *offsets, size_t count) {
    void *map = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, base);
    if (map == MAP_FAILED) { perror("mmap display registers"); return 1; }
    for (size_t i = 0; i < count; ++i) {
        volatile const uint32_t *reg = (volatile const uint32_t *)
            ((const unsigned char *)map + offsets[i]);
        printf("%s +0x%03x = 0x%08x\n", name, offsets[i], *reg);
    }
    if (munmap(map, 4096)) { perror("munmap"); return 1; }
    return 0;
}
int main(void) {
    const unsigned vo[] = {0x004,0x0c0,0x0c4,0x118,0x340,0x380,
                           0x828,0x82c,0x880,0x884,0x888,0x898,0x89c,0x8a0};
    const unsigned dsi[] = {0x004,0x010,0x034,0x038,0x03c,0x040,0x044,
                            0x048,0x04c,0x050,0x054,0x058,0x05c,0x060};
    int fd = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC);
    if (fd < 0) { perror("/dev/mem"); return 1; }
    int rc = snapshot(fd,"VO",0x90840000,vo,sizeof vo/sizeof vo[0]);
    if (!rc) rc = snapshot(fd,"DSI",0x90850000,dsi,sizeof dsi/sizeof dsi[0]);
    if (close(fd)) { perror("close"); return 1; }
    return rc;
}
