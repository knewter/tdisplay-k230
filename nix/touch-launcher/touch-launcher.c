/* A fixed-action portrait launcher. It deliberately uses only Wayland SHM and
 * layer-shell: no toolkit, GPU path, font catalogue, or long-lived service. */
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#include <wayland-client.h>
#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "xdg-shell-client-protocol.h"

enum action { ACT_TERMINAL, ACT_MONITOR, ACT_NEW_TERMINAL, ACT_BACK };
struct button { enum action action; const char *label; int y, h; uint32_t color; };
static struct button buttons[] = {
  { ACT_TERMINAL, "TERMINAL", 150, 178, 0xff276749 },
  { ACT_MONITOR, "MONITOR", 346, 178, 0xff1f5e78 },
  { ACT_NEW_TERMINAL, "NEW TERM", 542, 178, 0xff3f765a },
  { ACT_BACK, "BACK", 0, 112, 0xff374151 },
};
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct wl_pointer *pointer;
static struct wl_touch *touch;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static struct zwlr_layer_surface_v1 *layer_surface;
static struct wl_buffer *buffer;
static uint32_t *pixels;
static int width, height, stride, mapped_size;
static bool running = true, configured;
static int press_x, press_y, touch_id = -1;

/* 5x7 source-controlled glyphs keep labels legible without fontconfig. */
struct glyph { char c; uint8_t r[7]; };
static const struct glyph glyphs[] = {
 {'A',{14,17,17,31,17,17,17}}, {'B',{30,17,17,30,17,17,30}},
 {'C',{15,16,16,16,16,16,15}}, {'E',{31,16,16,30,16,16,31}},
 {'H',{17,17,17,31,17,17,17}}, {'I',{31,4,4,4,4,4,31}},
 {'K',{17,18,20,24,20,18,17}}, {'L',{16,16,16,16,16,16,31}},
 {'M',{17,27,21,21,17,17,17}}, {'N',{17,25,21,19,17,17,17}},
 {'O',{14,17,17,17,17,17,14}}, {'P',{30,17,17,30,16,16,16}},
 {'R',{30,17,17,30,20,18,17}}, {'S',{15,16,16,14,1,1,30}},
 {'T',{31,4,4,4,4,4,4}}, {'W',{17,17,17,21,21,27,17}},
 {' ',{0,0,0,0,0,0,0}}, {'-',{0,0,0,31,0,0,0}},
};
static const struct glyph *get_glyph(char c) {
  for (size_t i = 0; i < sizeof glyphs / sizeof glyphs[0]; i++) if (glyphs[i].c == c) return &glyphs[i];
  return &glyphs[sizeof glyphs / sizeof glyphs[0] - 2];
}
static void rect(int x, int y, int w, int h, uint32_t c) {
  if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
  if (x + w > width) w = width - x; if (y + h > height) h = height - y;
  for (int yy = y; yy < y + h; yy++) for (int xx = x; xx < x + w; xx++) pixels[yy * width + xx] = c;
}
static void text(const char *s, int cx, int y, int scale, uint32_t color) {
  int n = (int)strlen(s), total = n * 6 * scale - scale, x = cx - total / 2;
  for (; *s; s++, x += 6 * scale) { const struct glyph *g = get_glyph(*s);
    for (int row = 0; row < 7; row++) for (int col = 0; col < 5; col++)
      if (g->r[row] & (1u << (4-col))) rect(x + col*scale, y + row*scale, scale, scale, color);
  }
}
static void draw(void) {
  rect(0, 0, width, height, 0xff111827);
  rect(0, 0, width, 8, 0xff38bdf8);
  text("APPS", width/2, 42, 7, 0xffffffff);
  text("TOUCH A CARD", width/2, 104, 3, 0xffcbd5e1);
  buttons[3].y = height - 142;
  for (size_t i = 0; i < sizeof buttons/sizeof buttons[0]; i++) {
    struct button *b = &buttons[i];
    rect(28, b->y, width - 56, b->h, b->color);
    rect(28, b->y, width - 56, 5, 0xfff8fafc);
    text(b->label, width/2, b->y + (b->h - 42) / 2, 6, 0xffffffff);
  }
}
static void run_action(enum action a) {
  if (a == ACT_BACK) { running = false; return; }
  const char *name = a == ACT_TERMINAL ? "terminal" : a == ACT_MONITOR ? "monitor" : "new-terminal";
  const char *helper = getenv("K230_LAUNCHER_ACTION");
  if (!helper || !*helper) { fprintf(stderr, "k230-touch-launcher: action helper is unset\n"); return; }
  if (fork() == 0) { execl(helper, helper, name, (char *)NULL); _exit(127); }
  running = false;
}
static void release_at(int x, int y) {
  for (size_t i = 0; i < sizeof buttons/sizeof buttons[0]; i++) {
    struct button *b = &buttons[i];
    if (x >= 28 && x < width-28 && y >= b->y && y < b->y+b->h) { run_action(b->action); return; }
  }
}
static void buffer_release(void *d, struct wl_buffer *b) {}
static const struct wl_buffer_listener buffer_listener = { .release = buffer_release };
static struct wl_buffer *make_buffer(void) {
  stride = width * 4; mapped_size = stride * height; char name[64]; int fd = -1;
  for (int i = 0; i < 100 && fd < 0; i++) { snprintf(name, sizeof name, "/k230-launcher-%d-%d", getpid(), i); fd = shm_open(name, O_RDWR|O_CREAT|O_EXCL, 0600); }
  if (fd < 0 || ftruncate(fd, mapped_size) < 0) { perror("k230-touch-launcher shm"); exit(1); }
  shm_unlink(name); pixels = mmap(NULL, mapped_size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
  if (pixels == MAP_FAILED) { perror("k230-touch-launcher mmap"); exit(1); }
  struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, mapped_size);
  struct wl_buffer *b = wl_shm_pool_create_buffer(pool, 0, width, height, stride, WL_SHM_FORMAT_ARGB8888);
  wl_shm_pool_destroy(pool); close(fd); wl_buffer_add_listener(b, &buffer_listener, NULL); return b;
}
static void layer_configure(void *d, struct zwlr_layer_surface_v1 *ls, uint32_t serial, uint32_t w, uint32_t h) {
  zwlr_layer_surface_v1_ack_configure(ls, serial); if (configured) return;
  width = (int)w; height = (int)h; if (width < 200 || height < 800) { fprintf(stderr, "k230-touch-launcher: portrait surface is too small\n"); running=false; return; }
  buffer=make_buffer(); draw(); wl_surface_attach(surface, buffer, 0, 0); wl_surface_damage_buffer(surface, 0, 0, width, height); wl_surface_commit(surface); configured=true;
}
static void layer_closed(void *d, struct zwlr_layer_surface_v1 *ls) { running=false; }
static const struct zwlr_layer_surface_v1_listener layer_listener = { .configure=layer_configure, .closed=layer_closed };
static void pointer_enter(void*d,struct wl_pointer*p,uint32_t s,struct wl_surface*sf,wl_fixed_t x,wl_fixed_t y) { press_x=wl_fixed_to_int(x); press_y=wl_fixed_to_int(y); }
static void pointer_leave(void*d,struct wl_pointer*p,uint32_t s,struct wl_surface*sf) {}
static void pointer_motion(void*d,struct wl_pointer*p,uint32_t t,wl_fixed_t x,wl_fixed_t y) { press_x=wl_fixed_to_int(x); press_y=wl_fixed_to_int(y); }
static void pointer_button(void*d,struct wl_pointer*p,uint32_t s,uint32_t t,uint32_t b,uint32_t state) { if (state == WL_POINTER_BUTTON_STATE_RELEASED) release_at(press_x,press_y); }
static void pointer_axis(void*d,struct wl_pointer*p,uint32_t t,uint32_t a,wl_fixed_t v) {}
static const struct wl_pointer_listener pointer_listener = { .enter=pointer_enter,.leave=pointer_leave,.motion=pointer_motion,.button=pointer_button,.axis=pointer_axis };
static void touch_down(void*d,struct wl_touch*t,uint32_t s,uint32_t tm,struct wl_surface*sf,int32_t id,wl_fixed_t x,wl_fixed_t y) { touch_id=id; press_x=wl_fixed_to_int(x); press_y=wl_fixed_to_int(y); }
static void touch_up(void*d,struct wl_touch*t,uint32_t s,uint32_t tm,int32_t id) { if(id==touch_id) { release_at(press_x,press_y); touch_id=-1; } }
static void touch_motion(void*d,struct wl_touch*t,uint32_t tm,int32_t id,wl_fixed_t x,wl_fixed_t y) { if(id==touch_id) { press_x=wl_fixed_to_int(x); press_y=wl_fixed_to_int(y); } }
static void touch_frame(void*d,struct wl_touch*t) {} static void touch_cancel(void*d,struct wl_touch*t) { touch_id=-1; }
static const struct wl_touch_listener touch_listener = { .down=touch_down,.up=touch_up,.motion=touch_motion,.frame=touch_frame,.cancel=touch_cancel };
static void seat_caps(void*d,struct wl_seat*s,uint32_t caps) { if ((caps&WL_SEAT_CAPABILITY_POINTER) && !pointer) { pointer=wl_seat_get_pointer(s); wl_pointer_add_listener(pointer,&pointer_listener,NULL); } if ((caps&WL_SEAT_CAPABILITY_TOUCH) && !touch) { touch=wl_seat_get_touch(s); wl_touch_add_listener(touch,&touch_listener,NULL); } }
static void seat_name(void*d,struct wl_seat*s,const char*n) {}
static const struct wl_seat_listener seat_listener = { .capabilities=seat_caps,.name=seat_name };
static void global_add(void*d,struct wl_registry*r,uint32_t n,const char*i,uint32_t v) { if(!strcmp(i,wl_compositor_interface.name)) compositor=wl_registry_bind(r,n,&wl_compositor_interface,4); else if(!strcmp(i,wl_shm_interface.name)) shm=wl_registry_bind(r,n,&wl_shm_interface,1); else if(!strcmp(i,wl_seat_interface.name)) { seat=wl_registry_bind(r,n,&wl_seat_interface,1); wl_seat_add_listener(seat,&seat_listener,NULL); } else if(!strcmp(i,zwlr_layer_shell_v1_interface.name)) layer_shell=wl_registry_bind(r,n,&zwlr_layer_shell_v1_interface,1); }
static void global_remove(void*d,struct wl_registry*r,uint32_t n) {}
static const struct wl_registry_listener registry_listener = { .global=global_add,.global_remove=global_remove };
int main(int argc,char**argv) {
 if(argc==2 && !strcmp(argv[1],"--layout")) { puts("568x1176: title; Terminal y=150 h=178; Monitor y=346 h=178; New term y=542 h=178; Back y=1034 h=112"); return 0; }
 if(argc!=1) { fprintf(stderr,"usage: k230-touch-launcher [--layout]\n"); return 2; }
 display=wl_display_connect(NULL); if(!display) { fprintf(stderr,"k230-touch-launcher: cannot connect to Wayland\n"); return 1; }
 struct wl_registry*r=wl_display_get_registry(display); wl_registry_add_listener(r,&registry_listener,NULL); wl_display_roundtrip(display);
 if(!compositor||!shm||!layer_shell) { fprintf(stderr,"k230-touch-launcher: need wl_compositor, wl_shm, and layer-shell\n"); return 1; }
 surface=wl_compositor_create_surface(compositor); layer_surface=zwlr_layer_shell_v1_get_layer_surface(layer_shell,surface,NULL,ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY,"k230-launcher"); zwlr_layer_surface_v1_add_listener(layer_surface,&layer_listener,NULL);
 zwlr_layer_surface_v1_set_anchor(layer_surface, ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP|ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM|ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT|ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT); zwlr_layer_surface_v1_set_margin(layer_surface,56,0,0,0); zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface,ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE); zwlr_layer_surface_v1_set_exclusive_zone(layer_surface,0); wl_surface_commit(surface);
 while(running && wl_display_dispatch(display)>=0) {} return 0;
}
