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

struct register_def {
    const char *name;
    unsigned offset;
};

static int snapshot(int fd, const char *block, off_t base,
                    const struct register_def *registers, size_t count) {
    void *map = mmap(NULL, 4096, PROT_READ, MAP_SHARED, fd, base);
    if (map == MAP_FAILED) { perror("mmap display registers"); return 1; }
    for (size_t i = 0; i < count; ++i) {
        volatile const uint32_t *reg = (volatile const uint32_t *)
            ((const unsigned char *)map + registers[i].offset);
        printf("%s %-30s +0x%03x = 0x%08x\n", block, registers[i].name,
               registers[i].offset, *reg);
    }
    if (munmap(map, 4096)) { perror("munmap"); return 1; }
    return 0;
}
int main(void) {
    /* OSD4's four address slots and BD control distinguish stale
     * address-bank state from format/conversion state without writing MMIO. */
    const struct register_def vo[] = {
        { "VO_REG_LOAD_CTL", 0x004 }, { "VO_DMA_SW_CTL", 0x008 },
        { "VO_DMA_RD_CTL_OUT", 0x00c }, { "VO_DMA_ARB_MODE", 0x010 },
        { "VO_DISP_XZONE_CTL", 0x0c0 }, { "VO_DISP_YZONE_CTL", 0x0c4 },
        { "VO_DISP_ENABLE", 0x118 }, { "VO_OSD_RGB2YUV_CTL", 0x340 },
        { "VO_DISP_YUV2RGB_CTL", 0x380 },
        { "VO_DISP_MIX_LAYER_GLB_EN", 0x3c0 },
        { "VO_DISP_MIX_LAYER_GLB_ALPHA0", 0x3c4 },
        { "VO_DISP_MIX_LAYER_GLB_ALPHA1", 0x3c8 },
        { "VO_DISP_MIX_SEL", 0x3cc }, { "VO_DISP_BACKGROUND", 0x3d0 },
        { "VO_DISP_DITH_CTL", 0x3d4 }, { "VO_DISP_CLUT_CTL", 0x3d8 },
        { "VO_OSD4_BD_CTL", 0x804 }, { "VO_DISP_OSD4_XCTL", 0x828 },
        { "VO_DISP_OSD4_YCTL", 0x82c }, { "VO_OSD4_INFO", 0x880 },
        { "VO_OSD4_SIZE", 0x884 }, { "VO_OSD4_VLU_ADDR0", 0x888 },
        { "VO_OSD4_ALP_ADDR0", 0x88c }, { "VO_OSD4_VLU_ADDR1", 0x890 },
        { "VO_OSD4_ALP_ADDR1", 0x894 }, { "VO_OSD4_DMA_CTRL", 0x898 },
        { "VO_OSD4_STRIDE", 0x89c }, { "VO_OSD4_ADDR_SEL_MODE", 0x8a0 },
    };
    const struct register_def dsi[] = {
        { "VERSION", 0x004 }, { "DPI_COLOR_CODING", 0x010 },
        { "VID_MODE_CFG", 0x034 }, { "VID_PKT_SIZE", 0x038 },
        { "VID_HSA_TIME", 0x03c }, { "VID_HBP_TIME", 0x040 },
        { "VID_HLINE_TIME", 0x044 }, { "VID_VSA_LINES", 0x048 },
        { "VID_VBP_LINES", 0x04c }, { "VID_VFP_LINES", 0x050 },
        { "VID_VACTIVE_LINES", 0x054 }, { "EDPI_CMD_SIZE", 0x058 },
        { "CMD_MODE_CFG", 0x05c }, { "GEN_HDR", 0x060 },
    };
    int fd = open("/dev/mem", O_RDONLY | O_SYNC | O_CLOEXEC);
    if (fd < 0) { perror("/dev/mem"); return 1; }
    int rc = snapshot(fd,"VO",0x90840000,vo,sizeof vo/sizeof vo[0]);
    if (!rc) rc = snapshot(fd,"DSI",0x90850000,dsi,sizeof dsi/sizeof dsi[0]);
    if (close(fd)) { perror("close"); return 1; }
    return rc;
}
