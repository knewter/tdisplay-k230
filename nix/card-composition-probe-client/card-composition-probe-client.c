#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"

/* No capture, DRM, or other clients' data: deliberately synthetic SHM pixels. */
struct app;
struct plane;
struct buffer {
    struct plane *plane;
    struct wl_buffer *wl;
    uint32_t *pixels;
    size_t size;
    int width, height;
    bool busy;
};
struct plane {
    struct app *app;
    struct wl_surface *surface;
    struct wl_callback *callback;
    struct buffer buffers[3];
    int width, height;
    unsigned frames, callbacks, releases;
    uint64_t last_callback, max_gap;
    bool child, wanted;
};
struct app {
    struct wl_display *display;
    struct wl_compositor *compositor;
    struct wl_subcompositor *subcompositor;
    struct wl_shm *shm;
    struct wl_seat *seat;
    struct wl_keyboard *keyboard;
    unsigned key_presses;
    struct xdg_wm_base *wm;
    struct xdg_surface *xdg;
    struct xdg_toplevel *top;
    struct wl_subsurface *sub;
    struct plane main, child;
    const char *id;
    uint64_t start;
    unsigned duration, logs;
    bool refuse, configured, running, failed;
    /* Test-only: simulate a real app's redraw latency after a compositor
     * resize, instead of this client's own always-fast animation loop.
     * While stall_until is in the future, the main plane simply stops
     * redrawing (the old, wrong-sized buffer stays attached) so a
     * fixture can observe what the compositor does with a stale buffer
     * during a resize, the way a slow real app would leave one. */
    unsigned stall_resize_ms;
    uint64_t stall_until;
};
static volatile sig_atomic_t stopped;
static uint64_t now_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static void event(struct app *a, const char *name) {
    /* All string fields are constants or allowlisted IDs; bounded JSONL. */
    if (a->logs++ >= 10000) return;
    printf("{\"event\":\"%s\",\"app_id\":\"%s\",\"elapsed_ms\":%llu,"
           "\"frames\":%u,\"callbacks\":%u,\"releases\":%u,"
           "\"child_frames\":%u,\"child_callbacks\":%u,\"child_releases\":%u,"
           "\"callback_age_ms\":%llu,\"child_callback_age_ms\":%llu,"
           "\"max_callback_gap_ms\":%llu,\"child_max_callback_gap_ms\":%llu,"
           "\"width\":%d,\"height\":%d,\"stride\":%d,"
           "\"key_presses\":%u,\"format\":\"XRGB8888\",\"subsurface\":\"desynchronized\","
           "\"presentation\":\"unmeasured\"}\n",
           name, a->id, (unsigned long long)(now_ms()-a->start),
           a->main.frames,a->main.callbacks,a->main.releases,
           a->child.frames,a->child.callbacks,a->child.releases,
           (unsigned long long)(now_ms()-a->main.last_callback),
           (unsigned long long)(now_ms()-a->child.last_callback),
           (unsigned long long)a->main.max_gap,(unsigned long long)a->child.max_gap,
           a->main.width,a->main.height,a->main.width*4,a->key_presses);
    fflush(stdout);
}
static void draw(struct plane *p);
static void destroy_buffer(struct buffer *b) {
    if (b->wl) wl_buffer_destroy(b->wl);
    if (b->pixels) munmap(b->pixels,b->size);
    memset(b,0,sizeof(*b));
}
static void released(void *data, struct wl_buffer *wl) {
    (void)wl;
    struct buffer *b=data;
    b->busy=false;
    b->plane->releases++;
    if (b->plane->wanted) draw(b->plane);
}
static const struct wl_buffer_listener buffer_listener={.release=released};
static struct buffer *get_buffer(struct plane *p) {
    for (unsigned i=0;i<3;i++) {
        struct buffer *b=&p->buffers[i];
        if (b->busy) continue;
        if (b->wl && (b->width!=p->width || b->height!=p->height)) destroy_buffer(b);
        if (!b->wl) {
            size_t size=(size_t)p->width*p->height*4;
            int fd=memfd_create("card-probe-shm",MFD_CLOEXEC);
            if (fd<0) return NULL;
            if (ftruncate(fd,(off_t)size)<0) {close(fd);return NULL;}
            void *pixels=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
            if (pixels==MAP_FAILED) {close(fd);return NULL;}
            struct wl_shm_pool *pool=wl_shm_create_pool(p->app->shm,fd,(int)size);
            *b=(struct buffer){.plane=p,.pixels=pixels,.size=size,.width=p->width,.height=p->height};
            b->wl=wl_shm_pool_create_buffer(pool,0,p->width,p->height,p->width*4,WL_SHM_FORMAT_XRGB8888);
            wl_shm_pool_destroy(pool);
            close(fd);
            wl_buffer_add_listener(b->wl,&buffer_listener,b);
        }
        return b;
    }
    return NULL;
}
static void frame_done(void *data, struct wl_callback *callback, uint32_t time) {
    (void)time;
    struct plane *p=data;
    wl_callback_destroy(callback);
    p->callback=NULL;
    uint64_t now=now_ms(), gap=now-p->last_callback;
    if (gap>p->max_gap) p->max_gap=gap;
    p->last_callback=now;
    p->callbacks++;
    draw(p);
}
static const struct wl_callback_listener frame_listener={.done=frame_done};
static void draw(struct plane *p) {
    if (p->callback || !p->app->running) return;
    if (!p->child && p->app->stall_until && now_ms()<p->app->stall_until) {
        p->wanted=true;
        return;
    }
    struct buffer *b=get_buffer(p);
    if (!b) {p->wanted=true;return;}
    p->wanted=false;
    /* Moving bands and a binary counter make stale content obvious on glass. */
    uint32_t base=p->child ? 0x00e09020 :
        (!strcmp(p->app->id,"k230.card.one") ? 0x002070b0 :
            !strcmp(p->app->id,"k230.card.two") ? 0x00903080 : 0x00308050);
    for (int y=0;y<p->height;y++) for (int x=0;x<p->width;x++) {
        bool band=((x+(int)p->frames*5)/24)%2;
        uint32_t color=band ? base : base/2;
        if (y<24 && x<256) color=(p->frames & (1u<<(x/16))) ? 0x00ffffff : 0x00000000;
        if (y>=24 && y<48 && x<256) color=(p->app->key_presses & (1u<<(x/16))) ? 0x0000ff00 : 0x00000000;
        b->pixels[(size_t)y*p->width+x]=color;
    }
    b->busy=true;
    wl_surface_attach(p->surface,b->wl,0,0);
    wl_surface_damage_buffer(p->surface,0,0,p->width,p->height);
    p->callback=wl_surface_frame(p->surface);
    wl_callback_add_listener(p->callback,&frame_listener,p);
    wl_surface_commit(p->surface);
    p->frames++;
    if (p->frames==1) event(p->app,p->child ? "child_commit" : "commit");
}
static void ping(void *data,struct xdg_wm_base *wm,uint32_t serial) {(void)data;xdg_wm_base_pong(wm,serial);}
static const struct xdg_wm_base_listener wm_listener={.ping=ping};
static void configure(void *data,struct xdg_surface *surface,uint32_t serial) {
    struct app *a=data;
    xdg_surface_ack_configure(surface,serial);
    event(a,"configure");
    if (!a->configured) {
        a->configured=true;
        draw(&a->child);
        draw(&a->main);
    }
}
static const struct xdg_surface_listener surface_listener={.configure=configure};
static void top_configure(void *data,struct xdg_toplevel *top,int32_t w,int32_t h,struct wl_array *states) {
    (void)top;(void)states;
    struct app *a=data;
    bool resized=(w>0 && w<=4096 && w!=a->main.width) ||
                 (h>0 && h<=4096 && h!=a->main.height);
    if (w>0 && w<=4096) a->main.width=w;
    if (h>0 && h<=4096) a->main.height=h;
    if (resized && a->stall_resize_ms) a->stall_until=now_ms()+a->stall_resize_ms;
}
static void close_top(void *data,struct xdg_toplevel *top) {
    (void)top;
    struct app *a=data;
    event(a,"close_requested");
    if (a->refuse) event(a,"close_refused");
    else {event(a,"close_accepted");a->running=false;}
}
static const struct xdg_toplevel_listener top_listener={.configure=top_configure,.close=close_top};
static void keymap(void *data,struct wl_keyboard *k,uint32_t format,int fd,uint32_t size) {
    (void)data;(void)k;(void)format;(void)size;close(fd);
}
static void key_enter(void *data,struct wl_keyboard *k,uint32_t serial,struct wl_surface *surface,struct wl_array *keys) {
    (void)k;(void)serial;(void)surface;(void)keys;event(data,"keyboard_enter");
}
static void key_leave(void *data,struct wl_keyboard *k,uint32_t serial,struct wl_surface *surface) {
    (void)k;(void)serial;(void)surface;event(data,"keyboard_leave");
}
static void key(void *data,struct wl_keyboard *k,uint32_t serial,uint32_t time,uint32_t code,uint32_t state) {
    (void)k;(void)serial;(void)time;(void)code;
    struct app *a=data;
    if (state==WL_KEYBOARD_KEY_STATE_PRESSED) {a->key_presses++;event(a,"key_press");}
}
static void modifiers(void *data,struct wl_keyboard *k,uint32_t serial,uint32_t depressed,uint32_t latched,uint32_t locked,uint32_t group) {
    (void)data;(void)k;(void)serial;(void)depressed;(void)latched;(void)locked;(void)group;
}
static const struct wl_keyboard_listener keyboard_listener={
    .keymap=keymap,.enter=key_enter,.leave=key_leave,.key=key,.modifiers=modifiers
};
static void capabilities(void *data,struct wl_seat *seat,uint32_t caps) {
    struct app *a=data;
    if ((caps&WL_SEAT_CAPABILITY_KEYBOARD) && !a->keyboard) {
        a->keyboard=wl_seat_get_keyboard(seat);
        wl_keyboard_add_listener(a->keyboard,&keyboard_listener,a);
    } else if (!(caps&WL_SEAT_CAPABILITY_KEYBOARD) && a->keyboard) {
        wl_keyboard_destroy(a->keyboard);a->keyboard=NULL;
    }
}
static const struct wl_seat_listener seat_listener={.capabilities=capabilities};
static void global(void *data,struct wl_registry *reg,uint32_t name,const char *interface,uint32_t version) {
    struct app *a=data;
    if (!strcmp(interface,"wl_compositor") && version>=4) a->compositor=wl_registry_bind(reg,name,&wl_compositor_interface,4);
    else if (!strcmp(interface,"wl_subcompositor")) a->subcompositor=wl_registry_bind(reg,name,&wl_subcompositor_interface,1);
    else if (!strcmp(interface,"wl_seat") && !a->seat) {
        a->seat=wl_registry_bind(reg,name,&wl_seat_interface,1);
        wl_seat_add_listener(a->seat,&seat_listener,a);
    }
    else if (!strcmp(interface,"wl_shm")) a->shm=wl_registry_bind(reg,name,&wl_shm_interface,1);
    else if (!strcmp(interface,"xdg_wm_base")) {
        a->wm=wl_registry_bind(reg,name,&xdg_wm_base_interface,1);
        xdg_wm_base_add_listener(a->wm,&wm_listener,a);
    }
}
static void removed(void *data,struct wl_registry *reg,uint32_t name) {(void)data;(void)reg;(void)name;}
static const struct wl_registry_listener registry_listener={.global=global,.global_remove=removed};
static void stop_signal(int sig) {(void)sig;stopped=1;}
int main(int argc,char **argv) {
    struct app a={.id="k230.card.one",.duration=120,.running=true};
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--app-id") && i+1<argc) a.id=argv[++i];
        else if (!strcmp(argv[i],"--refuse-close")) a.refuse=true;
        else if (!strcmp(argv[i],"--duration") && i+1<argc) {
            char *end; unsigned long n=strtoul(argv[++i],&end,10);
            if (*end || n<1 || n>600) return 64;
            a.duration=(unsigned)n;
        } else if (!strcmp(argv[i],"--stall-resize-ms") && i+1<argc) {
            char *end; unsigned long n=strtoul(argv[++i],&end,10);
            if (*end || n>60000) return 64;
            a.stall_resize_ms=(unsigned)n;
        } else {fprintf(stderr,"usage: card-composition-probe-client --app-id k230.card.one|k230.card.two|k230.card.three [--refuse-close] [--duration 1..600] [--stall-resize-ms 0..60000]\n");return 64;}
    }
    if (strcmp(a.id,"k230.card.one") && strcmp(a.id,"k230.card.two") && strcmp(a.id,"k230.card.three"))
        return 64;
    a.start=now_ms();
    a.main=(struct plane){.app=&a,.width=480,.height=720,.last_callback=a.start};
    a.child=(struct plane){.app=&a,.width=128,.height=96,.child=true,.last_callback=a.start};
    event(&a,"start");
    signal(SIGINT,stop_signal);signal(SIGTERM,stop_signal);
    a.display=wl_display_connect(NULL);
    if (!a.display) {event(&a,"connect_failed");return 1;}
    struct wl_registry *reg=wl_display_get_registry(a.display);
    wl_registry_add_listener(reg,&registry_listener,&a);
    if (wl_display_roundtrip(a.display)<0 || !a.compositor || !a.subcompositor || !a.shm || !a.wm) {
        event(&a,"protocol_missing");wl_display_disconnect(a.display);return 1;
    }
    a.main.surface=wl_compositor_create_surface(a.compositor);
    a.xdg=xdg_wm_base_get_xdg_surface(a.wm,a.main.surface);
    xdg_surface_add_listener(a.xdg,&surface_listener,&a);
    a.top=xdg_surface_get_toplevel(a.xdg);
    xdg_toplevel_add_listener(a.top,&top_listener,&a);
    xdg_toplevel_set_app_id(a.top,a.id);
    xdg_toplevel_set_title(a.top,a.refuse ? "Card two: refuses close" : "Card one: accepts close");
    a.child.surface=wl_compositor_create_surface(a.compositor);
    a.sub=wl_subcompositor_get_subsurface(a.subcompositor,a.child.surface,a.main.surface);
    wl_subsurface_set_position(a.sub,32,48);
    wl_subsurface_set_desync(a.sub);
    wl_surface_commit(a.main.surface);
    uint64_t next_log=a.start+1000;
    while (a.running && !stopped && now_ms()-a.start<(uint64_t)a.duration*1000) {
        while (wl_display_prepare_read(a.display)!=0) {
            if (wl_display_dispatch_pending(a.display)<0) {a.failed=true;goto done;}
        }
        int flush=wl_display_flush(a.display);
        if (flush<0 && errno!=EAGAIN) {wl_display_cancel_read(a.display);a.failed=true;break;}
        struct pollfd fd={.fd=wl_display_get_fd(a.display),.events=POLLIN | (flush<0 ? POLLOUT : 0)};
        /* A pending stall has nothing to wait on from the display fd, so
         * poll briefly instead of the usual 100ms to notice it elapsing. */
        int timeout=a.stall_until ? 8 : 100;
        int ready=poll(&fd,1,timeout);
        if (ready>0 && (fd.revents&POLLIN)) {
            if (wl_display_read_events(a.display)<0) {a.failed=true;break;}
        } else wl_display_cancel_read(a.display);
        if ((ready<0 && errno!=EINTR) || (fd.revents&(POLLERR|POLLHUP))) {a.failed=true;break;}
        if (wl_display_dispatch_pending(a.display)<0) {a.failed=true;break;}
        if (a.stall_until && now_ms()>=a.stall_until) {
            a.stall_until=0;
            if (a.main.wanted) draw(&a.main);
        }
        if (now_ms()>=next_log) {event(&a,"heartbeat");next_log=now_ms()+1000;}
    }
done:
    a.running=false;
    event(&a,a.failed ? "connection_error" : stopped ? "signal_exit" : "exit");
    if (a.main.callback) wl_callback_destroy(a.main.callback);
    if (a.child.callback) wl_callback_destroy(a.child.callback);
    wl_subsurface_destroy(a.sub);wl_surface_destroy(a.child.surface);
    xdg_toplevel_destroy(a.top);xdg_surface_destroy(a.xdg);wl_surface_destroy(a.main.surface);
    for (unsigned i=0;i<3;i++) {destroy_buffer(&a.main.buffers[i]);destroy_buffer(&a.child.buffers[i]);}
    if (a.keyboard) wl_keyboard_destroy(a.keyboard);
    if (a.seat) wl_seat_destroy(a.seat);
    xdg_wm_base_destroy(a.wm);wl_shm_destroy(a.shm);wl_subcompositor_destroy(a.subcompositor);
    wl_compositor_destroy(a.compositor);wl_registry_destroy(reg);wl_display_disconnect(a.display);
    return a.failed ? 1 : 0;
}
