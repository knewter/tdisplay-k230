/* Wayland-free scene model for the SHM baseline. It reproduces the layout,
 * content and gestures of nix/qtquick-software-probe/Probe.qml with plain
 * pixel loops so the two clients can be compared on the same compositor.
 * Included by baseline.c (client) and tests/qtquick_baseline_fixture.c (host). */
#ifndef QTQ_SCENE_H
#define QTQ_SCENE_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "glyphs.h"

/* Geometry constants mirror Probe.qml; tests/test_qtquick_probe_scene.py
 * compares them with the QML source. */
#define SC_WIDTH 1232
#define SC_HEIGHT 568
#define SC_BG 0x161b28
#define SC_HEADER_H 80
#define SC_HEADER_COLOR 0x26344c
#define SC_LIST_X 20
#define SC_LIST_Y 96
#define SC_LIST_W 580
#define SC_LIST_H 452
#define SC_ROW_COUNT 20
#define SC_ROW_H 74
#define SC_ROW_SPACING 12
#define SC_ROW_COLOR 0x31415d
#define SC_ROW_SELECTED 0x4b6ea8
#define SC_EDITOR_X 628
#define SC_EDITOR_Y 96
#define SC_EDITOR_W 584
#define SC_EDITOR_H 90
#define SC_MOVER_Y 206
#define SC_MOVER_W 172
#define SC_MOVER_H 90
#define SC_MOVER_X_LEFT 628
#define SC_MOVER_X_RIGHT 1040
#define SC_ANIM_MS 280
#define SC_PANEL_X 628
#define SC_PANEL_Y 316
#define SC_PANEL_W 584
#define SC_PANEL_H 112
#define SC_SWATCH_X 740
#define SC_SWATCH_Y 448
#define SC_SWATCH_W 96
#define SC_SWATCH_H 64
#define SC_SWATCH_COLOR 0xff5b79
#define SC_DRAG_PX 10
#define SC_FLICK_DECEL 1500.0
#define SC_FLICK_MAX 2500.0
#define SC_FLICK_MIN 50.0
#define SC_CURSOR_MS 500
#define SC_EDIT_MAX 40
#define SC_CONTENT_H (SC_ROW_COUNT * SC_ROW_H + (SC_ROW_COUNT - 1) * SC_ROW_SPACING)
#define SC_MAX_SCROLL (SC_CONTENT_H - SC_LIST_H)

struct rect { int x0, y0, x1, y1; }; /* half open; empty when x1<=x0 */
static inline bool rect_empty(struct rect r) { return r.x1 <= r.x0 || r.y1 <= r.y0; }
static inline struct rect rect_union(struct rect a, struct rect b) {
    if (rect_empty(a)) return b;
    if (rect_empty(b)) return a;
    return (struct rect){a.x0 < b.x0 ? a.x0 : b.x0, a.y0 < b.y0 ? a.y0 : b.y0,
                         a.x1 > b.x1 ? a.x1 : b.x1, a.y1 > b.y1 ? a.y1 : b.y1};
}
static inline struct rect rect_isect(struct rect a, struct rect b) {
    struct rect r = {a.x0 > b.x0 ? a.x0 : b.x0, a.y0 > b.y0 ? a.y0 : b.y0,
                     a.x1 < b.x1 ? a.x1 : b.x1, a.y1 < b.y1 ? a.y1 : b.y1};
    if (rect_empty(r)) r = (struct rect){0, 0, 0, 0};
    return r;
}

struct anim { double from, to; uint64_t start_ms; bool active; };
struct scene {
    double scroll;           /* content offset of the list */
    bool selected, moved, focused;
    char text[SC_EDIT_MAX + 1];
    struct anim mover_x, mover_a;
    bool cursor_on;
    uint64_t cursor_toggle_ms;
    /* gesture state */
    bool down, dragging;
    int sx, sy, lx, ly;
    uint64_t down_ms;
    int target;              /* 0 none, 1 list row, 2 editor, 3 mover, 4 list gap/other */
    struct { uint64_t t; int y; } hist[8];
    int hist_n;
    bool flicking;
    double flick_v;          /* px/s, positive scrolls content down */
    uint64_t flick_ms;
    struct rect dirty;
    unsigned taps;
};

