/* Portrait desktop-entry launcher on Wayland SHM/layer-shell. GLib owns
 * desktop-entry semantics; Pango/Cairo render installed application names. */
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <signal.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/file.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include <pango/pangocairo.h>
#include "catalog.h"
#include "wlr-layer-shell-unstable-v1-client-protocol.h"
#include "xdg-shell-client-protocol.h"

#include "navigation.h"
#include "gesture.h"
#include "overview.h"

struct button { int action, x, y, w, h; const char *label, *hint; uint32_t color; };
static struct button buttons[8];
static int button_count;
static struct launcher_navigation navigation = { .page_size = 4 };
static struct launcher_overview overview = { .page_size = 4 };
static struct launcher_gesture gesture = { .id = -1 };
struct window_card { char *id, *title, *app_id, *state; };
static GPtrArray *apps, *windows;
#define ACT_WINDOW_BASE 10000
#define WINDOW_CATALOG_MAX_BYTES (64 * 1024)
static const int transition_budget_ms = 200;
enum catalog_purpose { CATALOG_IDLE, CATALOG_OPEN, CATALOG_FOCUS };
struct catalog_request {
  GPid pid;
  gint output_fd;
  GString *output;
  int64_t deadline_ms;
  enum catalog_purpose purpose;
  char *focus_id;
  bool term_sent, kill_sent, reported_failure;
};
static struct catalog_request catalog = { .output_fd = -1 };
enum transition_direction { TRANSITION_LEFT, TRANSITION_RIGHT, TRANSITION_UP, TRANSITION_DOWN };
struct page_transition {
  bool active;
  enum transition_direction direction;
  uint32_t *source, *destination;
  size_t bytes;
  int64_t release_ms, started_ms;
  struct wl_callback *callback;
};
static struct page_transition transition;
static char *launch_error;
static void redraw(void);
static bool transition_prepare(void);
static void transition_begin(enum transition_direction direction);
static void redraw_if_configured(void);
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
static uint32_t *last_frame;
static size_t last_frame_bytes;
static int width, height, stride, mapped_size;
static int lock_fd = -1;
static bool running = true, configured;
static volatile sig_atomic_t shutdown_requested;
static int press_x, press_y, touch_x, touch_y, touch_id = -1;
static bool pointer_pressed;
static void redraw_if_configured(void) {
  if (configured && surface && !transition.active) redraw();
}
static uint32_t pointer_button_code;
static int pointer_card = -1, touch_card = -1;
static int touch_contact_count;
static bool touch_from_card, touch_rejected, gestures_enabled;

static void rect(int x, int y, int w, int h, uint32_t c) {
  if (x < 0) { w += x; x = 0; } if (y < 0) { h += y; y = 0; }
  if (x + w > width) w = width - x;
  if (y + h > height) h = height - y;
  for (int yy = y; yy < y + h; yy++) for (int xx = x; xx < x + w; xx++) pixels[yy * width + xx] = c;
}
static void text_layout(const char *value, int x, int y, int w, int h, int size, uint32_t color, bool wrap) {
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
  pango_layout_set_height(layout,wrap?h*PANGO_SCALE:-1);
  pango_layout_set_wrap(layout,PANGO_WRAP_WORD_CHAR);
  pango_layout_set_ellipsize(layout,PANGO_ELLIPSIZE_END);
  pango_layout_set_alignment(layout,PANGO_ALIGN_CENTER);
  int th; pango_layout_get_pixel_size(layout,NULL,&th);
  cairo_rectangle(cr,x,y,w,h); cairo_clip(cr);
  cairo_set_source_rgb(cr,((color>>16)&255)/255.0,((color>>8)&255)/255.0,(color&255)/255.0);
  cairo_move_to(cr,x,y+(h-th)/2); pango_cairo_show_layout(cr,layout);
  pango_font_description_free(font); g_object_unref(layout);
  cairo_destroy(cr); cairo_surface_destroy(cs);
}
static void text(const char *value, int x, int y, int w, int h, int size, uint32_t color) {
  text_layout(value,x,y,w,h,size,color,false);
}
static const struct { const char *label, *hint; } help_topics[HELP_TOPIC_COUNT] = {
  {"Apps", "Open installed tools or return to a running app."},
  {"Keyboard", "Show or hide the keyboard for the focused app."},
  {"Windows / Home", "Pick a window. Home returns to Terminal or opens it."},
  {"System", "Reboot or power off. Confirm the action, or tap Cancel."},
  {"Terminal", "Type commands. New terminal opens another window."},
  {"Monitor", "See running programs and memory use."},
  {"Back", "Leave Help for Apps, or close Apps to return to your work."},
  {"Previous / Next", "Turn pages in Apps and Help."},
};
static void add_button(int action,const char *label,const char *hint,int x,int y,int w,int h,uint32_t color) {
  buttons[button_count++]=(struct button){action,x,y,w,h,label,hint,color};
}
static void free_window_card(gpointer value) {
  struct window_card *card = value;
  if (!card) return;
  g_free(card->id); g_free(card->title); g_free(card->app_id); g_free(card->state); g_free(card);
}
static bool valid_window_id(const char *value) {
  if (!value || !*value) return false;
  for (const unsigned char *p=(const unsigned char *)value; *p; p++) if (!isdigit(*p)) return false;
  return true;
}
static int64_t monotonic_ms(void) {
  struct timespec now;
  clock_gettime(CLOCK_MONOTONIC, &now);
  return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}
