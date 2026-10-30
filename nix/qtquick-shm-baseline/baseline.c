#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"
#include "text-input-unstable-v3-client-protocol.h"
#include "scene.h"

/* Equivalent small SHM client for the Qt Quick software probe: same viewport,
 * content, gestures, cursor blink and text-input behaviour, plain wl_shm
 * XRGB8888 buffers. Events use the shared fixed-schema JSONL boundary:
 * `input` = client receipt, `commit` = wl_surface.commit. Neither is
 * presentation or optical timing. */
#define NBUF 3
struct buffer { struct wl_buffer *wl; uint32_t *px; size_t size; bool busy; struct rect pending; };
struct app {
    struct wl_display *display;
    struct wl_compositor *compositor;
    struct wl_shm *shm;
    struct xdg_wm_base *wm;
    struct wl_seat *seat;
    struct wl_pointer *pointer;
    struct wl_touch *touch;
    struct wl_keyboard *keyboard;
    struct zwp_text_input_manager_v3 *tim;
    struct zwp_text_input_v3 *ti;
    struct wl_surface *surface;
    struct xdg_surface *xs;
    struct xdg_toplevel *top;
    struct wl_callback *frame_cb;
    struct buffer buf[NBUF];
    int width, height;
    bool configured, running, ti_entered, ti_enabled, first_logged, want_draw, closing;
    int touch_id;
    struct scene scene;
    unsigned commits, logged;
    uint64_t start_ms, last_input_ms, last_flush_ms;
    unsigned ti_serial;
};
static volatile sig_atomic_t stop_flag;
static uint64_t now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static void logev(struct app *a, const char *name, const char *extra) {
    if (a->logged++ >= 40000) return;
    printf("{\"e\":\"%s\",\"t\":%llu%s%s}\n", name, (unsigned long long)now_ms(), extra ? "," : "", extra ? extra : "");
}
static void flush_log(struct app *a) { fflush(stdout); a->last_flush_ms = now_ms(); }

static void buffer_release(void *data, struct wl_buffer *wl) { (void)wl; ((struct buffer *)data)->busy = false; }
static const struct wl_buffer_listener buffer_listener = {.release = buffer_release};
static struct buffer *get_buffer(struct app *a) {
    for (int i = 0; i < NBUF; i++) {
        struct buffer *b = &a->buf[i];
        if (b->busy) continue;
        if (!b->wl) {
            size_t size = (size_t)SC_WIDTH * SC_HEIGHT * 4;
            int fd = memfd_create("qtquick-shm-baseline", MFD_CLOEXEC);
            if (fd < 0 || ftruncate(fd, (off_t)size) < 0) return NULL;
            void *px = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
            if (px == MAP_FAILED) return NULL;
            struct wl_shm_pool *pool = wl_shm_create_pool(a->shm, fd, (int)size);
            b->wl = wl_shm_pool_create_buffer(pool, 0, SC_WIDTH, SC_HEIGHT, SC_WIDTH * 4, WL_SHM_FORMAT_XRGB8888);
            wl_shm_pool_destroy(pool);
            close(fd);
            wl_buffer_add_listener(b->wl, &buffer_listener, b);
            b->px = px; b->size = size;
            b->pending = (struct rect){0, 0, SC_WIDTH, SC_HEIGHT};
        }
        return b;
    }
    return NULL;
}
static void frame_done(void *data, struct wl_callback *cb, uint32_t t);
static const struct wl_callback_listener frame_listener = {.done = frame_done};
static void ti_sync(struct app *a) {
    if (!a->ti || !a->ti_entered) return;
    if (a->scene.focused && !a->ti_enabled) {
        zwp_text_input_v3_enable(a->ti);
        zwp_text_input_v3_set_content_type(a->ti, ZWP_TEXT_INPUT_V3_CONTENT_HINT_NONE,
                                           ZWP_TEXT_INPUT_V3_CONTENT_PURPOSE_NORMAL);
        zwp_text_input_v3_set_cursor_rectangle(a->ti, SC_EDITOR_X, SC_EDITOR_Y, SC_EDITOR_W, SC_EDITOR_H);
        zwp_text_input_v3_commit(a->ti);
        a->ti_enabled = true;
        logev(a, "text_input_enable", NULL);
    }
}
static void draw(struct app *a) {
    if (!a->configured || a->frame_cb) return;
    uint64_t now = now_ms();
    bool more = scene_tick(&a->scene, now);
    if (rect_empty(a->scene.dirty)) { a->want_draw = false; return; }
    struct buffer *b = get_buffer(a);
    if (!b) return; /* all buffers busy: retry on release/next dispatch */
    struct rect region = rect_union(b->pending, a->scene.dirty);
    struct canvas c = {b->px, SC_WIDTH, SC_WIDTH, SC_HEIGHT, region};
    scene_render(&a->scene, &c, now);
    for (int i = 0; i < NBUF; i++)
        a->buf[i].pending = (&a->buf[i] == b) ? (struct rect){0, 0, 0, 0}
                                              : rect_union(a->buf[i].pending, a->scene.dirty);
    wl_surface_attach(a->surface, b->wl, 0, 0);
    wl_surface_damage_buffer(a->surface, region.x0, region.y0, region.x1 - region.x0, region.y1 - region.y0);
    a->frame_cb = wl_surface_frame(a->surface);
    wl_callback_add_listener(a->frame_cb, &frame_listener, a);
    b->busy = true;
    wl_surface_commit(a->surface);
    a->scene.dirty = (struct rect){0, 0, 0, 0};
    a->commits++;
    logev(a, "commit", NULL);
    if (!a->first_logged) { a->first_logged = true; logev(a, "first_frame", NULL); }
    a->want_draw = more;
    ti_sync(a);
}
static void frame_done(void *data, struct wl_callback *cb, uint32_t t) {
    (void)t;
    struct app *a = data;
    wl_callback_destroy(cb);
    a->frame_cb = NULL;
    if (a->want_draw || !rect_empty(a->scene.dirty)) draw(a);
}
static void request_draw(struct app *a) { a->want_draw = true; draw(a); }