static inline double ease_out_cubic(double t) { double u = 1.0 - t; return 1.0 - u * u * u; }
static inline double anim_value(const struct anim *a, uint64_t now) {
    if (!a->active) return a->to;
    double t = (double)(now - a->start_ms) / SC_ANIM_MS;
    if (t >= 1.0) return a->to;
    if (t < 0.0) t = 0.0;
    return a->from + (a->to - a->from) * ease_out_cubic(t);
}
static inline void anim_retarget(struct anim *a, double to, uint64_t now) {
    a->from = anim_value(a, now);
    a->to = to;
    a->start_ms = now;
    a->active = true;
}

static inline void scene_init(struct scene *s) {
    memset(s, 0, sizeof *s);
    strcpy(s->text, "Tap to edit");
    s->mover_x = (struct anim){SC_MOVER_X_LEFT, SC_MOVER_X_LEFT, 0, false};
    s->mover_a = (struct anim){1.0, 1.0, 0, false};
    s->dirty = (struct rect){0, 0, SC_WIDTH, SC_HEIGHT};
}
static inline void scene_damage(struct scene *s, struct rect r) { s->dirty = rect_union(s->dirty, r); }
static inline struct rect mover_rect(const struct scene *s, uint64_t now) {
    int x = (int)anim_value(&s->mover_x, now);
    return (struct rect){x - 1, SC_MOVER_Y, x + SC_MOVER_W + 1, SC_MOVER_Y + SC_MOVER_H};
}
static inline struct rect list_rect(void) {
    return (struct rect){SC_LIST_X, SC_LIST_Y, SC_LIST_X + SC_LIST_W, SC_LIST_Y + SC_LIST_H};
}
static inline struct rect editor_rect(void) {
    return (struct rect){SC_EDITOR_X, SC_EDITOR_Y, SC_EDITOR_X + SC_EDITOR_W, SC_EDITOR_Y + SC_EDITOR_H};
}

/* ---- drawing -------------------------------------------------------- */
struct canvas { uint32_t *px; int stride_px, w, h; struct rect clip; };

static inline void put_px(struct canvas *c, int x, int y, uint32_t rgb, unsigned a) {
    if (x < c->clip.x0 || x >= c->clip.x1 || y < c->clip.y0 || y >= c->clip.y1) return;
    uint32_t *d = &c->px[(size_t)y * c->stride_px + x];
    if (a >= 255) { *d = 0xff000000u | rgb; return; }
    uint32_t o = *d;
    unsigned ia = 255 - a;
    unsigned r = (((rgb >> 16) & 255) * a + ((o >> 16) & 255) * ia + 127) / 255;
    unsigned g = (((rgb >> 8) & 255) * a + ((o >> 8) & 255) * ia + 127) / 255;
    unsigned b = ((rgb & 255) * a + (o & 255) * ia + 127) / 255;
    *d = 0xff000000u | (r << 16) | (g << 8) | b;
}
static inline void fill_rrect(struct canvas *c, struct rect r, int rad, uint32_t rgb, unsigned alpha,
                              struct rect within) {
    struct rect v = rect_isect(rect_isect(r, c->clip), within);
    for (int y = v.y0; y < v.y1; y++) {
        for (int x = v.x0; x < v.x1; x++) {
            int cx = x < r.x0 + rad ? r.x0 + rad : (x >= r.x1 - rad ? r.x1 - rad - 1 : x);
            int cy = y < r.y0 + rad ? r.y0 + rad : (y >= r.y1 - rad ? r.y1 - rad - 1 : y);
            int dx = x - cx, dy = y - cy;
            if (dx * dx + dy * dy > rad * rad) continue;
            put_px(c, x, y, rgb, alpha);
        }
    }
}
static inline const struct glyph *find_glyph(int size, unsigned ch) {
    for (unsigned i = 0; i < sizeof glyphs / sizeof glyphs[0]; i++)
        if (glyphs[i].size == size && glyphs[i].ch == ch) return &glyphs[i];
    return NULL;
}
static inline int text_width(int size, const char *t) {
    int w = 0;
    for (; *t; t++) { const struct glyph *g = find_glyph(size, (unsigned char)*t); if (g) w += g->adv; }
    return w;
}
/* y is the top of the text line (QML font ascent box); returns advance. */
static inline void draw_text(struct canvas *c, int size, int x, int y, const char *t, uint32_t rgb,
                             unsigned alpha, struct rect within) {
    for (; *t; t++) {
        const struct glyph *g = find_glyph(size, (unsigned char)*t);
        if (!g) continue;
        for (int gy = 0; gy < g->h; gy++) {
            for (int gx = 0; gx < g->w; gx++) {
                unsigned cov = glyph_data[g->off + gy * g->w + gx];
                if (!cov) continue;
                int px = x + g->ox + gx, py = y + g->oy + gy + size;
                if (px < within.x0 || px >= within.x1 || py < within.y0 || py >= within.y1) continue;
                put_px(c, px, py, rgb, cov * alpha / 255);
            }
        }
        x += g->adv;
    }
}
static inline void draw_text_centered(struct canvas *c, int size, struct rect box, const char *t,
                                      uint32_t rgb, unsigned alpha, struct rect within) {
    int w = text_width(size, t);
    int x = (box.x0 + box.x1 - w) / 2;
    int y = (box.y0 + box.y1) / 2 - (size * 117 / 100) / 2;
    draw_text(c, size, x, y, t, rgb, alpha, within);
}
static inline void fill_rect(struct canvas *c, struct rect r, uint32_t rgb, struct rect within) {
    fill_rrect(c, r, 0, rgb, 255, within);
}