static void catalog_child_setup(gpointer unused) {
  (void)unused;
  (void)setpgid(0, 0);
}
static GPtrArray *parse_window_catalog(const char *text) {
  GPtrArray *out=g_ptr_array_new_with_free_func(free_window_card);
  gchar **lines=g_strsplit(text,"\n",-1);
  for (gchar **line=lines; *line; line++) {
    gchar **fields=g_strsplit(*line,"\t",4);
    if (valid_window_id(fields[0]) && fields[1] && fields[2] && fields[3]) {
      struct window_card *card=g_new0(struct window_card,1);
      card->id=g_strdup(fields[0]);
      card->title=g_strdup(fields[1]);
      card->app_id=g_strdup(fields[2]);
      card->state=g_strdup(fields[3]);
      g_ptr_array_add(out,card);
    }
    g_strfreev(fields);
  }
  g_strfreev(lines);
  return out;
}
static void replace_windows(GPtrArray *fresh) {
  if (windows) g_ptr_array_unref(windows);
  windows=fresh;
}
static void clear_windows(void) {
  replace_windows(g_ptr_array_new_with_free_func(free_window_card));
}
static void catalog_error(const char *message) {
  g_free(launch_error);
  launch_error=g_strdup(message);
}
static void catalog_close_io(void) {
  if (catalog.output_fd >= 0) close(catalog.output_fd);
  catalog.output_fd=-1;
  if (catalog.output) g_string_free(catalog.output, true);
  catalog.output=NULL;
}
static void catalog_reap(void) {
  if (catalog.pid) g_spawn_close_pid(catalog.pid);
  catalog.pid=0;
  catalog_close_io();
  g_clear_pointer(&catalog.focus_id,g_free);
  catalog.purpose=CATALOG_IDLE;
  catalog.term_sent=false;
  catalog.kill_sent=false;
  catalog.reported_failure=false;
}
static void catalog_fail(const char *message) {
  if (!catalog.reported_failure) {
    catalog_error(message);
    clear_windows();
    catalog.reported_failure=true;
    redraw_if_configured();
  }
}
static void catalog_signal(int signal_number) {
  if (catalog.pid) {
    /* The child creates its own process group so a hung helper cannot retain
     * a pipeline child after the launcher has returned to its event loop. */
    (void)kill(-catalog.pid, signal_number);
  }
}
static void catalog_cancel(void) {
  if (!catalog.pid) return;
  g_clear_pointer(&catalog.focus_id,g_free);
  catalog.purpose=CATALOG_IDLE;
  catalog.reported_failure=true;
  if (catalog.output_fd >= 0) close(catalog.output_fd);
  catalog.output_fd=-1;
  if (!catalog.term_sent) {
    catalog_signal(SIGTERM);
    catalog.term_sent=true;
    catalog.deadline_ms=monotonic_ms()+20;
  }
}
static bool catalog_start(enum catalog_purpose purpose, const char *focus_id) {
  const char *helper=getenv("K230_WINDOW_CATALOG");
  char *argv[]={(char *)helper,NULL};
  GError *error=NULL;
  if (catalog.pid) {
    catalog_error("Window overview is still refreshing");
    return false;
  }
  if (!helper || !*helper) {
    catalog_error("Window overview helper is unavailable");
    return false;
  }
  if (!g_spawn_async_with_pipes(NULL,argv,NULL,G_SPAWN_DO_NOT_REAP_CHILD,
      catalog_child_setup,NULL,&catalog.pid,NULL,&catalog.output_fd,NULL,&error)) {
    catalog_error(error ? error->message : "Could not start window overview");
    g_clear_error(&error);
    return false;
  }
  catalog.output=g_string_sized_new(1024);
  catalog.deadline_ms=monotonic_ms()+transition_budget_ms;
  catalog.purpose=purpose;
  catalog.focus_id=g_strdup(focus_id);
  catalog.term_sent=false;
  catalog.kill_sent=false;
  catalog.reported_failure=false;
  int flags=fcntl(catalog.output_fd,F_GETFL);
  if (flags < 0 || fcntl(catalog.output_fd,F_SETFL,flags|O_NONBLOCK) < 0) {
    catalog_fail("Could not read window overview");
    catalog_signal(SIGKILL);
    catalog.kill_sent=true;
    return false;
  }
  return true;
}
static void finish_window_focus(const char *id) {
  const char *sway=getenv("K230_SWAYMSG");
  char criterion[64];
  GError *error=NULL;
  if (!sway || !*sway || !valid_window_id(id)) {
    catalog_error("Window focus is unavailable");
    redraw_if_configured();
    return;
  }
  snprintf(criterion,sizeof criterion,"[con_id=%s]",id);
  char *argv[]={(char *)sway,criterion,"focus",NULL};
  /* Yield the non-interactive layer before asking Sway to focus the target. */
  if (configured && surface) {
    running=false;
    wl_surface_attach(surface,NULL,0,0);
    wl_surface_commit(surface);
    wl_display_flush(display);
  }
  if (!g_spawn_async(NULL,argv,NULL,G_SPAWN_DEFAULT,NULL,NULL,NULL,&error)) {
    running=true;
    catalog_error(error ? error->message : "Could not focus window");
    g_clear_error(&error);
    redraw_if_configured();
  }
}
static void catalog_complete(int status) {
  enum catalog_purpose purpose=catalog.purpose;
  char *focus_id=g_steal_pointer(&catalog.focus_id);
  GPtrArray *fresh=NULL;
  if (WIFEXITED(status) && WEXITSTATUS(status)==0 && !catalog.reported_failure)
    fresh=parse_window_catalog(catalog.output ? catalog.output->str : "");
  if (!fresh) {
    catalog_fail("Window overview refresh failed");
    catalog_reap();
    g_free(focus_id);
    return;
  }
  replace_windows(fresh);
  catalog_reap();
  g_clear_pointer(&launch_error,g_free);
  if (purpose==CATALOG_OPEN) {
    redraw_if_configured();
  } else if (purpose==CATALOG_FOCUS) {
    bool found=false;
    for (guint i=0; focus_id && i<windows->len; i++) {
      struct window_card *card=g_ptr_array_index(windows,i);
      if (!strcmp(card->id,focus_id)) { found=true; break; }
    }
    if (found) finish_window_focus(focus_id);
    else { catalog_error("Window closed; overview refreshed"); redraw_if_configured(); }
  }
  g_free(focus_id);
}
static void catalog_poll(void) {
  if (!catalog.pid) return;
  char chunk[1024];
  ssize_t count;
  while ((count=read(catalog.output_fd,chunk,sizeof chunk)) > 0) {
    if (catalog.output->len + (gsize)count > WINDOW_CATALOG_MAX_BYTES) {
      catalog_fail("Window overview output is too large");
      if (catalog.output_fd >= 0) close(catalog.output_fd);
      catalog.output_fd=-1;
      if (!catalog.term_sent) {
        catalog_signal(SIGTERM);
        catalog.term_sent=true;
        catalog.deadline_ms=monotonic_ms()+20;
      }
      return;
    }
    g_string_append_len(catalog.output,chunk,count);
  }
  int status=0;
  if (waitpid(catalog.pid,&status,WNOHANG)>0) {
    catalog_complete(status);
    return;
  }
  int64_t now=monotonic_ms();
  if (now < catalog.deadline_ms) return;
  if (!catalog.term_sent) {
    catalog_fail("Window overview refresh exceeded 200 ms");
    catalog_signal(SIGTERM);
    catalog.term_sent=true;
    catalog.deadline_ms=now+20;
  } else if (!catalog.kill_sent) {
    catalog_signal(SIGKILL);
    catalog.kill_sent=true;
  }
}
static void begin_overview(void) {
  bool animate=transition_prepare();
  overview_open(&overview);
  clear_windows();
  catalog_error("Loading windows…");
  if (!catalog_start(CATALOG_OPEN,NULL)) clear_windows();
  if (animate) transition_begin(TRANSITION_UP);
  else redraw_if_configured();
}
static void draw_overview(void) {
  int count=windows?(int)windows->len:0;
  overview.page_size=height<900?3:4;
  int pages=overview_pages(&overview,count);
  if (overview.page>=pages) overview.page=pages-1;
  rect(0,0,width,height,0xff111827); text("Windows",24,22,width-48,64,42,0xfff8fafc);
  char subtitle[100]; snprintf(subtitle,sizeof subtitle,count?"%d running · Page %d of %d":"No running windows · Back returns to Apps",count,overview.page+1,pages);
  text(launch_error?launch_error:subtitle,24,90,width-48,44,22,launch_error?0xfffca5a5:0xffcbd5e1);
  int top=150,gap=14,footer=height-110,bh=(footer-top-24-(overview.page_size-1)*gap)/overview.page_size;
  button_count=0;
  if (!count) add_button(ACT_NONE,"No windows","Open an app, then return here",24,top,width-48,bh,0xff243547);
  for(int row=0;row<overview.page_size;row++) { int item=overview.page*overview.page_size+row; if(item>=count) break;
    struct window_card *card=g_ptr_array_index(windows,item); char *hint=g_strdup_printf("%s · %s",card->app_id,card->state);
    add_button(ACT_WINDOW_BASE+item,card->title,hint,24,top+row*(bh+gap),width-48,bh,0xff24495a); }
  int bw=(width-64)/3;
  add_button(ACT_PREVIOUS,"Previous",NULL,24,footer,bw,86,overview.page?0xff304f65:0xff202b38);
  add_button(ACT_BACK,"Back",NULL,32+bw,footer,bw,86,0xff374151);
  add_button(ACT_NEXT,"Next",NULL,40+2*bw,footer,bw,86,overview.page+1<pages?0xff304f65:0xff202b38);
  for(int i=0;i<button_count;i++) { struct button *b=&buttons[i]; rect(b->x,b->y,b->w,b->h,b->color);
    if(b->hint) { text(b->label,b->x+12,b->y+b->h/2-42,b->w-24,52,30,0xffffffff); text(b->hint,b->x+12,b->y+b->h/2+10,b->w-24,30,18,0xffcbd5e1); }
    else text(b->label,b->x+8,b->y,b->w-16,b->h,24,0xffffffff);
    if (b->action >= ACT_WINDOW_BASE) g_free((char *)b->hint);
  }
}
static void draw(void) {
  if (overview.open) { draw_overview(); return; }
  navigation.page_size=height<900?3:4;
  int page_size=navigation.page_size;
  int count=navigation.help?HELP_TOPIC_COUNT:BUILTIN_COUNT+(int)apps->len;
  int pages=launcher_pages(&navigation,(int)apps->len);
  int *current_page=navigation.help?&navigation.help_page:&navigation.page;
  if(*current_page>=pages) *current_page=pages-1;
  int page=launcher_current_page(&navigation);
  rect(0,0,width,height,0xff111827);
  text(navigation.help?"Help":"Applications",24,22,width-48,64,42,0xfff8fafc);
  char subtitle[100];
  if(navigation.help) snprintf(subtitle,sizeof subtitle,"Shell controls · Page %d of %d",page+1,pages);
  else snprintf(subtitle,sizeof subtitle,"%u installed · Page %d of %d",apps->len,page+1,pages);
  bool show_error=launch_error && !navigation.help;
  text(show_error?launch_error:subtitle,24,90,width-48,44,22,
    show_error?0xfffca5a5:0xffcbd5e1);
  int top=150,gap=14,footer=height-110;
  int bh=(footer-top-24-(page_size-1)*gap)/page_size;
  button_count=0;
  for(int row=0;row<page_size;row++) {
    int item=page*page_size+row;
    if(item>=count) break;
    if(navigation.help) {
      add_button(ACT_NONE,help_topics[item].label,help_topics[item].hint,
        24,top+row*(bh+gap),width-48,bh,0xff243547);
    } else if(item<3) {
      const char *labels[]={"Terminal","Monitor","New terminal"};
      const char *hints[]={"Resume or open a terminal","Resume or open system monitor","Open another terminal"};
      add_button(launcher_item_action(item),labels[item],hints[item],24,top+row*(bh+gap),width-48,bh,0xff24495a);
    } else if(item==3) { add_button(ACT_HELP,"Help","How to use this shell",24,top+row*(bh+gap),width-48,bh,0xff3f556b);
    } else {
      GAppInfo *app=g_ptr_array_index(apps,item-BUILTIN_COUNT);
      add_button(launcher_item_action(item),g_app_info_get_display_name(app),"Installed application",24,
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
    if(navigation.help && b->hint) {
      text(b->label,b->x+12,b->y+8,b->w-24,40,28,0xffffffff);
      text_layout(b->hint,b->x+16,b->y+48,b->w-32,b->h-56,20,0xffcbd5e1,true);
    } else if(b->hint) {
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
static void focus_window_card(int item) {
  struct window_card *selected=(item>=0 && windows && (guint)item<windows->len)
    ? g_ptr_array_index(windows,item) : NULL;
  /* The old card array may be replaced after refresh; retain its ID first. */
  char *id=selected ? g_strdup(selected->id) : NULL;
  if (!id || !valid_window_id(id)) {
    g_free(id);
    catalog_error("Window is no longer available");
    redraw();
    return;
  }
  catalog_error("Refreshing window…");
  if (!catalog_start(CATALOG_FOCUS,id)) {
    clear_windows();
    redraw();
  } else {
    redraw();
  }
  g_free(id);
}
static void run_action(int action) {
  if (overview.open) {
    if (action==ACT_BACK) { catalog_cancel(); overview_close(&overview); g_clear_pointer(&launch_error,g_free); redraw(); return; }
    if (action==ACT_PREVIOUS || action==ACT_NEXT) { overview_page(&overview,action==ACT_NEXT?1:-1,windows?(int)windows->len:0); redraw(); return; }
    if (action>=ACT_WINDOW_BASE) { focus_window_card(action-ACT_WINDOW_BASE); return; }
    return;
  }
  int navigation_result=launcher_navigate(&navigation,action,(int)apps->len);
  if(navigation_result==2) { running=false; return; }
  if(navigation_result==1) { redraw(); return; }
  if(action>=0 && (unsigned)action>=apps->len) return;
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
static void activate_card(int card) {
  if (!transition.active && card>=0 && card<button_count) run_action(buttons[card].action);
}
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
static bool save_last_frame(const uint32_t *source) {
  if (last_frame_bytes != (size_t)mapped_size) {
    uint32_t *replacement=realloc(last_frame,(size_t)mapped_size);
    if (!replacement) return false;
    last_frame=replacement;
    last_frame_bytes=(size_t)mapped_size;
  }
  memcpy(last_frame,source,last_frame_bytes);
  return true;
}
static void redraw(void) {
  current=make_buffer(); pixels=current->pixels; draw();
  (void)save_last_frame(pixels);
  wl_surface_attach(surface,current->buffer,0,0);
  wl_surface_damage_buffer(surface,0,0,width,height); wl_surface_commit(surface);
}
static void transition_cleanup(void) {
  if (transition.callback) wl_callback_destroy(transition.callback);
  transition.callback=NULL;
  free(transition.source);
  free(transition.destination);
  memset(&transition,0,sizeof transition);
}
static void transition_trace(int64_t render_ms, int64_t elapsed_ms, bool settled) {
  const char *path=getenv("K230_LAUNCHER_METRICS");
  if (!path || !*path) return;
  FILE *metrics=fopen(path,"a");
  if (!metrics) return;
  fprintf(metrics,"transition render_wall_ms=%lld release_to_submit_wall_ms=%lld extra_bytes=%zu settled=%d\n",
    (long long)render_ms,(long long)elapsed_ms,transition.bytes*2,settled ? 1 : 0);
  fclose(metrics);
}
static void transition_settle(void) {
  if (!transition.active) return;
  int64_t render_started=monotonic_ms();
  /* Submit the destination prepared at release; do not redraw it here. */
  current=make_buffer();
  pixels=current->pixels;
  memcpy(pixels,transition.destination,transition.bytes);
  (void)save_last_frame(pixels);
  wl_surface_attach(surface,current->buffer,0,0);
  wl_surface_damage_buffer(surface,0,0,width,height);
  wl_surface_commit(surface);
  transition_trace(monotonic_ms()-render_started,
    monotonic_ms()-transition.started_ms,true);
  transition_cleanup();
}
static void transition_compose(uint32_t *out, int progress) {
  if (transition.direction==TRANSITION_LEFT) {
    for (int y=0; y<height; y++) {
      memcpy(out+y*width,transition.source+y*width+progress,(size_t)(width-progress)*sizeof *out);
      memcpy(out+y*width+width-progress,transition.destination+y*width,(size_t)progress*sizeof *out);
    }
  } else if (transition.direction==TRANSITION_RIGHT) {
    for (int y=0; y<height; y++) {
      memcpy(out+y*width,transition.destination+y*width+width-progress,(size_t)progress*sizeof *out);
      memcpy(out+y*width+progress,transition.source+y*width,(size_t)(width-progress)*sizeof *out);
    }
  } else if (transition.direction==TRANSITION_UP) {
    memcpy(out,transition.source+(size_t)progress*width,(size_t)(height-progress)*width*sizeof *out);
    memcpy(out+(size_t)(height-progress)*width,transition.destination,(size_t)progress*width*sizeof *out);
  } else {
    memcpy(out,transition.destination+(size_t)(height-progress)*width,(size_t)progress*width*sizeof *out);
    memcpy(out+(size_t)progress*width,transition.source,(size_t)(height-progress)*width*sizeof *out);
  }
}
static void transition_present(void);
static void transition_frame_done(void *unused, struct wl_callback *callback, uint32_t time) {
  (void)unused; (void)time;
  if (transition.callback==callback) transition.callback=NULL;
  wl_callback_destroy(callback);
  if (!transition.active) return;
  int64_t elapsed=monotonic_ms()-transition.started_ms;
  if (elapsed>=120 || elapsed>=transition_budget_ms) {
    transition_settle();
    return;
  }
  transition_present();
}
static const struct wl_callback_listener transition_frame_listener = { .done=transition_frame_done };
static void transition_present(void) {
  int64_t render_started=monotonic_ms();
  int64_t elapsed=render_started-transition.started_ms;
  int axis=(transition.direction==TRANSITION_LEFT || transition.direction==TRANSITION_RIGHT) ? width : height;
  int progress=(int)(axis*(elapsed<120 ? elapsed : 120)/120);
  if (progress<0) progress=0;
  if (progress>axis) progress=axis;
  current=make_buffer();
  pixels=current->pixels;
  transition_compose(pixels,progress);
  (void)save_last_frame(pixels);
  transition.callback=wl_surface_frame(surface);
  wl_callback_add_listener(transition.callback,&transition_frame_listener,NULL);
  wl_surface_attach(surface,current->buffer,0,0);
  wl_surface_damage_buffer(surface,0,0,width,height);
  wl_surface_commit(surface);
  transition_trace(monotonic_ms()-render_started,elapsed,false);
}
static bool transition_prepare(void) {
  if (!configured || !last_frame || transition.active || mapped_size<=0 ||
      last_frame_bytes != (size_t)mapped_size) return false;
  transition.source=malloc(last_frame_bytes);
  if (!transition.source) return false;
  memcpy(transition.source,last_frame,last_frame_bytes);
  transition.bytes=last_frame_bytes;
  return true;
}
static void transition_begin(enum transition_direction direction) {
  if (!transition.source) { redraw_if_configured(); return; }
  transition.destination=malloc(transition.bytes);
  if (!transition.destination) { transition_cleanup(); redraw_if_configured(); return; }
  /* Include destination pre-rendering in the release-to-settle budget. */
  transition.direction=direction;
  transition.started_ms=transition.release_ms ? transition.release_ms : monotonic_ms();
  transition.active=true;
  uint32_t *saved=pixels;
  pixels=transition.destination;
  draw();
  pixels=saved;
  if (monotonic_ms()-transition.started_ms>=transition_budget_ms) {
    transition_settle();
    return;
  }
  transition_present();
}
static void layer_configure(void *d,struct zwlr_layer_surface_v1 *ls,uint32_t serial,uint32_t w,uint32_t h) {
  zwlr_layer_surface_v1_ack_configure(ls,serial);
  if((int)w==width && (int)h==height && configured) return;
  width=(int)w; height=(int)h;
  if(width<300 || height<600 || width>4096 || height>4096) {
    fprintf(stderr,"k230-touch-launcher: unsupported surface size\n"); running=false; return;
  }
  if (transition.active || transition.source) transition_cleanup();
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
static void page_with_transition(int action, enum transition_direction direction, int count) {
  int *page=navigation.help ? &navigation.help_page : &navigation.page;
  int before=*page;
  bool animate=transition_prepare();
  launcher_navigate(&navigation,action,count);
  if (*page==before) {
    if (animate) transition_cleanup();
    return;
  }
  if (animate) transition_begin(direction);
  else redraw();
}
static void overview_with_transition(int delta, enum transition_direction direction) {
  int before=overview.page;
  bool animate=transition_prepare();
  overview_page(&overview,delta,windows?(int)windows->len:0);
  if (overview.page==before) {
    if (animate) transition_cleanup();
    return;
  }
  if (animate) transition_begin(direction);
  else redraw();
}
static void apply_gesture(enum gesture_direction direction) {
  if (!gestures_enabled || transition.active || direction==GESTURE_NONE || direction==GESTURE_CANCELLED) return;
  /* The transition budget starts on release, before any page pre-rendering. */
  transition.release_ms=monotonic_ms();
  if (overview.open) {
    if (direction==GESTURE_DOWN) {
      bool animate=transition_prepare();
      catalog_cancel(); overview_close(&overview); g_clear_pointer(&launch_error,g_free);
      if (animate) transition_begin(TRANSITION_DOWN); else redraw();
    } else if (direction==GESTURE_LEFT) overview_with_transition(1,TRANSITION_LEFT);
    else if (direction==GESTURE_RIGHT) overview_with_transition(-1,TRANSITION_RIGHT);
    return;
  }
  if (direction==GESTURE_LEFT) page_with_transition(ACT_NEXT,TRANSITION_LEFT,(int)apps->len);
  else if (direction==GESTURE_RIGHT) page_with_transition(ACT_PREVIOUS,TRANSITION_RIGHT,(int)apps->len);
  else if (direction==GESTURE_UP && !navigation.help) begin_overview();
}
static void touch_down(void*d,struct wl_touch*t,uint32_t s,uint32_t tm,struct wl_surface*sf,int32_t id,wl_fixed_t x,wl_fixed_t y) {
  touch_contact_count++;
  if (transition.active || touch_rejected) return;
  if (touch_id != -1) {
    gesture_reject(&gesture);
    touch_rejected=true;
    return;
  }
  touch_id=id; touch_x=wl_fixed_to_int(x); touch_y=wl_fixed_to_int(y); touch_card=card_at(touch_x,touch_y);
  /* Gesture starts are limited to cards; footer controls retain tap semantics. */
  touch_from_card=touch_card>=0 && touch_y<height-110;
  gesture_begin(&gesture,id,touch_x,touch_y);
}
static void touch_up(void*d,struct wl_touch*t,uint32_t s,uint32_t tm,int32_t id) {
  if(id==touch_id) {
    enum gesture_direction direction=gesture_release(&gesture,id);
    if (!touch_rejected && touch_from_card && direction!=GESTURE_NONE) apply_gesture(direction);
    else if(!touch_rejected && direction==GESTURE_NONE && touch_card==card_at(touch_x,touch_y)) activate_card(touch_card);
    touch_id=-1; touch_card=-1; touch_from_card=false;
  }
  if (touch_contact_count>0) touch_contact_count--;
  if (!touch_contact_count) touch_rejected=false;
}
static void touch_motion(void*d,struct wl_touch*t,uint32_t tm,int32_t id,wl_fixed_t x,wl_fixed_t y) {
  if(id==touch_id) {
    touch_x=wl_fixed_to_int(x);
    touch_y=wl_fixed_to_int(y);
    if (!gestures_enabled && card_at(touch_x,touch_y) != touch_card) touch_card=-1;
    gesture_motion(&gesture,id,touch_x,touch_y);
  }
}
static void touch_frame(void*d,struct wl_touch*t) {} static void touch_cancel(void*d,struct wl_touch*t) {
  gesture_reject(&gesture); touch_id=-1; touch_card=-1; touch_contact_count=0;
  touch_rejected=false; touch_from_card=false;
}
static const struct wl_touch_listener touch_listener = { .down=touch_down,.up=touch_up,.motion=touch_motion,.frame=touch_frame,.cancel=touch_cancel };
static void seat_caps(void*d,struct wl_seat*s,uint32_t caps) { if ((caps&WL_SEAT_CAPABILITY_POINTER) && !pointer) { pointer=wl_seat_get_pointer(s); wl_pointer_add_listener(pointer,&pointer_listener,NULL); } if ((caps&WL_SEAT_CAPABILITY_TOUCH) && !touch) { touch=wl_seat_get_touch(s); wl_touch_add_listener(touch,&touch_listener,NULL); } }
static void seat_name(void*d,struct wl_seat*s,const char*n) {}
static const struct wl_seat_listener seat_listener = { .capabilities=seat_caps,.name=seat_name };
static void global_add(void*d,struct wl_registry*r,uint32_t n,const char*i,uint32_t v) { if(!strcmp(i,wl_compositor_interface.name)) { if (v < 4) return; compositor=wl_registry_bind(r,n,&wl_compositor_interface,4); } else if(!strcmp(i,wl_shm_interface.name)) shm=wl_registry_bind(r,n,&wl_shm_interface,1); else if(!strcmp(i,wl_seat_interface.name)) { seat=wl_registry_bind(r,n,&wl_seat_interface,1); wl_seat_add_listener(seat,&seat_listener,NULL); } else if(!strcmp(i,zwlr_layer_shell_v1_interface.name)) layer_shell=wl_registry_bind(r,n,&zwlr_layer_shell_v1_interface,1); }
static void global_remove(void*d,struct wl_registry*r,uint32_t n) {}
static const struct wl_registry_listener registry_listener = { .global=global_add,.global_remove=global_remove };
static void request_shutdown(int signal_number) {
  (void)signal_number;
  shutdown_requested=1;
}
int main(int argc,char**argv) {
 if(argc==2 && !strcmp(argv[1],"--layout")) { puts("Portrait application catalogue: 4 cards per page, 3 with keyboard; Previous / Back / Next; gestures settle immediately within 200 ms"); return 0; }
 if(argc!=1) { fprintf(stderr,"usage: k230-touch-launcher [--layout]\n"); return 2; }
 gestures_enabled=!(getenv("K230_LAUNCHER_GESTURES") && !strcmp(getenv("K230_LAUNCHER_GESTURES"),"0"));
 const char *runtime = getenv("XDG_RUNTIME_DIR");
 if (!runtime) { fprintf(stderr,"k230-touch-launcher: XDG_RUNTIME_DIR is unset\n"); return 1; }
 char lock_path[512]; snprintf(lock_path, sizeof lock_path, "%s/k230-touch-launcher.lock", runtime);
 lock_fd=open(lock_path,O_CREAT|O_RDWR|O_CLOEXEC,0600);
 if(lock_fd < 0) { perror("k230-touch-launcher lock"); return 1; }
 if(flock(lock_fd,LOCK_EX|LOCK_NB) < 0) return 0; /* Existing surface stays usable. */
 apps=k230_app_catalog();
 signal(SIGTERM,request_shutdown);
 signal(SIGINT,request_shutdown);
 display=wl_display_connect(NULL); if(!display) { fprintf(stderr,"k230-touch-launcher: cannot connect to Wayland\n"); return 1; }
 struct wl_registry*r=wl_display_get_registry(display); wl_registry_add_listener(r,&registry_listener,NULL); wl_display_roundtrip(display);
 if(!compositor||!shm||!layer_shell||!seat) { fprintf(stderr,"k230-touch-launcher: need wl_compositor, wl_shm, layer-shell, and a seat\n"); return 1; }
 surface=wl_compositor_create_surface(compositor); layer_surface=zwlr_layer_shell_v1_get_layer_surface(layer_shell,surface,NULL,ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY,"k230-launcher"); zwlr_layer_surface_v1_add_listener(layer_surface,&layer_listener,NULL);
 zwlr_layer_surface_v1_set_anchor(layer_surface, ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP|ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM|ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT|ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT); zwlr_layer_surface_v1_set_margin(layer_surface,0,0,0,0); zwlr_layer_surface_v1_set_keyboard_interactivity(layer_surface,ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE); zwlr_layer_surface_v1_set_exclusive_zone(layer_surface,0); wl_surface_commit(surface);
 while(running || catalog.pid) {
   if (shutdown_requested) {
     running=false;
     catalog_cancel();
   }
   if (wl_display_dispatch_pending(display)<0) break;
   if (!running && !catalog.pid) break;
   (void)wl_display_flush(display);
   int64_t deadline=-1;
   if (catalog.pid) deadline=catalog.deadline_ms;
   if (transition.active) {
     int64_t transition_deadline=transition.started_ms+120;
     if (deadline<0 || transition_deadline<deadline) deadline=transition_deadline;
   }
   int timeout=-1;
   if (deadline>=0) {
     int64_t until=deadline-monotonic_ms();
     timeout=(int)(until>0 ? until : 0);
   }
   struct pollfd fds[2] = {
     { .fd=wl_display_get_fd(display), .events=POLLIN },
     { .fd=catalog.output_fd, .events=POLLIN|POLLHUP },
   };
   int poll_result=poll(fds,catalog.pid ? 2 : 1,timeout);
   if (poll_result<0 && errno!=EINTR) break;
   catalog_poll();
   if (transition.active && monotonic_ms()-transition.started_ms>=120)
     transition_settle();
   if (fds[0].revents & (POLLERR|POLLHUP|POLLNVAL)) break;
   if (fds[0].revents & POLLIN && wl_display_dispatch(display)<0) break;
 }
 if (catalog.pid) catalog_cancel();

 return 0;
}