/* input */
static void input_ev(struct app *a, const char *kind) {
    char extra[48];
    snprintf(extra, sizeof extra, "\"k\":\"%s\"", kind);
    logev(a, "input", extra);
}
static void ptr_enter(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf, wl_fixed_t x, wl_fixed_t y) {
    (void)d; (void)p; (void)s; (void)sf; (void)x; (void)y;
}
static void ptr_leave(void *d, struct wl_pointer *p, uint32_t s, struct wl_surface *sf) { (void)d; (void)p; (void)s; (void)sf; }
static int px_x, px_y;
static void ptr_motion(void *d, struct wl_pointer *p, uint32_t t, wl_fixed_t x, wl_fixed_t y) {
    (void)p; (void)t;
    struct app *a = d;
    px_x = wl_fixed_to_int(x); px_y = wl_fixed_to_int(y);
    if (!a->scene.down) return;
    input_ev(a, "move");
    scene_move(&a->scene, px_x, px_y, now_ms());
    request_draw(a);
}
static void ptr_button(void *d, struct wl_pointer *p, uint32_t s, uint32_t t, uint32_t b, uint32_t st) {
    (void)p; (void)s; (void)t;
    struct app *a = d;
    if (b != 0x110) return;
    if (st == WL_POINTER_BUTTON_STATE_PRESSED) { input_ev(a, "press"); scene_press(&a->scene, px_x, px_y, now_ms()); }
    else { input_ev(a, "release"); scene_release(&a->scene, px_x, px_y, now_ms()); }
    request_draw(a);
}
static void ptr_axis(void *d, struct wl_pointer *p, uint32_t t, uint32_t ax, wl_fixed_t v) { (void)d; (void)p; (void)t; (void)ax; (void)v; }
static const struct wl_pointer_listener pointer_listener = {
    .enter = ptr_enter, .leave = ptr_leave, .motion = ptr_motion, .button = ptr_button, .axis = ptr_axis};