static inline void scene_render(const struct scene *s, struct canvas *c, uint64_t now) {
    struct rect all = {0, 0, c->w, c->h};
    struct rect clip = rect_isect(c->clip, all);
    c->clip = clip;
    if (rect_empty(clip)) return;
    fill_rect(c, (struct rect){0, 0, SC_WIDTH, SC_HEIGHT}, SC_BG, clip);
    fill_rect(c, (struct rect){0, 0, SC_WIDTH, SC_HEADER_H}, SC_HEADER_COLOR, clip);
    draw_text_centered(c, 30, (struct rect){0, 0, SC_WIDTH, SC_HEADER_H}, "Qt Quick software probe",
                       0xf2f6ff, 255, clip);
    /* list */
    struct rect lr = rect_isect(list_rect(), clip);
    if (!rect_empty(lr)) {
        int sc = (int)s->scroll;
        for (int i = 0; i < SC_ROW_COUNT; i++) {
            int top = SC_LIST_Y - sc + i * (SC_ROW_H + SC_ROW_SPACING);
            struct rect row = {SC_LIST_X, top, SC_LIST_X + SC_LIST_W, top + SC_ROW_H};
            if (row.y1 <= lr.y0 || row.y0 >= lr.y1) continue;
            fill_rrect(c, row, 12, (i == 0 && s->selected) ? SC_ROW_SELECTED : SC_ROW_COLOR, 255, lr);
            char label[24];
            int n = i + 1;
            if (n >= 10) { label[11] = '0' + n / 10; label[12] = '0' + n % 10; label[13] = 0; }
            else { label[11] = '0' + n; label[12] = 0; }
            memcpy(label, "Scroll row ", 11);
            draw_text_centered(c, 24, row, label, 0xf2f6ff, 255, lr);
        }
    }
    /* editor */
    struct rect er = editor_rect();
    fill_rrect(c, er, 12, SC_ROW_COLOR, 255, clip);
    {
        struct rect inner = {er.x0 + 22, er.y0 + 22, er.x1 - 22, er.y1 - 22};
        int ty = (inner.y0 + inner.y1) / 2 - (27 * 117 / 100) / 2;
        draw_text(c, 27, inner.x0, ty, s->text, 0xffffff, 255, rect_isect(inner, clip));
        if (s->focused && s->cursor_on) {
            int cx = inner.x0 + text_width(27, s->text);
            fill_rect(c, (struct rect){cx, ty, cx + 2, ty + 32}, 0xffffff, rect_isect(inner, clip));
        }
    }
    /* mover */
    {
        struct rect mr = mover_rect(s, now);
        int x = (int)anim_value(&s->mover_x, now);
        double op = anim_value(&s->mover_a, now);
        unsigned a = (unsigned)(op * 255.0 + 0.5);
        struct rect body = {x, SC_MOVER_Y, x + SC_MOVER_W, SC_MOVER_Y + SC_MOVER_H};
        fill_rrect(c, body, 14, s->moved ? 0x9bcfff : 0xf9c67a, a, rect_isect(mr, clip));
        draw_text_centered(c, 19, body, "Tap / retarget", 0x18243a, a, rect_isect(mr, clip));
    }
    /* image + caption panel */
    {
        struct rect pr = {SC_PANEL_X, SC_PANEL_Y, SC_PANEL_X + SC_PANEL_W, SC_PANEL_Y + SC_PANEL_H};
        fill_rrect(c, pr, 12, SC_ROW_COLOR, 255, clip);
        int ix = SC_PANEL_X + 20, iy = SC_PANEL_Y + (SC_PANEL_H - 64) / 2;
        for (int y = 0; y < 64; y++)
            for (int x = 0; x < 64; x++) {
                const unsigned char *p = &tile_rgba[((y * TILE_SIZE / 64) * TILE_SIZE + x * TILE_SIZE / 64) * 4];
                put_px(c, ix + x, iy + y, (p[0] << 16) | (p[1] << 8) | p[2], p[3]);
            }
        draw_text(c, 19, SC_PANEL_X + 100, SC_PANEL_Y + SC_PANEL_H / 2 - (19 * 117 / 100) / 2,
                  "Software-safe solid rectangle", 0xf2f6ff, 255, rect_isect(pr, clip));
    }
    fill_rect(c, (struct rect){SC_SWATCH_X, SC_SWATCH_Y, SC_SWATCH_X + SC_SWATCH_W, SC_SWATCH_Y + SC_SWATCH_H},
              SC_SWATCH_COLOR, clip);
}

