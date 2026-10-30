/* Host fixture for the SHM baseline scene model (no Wayland). It replays a
 * scripted gesture list and prints one JSON object with region colours, scroll
 * state and selection state, optionally writing a PPM of the final frame.
 *   fixture [--ppm PATH] [--wait-ms N] ACTION...
 *   ACTION: tap:X,Y | drag:X0,Y0,X1,Y1,MS | type:TEXT | back */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "scene.h"

static uint32_t px[SC_WIDTH * SC_HEIGHT];
static uint64_t T = 1000;

static void render(struct scene *s) {
    struct canvas c = {px, SC_WIDTH, SC_WIDTH, SC_HEIGHT, {0, 0, SC_WIDTH, SC_HEIGHT}};
    scene_render(s, &c, T);
}
static void advance(struct scene *s, unsigned ms) {
    for (unsigned i = 0; i < ms; i += 4) { T += 4; scene_tick(s, T); }
}
static uint32_t at(int x, int y) { return px[y * SC_WIDTH + x] & 0xffffff; }

int main(int argc, char **argv) {
    struct scene s;
    scene_init(&s);
    const char *ppm = NULL;
    unsigned wait_ms = 400;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--ppm") && i + 1 < argc) ppm = argv[++i];
        else if (!strcmp(argv[i], "--wait-ms") && i + 1 < argc) wait_ms = (unsigned)atoi(argv[++i]);
        else if (!strncmp(argv[i], "tap:", 4)) {
            int x, y;
            if (sscanf(argv[i] + 4, "%d,%d", &x, &y) != 2) return 2;
            scene_press(&s, x, y, T); advance(&s, 40); scene_release(&s, x, y, T); advance(&s, 10);
        } else if (!strncmp(argv[i], "drag:", 5)) {
            int x0, y0, x1, y1, ms;
            if (sscanf(argv[i] + 5, "%d,%d,%d,%d,%d", &x0, &y0, &x1, &y1, &ms) != 5) return 2;
            scene_press(&s, x0, y0, T);
            for (int k = 1; k <= ms / 8; k++) {
                T += 8;
                scene_move(&s, x0 + (x1 - x0) * k * 8 / ms, y0 + (y1 - y0) * k * 8 / ms, T);
            }
            scene_release(&s, x1, y1, T);
        } else if (!strncmp(argv[i], "type:", 5)) scene_type(&s, argv[i] + 5);
        else if (!strcmp(argv[i], "back")) scene_backspace(&s);
        else return 2;
    }
    advance(&s, wait_ms);
    render(&s);
    if (ppm) {
        FILE *f = fopen(ppm, "wb");
        if (!f) return 1;
        fprintf(f, "P6\n%d %d\n255\n", SC_WIDTH, SC_HEIGHT);
        for (int i = 0; i < SC_WIDTH * SC_HEIGHT; i++) {
            unsigned char rgb[3] = {(px[i] >> 16) & 255, (px[i] >> 8) & 255, px[i] & 255};
            fwrite(rgb, 1, 3, f);
        }
        fclose(f);
    }
    printf("{\"bg\":\"%06x\",\"header\":\"%06x\",\"row1\":\"%06x\",\"editor\":\"%06x\","
           "\"mover_left\":\"%06x\",\"mover_right\":\"%06x\",\"swatch\":\"%06x\","
           "\"scroll\":%d,\"selected\":%d,\"moved\":%d,\"focused\":%d,\"text\":\"%s\","
           "\"flicking\":%d,\"width\":%d,\"height\":%d,\"max_scroll\":%d}\n",
           at(2, 300), at(10, 10), at(40, SC_LIST_Y + 4), at(SC_EDITOR_X + 4, SC_EDITOR_Y + 4),
           at(SC_MOVER_X_LEFT + 4, SC_MOVER_Y + 40), at(SC_MOVER_X_RIGHT + 4, SC_MOVER_Y + 40),
           at(SC_SWATCH_X + 40, SC_SWATCH_Y + 30), (int)s.scroll, s.selected, s.moved, s.focused, s.text,
           s.flicking, SC_WIDTH, SC_HEIGHT, SC_MAX_SCROLL);
    return 0;
}