static void t_down(void *d, struct wl_touch *tc, uint32_t s, uint32_t t, struct wl_surface *sf, int32_t id,
                   wl_fixed_t x, wl_fixed_t y) {
    (void)tc; (void)s; (void)t; (void)sf;
    struct app *a = d;
    if (a->scene.down) return;
    a->touch_id = id;
    px_x = wl_fixed_to_int(x); px_y = wl_fixed_to_int(y);
    input_ev(a, "press");
    scene_press(&a->scene, px_x, px_y, now_ms());
    request_draw(a);
}
static void t_up(void *d, struct wl_touch *tc, uint32_t s, uint32_t t, int32_t id) {
    (void)tc; (void)s; (void)t;
    struct app *a = d;
    if (id != a->touch_id || !a->scene.down) return;
    input_ev(a, "release");
    scene_release(&a->scene, px_x, px_y, now_ms());
    request_draw(a);
}
static void t_motion(void *d, struct wl_touch *tc, uint32_t t, int32_t id, wl_fixed_t x, wl_fixed_t y) {
    (void)tc; (void)t;
    struct app *a = d;
    if (id != a->touch_id || !a->scene.down) return;
    px_x = wl_fixed_to_int(x); px_y = wl_fixed_to_int(y);
    input_ev(a, "move");
    scene_move(&a->scene, px_x, px_y, now_ms());
    request_draw(a);
}
static void t_frame(void *d, struct wl_touch *tc) { (void)d; (void)tc; }
static void t_cancel(void *d, struct wl_touch *tc) {
    (void)tc;
    struct app *a = d;
    a->scene.down = false; a->scene.dragging = false;
}
static void t_shape(void *d, struct wl_touch *tc, int32_t i, wl_fixed_t a, wl_fixed_t b) { (void)d; (void)tc; (void)i; (void)a; (void)b; }
static void t_orient(void *d, struct wl_touch *tc, int32_t i, wl_fixed_t o) { (void)d; (void)tc; (void)i; (void)o; }
static const struct wl_touch_listener touch_listener = {
    .down = t_down, .up = t_up, .motion = t_motion, .frame = t_frame, .cancel = t_cancel,
    .shape = t_shape, .orientation = t_orient};

/* Raw evdev keys (US layout) so an injected or physical keyboard types too. */
static void kb_keymap(void *d, struct wl_keyboard *k, uint32_t f, int32_t fd, uint32_t s) { (void)d; (void)k; (void)f; (void)s; close(fd); }
static void kb_enter(void *d, struct wl_keyboard *k, uint32_t s, struct wl_surface *sf, struct wl_array *keys) { (void)d; (void)k; (void)s; (void)sf; (void)keys; }
static void kb_leave(void *d, struct wl_keyboard *k, uint32_t s, struct wl_surface *sf) { (void)d; (void)k; (void)s; (void)sf; }
static void kb_key(void *d, struct wl_keyboard *k, uint32_t s, uint32_t t, uint32_t key, uint32_t st) {
    (void)k; (void)s; (void)t;
    struct app *a = d;
    if (st != WL_KEYBOARD_KEY_STATE_PRESSED) return;
    static const char row1[] = "qwertyuiop", row2[] = "asdfghjkl", row3[] = "zxcvbnm";
    char out[2] = {0, 0};
    if (key == 14) { input_ev(a, "key"); scene_backspace(&a->scene); request_draw(a); return; }
    if (key >= 16 && key <= 25) out[0] = row1[key - 16];
    else if (key >= 30 && key <= 38) out[0] = row2[key - 30];
    else if (key >= 44 && key <= 50) out[0] = row3[key - 44];
    else if (key >= 2 && key <= 10) out[0] = (char)('1' + key - 2);
    else if (key == 11) out[0] = '0';
    else if (key == 57) out[0] = ' ';
    if (!out[0]) return;
    input_ev(a, "key");
    scene_type(&a->scene, out);
    request_draw(a);
}
static void kb_mod(void *d, struct wl_keyboard *k, uint32_t s, uint32_t a, uint32_t b, uint32_t c, uint32_t e) { (void)d; (void)k; (void)s; (void)a; (void)b; (void)c; (void)e; }
static void kb_rate(void *d, struct wl_keyboard *k, int32_t r, int32_t dl) { (void)d; (void)k; (void)r; (void)dl; }
static const struct wl_keyboard_listener keyboard_listener = {
    .keymap = kb_keymap, .enter = kb_enter, .leave = kb_leave, .key = kb_key, .modifiers = kb_mod, .repeat_info = kb_rate};

static void seat_caps(void *d, struct wl_seat *seat, uint32_t caps) {
    struct app *a = d;
    if ((caps & WL_SEAT_CAPABILITY_POINTER) && !a->pointer) {
        a->pointer = wl_seat_get_pointer(seat);
        wl_pointer_add_listener(a->pointer, &pointer_listener, a);
    }
    if ((caps & WL_SEAT_CAPABILITY_TOUCH) && !a->touch) {
        a->touch = wl_seat_get_touch(seat);
        wl_touch_add_listener(a->touch, &touch_listener, a);
    }
    if ((caps & WL_SEAT_CAPABILITY_KEYBOARD) && !a->keyboard) {
        a->keyboard = wl_seat_get_keyboard(seat);
        wl_keyboard_add_listener(a->keyboard, &keyboard_listener, a);
    }
}
static void seat_name(void *d, struct wl_seat *s, const char *n) { (void)d; (void)s; (void)n; }
static const struct wl_seat_listener seat_listener = {.capabilities = seat_caps, .name = seat_name};