/* ---- behaviour ------------------------------------------------------- */
static inline int hit_target(const struct scene *s, int x, int y, uint64_t now, int *row_out) {
    struct rect lr = list_rect();
    if (x >= lr.x0 && x < lr.x1 && y >= lr.y0 && y < lr.y1) {
        int rel = y - SC_LIST_Y + (int)s->scroll;
        int pitch = SC_ROW_H + SC_ROW_SPACING;
        if (rel % pitch < SC_ROW_H && rel / pitch < SC_ROW_COUNT) { if (row_out) *row_out = rel / pitch; return 1; }
        return 4;
    }
    struct rect er = editor_rect();
    if (x >= er.x0 && x < er.x1 && y >= er.y0 && y < er.y1) return 2;
    struct rect mr = mover_rect(s, now);
    if (x >= mr.x0 + 1 && x < mr.x1 - 1 && y >= mr.y0 && y < mr.y1) return 3;
    return 0;
}
static inline void set_scroll(struct scene *s, double v) {
    if (v < 0) v = 0;
    if (v > SC_MAX_SCROLL) v = SC_MAX_SCROLL;
    if ((int)v != (int)s->scroll) scene_damage(s, list_rect());
    s->scroll = v;
}
static inline void scene_press(struct scene *s, int x, int y, uint64_t now) {
    s->down = true; s->dragging = false;
    s->sx = s->lx = x; s->sy = s->ly = y; s->down_ms = now;
    s->target = hit_target(s, x, y, now, NULL);
    s->flicking = false;
    s->hist_n = 0;
    s->hist[s->hist_n].t = now; s->hist[s->hist_n++].y = y;
    if (s->target == 2 && !s->focused) {
        s->focused = true; s->cursor_on = true; s->cursor_toggle_ms = now;
        scene_damage(s, editor_rect());
    }
}
static inline void scene_move(struct scene *s, int x, int y, uint64_t now) {
    if (!s->down) return;
    if (!s->dragging) {
        int dx = x - s->sx, dy = y - s->sy;
        if (s->target >= 1 && s->target <= 4 && s->target != 2 && s->target != 3 &&
            (dy * dy + dx * dx) >= SC_DRAG_PX * SC_DRAG_PX && (dy < 0 ? -dy : dy) >= (dx < 0 ? -dx : dx) &&
            s->target != 0)
            s->dragging = true;
        else if ((dy * dy + dx * dx) >= SC_DRAG_PX * SC_DRAG_PX)
            s->target = 0; /* a tap handler is cancelled by movement beyond the drag threshold */
    }
    if (s->dragging) set_scroll(s, s->scroll - (y - s->ly));
    s->lx = x; s->ly = y;
    if (s->hist_n == 8) { memmove(&s->hist[0], &s->hist[1], 7 * sizeof s->hist[0]); s->hist_n = 7; }
    s->hist[s->hist_n].t = now; s->hist[s->hist_n++].y = y;
}
static inline void scene_release(struct scene *s, int x, int y, uint64_t now) {
    if (!s->down) return;
    s->down = false;
    if (s->dragging) {
        int i = 0;
        while (i < s->hist_n - 1 && now - s->hist[i].t > 100) i++;
        double dt = (double)(now - s->hist[i].t) / 1000.0;
        double v = dt > 0.001 ? (double)(y - s->hist[i].y) / dt : 0.0;
        v = -v; /* finger up scrolls content down */
        if (v > SC_FLICK_MAX) v = SC_FLICK_MAX;
        if (v < -SC_FLICK_MAX) v = -SC_FLICK_MAX;
        if ((v < 0 ? -v : v) >= SC_FLICK_MIN) { s->flicking = true; s->flick_v = v; s->flick_ms = now; }
        s->dragging = false;
        return;
    }
    /* TapHandler grabs on press: the target was fixed there and any movement
     * beyond the drag threshold already cleared it, so no re-hit-test. */
    int t = s->target;
    (void)x; (void)y;
    if (t && now - s->down_ms < 800) {
        if (t == 1) { s->selected = !s->selected; scene_damage(s, list_rect()); s->taps++; }
        else if (t == 3) {
            s->moved = !s->moved;
            anim_retarget(&s->mover_x, s->moved ? SC_MOVER_X_RIGHT : SC_MOVER_X_LEFT, now);
            anim_retarget(&s->mover_a, s->moved ? 0.7 : 1.0, now);
            s->taps++;
        } else if (t == 2) s->taps++;
    }
}
static inline void scene_type(struct scene *s, const char *utf8) {
    if (!s->focused) return;
    size_t n = strlen(s->text);
    for (; *utf8 && n < SC_EDIT_MAX; utf8++)
        if (find_glyph(27, (unsigned char)*utf8)) s->text[n++] = *utf8;
    s->text[n] = 0;
    scene_damage(s, editor_rect());
}
static inline void scene_backspace(struct scene *s) {
    size_t n = strlen(s->text);
    if (s->focused && n) { s->text[n - 1] = 0; scene_damage(s, editor_rect()); }
}
/* Advance time-driven state; returns true while another frame is needed
 * soon (animation/fling), and accumulates damage. cursor blink is separate. */
