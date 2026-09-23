/* Portrait desktop-entry launcher on Wayland SHM/layer-shell. GLib owns
 * desktop-entry semantics; Pango/Cairo render installed application names. */
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/file.h>
#include <sys/wait.h>
#include <unistd.h>
#include <wayland-client.h>
#include <pango/pangocairo.h>
#include "catalog.h"
#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "xdg-shell-client-protocol.h"

enum action { ACT_TERMINAL=-1, ACT_MONITOR=-2, ACT_NEW_TERMINAL=-3,
  ACT_BACK=-4, ACT_PREVIOUS=-5, ACT_NEXT=-6, ACT_HELP=-7 };
struct button { int action, x, y, w, h; const char *label, *hint; uint32_t color; };
static struct button buttons[8];
static int button_count, page, page_size=4;
static GPtrArray *apps;
static char *launch_error;
static bool help_page;
static void redraw(void);
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_seat *seat;
static struct wl_pointer *pointer;
static struct wl_touch *touch;
static struct zwlr_layer_shell_v1 *layer_shell;
static struct wl_surface *surface;
static struct zwlr_layer_surface_v1 *layer_surface;
struct shm_buffer { struct wl_buffer *buffer; uint32_t *pixels; int size; };
static struct shm_buffer *current;
static uint32_t *pixels;
static int width, height, stride, mapped_size;
static int lock_fd = -1;
static bool running = true, configured;
static int press_x, press_y, touch_x, touch_y, touch_id = -1;
static bool pointer_pressed;
static uint32_t pointer_button_code;
static int pointer_card = -1, touch_card = -1;