/* text-input-v3: the shell's on-screen keyboard keys off this protocol. */
static void ti_enter(void *d, struct zwp_text_input_v3 *t, struct wl_surface *s) { (void)t; (void)s; struct app *a = d; a->ti_entered = true; ti_sync(a); }
static void ti_leave(void *d, struct zwp_text_input_v3 *t, struct wl_surface *s) { (void)t; (void)s; struct app *a = d; a->ti_entered = false; a->ti_enabled = false; }
static void ti_preedit(void *d, struct zwp_text_input_v3 *t, const char *x, int32_t b, int32_t e) { (void)d; (void)t; (void)x; (void)b; (void)e; }
static char pending_commit[64];
static unsigned pending_delete;
static void ti_commit_string(void *d, struct zwp_text_input_v3 *t, const char *x) { (void)d; (void)t; snprintf(pending_commit, sizeof pending_commit, "%s", x ? x : ""); }
static void ti_delete(void *d, struct zwp_text_input_v3 *t, uint32_t b, uint32_t after) { (void)d; (void)t; pending_delete = b + after; }
static void ti_done(void *d, struct zwp_text_input_v3 *t, uint32_t serial) {
    (void)t;
    struct app *a = d;
    a->ti_serial = serial;
    bool changed = false;
    while (pending_delete--) { scene_backspace(&a->scene); changed = true; }
    pending_delete = 0;
    if (pending_commit[0]) { input_ev(a, "key"); scene_type(&a->scene, pending_commit); pending_commit[0] = 0; changed = true; }
    if (changed) request_draw(a);
}
static const struct zwp_text_input_v3_listener ti_listener = {
    .enter = ti_enter, .leave = ti_leave, .preedit_string = ti_preedit, .commit_string = ti_commit_string,
    .delete_surrounding_text = ti_delete, .done = ti_done};

static void xs_configure(void *d, struct xdg_surface *xs, uint32_t serial) {
    struct app *a = d;
    xdg_surface_ack_configure(xs, serial);
    if (!a->configured) {
        a->configured = true;
        char extra[64];
        snprintf(extra, sizeof extra, "\"w\":%d,\"h\":%d", a->width, a->height);
        logev(a, "configured", extra);
        request_draw(a);
    }
}
static const struct xdg_surface_listener xs_listener = {.configure = xs_configure};
static void top_configure(void *d, struct xdg_toplevel *t, int32_t w, int32_t h, struct wl_array *s) {
    (void)t; (void)s;
    struct app *a = d;
    if (w > 0) a->width = w;
    if (h > 0) a->height = h;
}
static void top_close(void *d, struct xdg_toplevel *t) { (void)t; ((struct app *)d)->running = false; }
static void top_bounds(void *d, struct xdg_toplevel *t, int32_t w, int32_t h) { (void)d; (void)t; (void)w; (void)h; }
static void top_caps(void *d, struct xdg_toplevel *t, struct wl_array *c) { (void)d; (void)t; (void)c; }
static const struct xdg_toplevel_listener top_listener = {
    .configure = top_configure, .close = top_close, .configure_bounds = top_bounds, .wm_capabilities = top_caps};
static void wm_ping(void *d, struct xdg_wm_base *wm, uint32_t s) { (void)d; xdg_wm_base_pong(wm, s); }
static const struct xdg_wm_base_listener wm_listener = {.ping = wm_ping};

static void reg_global(void *d, struct wl_registry *r, uint32_t name, const char *iface, uint32_t ver) {
    struct app *a = d;
    if (!strcmp(iface, "wl_compositor")) a->compositor = wl_registry_bind(r, name, &wl_compositor_interface, 4);
    else if (!strcmp(iface, "wl_shm")) a->shm = wl_registry_bind(r, name, &wl_shm_interface, 1);
    else if (!strcmp(iface, "xdg_wm_base")) { a->wm = wl_registry_bind(r, name, &xdg_wm_base_interface, ver < 5 ? ver : 5); xdg_wm_base_add_listener(a->wm, &wm_listener, a); }
    else if (!strcmp(iface, "wl_seat")) { a->seat = wl_registry_bind(r, name, &wl_seat_interface, ver < 5 ? ver : 5); wl_seat_add_listener(a->seat, &seat_listener, a); }
    else if (!strcmp(iface, "zwp_text_input_manager_v3")) a->tim = wl_registry_bind(r, name, &zwp_text_input_manager_v3_interface, 1);
}
static void reg_remove(void *d, struct wl_registry *r, uint32_t n) { (void)d; (void)r; (void)n; }
static const struct wl_registry_listener reg_listener = {.global = reg_global, .global_remove = reg_remove};
static void on_signal(int s) { (void)s; stop_flag = 1; }