static inline bool scene_tick(struct scene *s, uint64_t now) {
    bool more = false;
    if (s->flicking) {
        double dt = (double)(now - s->flick_ms) / 1000.0;
        s->flick_ms = now;
        double sign = s->flick_v < 0 ? -1.0 : 1.0;
        double mag = (s->flick_v < 0 ? -s->flick_v : s->flick_v) - SC_FLICK_DECEL * dt;
        double dist = ((s->flick_v < 0 ? -s->flick_v : s->flick_v) + (mag > 0 ? mag : 0)) * 0.5 * dt;
        double before = s->scroll;
        set_scroll(s, s->scroll + sign * dist);
        if (mag <= 0 || s->scroll == before) s->flicking = false; else s->flick_v = sign * mag;
        more = more || s->flicking;
    }
    if (s->mover_x.active || s->mover_a.active) {
        scene_damage(s, (struct rect){SC_MOVER_X_LEFT - 2, SC_MOVER_Y, SC_MOVER_X_RIGHT + SC_MOVER_W + 2,
                                      SC_MOVER_Y + SC_MOVER_H});
        if (now - s->mover_x.start_ms >= SC_ANIM_MS) { s->mover_x.active = false; s->mover_a.active = false; }
        else more = true;
    }
    if (s->focused && now - s->cursor_toggle_ms >= SC_CURSOR_MS) {
        s->cursor_on = !s->cursor_on;
        s->cursor_toggle_ms = now;
        scene_damage(s, editor_rect());
    }
    return more;
}
#endif