static void rect(int x, int y, int w, int h, uint32_t c) {
  if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
  if (x + w > width) w = width - x; if (y + h > height) h = height - y;
  for (int yy = y; yy < y + h; yy++) for (int xx = x; xx < x + w; xx++) pixels[yy * width + xx] = c;
}
static void text(const char *value, int x, int y, int w, int h, int size, uint32_t color) {
  cairo_surface_t *cs=cairo_image_surface_create_for_data((unsigned char *)pixels,
    CAIRO_FORMAT_ARGB32,width,height,stride);
  cairo_t *cr=cairo_create(cs);
  PangoLayout *layout=pango_cairo_create_layout(cr);
  PangoFontDescription *font=pango_font_description_new();
  pango_font_description_set_family(font,"DejaVu Sans");
  pango_font_description_set_absolute_size(font,size*PANGO_SCALE);
  pango_layout_set_font_description(layout,font);
  pango_layout_set_text(layout,value,-1);
  pango_layout_set_width(layout,w*PANGO_SCALE);
  pango_layout_set_height(layout,-1);
  pango_layout_set_ellipsize(layout,PANGO_ELLIPSIZE_END);
  pango_layout_set_alignment(layout,PANGO_ALIGN_CENTER);
  int th; pango_layout_get_pixel_size(layout,NULL,&th);
  cairo_rectangle(cr,x,y,w,h); cairo_clip(cr);
  cairo_set_source_rgb(cr,((color>>16)&255)/255.0,((color>>8)&255)/255.0,(color&255)/255.0);
  cairo_move_to(cr,x,y+(h-th)/2); pango_cairo_show_layout(cr,layout);
  pango_font_description_free(font); g_object_unref(layout);
  cairo_destroy(cr); cairo_surface_destroy(cs);
}
static void add_button(int action,const char *label,const char *hint,int x,int y,int w,int h,uint32_t color) {
  buttons[button_count++]=(struct button){action,x,y,w,h,label,hint,color};
}
static void draw(void) {
  if(help_page){ rect(0,0,width,height,0xff111827); text("Help",24,22,width-48,64,42,0xfff8fafc); const char *t[]={"Apps: launch tools","Keyboard: show or hide","Windows/Home: focus or recover","System: confirm actions","Terminal and Monitor","Previous/Next: more apps"}; button_count=0; int h=(height-250)/6; for(int i=0;i<6;i++) add_button(ACT_HELP,t[i],NULL,24,110+i*h,width-48,h-8,0xff243547); add_button(ACT_BACK,"Back",NULL,24,height-110,width-48,86,0xff374151); for(int i=0;i<button_count;i++){struct button*b=&buttons[i];rect(b->x,b->y,b->w,b->h,b->color);text(b->label,b->x+8,b->y,b->w-16,b->h,24,0xffffffff);} return; }
  int count=4+(int)apps->len;
  page_size=height<900?3:4;
  int pages=(count+page_size-1)/page_size;
  if(page>=pages) page=pages-1;
  rect(0,0,width,height,0xff111827);
  text("Applications",24,22,width-48,64,42,0xfff8fafc);
  char subtitle[100];
  snprintf(subtitle,sizeof subtitle,"%u installed · Page %d of %d",apps->len,page+1,pages);
  text(launch_error?launch_error:subtitle,24,90,width-48,44,22,
    launch_error?0xfffca5a5:0xffcbd5e1);
  int top=150,gap=14,footer=height-110;
  int bh=(footer-top-24-(page_size-1)*gap)/page_size;
  button_count=0;
  for(int row=0;row<page_size;row++) {
    int item=page*page_size+row;
    if(item>=count) break;
    if(item<3) {
      const char *labels[]={"Terminal","Monitor","New terminal"};
      const char *hints[]={"Resume or open a terminal","Resume or open system monitor","Open another terminal"};
      add_button(-item-1,labels[item],hints[item],24,top+row*(bh+gap),width-48,bh,0xff24495a);
    } else if(item==3) { add_button(ACT_HELP,"Help","How to use this shell",24,top+row*(bh+gap),width-48,bh,0xff3f556b);
    } else {
      GAppInfo *app=g_ptr_array_index(apps,item-4);
      add_button(item-4,g_app_info_get_display_name(app),"Installed application",24,
        top+row*(bh+gap),width-48,bh,0xff243547);
    }
  }
  int bw=(width-64)/3;
  add_button(ACT_PREVIOUS,"Previous",NULL,24,footer,bw,86,page?0xff304f65:0xff202b38);
  add_button(ACT_BACK,"Back",NULL,32+bw,footer,bw,86,0xff374151);
  add_button(ACT_NEXT,"Next",NULL,40+2*bw,footer,bw,86,page+1<pages?0xff304f65:0xff202b38);
  for(int i=0;i<button_count;i++) {
    struct button *b=&buttons[i];
    rect(b->x,b->y,b->w,b->h,b->color);
    if(b->hint) {
      text(b->label,b->x+12,b->y+b->h/2-42,b->w-24,52,32,0xffffffff);
      text(b->hint,b->x+12,b->y+b->h/2+10,b->w-24,30,18,0xffcbd5e1);
    } else text(b->label,b->x+8,b->y,b->w-16,b->h,24,0xffffffff);
  }
}
static int card_at(int x,int y) {
  for(int i=0;i<button_count;i++) {
    struct button *b=&buttons[i];
    if(x>=b->x && x<b->x+b->w && y>=b->y && y<b->y+b->h) return i;
  }
  return -1;
}
static void run_action(int action) {
  if(action==ACT_BACK) { if(help_page){help_page=false;redraw();}else running=false; return; }
  if(action==ACT_HELP) { help_page=true; redraw(); return; }
  if(action==ACT_PREVIOUS || action==ACT_NEXT) {
    int pages=(4+(int)apps->len+page_size-1)/page_size;
    int next=page+(action==ACT_NEXT?1:-1);
    if(next>=0 && next<pages) { page=next; g_clear_pointer(&launch_error,g_free); redraw(); }
    return;
  }
  GError *error=NULL;
  gboolean ok=FALSE;
  if(action>=0) {
    GAppInfo *app=g_ptr_array_index(apps,action);
    ok=k230_app_launch(g_app_info_get_id(app),&error);
  } else {
    const char *helper=getenv("K230_LAUNCHER_ACTION");
    const char *name=action==ACT_TERMINAL?"terminal":action==ACT_MONITOR?"monitor":"new-terminal";
    if(helper && *helper) {
      char *argv[]={(char *)helper,(char *)name,NULL};
      ok=g_spawn_async(NULL,argv,NULL,G_SPAWN_DEFAULT,NULL,NULL,NULL,&error);
    } else g_set_error_literal(&error,G_IO_ERROR,G_IO_ERROR_NOT_FOUND,"Application action is unavailable");
  }
  if(ok) { running=false; return; }
  g_free(launch_error); launch_error=g_strdup(error?error->message:"Could not launch application");
  fprintf(stderr,"k230-touch-launcher: %s\n",launch_error);
  g_clear_error(&error); redraw();
}
static void activate_card(int card) { if(card>=0 && card<button_count) run_action(buttons[card].action); }
static void buffer_release(void *d, struct wl_buffer *b) {
  struct shm_buffer *old = d; munmap(old->pixels, old->size); wl_buffer_destroy(b); free(old);
}
static const struct wl_buffer_listener buffer_listener = { .release = buffer_release };
static struct shm_buffer *make_buffer(void) {
  stride = width * 4; mapped_size = stride * height; char name[64]; int fd = -1;
  for (int i = 0; i < 100 && fd < 0; i++) { snprintf(name, sizeof name, "/k230-launcher-%d-%d", getpid(), i); fd = shm_open(name, O_RDWR|O_CREAT|O_EXCL, 0600); }
  if (fd < 0 || ftruncate(fd, mapped_size) < 0) { perror("k230-touch-launcher shm"); exit(1); }
  shm_unlink(name); struct shm_buffer *out = calloc(1, sizeof *out); if(!out) { perror("k230-touch-launcher calloc"); close(fd); exit(1); } out->size = mapped_size;
  out->pixels = mmap(NULL, mapped_size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
  if (out->pixels == MAP_FAILED) { perror("k230-touch-launcher mmap"); exit(1); }
  struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, mapped_size);
  if(!pool) { close(fd); munmap(out->pixels,out->size); free(out); exit(1); }
  out->buffer = wl_shm_pool_create_buffer(pool, 0, width, height, stride, WL_SHM_FORMAT_ARGB8888);
  wl_shm_pool_destroy(pool); close(fd);
  if(!out->buffer || wl_buffer_add_listener(out->buffer,&buffer_listener,out)<0) {
    if(out->buffer) wl_buffer_destroy(out->buffer); munmap(out->pixels,out->size); free(out); exit(1);
  }
  return out;
}
static void redraw(void) {
  current=make_buffer(); pixels=current->pixels; draw();
  wl_surface_attach(surface,current->buffer,0,0);
  wl_surface_damage_buffer(surface,0,0,width,height); wl_surface_commit(surface);
}
static void layer_configure(void *d,struct zwlr_layer_surface_v1 *ls,uint32_t serial,uint32_t w,uint32_t h) {
  zwlr_layer_surface_v1_ack_configure(ls,serial);
  if((int)w==width && (int)h==height && configured) return;
  width=(int)w; height=(int)h;
  if(width<300 || height<600 || width>4096 || height>4096) {
    fprintf(stderr,"k230-touch-launcher: unsupported surface size\n"); running=false; return;
  }
  pointer_card=touch_card=-1; pointer_pressed=false; pointer_button_code=0; touch_id=-1;
  redraw(); configured=true;
}
static void layer_closed(void *d, struct zwlr_layer_surface_v1 *ls) { running=false; }
static const struct zwlr_layer_surface_v1_listener layer_listener = { .configure=layer_configure, .closed=layer_closed };
static void pointer_enter(void*d,struct wl_pointer*p,uint32_t s,struct wl_surface*sf,wl_fixed_t x,wl_fixed_t y) { press_x=wl_fixed_to_int(x); press_y=wl_fixed_to_int(y); }
static void pointer_leave(void*d,struct wl_pointer*p,uint32_t s,struct wl_surface*sf) { pointer_pressed=false; pointer_card=-1; }
static void pointer_motion(void*d,struct wl_pointer*p,uint32_t t,wl_fixed_t x,wl_fixed_t y) { press_x=wl_fixed_to_int(x); press_y=wl_fixed_to_int(y); if (pointer_pressed && card_at(press_x,press_y) != pointer_card) pointer_card=-1; }
static void pointer_button(void*d,struct wl_pointer*p,uint32_t s,uint32_t t,uint32_t b,uint32_t state) {
  if (state == WL_POINTER_BUTTON_STATE_PRESSED && b == 0x110) { pointer_pressed=true; pointer_button_code=b; pointer_card=card_at(press_x,press_y); }
  if (state == WL_POINTER_BUTTON_STATE_RELEASED && pointer_pressed && b == pointer_button_code) { pointer_pressed=false; if (pointer_card == card_at(press_x,press_y)) activate_card(pointer_card); pointer_card=-1; }
}
static void pointer_axis(void*d,struct wl_pointer*p,uint32_t t,uint32_t a,wl_fixed_t v) {}
static const struct wl_pointer_listener pointer_listener = { .enter=pointer_enter,.leave=pointer_leave,.motion=pointer_motion,.button=pointer_button,.axis=pointer_axis };
static void touch_down(void*d,struct wl_touch*t,uint32_t s,uint32_t tm,struct wl_surface*sf,int32_t id,wl_fixed_t x,wl_fixed_t y) { if (touch_id != -1) return; touch_id=id; touch_x=wl_fixed_to_int(x); touch_y=wl_fixed_to_int(y); touch_card=card_at(touch_x,touch_y); }
static void touch_up(void*d,struct wl_touch*t,uint32_t s,uint32_t tm,int32_t id) { if(id==touch_id) { if (touch_card == card_at(touch_x,touch_y)) activate_card(touch_card); touch_id=-1; touch_card=-1; } }
static void touch_motion(void*d,struct wl_touch*t,uint32_t tm,int32_t id,wl_fixed_t x,wl_fixed_t y) { if(id==touch_id) { touch_x=wl_fixed_to_int(x); touch_y=wl_fixed_to_int(y); if (card_at(touch_x,touch_y) != touch_card) touch_card=-1; } }
static void touch_frame(void*d,struct wl_touch*t) {} static void touch_cancel(void*d,struct wl_touch*t) { touch_id=-1; touch_card=-1; }
static const struct wl_touch_listener touch_listener = { .down=touch_down,.up=touch_up,.motion=touch_motion,.frame=touch_frame,.cancel=touch_cancel };
static void seat_caps(void*d,struct wl_seat*s,uint32_t caps) { if ((caps&WL_SEAT_CAPABILITY_POINTER) && !pointer) { pointer=wl_seat_get_pointer(s); wl_pointer_add_listener(pointer,&pointer_listener,NULL); } if ((caps&WL_SEAT_CAPABILITY_TOUCH) && !touch) { touch=wl_seat_get_touch(s); wl_touch_add_listener(touch,&touch_listener,NULL); } }
static void seat_name(void*d,struct wl_seat*s,const char*n) {}
static const struct wl_seat_listener seat_listener = { .capabilities=seat_caps,.name=seat_name };
static void global_add(void*d,struct wl_registry*r,uint32_t n,const char*i,uint32_t v) { if(!strcmp(i,wl_compositor_interface.name)) { if (v < 4) return; compositor=wl_registry_bind(r,n,&wl_compositor_interface,4); } else if(!strcmp(i,wl_shm_interface.name)) shm=wl_registry_bind(r,n,&wl_shm_interface,1); else if(!strcmp(i,wl_seat_interface.name)) { seat=wl_registry_bind(r,n,&wl_seat_interface,1); wl_seat_add_listener(seat,&seat_listener,NULL); } else if(!strcmp(i,zwlr_layer_shell_v1_interface.name)) layer_shell=wl_registry_bind(r,n,&zwlr_layer_shell_v1_interface,1); }
static void global_remove(void*d,struct wl_registry*r,uint32_t n) {}
static const struct wl_registry_listener registry_listener = { .global=global_add,.global_remove=global_remove };
int main(int argc,char**argv) {
 if(argc==2 && !strcmp(argv[1],"--layout")) { puts("Portrait application catalogue: 4 cards per page, 3 with keyboard; Previous / Back / Next"); return 0; }
 if(argc!=1) { fprintf(stderr,"usage: k230-touch-launcher [--layout]\n"); return 2; }
 const char *runtime = getenv("XDG_RUNTIME_DIR");
 if (!runtime) { fprintf(stderr,"k230-touch-launcher: XDG_RUNTIME_DIR is unset\n"); return 1; }
 char lock_path[512]; snprintf(lock_path, sizeof lock_path, "%s/k230-touch-launcher.lock", runtime);
 lock_fd=open(lock_path,O_CREAT|O_RDWR|O_CLOEXEC,0600);
 if(lock_fd < 0) { perror("k230-touch-launcher lock"); return 1; }
 if(flock(lock_fd,LOCK_EX|LOCK_NB) < 0) return 0; /* Existing surface stays usable. */
 apps=k230_app_catalog();
 display=wl_display_connect(NULL); if(!display) { fprintf(stderr,"k230-touch-launcher: cannot connect to Wayland\n"); return 1; }
 struct wl_registry*r=wl_display_get_registry(display); wl_registry_add_listener(r,&registry_listener,NULL); wl_display_roundtrip(display);
 if(!compositor||!shm||!layer_shell||!seat) { fprintf(stderr,"k230-touch-launcher: need wl_compositor, wl_shm, layer-shell, and a seat\n"); return 1; }
 surface=wl_compositor_create_surface(compositor); layer_surface=zwlr_layer_shell_v1_get_layer_surface(layer_shell,surface,NULL,ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY,"k230-launcher"); zwlr_layer_surface_v1_add_listener(layer_surface,&layer_listener,NULL);
 zwlr_layer_surface_v1_set_anchor(layer_surface, ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP|ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM|ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT|ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT); zwlr_layer_surface_v1_set_margin(layer_surface,0,0,0,0); zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface,ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE); zwlr_layer_surface_v1_set_exclusive_zone(layer_surface,0); wl_surface_commit(surface);
 while(running && wl_display_dispatch(display)>=0) {} return 0;
}