int main(int argc, char **argv) {
    unsigned duration_ms = 0;
    const char *app_id = "qtquick-shm-baseline";
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--exit-after-ms") && i + 1 < argc) duration_ms = (unsigned)strtoul(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--negative-effect")) { /* baseline has no shader path: accepted, draws nothing */ }
        else { fprintf(stderr, "usage: qtquick-shm-baseline [--exit-after-ms N] [--negative-effect]\n"); return 2; }
    }
    struct app a = {0};
    a.start_ms = now_ms();
    setvbuf(stdout, NULL, _IOFBF, 1 << 16);
    struct sigaction sa = {.sa_handler = on_signal};
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    a.width = SC_WIDTH; a.height = SC_HEIGHT;
    scene_init(&a.scene);
    a.display = wl_display_connect(NULL);
    if (!a.display) { fprintf(stderr, "no wayland display\n"); return 3; }
    struct wl_registry *reg = wl_display_get_registry(a.display);
    wl_registry_add_listener(reg, &reg_listener, &a);
    wl_display_roundtrip(a.display);
    wl_display_roundtrip(a.display);
    if (!a.compositor || !a.shm || !a.wm) { fprintf(stderr, "missing wl_compositor/wl_shm/xdg_wm_base\n"); return 3; }
    if (a.tim && a.seat) { a.ti = zwp_text_input_manager_v3_get_text_input(a.tim, a.seat); zwp_text_input_v3_add_listener(a.ti, &ti_listener, &a); }
    printf("{\"e\":\"start\",\"t\":%llu,\"client\":\"qtquick-shm-baseline\",\"buffer\":\"wl_shm XRGB8888\","
           "\"text_input\":%s,\"boundary\":\"client_commit\"}\n",
           (unsigned long long)a.start_ms, a.ti ? "true" : "false");
    a.surface = wl_compositor_create_surface(a.compositor);
    a.xs = xdg_wm_base_get_xdg_surface(a.wm, a.surface);
    xdg_surface_add_listener(a.xs, &xs_listener, &a);
    a.top = xdg_surface_get_toplevel(a.xs);
    xdg_toplevel_add_listener(a.top, &top_listener, &a);
    xdg_toplevel_set_app_id(a.top, app_id);
    xdg_toplevel_set_title(a.top, "SHM baseline");
    wl_surface_commit(a.surface);
    a.running = true;
    while (a.running && !stop_flag) {
        wl_display_flush(a.display);
        uint64_t now = now_ms();
        if (duration_ms && now - a.start_ms >= duration_ms) break;
        int timeout = 250;
        if (a.scene.focused) {
            int64_t left = (int64_t)a.scene.cursor_toggle_ms + SC_CURSOR_MS - (int64_t)now;
            timeout = left < 1 ? 1 : (int)left;
        }
        if (a.want_draw && !a.frame_cb) timeout = 1;
        if (a.scene.flicking || a.scene.mover_x.active) timeout = timeout < 8 ? timeout : 8;
        if (duration_ms) { int64_t rem = (int64_t)duration_ms - (int64_t)(now - a.start_ms); if (rem < timeout) timeout = rem < 1 ? 1 : (int)rem; }
        if (wl_display_prepare_read(a.display) != 0) { wl_display_dispatch_pending(a.display); continue; }
        struct pollfd pfd = {wl_display_get_fd(a.display), POLLIN, 0};
        int rc = poll(&pfd, 1, timeout);
        if (rc > 0) wl_display_read_events(a.display); else wl_display_cancel_read(a.display);
        wl_display_dispatch_pending(a.display);
        if (a.configured && !a.frame_cb && (a.want_draw || a.scene.focused || a.scene.mover_x.active || a.scene.flicking))
            draw(&a);
        if (now_ms() - a.last_flush_ms > 2000) flush_log(&a);
    }
    logev(&a, "exit", NULL);
    flush_log(&a);
    return 0;
}
